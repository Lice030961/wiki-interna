// Testes do parser do Gerador de Script de SA (static/js/sa_parser.js).
// Rodar: node --test tests_js/
// Todas as fichas e e-mails abaixo são FICTÍCIOS (o repo é espelhado em público): nunca colar dados reais aqui.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createSAParser } = require('../static/js/sa_parser.js');

const OLT_DATA = {
  fabricantes: {
    ZTE: { onu: 'ZG', aviso: '' },
    Nokia: { onu: 'ZN', aviso: '' },
    Huawei: { onu: 'HW', aviso: 'Huawei é legado: valide com o NOC.' },
  },
  olts: { 'LT-G01-VLV001-SP': 'ZTE', 'LT-G02-VLV002-SP': 'Nokia' },
  cidades: {
    'vale verde': { nome: 'Vale Verde', fabs: ['ZTE', 'Nokia'] },
    'sao jorge do campo': { nome: 'São Jorge do Campo', fabs: ['Huawei'] },
    'pedra alta': { nome: 'Pedra Alta', fabs: ['ZTE'] },
  },
  siglas: { VLV: ['ZTE', 'Nokia'], PDA: ['ZTE'] },
  projetos: { 'vale verde area a': 'VLV' },
};
const P = createSAParser(OLT_DATA);

// Ficha do SIS fictícia, no formato "Rótulo<TAB>valor" que o Ctrl+A/Ctrl+C produz.
function ficha({ plano = 'Fibra Business+ 600M 2024 T-F-24.600M.6000G.IP', ativos = ['ZN220280 - ONT Zyxel-PMG2005'],
  hostname = 'LT-G01-VLV001-SP', cto = true, base = null, cidade = 'Vale Verde', usuario = 'padaria.sol@desktop.com.br' } = {}) {
  return [
    'Área do Assinante (SAC)\t123456 - Padaria Sol Nascente',
    'Padaria Sol Nascente LTDA',
    'E-mail\tcontato@padariasol.exemplo',
    'Celular\t(19) 99999-0001',
    'Fixo\t(19) 3333-0002',
    'Logradouro\tRua das Flores',
    'Número\t100',
    'Bairro\tCentro',
    'Cidade\t' + cidade,
    'Serviços',
    'Fibra Home 300M 2023',
    plano,
    'Adicionais do Contrato',
    'Usuário\t' + usuario,
    ...(hostname ? ['Hostname\t' + hostname] : []),
    ...(cto ? ['Projeto\tGPON Vale Verde Area A', 'Caixa\t1945\tNum\t8'] : []),
    ...(base ? [base] : []),
    'Ativos',
    ...ativos,
    "IP's Adicionais",
    'XX999999 fora da lista de ativos',
  ].join('\n');
}

// ── Utilitários ──────────────────────────────────────────────────────────────

test('trimPlano corta código e o que vem depois da velocidade/ano', () => {
  assert.equal(P.trimPlano('Fibra Business+ 600M 2024 T-F-24.600M.6000G.IP'), 'Fibra Business+ 600M 2024');
  assert.equal(P.trimPlano('Fibra Home 750M+ c/ Servicos Digitais 2026 * Turbo-G-1G'), 'Fibra Home 750M+ c/ Servicos Digitais 2026');
  assert.equal(P.trimPlano('Plano Sem Velocidade'), 'Plano Sem Velocidade');
});

test('isDedicado: mesma lista do Rotas Premium; "Fibra Corporativo" é GPON', () => {
  ['Link Dedicado 100M', 'Corporativo+ 200M', 'Corporativo Plus', 'Banda IP 50M', 'Trânsito BGP',
    'Clear Channel 1G', 'IP Ethernet'].forEach((p) => assert.ok(P.isDedicado(p), p));
  ['Fibra Corporativo 500M', 'Fibra Business+ 600M', 'Fibra Home 300M', ''].forEach((p) => assert.ok(!P.isDedicado(p), p));
});

test('isCombo: Home e Business Combo', () => {
  assert.ok(P.isCombo('Fibra Home 300M'));
  assert.ok(P.isCombo('Bus. Combo 500M'));
  assert.ok(P.isCombo('Business Combo 1G'));
  assert.ok(!P.isCombo('Fibra Business+ 600M'));
});

test('formatPppoe encurta só o domínio da Desktop', () => {
  assert.equal(P.formatPppoe('cliente@desktop.com.br'), 'cliente@');
  assert.equal(P.formatPppoe('cliente@outro.com.br'), 'cliente@outro.com.br');
});

test('chaves de cidade e projeto iguais às da view (city_key/projeto_key)', () => {
  assert.equal(P.cityKey("Santa Bárbara d'Oeste"), 'santa barbara doeste');
  assert.equal(P.projetoKey('GPON Bauru Área E - LPNET'), 'bauru area e lpnet');
});

test('matchCity aceita abreviação', () => {
  assert.equal(P.matchCity('Vale Verde').nome, 'Vale Verde');
  assert.equal(P.matchCity('S. Jorge do Campo').nome, 'São Jorge do Campo');
  assert.equal(P.matchCity('Cidade Inexistente'), null);
});

test('formatEndereco no formato do SIS', () => {
  assert.equal(P.formatEndereco('Rua A, 10 - Centro - Pedra Alta SP cep 13000-000'), 'Rua A, 10 - Centro - Pedra Alta/SP - 13000-000');
});

// ── Compatibilidade ──────────────────────────────────────────────────────────

test('compatibilidade: hostname exato resolve cidade com dois fabricantes', () => {
  const c = P.compatibilidade('LT-G02-VLV002-SP', 'Vale Verde', P.matchCity('Vale Verde'), 'Fibra Business+ 600M');
  assert.equal(c.compat, 'OLT Nokia - ONU ZN');
  assert.deepEqual(c.avisos, []);
});

test('compatibilidade: só a cidade traz todos os fabricantes com aviso', () => {
  const c = P.compatibilidade('', 'Vale Verde', P.matchCity('Vale Verde'), 'Fibra Business+ 600M');
  assert.equal(c.compat, 'OLT ZTE - ONU ZG / OLT Nokia - ONU ZN');
  assert.equal(c.avisos.length, 1);
});

test('compatibilidade: aviso do fabricante (Huawei legado)', () => {
  const c = P.compatibilidade('', 'São Jorge do Campo', P.matchCity('São Jorge do Campo'), 'Fibra Business+');
  assert.equal(c.compat, 'OLT Huawei - ONU HW');
  assert.ok(c.avisos.some((a) => a.includes('legado')));
});

test('compatibilidade: combo e dedicado', () => {
  assert.equal(P.compatibilidade('', 'Vale Verde', P.matchCity('Vale Verde'), 'Fibra Home 300M').compat,
    'DS / ONU Integrada / Kit (ZG ou ZN)');
  assert.equal(P.compatibilidade('LT-G01-VLV001-SP', '', null, 'Link Dedicado').compat, '-');
});

test('compatibilidade: cidade sem OLT pede preenchimento à mão', () => {
  const c = P.compatibilidade('', 'Lugar Nenhum', null, 'Fibra Business+');
  assert.equal(c.compat, '');
  assert.match(c.avisos[0], /Nenhuma OLT/);
});

// ── Ficha do SIS ─────────────────────────────────────────────────────────────

test('parse: ficha de fibra completa', () => {
  const r = P.parse(ficha());
  assert.equal(r.adm, '123456');
  assert.equal(r.nome, 'Padaria Sol Nascente LTDA');
  assert.equal(r.pppoe, 'padaria.sol@');
  assert.equal(r.plano, 'Fibra Business+ 600M 2024');  // serviço aberto, não o primeiro da lista
  assert.equal(r.ativo, 'ZN220280');                    // XX999999 depois de "IP's Adicionais" não entra
  assert.equal(r.endereco, 'Rua das Flores, 100 - Centro - Vale Verde/SP');
  assert.equal(r.tel, '19999990001 / 1933330002');
  assert.equal(r.compat, 'OLT ZTE - ONU ZG');
  assert.equal(r.cto, 'GPON Vale Verde Area A / VLV-1945 Porta 8');
  assert.equal(r.radio, false);
  assert.equal(r.base, '');
});

test('parse: projeto sem sigla vira "?" com aviso', () => {
  const r = createSAParser({ ...OLT_DATA, projetos: {} }).parse(ficha());
  assert.equal(r.cto, 'GPON Vale Verde Area A / ?-1945 Porta 8');
  assert.ok(r.avisos.some((a) => a.includes('sem sigla')));
});

test('parse: link rádio pela linha Base (com tab ou um espaço só)', () => {
  for (const base of ['Base\tBase TTI.Torre Exemplo', 'Base Base Torre Exemplo II', 'Base Torre Exemplo II']) {
    const r = P.parse(ficha({ hostname: null, cto: false, base, ativos: ['NM300239 - Nano M5'] }));
    assert.equal(r.radio, true, base);
    assert.match(r.base, /Torre Exemplo/);
  }
});

test('parse: Hostname/CTO na ficha = fibra, mesmo com linha Base', () => {
  const r = P.parse(ficha({ base: 'Base Torre Exemplo' }));
  assert.equal(r.radio, false);
  assert.equal(r.base, '');
});

test('parse: PPPoE .radio não decide a tecnologia (cliente migrado para a fibra)', () => {
  const r = P.parse(ficha({ usuario: 'cliente.radio@desktop.com.br' }));
  assert.equal(r.radio, false);
  assert.equal(r.compat, 'OLT ZTE - ONU ZG');
});

test('parse: linha "Base" com GPON no nome não é rádio', () => {
  assert.equal(P.baseRadio(['Base GPON Vale Verde']), '');
});

test('parse: sem Ativo e sem Hostname não busca pela cidade', () => {
  const r = P.parse(ficha({ hostname: null, cto: false, ativos: [] }));
  assert.equal(r.compat, '');
});

test('parse: plano dedicado → Compatibilidade "-"', () => {
  const r = P.parse(ficha({ plano: 'Link Dedicado 100M' }));
  assert.equal(r.compat, '-');
});

// ── Prospect ─────────────────────────────────────────────────────────────────

const PROSPECT = [
  'Prospect',
  'Mercado Bom Preço ME',
  'Status SPC\tOK',
  'CNPJ\t00.000.000/0001-00',
  'Código do Contrato\t98765',
  'Contratos',
  'Fibra Business+ 300M 2025 T-F-25.300M',
  'Logradouro\tAvenida Brasil',
  'Número\t2000',
  'Bairro\tJardim',
  'Cidade\tPedra Alta',
  'Complemento\tSala 2',
  'Celular\t(19) 98888-0000',
].join('\n');

test('isProspect / parseProspect', () => {
  assert.ok(P.isProspect(PROSPECT));
  assert.ok(!P.isProspect(ficha()));
  const r = P.parseProspect(PROSPECT);
  assert.equal(r.nome, 'Mercado Bom Preço ME');
  assert.equal(r.prospect, '98765');
  assert.equal(r.plano_novo, 'Fibra Business+ 300M 2025');
  assert.equal(r.endereco, 'Avenida Brasil, 2000 - Jardim - Pedra Alta/SP');
  assert.equal(r.complemento, 'Sala 2');
  assert.equal(r.compat, 'OLT ZTE - ONU ZG');
});

// ── E-mail (Mudança de plano / Instalação) ───────────────────────────────────

const EMAIL = [
  'From: Ana Paula Souza <ana.souza@desktop.com.br>',
  'To: premium@desktop.com.br',
  'Subject: Mudança de plano ADM 00123456',
  '',
  'Razão social: Oficina do Zé LTDA',
  'Plano atual: Fibra Business+ 300M 2023 T-F',
  'Novo plano: Fibra Business+ 1G 2026 T-F-26',
  'Endereço completo: Rua Sete, 70 - Centro',
  'Pedra Alta SP cep 13000-000',
  'Contato para agendar: João',
  '(19) 97777-1234',
  'Horário: 08h às 18h',
  '',
  'Att,',
  'Ana Paula Souza',
].join('\n');

test('parseEmail: campos da mudança de plano', () => {
  const r = P.parseEmail(EMAIL);
  assert.equal(r.adm, '123456');
  assert.equal(r.solicitante, 'Ana Souza');
  assert.equal(r.nome, 'Oficina do Zé LTDA');
  assert.equal(r.plano_atual, 'Fibra Business+ 300M 2023');
  assert.equal(r.plano_novo, 'Fibra Business+ 1G 2026');
  assert.equal(r.endereco, 'Rua Sete, 70 - Centro - Pedra Alta/SP - 13000-000');
  assert.equal(r.compat, 'OLT ZTE - ONU ZG');
  assert.equal(r.responsavel, 'João');
  assert.equal(r.tel, '19977771234');
  assert.equal(r.horario, '08h às 18h');
});

test('parseEmail: solicitante com inicial do nome do meio (nome.<inicial>sobrenome)', () => {
  const r = P.parseEmail('De: Pedro Martins Caxias <pedro.mcaxias@desktop.com.br>\n\nPedro Martins Caxias');
  assert.equal(r.solicitante, 'Pedro Caxias');
});

test('parseEmail: caixa genérica não é solicitante; nota do Salesforce é usada', () => {
  const r = P.parseEmail('From: premium@desktop.com.br\nExterno User adicionou uma nota');
  assert.equal(r.solicitante, 'Externo User');
});

test('parseEmail: nome e telefone do contato em linhas separadas', () => {
  const r = P.parseEmail('Nome Contato Técnico: Maria\nTelefone Contato Técnico: (19) 3456-7890');
  assert.equal(r.responsavel, 'Maria');
  assert.equal(r.tel, '1934567890');
});

test('parseEmail: cidade sem OLT avisa', () => {
  const r = P.parseEmail('Endereço: Rua X, 1 - Bairro - Lugar Nenhum/SP');
  assert.equal(r.compat, '');
  assert.ok(r.avisos.some((a) => a.includes('Cidade sem OLT')));
});
