"""
Chatbot de navegação da wiki (RAG simples via Cloudflare Workers AI).

Fluxo: pergunta -> embedding -> busca por similaridade nos ContentBlock ->
os trechos mais relevantes viram contexto para o modelo de chat, que só
formata a resposta em cima deles (não inventa fora do conteúdo da wiki).
"""
import requests
from django.conf import settings

CF_API_URL = 'https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}'

SYSTEM_PROMPT = (
    'Você é o assistente de navegação da wiki interna da empresa. '
    'Responda de forma direta e simples, em português, usando APENAS as informações de contexto abaixo. '
    'Se o contexto tiver um passo a passo, responda em passos. Se for uma explicação geral, responda em '
    'poucas frases. Se a resposta não estiver no contexto, diga que não encontrou isso na wiki e sugira '
    'usar a busca.\n\nContexto:\n{context}'
)


class ChatbotError(Exception):
    pass


def _cf_run(model, payload):
    account_id = getattr(settings, 'CF_ACCOUNT_ID', None)
    api_token = getattr(settings, 'CF_API_TOKEN', None)
    if not account_id or not api_token:
        raise ChatbotError('Workers AI não configurado (CF_ACCOUNT_ID / CF_API_TOKEN ausentes).')

    url = CF_API_URL.format(account=account_id, model=model)
    headers = {'Authorization': f'Bearer {api_token}'}
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not data.get('success', True):
        raise ChatbotError(str(data.get('errors')))
    return data['result']


def get_embedding(text):
    result = _cf_run(settings.CF_EMBED_MODEL, {'text': [text]})
    return result['data'][0]


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def block_index_text(block):
    """Texto usado para gerar o embedding de um bloco de conteúdo."""
    return f'{block.title}\n{block.content}'.strip()


def update_block_embedding(block):
    """Recalcula e salva o embedding de um bloco. Falha em silêncio (rede/API fora do ar
    não pode quebrar o fluxo de edição de conteúdo do admin)."""
    text = block_index_text(block)
    if not text:
        return
    try:
        embedding = get_embedding(text)
    except (requests.RequestException, ChatbotError):
        return
    type(block).objects.filter(pk=block.pk).update(embedding=embedding)


def search_relevant_blocks(query, top_k=4):
    from core.models import ContentBlock

    query_embedding = get_embedding(query)
    candidates = ContentBlock.objects.exclude(embedding__isnull=True).select_related(
        'minor_topic', 'minor_topic__major_topic'
    )
    scored = [(cosine_similarity(query_embedding, block.embedding), block) for block in candidates]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [block for score, block in scored[:top_k] if score > 0.3]


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
