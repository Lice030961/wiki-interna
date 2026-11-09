"""Painel admin: Regiões, Territórios e Cidades (página de regionais)."""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test

from ..models import Regiao, Territorio, Cidade
from .helpers import is_admin


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
