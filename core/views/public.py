"""Páginas públicas: Home, busca, chat e tópicos (não exigem login)."""
import json
import logging
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.db.models import Q

from ..models import MajorTopic, MinorTopic, GlossaryTerm, Regiao, Territorio, Cidade
from .. import chatbot, ratelimit
from ..tools import search_tools
from .helpers import apply_glossary

logger = logging.getLogger(__name__)


def healthz(request):
    """Alvo do monitor (UptimeRobot). Resposta fixa, sem tocar no banco: acordar o Neon a cada ping gasta a cota."""
    return HttpResponse('ok', content_type='text/plain')


# ── Home ──────────────────────────────────────────────────────────────────────

def home(request):
    major_topics = MajorTopic.objects.prefetch_related('minor_topics').all()
    return render(request, 'home.html', {'major_topics': major_topics})


# ── Search ────────────────────────────────────────────────────────────────────

def search(request):
    q = request.GET.get('q', '').strip()
    results = []
    if q:
        seen = set()

        for tool in search_tools(q):
            seen.add(tool['url'])
            results.append({'title': tool['name'], 'major': 'Ferramentas', 'url': tool['url']})

        minor_topics = MinorTopic.objects.filter(
            Q(title__icontains=q) | Q(description__icontains=q)
        ).select_related('major_topic')[:20]
        for mt in minor_topics:
            url = f'/topico/{mt.major_topic.slug}/{mt.slug}/'
            if url not in seen:
                seen.add(url)
                results.append({'title': mt.title, 'major': mt.major_topic.title, 'url': url})

        block_topics = MinorTopic.objects.filter(
            Q(blocks__content__icontains=q) | Q(blocks__title__icontains=q)
        ).select_related('major_topic').distinct()[:20]
        for mt in block_topics:
            url = f'/topico/{mt.major_topic.slug}/{mt.slug}/'
            if url not in seen:
                seen.add(url)
                results.append({'title': mt.title, 'major': mt.major_topic.title, 'url': url})

        major_topics = MajorTopic.objects.filter(
            Q(title__icontains=q) | Q(description__icontains=q)
        )[:10]
        for mt in major_topics:
            url = f'/topico/{mt.slug}/'
            if url not in seen:
                seen.add(url)
                results.append({'title': mt.title, 'major': 'Tópico Principal', 'url': url})

    # Busca regionais (cidades e territórios)
    if q:
        regionais_topic = MinorTopic.objects.filter(
            is_territory_map=True
        ).select_related('major_topic').first()
        if regionais_topic:
            regionais_url = f'/topico/{regionais_topic.major_topic.slug}/{regionais_topic.slug}/'
            cidades = Cidade.objects.filter(
                nome__icontains=q
            ).select_related('territorio__regiao')[:10]
            for cidade in cidades:
                results.append({
                    'title': cidade.nome,
                    'major': f'{cidade.territorio.regiao.nome} / {cidade.territorio.nome}',
                    'url': regionais_url,
                })
            territorios = Territorio.objects.filter(
                nome__icontains=q
            ).select_related('regiao')[:5]
            for territorio in territorios:
                results.append({
                    'title': territorio.nome,
                    'major': territorio.regiao.nome,
                    'url': regionais_url,
                })

    return JsonResponse({'results': results})


# ── Chatbot ───────────────────────────────────────────────────────────────────

def chat(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido.'}, status=405)

    if not ratelimit.chat_allowed(request):
        return JsonResponse({'error': 'Muitas perguntas seguidas. Espera um pouco e tenta de novo.'}, status=429)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Requisição inválida.'}, status=400)

    question = (data.get('question') or '').strip()
    if not question:
        return JsonResponse({'error': 'Digite uma pergunta.'}, status=400)

    history = data.get('history') if isinstance(data.get('history'), list) else None

    try:
        result = chatbot.answer_question(question, history=history)
    except chatbot.ChatbotError as e:
        return JsonResponse({'error': str(e)}, status=503)
    except Exception:
        logger.exception('Erro no chatbot')
        return JsonResponse({'error': 'Não foi possível responder agora. Tenta de novo em instantes.'}, status=502)

    return JsonResponse(result)


# ── Major Topic ───────────────────────────────────────────────────────────────

def major_topic(request, major_slug):
    topic = get_object_or_404(MajorTopic, slug=major_slug)
    minor_topics = topic.minor_topics.all()
    return render(request, 'major_topic.html', {'topic': topic, 'minor_topics': minor_topics})


# ── Minor Topic ───────────────────────────────────────────────────────────────

def minor_topic(request, major_slug, minor_slug):
    major = get_object_or_404(MajorTopic, slug=major_slug)
    topic = get_object_or_404(MinorTopic, major_topic=major, slug=minor_slug)

    if topic.is_territory_map:
        regioes = Regiao.objects.prefetch_related('territorios__cidades').all()
        regioes_json = json.dumps([
            {
                'id': r.id,
                'nome': r.nome,
                'icon': r.icon or '🌎',
                'territorios': [
                    {
                        'id': t.id,
                        'nome': t.nome,
                        'cidades': [c.nome for c in t.cidades.all()],
                    }
                    for t in r.territorios.all()
                ],
            }
            for r in regioes
        ], ensure_ascii=False)
        return render(request, 'regionais.html', {
            'major': major,
            'topic': topic,
            'regioes_json': regioes_json,
        })

    blocks = topic.blocks.all()
    terms = GlossaryTerm.objects.all()

    processed_blocks = []
    for block in blocks:
        if block.block_type == 'text':
            block.rendered_content = apply_glossary(block.content, terms)
        elif block.block_type == 'checklist':
            block.checklist_lines = [
                apply_glossary(line, terms)
                for line in block.content.splitlines()
                if line.strip()
            ]
        processed_blocks.append(block)

    return render(request, 'minor_topic.html', {
        'major': major,
        'topic': topic,
        'blocks': processed_blocks,
    })
