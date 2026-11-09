"""Painel admin: tópicos, blocos de conteúdo e glossário."""
import os
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.utils.text import slugify
from django.conf import settings
from django.contrib import messages

from ..models import MajorTopic, MinorTopic, ContentBlock, GlossaryTerm
from .. import chatbot
from .helpers import is_admin


# Tipos aceitos em cada bloco com arquivo (pela extensão: o content-type vem do navegador).
UPLOAD_EXTENSIONS = {
    ContentBlock.IMAGE: {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'},
    ContentBlock.VIDEO: {'.mp4', '.webm', '.ogg', '.mov', '.m4v'},
}


def _upload_error(block_type, upload):
    """Mensagem de erro do arquivo enviado, ou None se estiver ok."""
    allowed = UPLOAD_EXTENSIONS.get(block_type)
    if allowed is None:
        return 'Este tipo de bloco não aceita arquivo.'
    ext = os.path.splitext(upload.name)[1].lower()
    if ext not in allowed:
        return f'Arquivo "{upload.name}" não aceito. Use: {", ".join(sorted(allowed))}.'
    if upload.size > settings.MAX_UPLOAD_SIZE:
        return f'Arquivo muito grande (máximo {settings.MAX_UPLOAD_SIZE // (1024 * 1024)} MB).'
    return None


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
        if block_type not in dict(ContentBlock.BLOCK_TYPES):
            block_type = ContentBlock.TEXT
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        order = topic.blocks.count()
        block = ContentBlock(minor_topic=topic, block_type=block_type, title=title, content=content, order=order)
        upload = request.FILES.get('file')
        if upload:
            error = _upload_error(block_type, upload)
            if error:
                messages.error(request, error)
                return redirect('admin_content_edit', major_slug=major_slug, minor_slug=minor_slug)
            block.file = upload
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
        upload = request.FILES.get('file')
        if upload:
            error = _upload_error(block.block_type, upload)
            if error:
                messages.error(request, error)
                return redirect('admin_block_edit', block_id=block.id)
            block.file = upload
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
