import os
import re
import io
import csv
import json
import unicodedata
from collections import Counter, defaultdict
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout
from django.contrib.staticfiles import finders
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.utils.text import slugify
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.db.models import Q

from .models import MajorTopic, MinorTopic, ContentBlock, GlossaryTerm, Regiao, Territorio, Cidade, FabricanteOLT, OLT, ProjetoGPON
from . import chatbot
from .tools import search_tools


def is_admin(user):
    return user.is_staff or user.is_superuser


def apply_markdown(text):
    """Converte marcadores de formatação em HTML. Chamado sobre texto já HTML-escapado."""
    def attention_replace(m):
        inner = m.group(1).strip('\n')
        return (
            '\n<div class="attention-box">'
            '<span class="attention-label">⚠️ ATENÇÃO</span>'
            + inner +
            '</div>\n'
        )
    text = re.sub(
        r'\n*\[ATENÇÃO\]\n?(.*?)\n?\[/ATENÇÃO\]\n*',
        attention_replace,
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    pairs = [
        (re.compile(r'\~\~(.+?)\~\~', re.DOTALL), r'<s>\1</s>'),
        (re.compile(r'\*\*(.+?)\*\*', re.DOTALL), r'<strong>\1</strong>'),
        (re.compile(r'\_\_(.+?)\_\_', re.DOTALL), r'<u>\1</u>'),
        (re.compile(r'\_(.+?)\_', re.DOTALL), r'<em>\1</em>'),
        (re.compile(r'\`(.+?)\`'), r'<code class="bg-gray-100 px-1 rounded text-xs font-mono">\1</code>'),
    ]
    for pattern, repl in pairs:
        text = pattern.sub(repl, text)
    return text


def apply_glossary(text, terms):
    """
    Converte marcadores de formatação e substitui termos do glossário por spans com tooltip.
    Retorna HTML seguro.
    """
    escaped = escape(text)
    escaped = apply_markdown(escaped)

    if terms:
        sorted_terms = sorted(terms, key=lambda t: len(t.term), reverse=True)
        for term_obj in sorted_terms:
            # (?![^<>]*>) impede substituição dentro de atributos de tags já inseridas
            pattern = re.compile(
                r'(?<!\w)(?![^<>]*>)(' + re.escape(escape(term_obj.term)) + r')(?!\w)',
                re.IGNORECASE
            )
            tooltip_def = escape(term_obj.definition).replace('"', '&quot;')
            replacement = (
                f'<span class="glossary-term" '
                f'data-term="{escape(term_obj.term)}" '
                f'data-def="{tooltip_def}">'
                f'\\1</span>'
            )
            escaped = pattern.sub(replacement, escaped)

    return mark_safe(escaped.replace('\n', '<br>'))


# ── Auth ──────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return redirect('admin_dashboard')
    error = None
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user and (user.is_staff or user.is_superuser):
            login(request, user)
            return redirect(request.GET.get('next', 'admin_dashboard'))
        error = 'Credenciais inválidas ou sem permissão de administrador.'
    return render(request, 'login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('home')


# ── Home ──────────────────────────────────────────────────────────────────────

def home(request):
    major_topics = MajorTopic.objects.prefetch_related('minor_topics').all()
    return render(request, 'home.html', {'major_topics': major_topics})


# ── Ferramentas ───────────────────────────────────────────────────────────────

def script_generator(request):
    # Toda a extração roda no navegador (static/js/script_generator.js);
    # o texto colado do SIS nunca chega ao servidor.
    # Versão do JS na URL: o navegador nunca roda um script antigo do cache com a página nova.
    js_path = finders.find('js/script_generator.js')
    return render(request, 'tools/script_generator.html', {
        'js_version': int(os.path.getmtime(js_path)) if js_path else 0,
        'olt_data': olt_data(),
        'dedicado_options': [('nao', 'Não'), ('sim', 'Sim')],
        'gpon_options': ['UP', 'DOWN'],
        # Só na Mudança de plano e na Instalação (Sim/Não, padrão Não).
        'equip_groups': [('roteador', 'Roteador?'), ('rb', 'RB?'), ('ata', 'ATA?')],
        'tratativa_options': [
            # Ordem: GPON UP/DOWN, só GPON UP, sem GPON.
            ('conexao', 'Conexão'),
            ('oscilacao', 'Oscilação'),
            ('navegacao', 'Navegação'),
            ('lentidao', 'Lentidão'),
            ('mudanca', 'Mudança de ponto'),
            # Mudança de plano e Instalação trocam o modelo do script: dados vêm do e-mail, não do SIS.
            ('plano', 'Mudança de plano'),
            ('instalacao', 'Instalação'),
        ],
        # (texto no script, rótulo do botão)
        'obs_options': [
            ('IGREJA', 'IGREJA'),
            ('LIGAR ANTES DE IR AO LOCAL', 'LIGAR ANTES DE IR AO LOCAL'),
            ('REPASSE DE DROP', 'REPASSE DE DROP'),
            ('LOS VERMELHA', 'LOS VERMELHA'),
            ('NECESSÁRIO LIBERAR TÉCNICO', 'LIBERAR TÉCNICO'),
        ],
        'fields': [
            ('adm', 'ADM'),
            ('pppoe', 'PPPoE'),
            ('nome', 'Nome da Empresa'),
            ('plano', 'Plano'),
            ('ativo', 'Ativo do equipamento'),
            ('compat', 'Compatibilidade'),
            ('cto', 'CTO'),
            ('tel', 'Tel'),
            ('endereco', 'Endereço'),
            ('horario', 'Horário de atendimento'),
            ('responsavel', 'Responsável'),
        ],
        'plano_fields': [
            ('adm', 'ADM'),
            ('solicitante', 'Quem solicitou (Desktop)'),
            ('nome', 'Nome da Empresa'),
            ('plano_atual', 'Plano atual'),
            ('ativo', 'Ativo do equipamento'),
            ('plano_novo', 'Plano novo'),
            ('prospect', 'Prospect'),
            ('compat', 'Compatibilidade'),
            ('tel', 'Contato'),
            ('endereco', 'Endereço'),
            ('complemento', 'Complemento'),
            ('horario', 'Horário de atendimento'),
            ('responsavel', 'Responsável'),
        ],
    })


def city_key(name):
    name = unicodedata.normalize('NFKD', name or '').encode('ascii', 'ignore').decode().lower()
    name = re.sub(r"['`´’]", '', name)
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', name).split())


def olt_data():
    """OLTs para o Gerador achar a Compatibilidade no navegador: por hostname (SIS),
    pela sigla do hostname e pela cidade (endereço do e-mail/prospect). Os fabricantes
    de cada cidade/sigla vão do que tem mais OLTs para o que tem menos."""
    by_host, by_city, by_sigla, city_names = {}, defaultdict(Counter), defaultdict(Counter), {}
    for olt in OLT.objects.select_related('fabricante'):
        fab = olt.fabricante.nome
        by_host[olt.nome.upper()] = fab
        # Mesma chave que cityKey() no JS: o CSV tem "Jacarei" e "Jacareí", "d'Oeste" e "dOeste"...
        key = city_key(olt.cidade)
        if key:
            by_city[key][fab] += 1
            # Entre "Sumare" e "Sumaré", mostra a grafia com acento.
            if sum(ord(ch) > 127 for ch in olt.cidade) > sum(ord(ch) > 127 for ch in city_names.get(key, '')):
                city_names[key] = olt.cidade
            city_names.setdefault(key, olt.cidade)
        m = re.match(r'LT-G\d+-([A-Z]+)\d*-', olt.nome.upper())
        sigla = m.group(1) if m else re.sub(r'\d+', '', olt.sigla.upper())
        if sigla:
            by_sigla[sigla][fab] += 1
    order = lambda counter: [fab for fab, _ in counter.most_common()]
    return {
        'fabricantes': {f.nome: {'onu': f.onu, 'aviso': f.aviso} for f in FabricanteOLT.objects.all()},
        'olts': by_host,
        'cidades': {key: {'nome': city_names[key], 'fabs': order(c)} for key, c in by_city.items()},
        'siglas': {sigla: order(c) for sigla, c in by_sigla.items()},
        # Projeto GPON do SIS → sigla da CTO (mesma chave que projetoKey() no JS).
        'projetos': {projeto_key(p.nome): p.sigla for p in ProjetoGPON.objects.all()},
    }


def projeto_key(name):
    """ "GPON Bauru Area E LPNET" e "Bauru Área E - LPNET" viram a mesma chave."""
    return re.sub(r'^gpon ', '', city_key(name))


def batimento(request):
    # A planilha do Power BI é lida e filtrada só no navegador (static/js/batimento.js);
    # o arquivo nunca chega ao servidor.
    js_path = finders.find('js/batimento.js')
    return render(request, 'tools/batimento.html', {
        'js_version': int(os.path.getmtime(js_path)) if js_path else 0,
    })


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


# ── Admin: Manage Topics ──────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    major_topics = MajorTopic.objects.prefetch_related('minor_topics').all()
    return render(request, 'admin/dashboard.html', {'major_topics': major_topics})


@login_required
@user_passes_test(is_admin)
def admin_major_topic_create(request):
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        icon = request.POST.get('icon', '').strip()
        slug = slugify(title)
        if title and slug:
            base_slug = slug
            counter = 1
            while MajorTopic.objects.filter(slug=slug).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            MajorTopic.objects.create(title=title, slug=slug, description=description, icon=icon)
            return redirect('admin_dashboard')
    return render(request, 'admin/major_topic_form.html', {'action': 'Criar', 'topic': None})


@login_required
@user_passes_test(is_admin)
def admin_major_topic_edit(request, major_slug):
    topic = get_object_or_404(MajorTopic, slug=major_slug)
    if request.method == 'POST':
        topic.title = request.POST.get('title', topic.title).strip()
        topic.description = request.POST.get('description', '').strip()
        topic.icon = request.POST.get('icon', '').strip()
        topic.save()
        return redirect('admin_dashboard')
    return render(request, 'admin/major_topic_form.html', {'action': 'Editar', 'topic': topic})


@login_required
@user_passes_test(is_admin)
def admin_major_topic_delete(request, major_slug):
    topic = get_object_or_404(MajorTopic, slug=major_slug)
    if request.method == 'POST':
        topic.delete()
        return redirect('admin_dashboard')
    return render(request, 'admin/confirm_delete.html', {'object': topic, 'type': 'tópico principal'})


@login_required
@user_passes_test(is_admin)
def admin_minor_topic_create(request, major_slug):
    major = get_object_or_404(MajorTopic, slug=major_slug)
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        icon = request.POST.get('icon', '').strip()
        slug = slugify(title)
        if title and slug:
            base_slug = slug
            counter = 1
            while MinorTopic.objects.filter(major_topic=major, slug=slug).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            MinorTopic.objects.create(major_topic=major, title=title, slug=slug, description=description, icon=icon)
            return redirect('admin_dashboard')
    return render(request, 'admin/minor_topic_form.html', {'action': 'Criar', 'major': major, 'topic': None})


@login_required
@user_passes_test(is_admin)
def admin_minor_topic_edit(request, major_slug, minor_slug):
    major = get_object_or_404(MajorTopic, slug=major_slug)
    topic = get_object_or_404(MinorTopic, major_topic=major, slug=minor_slug)
    if request.method == 'POST':
        topic.title = request.POST.get('title', topic.title).strip()
        topic.description = request.POST.get('description', '').strip()
        topic.icon = request.POST.get('icon', '').strip()
        topic.is_territory_map = 'is_territory_map' in request.POST
        topic.save()
        return redirect('admin_dashboard')
    return render(request, 'admin/minor_topic_form.html', {'action': 'Editar', 'major': major, 'topic': topic})


@login_required
@user_passes_test(is_admin)
def admin_minor_topic_delete(request, major_slug, minor_slug):
    major = get_object_or_404(MajorTopic, slug=major_slug)
    topic = get_object_or_404(MinorTopic, major_topic=major, slug=minor_slug)
    if request.method == 'POST':
        topic.delete()
        return redirect('admin_dashboard')
    return render(request, 'admin/confirm_delete.html', {'object': topic, 'type': 'sub-tópico'})


# ── Admin: Content Blocks ─────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def admin_content_edit(request, major_slug, minor_slug):
    major = get_object_or_404(MajorTopic, slug=major_slug)
    topic = get_object_or_404(MinorTopic, major_topic=major, slug=minor_slug)
    blocks = topic.blocks.all()
    terms = GlossaryTerm.objects.all()
    return render(request, 'admin/content_edit.html', {
        'major': major,
        'topic': topic,
        'blocks': blocks,
        'block_types': ContentBlock.BLOCK_TYPES,
        'glossary_terms': json.dumps(list(terms.values('term', 'definition'))),
    })


@login_required
@user_passes_test(is_admin)
def admin_block_add(request, major_slug, minor_slug):
    major = get_object_or_404(MajorTopic, slug=major_slug)
    topic = get_object_or_404(MinorTopic, major_topic=major, slug=minor_slug)
    if request.method == 'POST':
        block_type = request.POST.get('block_type', 'text')
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        order = topic.blocks.count()
        block = ContentBlock(minor_topic=topic, block_type=block_type, title=title, content=content, order=order)
        if request.FILES.get('file'):
            block.file = request.FILES['file']
        block.save()
        chatbot.update_block_embedding(block)
    return redirect('admin_content_edit', major_slug=major_slug, minor_slug=minor_slug)


@login_required
@user_passes_test(is_admin)
def admin_block_edit(request, block_id):
    block = get_object_or_404(ContentBlock, id=block_id)
    major_slug = block.minor_topic.major_topic.slug
    minor_slug = block.minor_topic.slug
    if request.method == 'POST':
        block.title = request.POST.get('title', '').strip()
        block.content = request.POST.get('content', '').strip()
        if request.FILES.get('file'):
            block.file = request.FILES['file']
            block.image_description = ''
        block.save()
        chatbot.update_block_embedding(block)
        return redirect('admin_content_edit', major_slug=major_slug, minor_slug=minor_slug)
    terms = GlossaryTerm.objects.all()
    return render(request, 'admin/block_edit.html', {
        'content_block': block,
        'glossary_terms': json.dumps(list(terms.values('term', 'definition'))),
    })


@login_required
@user_passes_test(is_admin)
def admin_block_delete(request, block_id):
    block = get_object_or_404(ContentBlock, id=block_id)
    major_slug = block.minor_topic.major_topic.slug
    minor_slug = block.minor_topic.slug
    if request.method == 'POST':
        block.delete()
    return redirect('admin_content_edit', major_slug=major_slug, minor_slug=minor_slug)


@login_required
@user_passes_test(is_admin)
def admin_block_reorder(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        for item in data.get('order', []):
            ContentBlock.objects.filter(id=item['id']).update(order=item['order'])
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': False}, status=400)


@login_required
@user_passes_test(is_admin)
def admin_major_topic_reorder(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        for item in data.get('order', []):
            MajorTopic.objects.filter(id=item['id']).update(order=item['order'])
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': False}, status=400)


@login_required
@user_passes_test(is_admin)
def admin_minor_topic_reorder(request, major_slug):
    major = get_object_or_404(MajorTopic, slug=major_slug)
    if request.method == 'POST':
        data = json.loads(request.body)
        for item in data.get('order', []):
            MinorTopic.objects.filter(id=item['id'], major_topic=major).update(order=item['order'])
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': False}, status=400)


# ── Admin: Glossário ──────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def admin_glossary(request):
    """Lista todos os termos do glossário."""
    terms = GlossaryTerm.objects.all()
    return render(request, 'admin/glossary.html', {'terms': terms})


@login_required
@user_passes_test(is_admin)
def admin_glossary_save(request):
    """Cria ou atualiza um termo via AJAX. Aceita 'id' opcional para editar termo específico."""
    if request.method == 'POST':
        data = json.loads(request.body)
        term_text = data.get('term', '').strip()
        definition = data.get('definition', '').strip()
        term_id = data.get('id')
        if not (term_text and definition):
            return JsonResponse({'ok': False, 'error': 'Termo e definição são obrigatórios.'}, status=400)
        if term_id:
            obj = get_object_or_404(GlossaryTerm, id=term_id)
            obj.term = term_text
            obj.definition = definition
            obj.save()
            created = False
        else:
            obj, created = GlossaryTerm.objects.update_or_create(
                term__iexact=term_text,
                defaults={'term': term_text, 'definition': definition},
            )
        return JsonResponse({'ok': True, 'created': created, 'id': obj.id, 'term': obj.term, 'definition': obj.definition})
    return JsonResponse({'ok': False}, status=400)


@login_required
@user_passes_test(is_admin)
def admin_glossary_delete(request, term_id):
    """Exclui um termo do glossário."""
    term = get_object_or_404(GlossaryTerm, id=term_id)
    if request.method == 'POST':
        term.delete()
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': False}, status=400)


@login_required
@user_passes_test(is_admin)
def admin_glossary_list(request):
    """Retorna todos os termos como JSON (para o editor carregar)."""
    terms = list(GlossaryTerm.objects.values('id', 'term', 'definition'))
    return JsonResponse({'terms': terms})


# ── Admin: Regionais ──────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def admin_regionais(request):
    regioes = Regiao.objects.prefetch_related('territorios__cidades').all()
    return render(request, 'admin/regionais.html', {'regioes': regioes})


@login_required
@user_passes_test(is_admin)
def admin_regiao_create(request):
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        icon = request.POST.get('icon', '').strip() or '🌎'
        if nome:
            Regiao.objects.create(nome=nome, icon=icon)
        return redirect('admin_regionais')
    return render(request, 'admin/regiao_form.html', {'action': 'Criar', 'obj': None})


@login_required
@user_passes_test(is_admin)
def admin_regiao_edit(request, regiao_id):
    regiao = get_object_or_404(Regiao, id=regiao_id)
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        icon = request.POST.get('icon', '').strip() or '🌎'
        if nome:
            regiao.nome = nome
            regiao.icon = icon
            regiao.save()
        return redirect('admin_regionais')
    return render(request, 'admin/regiao_form.html', {'action': 'Editar', 'obj': regiao})


@login_required
@user_passes_test(is_admin)
def admin_regiao_delete(request, regiao_id):
    regiao = get_object_or_404(Regiao, id=regiao_id)
    if request.method == 'POST':
        regiao.delete()
        return redirect('admin_regionais')
    return render(request, 'admin/confirm_delete.html', {'object': regiao, 'type': 'região'})


@login_required
@user_passes_test(is_admin)
def admin_territorio_create(request):
    regiao_id = request.POST.get('regiao_id') or request.GET.get('regiao_id')
    regiao = get_object_or_404(Regiao, id=regiao_id) if regiao_id else None
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        if nome and regiao:
            Territorio.objects.create(nome=nome, regiao=regiao)
        return redirect('admin_regionais')
    return render(request, 'admin/territorio_form.html', {'action': 'Criar', 'obj': None, 'regiao': regiao})


@login_required
@user_passes_test(is_admin)
def admin_territorio_edit(request, territorio_id):
    territorio = get_object_or_404(Territorio, id=territorio_id)
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        if nome:
            territorio.nome = nome
            territorio.save()
        return redirect('admin_regionais')
    return render(request, 'admin/territorio_form.html', {'action': 'Editar', 'obj': territorio, 'regiao': territorio.regiao})


@login_required
@user_passes_test(is_admin)
def admin_territorio_delete(request, territorio_id):
    territorio = get_object_or_404(Territorio, id=territorio_id)
    if request.method == 'POST':
        territorio.delete()
        return redirect('admin_regionais')
    return render(request, 'admin/confirm_delete.html', {'object': territorio, 'type': 'território'})


@login_required
@user_passes_test(is_admin)
def admin_cidade_create(request):
    territorio_id = request.POST.get('territorio_id') or request.GET.get('territorio_id')
    territorio = get_object_or_404(Territorio, id=territorio_id) if territorio_id else None
    if request.method == 'POST':
        nomes = request.POST.get('nomes', '')
        if territorio and nomes.strip():
            for nome in nomes.splitlines():
                nome = nome.strip()
                if nome:
                    Cidade.objects.get_or_create(nome=nome, territorio=territorio)
        return redirect('admin_regionais')
    return render(request, 'admin/cidade_form.html', {'action': 'Criar', 'obj': None, 'territorio': territorio})


@login_required
@user_passes_test(is_admin)
def admin_cidade_edit(request, cidade_id):
    cidade = get_object_or_404(Cidade, id=cidade_id)
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        if nome:
            cidade.nome = nome
            cidade.save()
        return redirect('admin_regionais')
    return render(request, 'admin/cidade_form.html', {'action': 'Editar', 'obj': cidade, 'territorio': cidade.territorio})


@login_required
@user_passes_test(is_admin)
def admin_cidade_delete(request, cidade_id):
    cidade = get_object_or_404(Cidade, id=cidade_id)
    if request.method == 'POST':
        cidade.delete()
        return redirect('admin_regionais')
    return render(request, 'admin/confirm_delete.html', {'object': cidade, 'type': 'cidade'})


# ── Admin: OLTs (compatibilidade do Gerador de Script SA) ─────────────────────

# Colunas do CSV (cabeçalho sem acento/maiúscula) → campo do model.
OLT_CSV_COLUMNS = {
    'NOME OLT': 'nome', 'FABRICANTE': 'fabricante', 'MODELO': 'modelo', 'CIDADE': 'cidade',
    'SIGLA': 'sigla', 'SITE': 'site', 'ENDERECO': 'endereco',
}


def _csv_header(name):
    name = unicodedata.normalize('NFKD', name or '').encode('ascii', 'ignore').decode()
    return ' '.join(name.upper().split())


@login_required
@user_passes_test(is_admin)
def admin_olts(request):
    olts = list(OLT.objects.select_related('fabricante'))
    por_cidade = defaultdict(list)
    for olt in olts:
        por_cidade[olt.cidade].append(olt)
    cidades = []
    for cidade, lista in sorted(por_cidade.items(), key=lambda kv: _csv_header(kv[0])):
        fabs = Counter(o.fabricante.nome for o in lista)
        cidades.append({'nome': cidade, 'olts': lista, 'fabricantes': fabs.most_common()})
    return render(request, 'admin/olts.html', {
        'fabricantes': FabricanteOLT.objects.all(),
        'projetos': ProjetoGPON.objects.all(),
        'cidades': cidades,
        'total': len(olts),
        'mistas': sum(1 for c in cidades if len(c['fabricantes']) > 1),
    })


@login_required
@user_passes_test(is_admin)
def admin_olt_import(request):
    """Substitui todas as OLTs pelas do CSV (colunas NOME OLT, FABRICANTE, CIDADE e,
    opcionais, MODELO, SIGLA, SITE, ENDEREÇO). Fabricante novo é criado com ONU "?"."""
    if request.method != 'POST' or not request.FILES.get('arquivo'):
        return redirect('admin_olts')
    raw = request.FILES['arquivo'].read()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('latin-1')
    first = text.split('\n', 1)[0]
    reader = csv.DictReader(io.StringIO(text), delimiter=';' if first.count(';') > first.count(',') else ',')
    reader.fieldnames = [OLT_CSV_COLUMNS.get(_csv_header(h), h) for h in reader.fieldnames or []]
    if any(c not in reader.fieldnames for c in ('nome', 'fabricante', 'cidade')):
        messages.error(request, 'CSV sem as colunas NOME OLT, FABRICANTE e CIDADE.')
        return redirect('admin_olts')

    fabricantes = {f.nome.lower(): f for f in FabricanteOLT.objects.all()}
    novos_fabs, linhas, vistos = [], [], set()
    for row in reader:
        nome = (row.get('nome') or '').strip()
        fab_nome = (row.get('fabricante') or '').strip()
        if not nome or not fab_nome or nome.upper() in vistos:
            continue
        vistos.add(nome.upper())
        fab = fabricantes.get(fab_nome.lower())
        if not fab:
            fab = fabricantes[fab_nome.lower()] = FabricanteOLT(nome=fab_nome, onu='?')
            novos_fabs.append(fab)
        campos = {k: (row.get(k) or '').strip() for k in ('modelo', 'cidade', 'sigla', 'site', 'endereco')}
        linhas.append((nome, fab, campos))

    with transaction.atomic():
        for fab in novos_fabs:
            fab.save()
        OLT.objects.all().delete()
        OLT.objects.bulk_create([OLT(nome=nome, fabricante=fab, **campos) for nome, fab, campos in linhas])
    msg = f'{len(linhas)} OLTs importadas.'
    if novos_fabs:
        msg += ' Fabricantes novos (preencha a ONU): ' + ', '.join(f.nome for f in novos_fabs) + '.'
    messages.success(request, msg)
    return redirect('admin_olts')


@login_required
@user_passes_test(is_admin)
def admin_fabricante_save(request, fabricante_id):
    fab = get_object_or_404(FabricanteOLT, id=fabricante_id)
    if request.method == 'POST':
        onu = request.POST.get('onu', '').strip()
        if onu:
            fab.onu = onu
            fab.aviso = request.POST.get('aviso', '').strip()
            fab.save()
            messages.success(request, f'Compatibilidade {fab.nome} salva.')
    return redirect('admin_olts')


# ── Admin: Projetos GPON (linha CTO do Gerador de Script SA) ──────────────────

SIGLA_RE = re.compile(r'^[A-Z0-9]{2,8}$', re.I)


def _split_projeto(line):
    """ "GPON Bauru Area E LPNET;BRE" (ou TAB, " - ", "=", ",", "|", espaços) → (projeto, sigla).
    A sigla é a ponta da linha que parece sigla: fim ou, invertido, começo."""
    for sep in ('\t', ';', '|', '=', ' - ', ',', '  '):
        if sep in line:
            parts = [p.strip() for p in line.split(sep) if p.strip()]
            break
    else:
        # Só espaço simples: a sigla tem que estar em maiúsculas no fim ("... LPNET BRE").
        parts = line.rsplit(' ', 1)
        if len(parts) < 2 or not parts[1].isupper():
            return None
    if len(parts) < 2:
        return None
    if SIGLA_RE.match(parts[-1]):
        return ' - '.join(parts[:-1]), parts[-1].upper()
    if SIGLA_RE.match(parts[0]):
        return ' - '.join(parts[1:]), parts[0].upper()
    return None


@login_required
@user_passes_test(is_admin)
def admin_projeto_import(request):
    """Substitui todos os projetos pelos do arquivo: uma linha por projeto, com a sigla."""
    if request.method != 'POST' or not request.FILES.get('arquivo'):
        return redirect('admin_olts')
    raw = request.FILES['arquivo'].read()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('latin-1')
    projetos, ignoradas = {}, []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        par = _split_projeto(line)
        # Cabeçalho ("PROJETO;SIGLA") não entra.
        if not par or not par[0] or _csv_header(par[0]) in ('PROJETO', 'NOME', 'GPON'):
            ignoradas.append(line)
            continue
        projetos.setdefault(projeto_key(par[0]), par)
    with transaction.atomic():
        ProjetoGPON.objects.all().delete()
        ProjetoGPON.objects.bulk_create([ProjetoGPON(nome=n, sigla=s) for n, s in projetos.values()])
    msg = f'{len(projetos)} projetos GPON importados.'
    if ignoradas:
        msg += f' {len(ignoradas)} linha(s) sem sigla ignorada(s): ' + ' | '.join(ignoradas[:5])
    messages.success(request, msg)
    return redirect('admin_olts')


@login_required
@user_passes_test(is_admin)
def admin_projeto_save(request, projeto_id=None):
    projeto = get_object_or_404(ProjetoGPON, id=projeto_id) if projeto_id else ProjetoGPON()
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        sigla = request.POST.get('sigla', '').strip().upper()
        if not nome or not sigla:
            messages.error(request, 'Preencha o projeto e a sigla.')
        elif ProjetoGPON.objects.filter(nome__iexact=nome).exclude(id=projeto.id).exists():
            messages.error(request, f'Já existe o projeto {nome}.')
        else:
            projeto.nome, projeto.sigla = nome, sigla
            projeto.save()
            messages.success(request, f'Projeto {nome} salvo.')
    return redirect(reverse('admin_olts') + '#projetos')


@login_required
@user_passes_test(is_admin)
def admin_projeto_delete(request, projeto_id):
    if request.method == 'POST':
        get_object_or_404(ProjetoGPON, id=projeto_id).delete()
    return redirect(reverse('admin_olts') + '#projetos')


def _olt_form(request, olt):
    fabricantes = FabricanteOLT.objects.all()
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        cidade = request.POST.get('cidade', '').strip()
        fab = fabricantes.filter(id=request.POST.get('fabricante')).first()
        if nome and cidade and fab:
            if OLT.objects.filter(nome__iexact=nome).exclude(id=olt.id if olt else None).exists():
                messages.error(request, f'Já existe uma OLT {nome}.')
            else:
                olt = olt or OLT()
                olt.nome, olt.cidade, olt.fabricante = nome, cidade, fab
                for campo in ('modelo', 'sigla', 'site', 'endereco'):
                    setattr(olt, campo, request.POST.get(campo, '').strip())
                olt.save()
                return redirect('admin_olts')
    return render(request, 'admin/olt_form.html', {
        'action': 'Editar' if olt else 'Criar', 'obj': olt, 'fabricantes': fabricantes,
    })


@login_required
@user_passes_test(is_admin)
def admin_olt_create(request):
    return _olt_form(request, None)


@login_required
@user_passes_test(is_admin)
def admin_olt_edit(request, olt_id):
    return _olt_form(request, get_object_or_404(OLT, id=olt_id))


@login_required
@user_passes_test(is_admin)
def admin_olt_delete(request, olt_id):
    olt = get_object_or_404(OLT, id=olt_id)
    if request.method == 'POST':
        olt.delete()
        return redirect('admin_olts')
    return render(request, 'admin/confirm_delete.html', {'object': olt, 'type': 'OLT'})
