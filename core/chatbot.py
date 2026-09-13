"""
Chatbot de navegação da wiki (RAG simples via Cloudflare Workers AI).

Fluxo: pergunta -> embedding -> busca por similaridade nos ContentBlock ->
os trechos mais relevantes viram contexto para o modelo de chat, que só
formata a resposta em cima deles (não inventa fora do conteúdo da wiki).
"""
import unicodedata

import requests
from django.conf import settings

CF_API_URL = 'https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}'

SYSTEM_PROMPT = (
    'Você é o assistente de navegação da wiki interna da empresa. '
    'Responda de forma direta e simples, em português, usando APENAS as informações de contexto abaixo.\n\n'
    'Regras de tamanho:\n'
    '- Se a pergunta pede uma informação pontual (um valor, uma definição, uma resposta curta), responda '
    'direto com essa informação.\n'
    '- Se o contexto for um tutorial longo e já pronto (passo a passo com várias etapas, checklist grande), '
    'NÃO reproduza tudo: resuma em 1-2 frases o que o tutorial cobre e diga pro usuário abrir o link do '
    'tópico (mostrado abaixo da resposta) pra ver o passo a passo completo.\n\n'
    'Se a resposta não estiver no contexto, diga que não encontrou isso na wiki e sugira usar a busca.\n\n'
    'Contexto:\n{context}'
)


class ChatbotError(Exception):
    pass


def _cf_run(model, payload, timeout=30):
    account_id = getattr(settings, 'CF_ACCOUNT_ID', None)
    api_token = getattr(settings, 'CF_API_TOKEN', None)
    if not account_id or not api_token:
        raise ChatbotError('Workers AI não configurado (CF_ACCOUNT_ID / CF_API_TOKEN ausentes).')

    url = CF_API_URL.format(account=account_id, model=model)
    headers = {'Authorization': f'Bearer {api_token}'}
    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if response.status_code == 429:
        raise ChatbotError(
            'Os neurons diários da Workers AI acabaram por hoje 🤖💤 Tenta de novo amanhã, ou usa a busca aqui em cima.'
        )
    response.raise_for_status()
    data = response.json()
    if not data.get('success', True):
        raise ChatbotError(str(data.get('errors')))
    return data['result']


def get_embedding(text):
    result = _cf_run(settings.CF_EMBED_MODEL, {'text': [text]})
    return result['data'][0]


IMAGE_PROMPT = (
    'Descreva esta imagem em português: liste todo texto visível (botões, campos, menus, mensagens de erro) '
    'e o que está sendo mostrado, de forma objetiva, como legenda de um passo de tutorial interno.'
)


def describe_image(file_field):
    """Usa um modelo de visão da Workers AI pra extrair texto/contexto de uma imagem de bloco."""
    file_field.open('rb')
    try:
        image_bytes = file_field.read()
    finally:
        file_field.close()

    result = _cf_run(settings.CF_VISION_MODEL, {
        'image': list(image_bytes),
        'prompt': IMAGE_PROMPT,
        'max_tokens': 512,
    }, timeout=60)
    return (result.get('description') or result.get('response') or '').strip()


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def block_index_text(block):
    """Texto usado para gerar o embedding de um bloco de conteúdo.
    Inclui o título dos tópicos pai: muitos blocos não repetem no título/conteúdo
    o assunto (ex.: SLA) porque a página já mostra o nome do tópico — sem isso o
    embedding do bloco não tem nenhuma relação com o nome do tópico em que ele está."""
    parts = [
        block.minor_topic.major_topic.title,
        block.minor_topic.title,
        block.title,
        block.content,
        block.image_description,
    ]
    return '\n'.join(p for p in parts if p).strip()


def update_block_embedding(block):
    """Recalcula e salva o embedding (e a descrição de imagem, se for o caso) de um bloco.
    Falha em silêncio (rede/API fora do ar não pode quebrar o fluxo de edição do admin)."""
    if block.block_type == block.IMAGE and block.file and not block.image_description:
        try:
            description = describe_image(block.file)
        except (requests.RequestException, ChatbotError):
            description = ''
        if description:
            block.image_description = description
            type(block).objects.filter(pk=block.pk).update(image_description=description)

    text = block_index_text(block)
    if not text:
        return
    try:
        embedding = get_embedding(text)
    except (requests.RequestException, ChatbotError):
        return
    type(block).objects.filter(pk=block.pk).update(embedding=embedding)


def _normalize(text):
    """minúsculas e sem acento, pra comparar 'SLA'/'sla', 'PPPoE'/'pppoe' etc."""
    decomposed = unicodedata.normalize('NFKD', text or '')
    return ''.join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _topic_keyword_boost(query_norm, block):
    """Reforço léxico: siglas curtas de tópico (SLA, PPPoE...) às vezes não ficam
    bem separadas umas das outras no espaço vetorial do modelo multilíngue — se o
    nome do tópico aparece literalmente na pergunta, garante que o bloco não fique
    de fora só por causa da similaridade semântica."""
    for title in (block.minor_topic.title, block.minor_topic.major_topic.title):
        title_norm = _normalize(title)
        if len(title_norm) >= 3 and title_norm in query_norm:
            return 0.25
    return 0.0


def search_relevant_blocks(query, top_k=6):
    from core.models import ContentBlock

    query_embedding = get_embedding(query)
    query_norm = _normalize(query)
    candidates = ContentBlock.objects.exclude(embedding__isnull=True).select_related(
        'minor_topic', 'minor_topic__major_topic'
    )
    scored = [
        (cosine_similarity(query_embedding, block.embedding) + _topic_keyword_boost(query_norm, block), block)
        for block in candidates
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    if not scored:
        return []

    # Corte relativo em vez de threshold fixo: quando a melhor resposta é muito boa,
    # descarta ruído distante; quando a melhor é só razoável, ainda deixa passar as
    # próximas — um limiar fixo (ex. score > 0.3) tanto deixava passar lixo quanto
    # descartava blocos bons dependendo de quem mais competia pelo top_k naquela busca.
    best_score = scored[0][0]
    floor = max(0.3, best_score - 0.15)
    return [block for score, block in scored[:top_k] if score >= floor]


def generate_answer(query, blocks):
    context = '\n\n'.join(
        f'[Tópico: {b.minor_topic.major_topic.title} > {b.minor_topic.title}]\n{block_index_text(b)}'
        for b in blocks
    )
    result = _cf_run(settings.CF_CHAT_MODEL, {
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT.format(context=context)},
            {'role': 'user', 'content': query},
        ],
        'max_tokens': 500,
    })
    return result['response'].strip()


def answer_question(query):
    blocks = search_relevant_blocks(query)
    if not blocks:
        return {
            'answer': 'Não encontrei nada na wiki sobre isso. Tenta reformular ou usar a busca no topo da página.',
            'sources': [],
        }

    answer = generate_answer(query, blocks)

    sources = []
    seen_urls = set()
    for b in blocks:
        url = f'/topico/{b.minor_topic.major_topic.slug}/{b.minor_topic.slug}/'
        if url not in seen_urls:
            seen_urls.add(url)
            sources.append({'title': b.minor_topic.title, 'url': url})

    return {'answer': answer, 'sources': sources}
