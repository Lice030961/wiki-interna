import re
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.utils.text import slugify
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.db.models import Q

from .models import MajorTopic, MinorTopic, ContentBlock, GlossaryTerm


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


# ── Search ────────────────────────────────────────────────────────────────────

def search(request):
    q = request.GET.get('q', '').strip()
    results = []
    if q:
        minor_topics = MinorTopic.objects.filter(
            Q(title__icontains=q) | Q(description__icontains=q)
        ).select_related('major_topic')[:20]
        for mt in minor_topics:
            results.append({
                'title': mt.title,
                'major': mt.major_topic.title,
                'url': f'/topico/{mt.major_topic.slug}/{mt.slug}/',
            })
        major_topics = MajorTopic.objects.filter(
            Q(title__icontains=q) | Q(description__icontains=q)
        )[:10]
        for mt in major_topics:
            results.append({
                'title': mt.title,
                'major': 'Tópico Principal',
                'url': f'/topico/{mt.slug}/',
            })
    return JsonResponse({'results': results})


# ── Major Topic ───────────────────────────────────────────────────────────────

def major_topic(request, major_slug):
    topic = get_object_or_404(MajorTopic, slug=major_slug)
    minor_topics = topic.minor_topics.all()
    return render(request, 'major_topic.html', {'topic': topic, 'minor_topics': minor_topics})


# ── Minor Topic ───────────────────────────────────────────────────────────────

def minor_topic(request, major_slug, minor_slug):
    major = get_object_or_404(MajorTopic, slug=major_slug)
    topic = get_object_or_404(MinorTopic, major_topic=major, slug=minor_slug)
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
        block.save()
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