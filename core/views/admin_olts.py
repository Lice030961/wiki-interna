"""Painel admin: OLTs, fabricantes e projetos GPON (Gerador de Script SA)."""
import re
import io
import csv
import unicodedata
from collections import Counter, defaultdict
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction

from ..models import FabricanteOLT, OLT, ProjetoGPON
from .helpers import is_admin, projeto_key


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
