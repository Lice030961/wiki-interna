"""
Chatbot de navegação da wiki (RAG simples via Cloudflare Workers AI).

Fluxo: pergunta -> embedding -> busca por similaridade nos ContentBlock ->
os trechos mais relevantes viram contexto para o modelo de chat, que só
formata a resposta em cima deles (não inventa fora do conteúdo da wiki).
"""
import re
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
    '- Cite cada tópico da wiki no máximo uma vez ao longo da resposta — não repita o nome do mesmo tópico '
    'várias vezes, os links pra cada tópico citado já aparecem separadamente abaixo da resposta.\n\n'
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


_STOPWORDS = {
    'a', 'o', 'os', 'as', 'de', 'da', 'do', 'das', 'dos', 'em', 'no', 'na', 'nos', 'nas',
    'um', 'uma', 'uns', 'umas', 'e', 'ou', 'que', 'como', 'para', 'pra', 'por', 'com', 'sem',
    'eu', 'me', 'minha', 'meu', 'isso', 'essa', 'esse', 'ao', 'aos', 'se', 'sua', 'seu', 'tem',
    'ter', 'ha', 'la', 'lo',
}

# Vocabulário de atendimento onde a pergunta do usuário e o título do tópico usam
# palavras diferentes pra mesma ação/conceito (ex.: "como eu ABRO uma SA" quer dizer
# "como CRIAR uma SA" — o tópico se chama "Como Criar SA", não "abrir").
_SYNONYMS = {
    'abro': 'criar', 'abrir': 'criar', 'abertura': 'criar', 'aberto': 'criar', 'abra': 'criar',
    'gerar': 'criar', 'gero': 'criar', 'fazer': 'criar', 'faço': 'criar', 'cadastrar': 'criar',
    'criacao': 'criar',
    'erro': 'erro', 'erros': 'erro', 'falha': 'erro', 'falhou': 'erro', 'problema': 'erro',
    'travou': 'erro', 'travando': 'erro',
}


def _concept_words(text):
    """Palavras normalizadas e relevantes de um texto pra comparar pergunta x título de
    tópico: sem acento, sem stopword, com sinônimos comuns de atendimento unificados."""
    words = re.findall(r'[a-z0-9]+', _normalize(text))
    return {_SYNONYMS.get(w, w) for w in words if w not in _STOPWORDS and len(w) > 1}


def _topic_keyword_boost(query_words, block):
    """Reforço léxico proporcional à fração de palavras-chave do tópico (título do
    tópico maior/menor, já passadas por sinônimo) que aparecem na pergunta. Cobre
    tanto siglas curtas (SA, INC) quanto verbos equivalentes (abrir/criar) que o
    embedding multilíngue nem sempre aproxima bem — e desempata a favor do tópico
    mais específico quando dois títulos compartilham a mesma sigla."""
    best = 0.0
    for title in (block.minor_topic.title, block.minor_topic.major_topic.title):
        title_words = _concept_words(title)
        if not title_words:
            continue
        overlap = len(title_words & query_words) / len(title_words)
        best = max(best, overlap)
    return best * 0.3


def search_relevant_blocks(query, max_topics=3):
    """Busca os blocos mais relevantes, agrupados por sub-tópico: rankeia tópicos
    (não blocos soltos) pra evitar que o mesmo assunto apareça espalhado e repetido
    no contexto do LLM, e corta por relevância relativa ao melhor resultado em vez
    de um threshold fixo, que deixava passar ruído ou descartava bons resultados
    dependendo de quantos outros blocos competiam na mesma busca."""
    from core.models import ContentBlock

    query_embedding = get_embedding(query)
    query_words = _concept_words(query)
    candidates = ContentBlock.objects.exclude(embedding__isnull=True).select_related(
        'minor_topic', 'minor_topic__major_topic'
    )

    topics = {}
    for block in candidates:
        score = cosine_similarity(query_embedding, block.embedding)
        score += _topic_keyword_boost(query_words, block)
        topic = topics.setdefault(block.minor_topic_id, {'score': 0.0, 'blocks': []})
        topic['blocks'].append((score, block))
        topic['score'] = max(topic['score'], score)

    if not topics:
        return []

    ranked = sorted(topics.values(), key=lambda t: t['score'], reverse=True)
    best_score = ranked[0]['score']
    floor = max(0.3, best_score - 0.15)

    selected = []
    for topic in ranked[:max_topics]:
        if topic['score'] < floor:
            break
        selected.extend(b for score, b in sorted(topic['blocks'], key=lambda p: p[0], reverse=True) if score >= floor)
    return selected


def generate_answer(query, blocks):
    # Agrupa por tópico (1 cabeçalho por tópico, mesmo com vários blocos) — do
    # contrário o mesmo nome de tópico aparece repetido várias vezes no contexto
    # e o modelo tende a repeti-lo de volta na resposta.
    topics = {}
    order = []
    for b in blocks:
        key = b.minor_topic_id
        if key not in topics:
            topics[key] = {'label': f'{b.minor_topic.major_topic.title} > {b.minor_topic.title}', 'texts': []}
            order.append(key)
        topics[key]['texts'].append(block_index_text(b))

    context = '\n\n'.join(
        f"[Tópico: {topics[key]['label']}]\n" + '\n'.join(topics[key]['texts'])
        for key in order
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
