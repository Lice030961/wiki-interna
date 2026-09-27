// Gerador de Script de SA — roda 100% no navegador. O texto colado do SIS
// nunca é enviado ao servidor nem salvo.
(function () {
  // PPPoE desse domínio (plano não legado) é encurtado até o "@".
  const SHORT_PPPOE_DOMAIN = 'desktop.com.br';
  const DEFAULT_RESPONSAVEL = 'Quem estiver no local';
  const SOLICITACAO = {
    conexao: 'SEM ACESSO',
    navegacao: 'SEM NAVEGAÇÃO',
    oscilacao: 'OSCILAÇÃO',
    mudanca: 'MUDANÇA DE PONTO',
  };
  const ATIVO_RE = /\b[A-Z]{2}\d{6}\b/;
  const PHONE_RE = /\(?\d{2}\)?\s*9?\d{4}[-\s]?\d{4}/;

  const $ = (id) => document.getElementById(id);
  const fieldIds = ['nome', 'pppoe', 'plano', 'ativo', 'endereco', 'responsavel', 'tel'];

  // Remove acentos preservando o tamanho da string, para os índices baterem com o original.
  function fold(s) {
    return s.split('').map((c) => c.normalize('NFD')[0]).join('').toLowerCase();
  }

  function escapeRe(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  // O SIS copia as linhas como "Rótulo<TAB>valor" (ou com vários espaços).
  function labelRe(label) {
    return new RegExp('^' + escapeRe(label) + '(?:\\s*:|\\t|\\s{2,}|$)\\s*');
  }

  // Valores de todas as linhas com esse rótulo. Com nextLine, rótulo sozinho na linha
  // (ex.: "Serviços") pega a linha seguinte como valor.
  function findAll(lines, label, nextLine) {
    const re = labelRe(label);
    const values = [];
    lines.forEach((line, i) => {
      const m = fold(line).match(re);
      if (!m) return;
      let value = line.slice(m[0].length).trim();
      if (!value && nextLine && lines[i + 1]) value = lines[i + 1].trim();
      if (value) values.push(value);
    });
    return values;
  }

  function find(lines, label, nextLine) {
    return findAll(lines, label, nextLine)[0] || '';
  }

  function formatPppoe(login) {
    const at = login.indexOf('@');
    if (at !== -1 && login.slice(at + 1).toLowerCase() === SHORT_PPPOE_DOMAIN) {
      return login.slice(0, at + 1);
    }
    return login;
  }

  function parse(text) {
    const lines = text.split(/\r?\n/).map((l) => l.normalize('NFC').trim()).filter(Boolean);
    const out = {};

    // ADM = número da "Área do Assinante (SAC)".
    const sac = find(lines, 'area do assinante (sac)').match(/^\d+/);
    out.adm = sac ? sac[0] : '';

    // O nome não tem rótulo: é a linha logo antes de "E-mail".
    const emailIdx = lines.findIndex((l) => labelRe('e-mail').test(fold(l)));
    out.nome = emailIdx > 0 ? lines[emailIdx - 1] : '';

    const login = find(lines, 'usuario').match(/^\S+@[\w.-]+/);
    out.pppoe = login ? formatPppoe(login[0]) : '';

    // Com vários links no mesmo ADM, "Serviços" lista todos; o serviço aberto é a
    // linha logo antes de "Adicionais do Contrato".
    const adicionaisIdx = lines.findIndex((l) => fold(l).startsWith('adicionais do contrato'));
    out.plano = adicionaisIdx > 0 ? lines[adicionaisIdx - 1] : find(lines, 'servicos', true);

    // Só aparece com o "Mostrar" dos Ativos aberto (ex.: "ZN220280 - ONT Zyxel-PMG2005").
    // Pode haver mais de um (ONU + roteador); procura só até "IP's Adicionais".
    const ativos = [];
    const ativosIdx = lines.findIndex((l) => labelRe('ativos').test(fold(l)));
    if (ativosIdx !== -1) {
      let endIdx = lines.findIndex((l, i) => i > ativosIdx && fold(l).startsWith("ip's adicionais"));
      if (endIdx === -1) endIdx = lines.length;
      lines.slice(ativosIdx, endIdx).forEach((l) => {
        (l.match(new RegExp(ATIVO_RE.source, 'g')) || []).forEach((code) => {
          if (!ativos.includes(code)) ativos.push(code);
        });
      });
    }
    out.ativo = ativos.join(' / ');

    // Formato fixo: Rua, número - Bairro - Cidade/SP
    const rua = find(lines, 'logradouro');
    const numero = find(lines, 'numero');
    const bairro = find(lines, 'bairro');
    const cidade = find(lines, 'cidade');
    out.endereco = rua
      ? rua + (numero ? ', ' + numero : '') + (bairro ? ' - ' + bairro : '') + (cidade ? ' - ' + cidade + '/SP' : '')
      : '';

    const phones = [];
    ['celular', 'fixo', 'telefone', 'fone'].forEach((label) => {
      findAll(lines, label).forEach((value) => {
        (value.match(new RegExp(PHONE_RE.source, 'g')) || []).forEach((m) => {
          const digits = m.replace(/\D/g, '');
          if (!phones.includes(digits)) phones.push(digits);
        });
      });
    });
    out.tel = phones.join(' / ');

    return out;
  }

  function selected(name) {
    const el = document.querySelector('input[name="' + name + '"]:checked');
    return el ? el.value : '';
  }

  function buildSolicitacao(dedicado, tratativa, gpon) {
    if (!tratativa) return '';
    let s = SOLICITACAO[tratativa];
    if (!dedicado && tratativa !== 'mudanca' && gpon) s += ' - GPON ' + gpon;
    return s;
  }

  function buildObs() {
    const parts = Array.from(document.querySelectorAll('input[name="obs"]:checked')).map((el) => el.value);
    const extra = $('f-obs').value.trim();
    if (extra) parts.push(extra);
    return parts.join(' / ');
  }

  function render() {
    const dedicado = selected('dedicado') === 'sim';
    const tratativa = selected('tratativa');
    const needsGpon = !dedicado && tratativa !== 'mudanca';
    const gpon = needsGpon ? selected('gpon') : '';

    $('gpon-group').classList.toggle('hidden', !needsGpon);
    $('f-ativo').disabled = dedicado;
    // As Obs padrão (IGREJA, LOS VERMELHA...) não se aplicam a dedicado: só texto livre.
    $('obs-presets').classList.toggle('hidden', dedicado);
    if (dedicado) document.querySelectorAll('input[name="obs"]').forEach((el) => { el.checked = false; });

    const v = {};
    fieldIds.forEach((id) => { v[id] = $('f-' + id).value.trim(); });
    if (dedicado) v.ativo = '-';
    if (!v.responsavel) v.responsavel = DEFAULT_RESPONSAVEL;

    ['adm'].concat(fieldIds).forEach((id) => {
      const el = $('f-' + id);
      const missing = !el.disabled && !el.value.trim() && id !== 'responsavel';
      el.classList.toggle('border-amber-400', missing);
      el.classList.toggle('bg-amber-50', missing);
    });

    const obs = buildObs();
    $('preview').value = [
      'ATENDIMENTO PREMIUM',
      '',
      'Obs:' + (obs ? ' ' + obs : ''),
      '',
      'Nome da Empresa: ' + v.nome,
      'PPPOE: ' + v.pppoe,
      'ADM: ' + $('f-adm').value.trim(),
      'Plano: ' + v.plano,
      'Ativo do equipamento: ' + v.ativo,
      '',
      'Endereço: ' + v.endereco,
      'Horário de atendimento: ' + ($('f-horario').value.trim() || 'Administrativo'),
      'Responsável: ' + v.responsavel,
      'CONTATO:',
      // Um telefone por linha: o primeiro logo após "Tel:", os demais embaixo.
      'Tel: ' + v.tel.split('/').map((t) => t.trim()).filter(Boolean).join('\n'),
      '',
      'SOLICITAÇÃO: ' + buildSolicitacao(dedicado, tratativa, gpon),
    ].join('\n');

    const pending = [];
    if (!tratativa) pending.push('tratativa');
    if (needsGpon && tratativa && !gpon) pending.push('GPON UP/DOWN');
    if (!dedicado && !v.ativo) pending.push('ativo (abra o "Mostrar" no SIS)');
    $('pending').textContent = pending.length ? 'Falta: ' + pending.join(', ') : '';
  }

  // Com vários links no mesmo ADM, o SIS costuma repetir o mesmo endereço em todos;
  // desmarcar "Manter endereço" deixa o campo vazio para preencher à mão.
  let sisEndereco = '';

  function reparse() {
    const parsed = parse($('f-sis').value);
    sisEndereco = parsed.endereco;
    if (!$('keep-endereco').checked) parsed.endereco = '';
    fieldIds.forEach((id) => { $('f-' + id).value = parsed[id] || ''; });
    // Não sobrescreve um ADM digitado à mão.
    const adm = $('f-adm');
    if (!adm.value.trim() || adm.dataset.auto === '1') {
      adm.value = parsed.adm;
      adm.dataset.auto = '1';
    }
    render();
  }

  async function copy() {
    const text = $('preview').value;
    try {
      await navigator.clipboard.writeText(text);
    } catch (e) {
      $('preview').select();
      document.execCommand('copy');
    }
    const btn = $('copy-btn');
    const original = btn.textContent;
    btn.textContent = 'Copiado!';
    setTimeout(() => { btn.textContent = original; }, 1500);
  }

  function clearAll() {
    ['f-adm', 'f-sis', 'f-obs'].forEach((id) => { $(id).value = ''; });
    $('f-adm').dataset.auto = '1';
    $('f-horario').value = '';
    document.querySelectorAll('input[name="tratativa"], input[name="gpon"], input[name="obs"]').forEach((r) => { r.checked = false; });
    document.querySelector('input[name="dedicado"][value="nao"]').checked = true;
    $('keep-endereco').checked = true;
    reparse();
    $('f-sis').focus();
  }

  $('f-sis').addEventListener('input', reparse);
  $('f-adm').addEventListener('input', () => { $('f-adm').dataset.auto = ''; render(); });
  document.querySelectorAll('.sg-input').forEach((el) => el.addEventListener('input', render));
  document.querySelectorAll('input[type="radio"], input[type="checkbox"]').forEach((el) => el.addEventListener('change', render));
  $('keep-endereco').addEventListener('change', (e) => {
    $('f-endereco').value = e.target.checked ? sisEndereco : '';
    render();
    if (!e.target.checked) $('f-endereco').focus();
  });
  $('copy-btn').addEventListener('click', copy);
  $('clear-btn').addEventListener('click', clearAll);

  render();
})();
