"""Ferramentas (registradas em core/tools.py): tudo é processado no navegador."""
import os
import re
from collections import Counter, defaultdict
from django.shortcuts import render
from django.contrib.staticfiles import finders

from ..models import FabricanteOLT, OLT, ProjetoGPON
from .helpers import city_key, projeto_key


def _js_version(*paths):
    """Versão na URL do JS (mtime mais recente): o navegador nunca roda um script antigo do cache com a página nova."""
    found = [finders.find(p) for p in paths]
    return max((int(os.path.getmtime(f)) for f in found if f), default=0)


# ── Ferramentas ───────────────────────────────────────────────────────────────

def script_generator(request):
    # Toda a extração roda no navegador (static/js/script_generator.js);
    # o texto colado do SIS nunca chega ao servidor.
    # Versão do JS na URL: o navegador nunca roda um script antigo do cache com a página nova.
    return render(request, 'tools/script_generator.html', {
        'js_version': _js_version('js/sa_parser.js', 'js/script_generator.js'),
        'olt_data': olt_data(),
        'dedicado_options': [('nao', 'Não'), ('sim', 'Sim')],
        'gpon_options': ['UP', 'DOWN'],
        # Link rádio (não é GPON): no lugar de GPON, Compatibilidade e CTO vai a Base (torre) do SIS.
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
            ('base', 'Base (rádio)'),
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


def batimento(request):
    # A planilha do Power BI é lida e filtrada só no navegador (static/js/batimento.js);
    # o arquivo nunca chega ao servidor.
    return render(request, 'tools/batimento.html', {
        'js_version': _js_version('js/batimento.js'),
    })
