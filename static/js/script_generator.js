// Gerador de Script de SA — roda 100% no navegador. O texto colado (ficha do SIS
// ou e-mail de mudança de plano) nunca é enviado ao servidor nem salvo.
(function () {
  // PPPoE desse domínio (plano não legado) é encurtado até o "@".
  const SHORT_PPPOE_DOMAIN = 'desktop.com.br';
  const DEFAULT_RESPONSAVEL = 'Quem estiver no local';
  const SOLICITACAO = {
    conexao: 'SEM ACESSO',
    navegacao: 'SEM NAVEGAÇÃO',
    oscilacao: 'OSCILAÇÃO',
    lentidao: 'LENTIDÃO',
    mudanca: 'MUDANÇA DE PONTO',
    plano: 'Mudança de plano',
  };
  const SOLICITANTE_SUFIXO = ' - B2B Desktop';
  const ATIVO_RE = /\b[A-Z]{2}\d{6}\b/;
  const PHONE_RE = /\(?\d{2}\)?\s*9?\d{4}[-\s]?\d{4}/;

  const $ = (id) => document.getElementById(id);
  const fieldIds = ['nome', 'pppoe', 'plano', 'ativo', 'endereco', 'responsavel', 'tel'];
  // Campos do modo Mudança de plano (ids "p-..."), preenchidos a partir do e-mail.
  const planoIds = ['adm', 'solicitante', 'nome', 'plano_atual', 'plano_novo', 'roteador', 'ativo',
    'endereco', 'complemento', 'horario', 'responsavel', 'tel'];
  // Podem ficar vazios: têm valor padrão ou são preenchidos à mão só quando existem.
  const planoOpcionais = ['ativo', 'complemento', 'horario', 'responsavel'];

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

  // ── E-mail de mudança de plano ──────────────────────────────────────────────
  // Rótulos do formulário do e-mail; uma linha que começa com um deles nunca é
  // continuação da anterior.
  const EMAIL_LABELS = ['razao social', 'cnpj', 'adm', 'plano contratado', 'valor negociado',
    'taxa de instalacao', 'sla', 'endereco', 'quantidade de links', 'vigencia', 'contato',
    'e-mail', 'precisa de roteador', 'obs', 'nome', 'telefone', 'empresa'];

  function titleCase(s) {
    return s.toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase());
  }

  // "Rótulo: valor" ou "Pergunta? valor". O e-mail quebra linhas longas (~76 colunas),
  // então uma linha comprida continua na seguinte até uma linha vazia ou outro rótulo.
  function emailField(lines, label) {
    const re = new RegExp('^' + escapeRe(label) + '[^:?]*[?:]+\\s*');
    for (let i = 0; i < lines.length; i++) {
      const m = fold(lines[i]).match(re);
      if (!m) continue;
      let value = lines[i].slice(m[0].length).trim();
      let prev = lines[i];
      while (prev.length >= 65 && lines[i + 1] && !EMAIL_LABELS.some((l) => fold(lines[i + 1]).startsWith(l))) {
        i += 1;
        prev = lines[i];
        value += ' ' + prev;
      }
      value = value.replace(/\s+/g, ' ').trim();
      if (value) return value;
    }
    return '';
  }

  function phonesIn(value) {
    const phones = [];
    (value.match(new RegExp(PHONE_RE.source, 'g')) || []).forEach((m) => {
      const digits = m.replace(/\D/g, '');
      if (!phones.includes(digits)) phones.push(digits);
    });
    return phones;
  }

  // Quem enviou o e-mail (funcionário da Desktop), como "Nome Sobrenome".
  // O remetente vem do primeiro "From:" (nome.sobrenome ou nome.<inicial>sobrenome,
  // ex.: pedro.mcaxias). Procura no texto (assinatura, linha "… adicionou uma nota")
  // um nome que case com ele; se não achar, monta a partir do próprio e-mail.
  function findSolicitante(text, lines) {
    const from = text.match(/^\s*From:\s*([\w.-]+)@/im);
    if (!from) {
      const nota = text.match(/^\s*(.+?)\s+adicionou uma nota/im);
      const words = nota ? nota[1].trim().split(/\s+/) : [];
      return titleCase(words.length > 1 ? words[0] + ' ' + words[words.length - 1] : words.join(''));
    }
    const parts = fold(from[1]).split(/[._-]+/).filter(Boolean);
    const first = parts[0];
    const rest = parts.slice(1).join('');
    if (!rest) return titleCase(first);

    for (const raw of lines) {
      const line = raw.replace(/\s+adicionou uma nota.*$/i, '').trim();
      if (!/^[A-Za-zÀ-ÿ' ]+$/.test(line)) continue;
      const original = line.split(/\s+/);
      const words = fold(line).split(/\s+/);
      if (original.length < 2 || original.length > 6 || words[0] !== first) continue;
      for (let i = 1; i < words.length; i++) {
        // "reis" == "reis", ou "mcaxias" == "m" + "caxias" (inicial de um nome do meio).
        const initialOk = words.slice(1, i).some((w) => w[0] + words[i] === rest);
        if (words[i] === rest || initialOk) return titleCase(original[0] + ' ' + original[i]);
      }
    }
    return titleCase(first + ' ' + rest);
  }

  function parseEmail(text) {
    const lines = text.split(/\r?\n/).map((l) => l.normalize('NFC').trim());
    const out = {};

    // Primeiro "ADM: <número>" ou "ADM <número>" do e-mail (assunto ou corpo), sem os zeros à esquerda.
    const adm = text.match(/\bADM\b[:# \t]*0*(\d{4,})/i);
    out.adm = adm ? adm[1] : '';

    out.solicitante = findSolicitante(text, lines);

    out.nome = emailField(lines, 'razao social');
    out.plano_novo = emailField(lines, 'plano contratado');

    // "Rod. X, s/n - km 74 - Dist. industrial / Sarapui. Cep: 18.225-000"
    // → "Rod. X, s/n - km 74 - Dist. industrial, Sarapui - 18.225-000"
    out.endereco = emailField(lines, 'endereco')
      .replace(/\s+\/\s+/g, ', ')
      .replace(/[.,]?\s*cep\s*:?\s*/i, ' - ')
      .trim();

    // "Precisa de roteador? SIM/NÃO". Sem essa pergunta, "Instalação de Roteador" ou
    // "+ Roteador" no texto indica SIM; senão fica vazio para preencher.
    const roteador = fold(emailField(lines, 'precisa de roteador'));
    if (roteador) {
      out.roteador = roteador.startsWith('s') ? 'SIM' : roteador.startsWith('n') ? 'NÃO' : '';
    } else {
      out.roteador = /(instala[çc][ãa]o de|\+)\s*roteador/i.test(text) ? 'SIM' : '';
    }

    // Quem vai atender o técnico: "Contato para Agendar instalação: Franciele - 1532769323"
    // ou, sem ele, "Nome Contato Técnico" + "Telefone Contato Técnico".
    const contato = emailField(lines, 'contato');
    const tecnicoNome = emailField(lines, 'nome contato tecnico') || emailField(lines, 'nome do contato');
    const tecnicoTel = emailField(lines, 'telefone contato tecnico') || emailField(lines, 'telefone do contato');
    let phones = phonesIn(contato);
    if (!phones.length) phones = phonesIn(tecnicoTel);
    out.tel = phones.join(' / ');
    out.responsavel = contato
      .replace(new RegExp(PHONE_RE.source, 'g'), ' ')
      .replace(/[\s\-–\/|,:]+$/, '')
      .replace(/^[\s\-–\/|,:]+/, '')
      .trim() || tecnicoNome;

    out.ativo = '-';
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

  // Um telefone por linha: o primeiro logo após o rótulo, os demais embaixo.
  function phoneLines(tel) {
    return tel.split('/').map((t) => t.trim()).filter(Boolean).join('\n');
  }

  function markMissing(el, missing) {
    el.classList.toggle('!border-brand-yellow', missing);
    el.classList.toggle('!bg-brand-yellow/10', missing);
  }

  function isPlano() {
    return selected('tratativa') === 'plano';
  }

  function setMode(plano) {
    $('fields-sis').classList.toggle('hidden', plano);
    $('fields-plano').classList.toggle('hidden', !plano);
    $('gpon-row').classList.toggle('hidden', plano);
    $('intro-sis').classList.toggle('hidden', plano);
    $('intro-plano').classList.toggle('hidden', !plano);
    $('sis-label').textContent = plano ? 'Texto do e-mail' : 'Texto da página do SIS';
    $('f-sis').placeholder = plano ? 'Cole aqui o conteúdo do e-mail da solicitação...' : 'Cole aqui o conteúdo da ficha do cliente...';
  }

  function renderPlano() {
    // Na mudança de plano as Obs padrão valem sempre (não há "cliente dedicado").
    $('obs-presets').classList.remove('hidden');

    const v = {};
    planoIds.forEach((id) => {
      const el = $('p-' + id);
      v[id] = el.value.trim();
      markMissing(el, !v[id] && !planoOpcionais.includes(id));
    });

    const obs = buildObs();
    $('preview').value = [
      'ATENDIMENTO PREMIUM',
      '',
      'Obs:' + (obs ? ' ' + obs : ''),
      '',
      'Roteador desbloqueado: ' + v.roteador,
      '',
      'Nome de quem solicitou a VT: ' + (v.solicitante ? v.solicitante + SOLICITANTE_SUFIXO : ''),
      '',
      'Nome da Empresa: ' + v.nome,
      'ADM: ' + v.adm,
      'Ativo do equipamento: ' + (v.ativo || '-'),
      '',
      'Plano atual: ' + v.plano_atual,
      'Plano novo: ' + v.plano_novo,
      '',
      'Endereço: ' + v.endereco,
      'Complemento: ' + v.complemento,
      '',
      'Horário de atendimento: ' + (v.horario || 'Administrativo'),
      'Responsável: ' + (v.responsavel || DEFAULT_RESPONSAVEL),
      'Contato: ' + phoneLines(v.tel),
      '',
      'SOLICITAÇÃO: ' + SOLICITACAO.plano,
    ].join('\n');

    $('pending').textContent = v.plano_atual ? '' : 'Falta: plano atual';
  }

  function render() {
    if (isPlano()) {
      renderPlano();
      return;
    }
    const dedicado = selected('dedicado') === 'sim';
    const tratativa = selected('tratativa');
    const needsGpon = !dedicado && tratativa !== 'mudanca';
    // Sem navegação / lentidão = cliente conectado (GPON UP): GPON é sempre UP, sem perguntar.
    const gponFixo = tratativa === 'navegacao' || tratativa === 'lentidao';
    const gpon = !needsGpon ? '' : gponFixo ? 'UP' : selected('gpon');

    $('gpon-group').classList.toggle('hidden', !needsGpon || gponFixo);
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
      markMissing(el, !el.disabled && !el.value.trim() && id !== 'responsavel');
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
      'Tel: ' + phoneLines(v.tel),
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
    if (isPlano()) {
      const parsed = parseEmail($('f-sis').value);
      planoIds.forEach((id) => {
        // Plano atual, complemento e horário não vêm do e-mail: não apaga o que foi digitado.
        if (id in parsed) $('p-' + id).value = parsed[id];
      });
      render();
      return;
    }
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
    planoIds.forEach((id) => { $('p-' + id).value = ''; });
    $('f-adm').dataset.auto = '1';
    $('f-horario').value = '';
    document.querySelectorAll('input[name="tratativa"], input[name="gpon"], input[name="obs"]').forEach((r) => { r.checked = false; });
    document.querySelector('input[name="dedicado"][value="nao"]').checked = true;
    $('keep-endereco').checked = true;
    modoPlano = false;
    setMode(false);
    reparse();
    $('f-sis').focus();
  }

  $('f-sis').addEventListener('input', reparse);
  $('f-adm').addEventListener('input', () => { $('f-adm').dataset.auto = ''; render(); });
  document.querySelectorAll('.sg-input').forEach((el) => el.addEventListener('input', render));
  document.querySelectorAll('input[type="radio"], input[type="checkbox"]').forEach((el) => el.addEventListener('change', render));
  // Entrar ou sair da Mudança de plano troca o modelo e relê o texto colado.
  let modoPlano = false;
  document.querySelectorAll('input[name="tratativa"]').forEach((el) => el.addEventListener('change', () => {
    if (isPlano() === modoPlano) return;
    modoPlano = isPlano();
    setMode(modoPlano);
    reparse();
  }));
  $('keep-endereco').addEventListener('change', (e) => {
    $('f-endereco').value = e.target.checked ? sisEndereco : '';
    render();
    if (!e.target.checked) $('f-endereco').focus();
  });
  $('copy-btn').addEventListener('click', copy);
  $('clear-btn').addEventListener('click', clearAll);

  render();
})();
