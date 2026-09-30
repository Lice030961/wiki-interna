// Gerador de Script de SA — roda 100% no navegador. O texto colado (ficha do SIS
// ou e-mail de mudança de plano/instalação) nunca é enviado ao servidor nem salvo.
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
    instalacao: 'Instalação',
  };
  // Com um telefone só, a Obs "ligar antes" já leva o número.
  const OBS_LIGAR = 'LIGAR ANTES DE IR AO LOCAL';
  const SOLICITANTE_SUFIXO = ' - B2B Desktop';
  const ATIVO_RE = /\b[A-Z]{2}\d{6}\b/;
  const PHONE_RE = /\(?\d{2}\)?\s*9?\d{4}[-\s]?\d{4}/;

  const $ = (id) => document.getElementById(id);
  const fieldIds = ['nome', 'pppoe', 'plano', 'ativo', 'endereco', 'responsavel', 'tel'];
  // Tratativas cujo texto colado é o e-mail da solicitação (campos "p-...") e os campos de cada uma.
  const EMAIL_MODES = {
    plano: ['adm', 'solicitante', 'nome', 'plano_atual', 'ativo', 'plano_novo', 'tel',
      'endereco', 'complemento', 'horario', 'responsavel'],
    instalacao: ['nome', 'plano_novo', 'prospect', 'tel', 'endereco', 'complemento', 'horario', 'responsavel'],
  };
  const emailIds = [...new Set(Object.values(EMAIL_MODES).flat())];
  // Podem ficar vazios: têm valor padrão ou são preenchidos à mão só quando existem.
  const emailOpcionais = ['complemento', 'horario', 'responsavel'];

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

  // ── E-mail (mudança de plano / instalação) ──────────────────────────────────
  // Diferente da ficha do SIS, o e-mail não tem formato fixo: vem de pessoas
  // diferentes, às vezes encaminhado, com rótulos variados. Cada campo aceita
  // vários rótulos (regex sobre a linha sem acento e minúscula, sempre no começo
  // da linha), seguidos de um separador opcional (":", "?", "=", ">>>", "-").
  // O valor fica na mesma linha ou, se a linha acaba no rótulo, na de baixo.
  const EMAIL_FIELDS = {
    nome: ['razao social( do cliente)?', 'nome da empresa', 'empresa cliente', 'cliente(?=\\s*:)'],
    plano_novo: ['plano novo', 'novo plano', '(plano|produto)( \\/ (plano|produto))? contratad[oa]', 'plano(?=\\s*:)'],
    plano_atual: ['plano atual'],
    endereco: ['endereco( completo)?( d[aeo])?( (instalacao|ativacao))?'],
    complemento: ['complemento'],
    horario: ['horario( de (atendimento|funcionamento))?'],
    prospect: ['(n[º°o.]?\\s*(d[oa]\\s*)?)?prospect'],
    // Quem vai receber o técnico no local (não quem enviou o e-mail), em ordem de preferência.
    contato: ['contato para agendar( a)?( instalacao)?', 'contato( no)? local', 'contato tecnico',
      'responsavel( no local| tecnico| pelo local)?', 'contato(?=\\s*:)'],
    contatoNome: ['nome( do)? contato( tecnico)?'],
    contatoTel: ['(telefone|tel|celular)( do)? contato( tecnico)?'],
  };
  const EMAIL_SEP = '\\b\\s*[:?=>\\-–]*\\s*';
  const emailRes = {};
  Object.keys(EMAIL_FIELDS).forEach((key) => {
    emailRes[key] = EMAIL_FIELDS[key].map((p) => new RegExp('^(' + p + ')' + EMAIL_SEP));
  });
  // Outros rótulos comuns do e-mail: uma linha que começa com eles nunca é continuação da anterior.
  const EMAIL_LABELS_RE = /^(cnpj|valor|taxa|sla|quantidade|qtde|vigencia|contrato|e-?mail|obs|empresa|telefone|nome|mailto|instalacao|att|grato|precisa|roteador|ata)\b/;
  // Caixas de e-mail da Desktop que não são pessoas.
  const GENERIC_MAILBOXES = ['premium', 'operacoes', 'suporte', 'analises', 'noc', 'comercial', 'financeiro', 'atendimento'];
  const HEADER_RE = /^\s*(from|de|enviad[oa] por|remetente)\s*:/i;

  function titleCase(s) {
    return s.toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase());
  }

  function isEmailLabel(line) {
    const f = fold(line);
    return EMAIL_LABELS_RE.test(f) || Object.keys(emailRes).some((k) => emailRes[k].some((re) => re.test(f)));
  }

  // Se o valor continua na próxima linha. O e-mail quebra linhas longas (~76 colunas);
  // endereço também continua numa linha com CEP/cidade, e contato numa linha com o telefone.
  function continues(kind, value, prev, next) {
    if (!next || isEmailLabel(next)) return false;
    if (!value) return true;
    if (prev.length >= 65) return true;
    if (kind === 'endereco') return /\bcep\b|\d{2}\.?\d{3}-?\d{3}|^[-–]|\bsp\b/.test(fold(next));
    if (kind === 'contato') return !PHONE_RE.test(value) && PHONE_RE.test(next);
    return false;
  }

  function emailField(lines, key, kind) {
    for (const re of emailRes[key]) {
      for (let i = 0; i < lines.length; i++) {
        const m = fold(lines[i]).match(re);
        if (!m) continue;
        let value = lines[i].slice(m[0].length).trim();
        let prev = lines[i];
        for (let n = 0; n < 3 && continues(kind, value, prev, lines[i + 1]); n++) {
          i += 1;
          prev = lines[i];
          // Linhas de endereço viram partes separadas por " - ", a não ser que já tenham o traço.
          const glue = kind === 'endereco' && value && !/[-–]$/.test(value) && !/^[-–]/.test(prev) ? ' - ' : ' ';
          value = value ? value + glue + prev : prev;
        }
        value = value.replace(/\s+/g, ' ').trim();
        if (value) return value;
      }
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

  // "Marcelo  (16)99742-3851" → "Marcelo"
  function contactName(value) {
    return value
      .replace(new RegExp(PHONE_RE.source, 'g'), ' ')
      .replace(/\b(tel|telefone|cel|celular|fone|whats(app)?)\b\.?:?/gi, ' ')
      .replace(/[()]/g, ' ')
      .replace(/\s+/g, ' ')
      .replace(/^[\s\-–\/|,:]+|[\s\-–\/|,:]+$/g, '')
      .trim();
  }

  // Formato parecido com o do SIS: "Rua, número - Bairro - Cidade/SP - CEP".
  // "Dist. industrial / Sarapui. Cep: 18.225-000" → "Dist. industrial, Sarapui - 18.225-000"
  // "Santa Helena  SP  cep 14920-110" → "Santa Helena/SP - 14920-110"
  function formatEndereco(s) {
    return s
      .replace(/\s+/g, ' ')
      .replace(/\s+\/\s+/g, ', ')
      .replace(/[.,]?\s*\bcep\b\s*:?\s*/i, ' - ')
      .replace(/\s*[-–]?\s*\bSP\b\.?(?=\s*[-–]|\s*$)/i, '/SP')
      .replace(/\s+[-–](\s+[-–])+\s+/g, ' - ')
      .replace(/^[\s\-–,]+|[\s\-–,]+$/g, '')
      .trim();
  }

  // E-mails pessoais da Desktop (nome.sobrenome) de um trecho, como [nome, sobrenome].
  function desktopPeople(s) {
    return Array.from(fold(s).matchAll(/\b([a-z]+)\.([a-z]+)@desktop\.[a-z.]+/g))
      .filter((m) => !GENERIC_MAILBOXES.includes(m[1]))
      .map((m) => [m[1], m[2]]);
  }

  // Quem enviou o e-mail (funcionário da Desktop), como "Nome Sobrenome".
  // Remetente = e-mail pessoal da Desktop no primeiro "From:"/"De:" que tiver um
  // (encaminhados trazem vários); sem nenhum, o primeiro fora de To/CC. O e-mail é
  // nome.sobrenome ou nome.<inicial>sobrenome (ex.: pedro.mcaxias), então procura no
  // texto (assinatura, cabeçalho, "… adicionou uma nota") um nome que case com ele.
  function findSolicitante(text, lines) {
    let person = null;
    for (const line of lines) {
      if (HEADER_RE.test(line) && desktopPeople(line).length) { person = desktopPeople(line)[0]; break; }
    }
    if (!person) {
      const body = lines.filter((l) => !/^\s*(to|cc|para|destinat[aá]rios?)\s*:/i.test(l)).join('\n');
      person = desktopPeople(body)[0] || null;
    }
    if (!person) {
      const nota = text.match(/^\s*(.+?)\s+adicionou uma nota/im);
      const words = nota ? nota[1].trim().split(/\s+/) : [];
      return titleCase(words.length > 1 ? words[0] + ' ' + words[words.length - 1] : words.join(''));
    }
    const [first, rest] = person;

    for (const raw of lines) {
      const line = raw
        .replace(/\s+adicionou uma nota.*$/i, '')
        .replace(HEADER_RE, '')
        .replace(/<[^>]*>|mailto:\S+|\S+@\S+/gi, ' ')
        .replace(/\s+/g, ' ')
        .trim();
      if (!/^[A-Za-zÀ-ÿ' ]+$/.test(line)) continue;
      const original = line.split(' ');
      const words = fold(line).split(' ');
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

    // Primeiro "ADM: <número>" / "ADM <número>" / "ADM Nº <número>" do e-mail (assunto ou
    // corpo), sem os zeros à esquerda.
    const adm = text.match(/\bADM\b\s*(?:n[º°o.]\s*)?[:#º°\s]*0*(\d{4,})/i);
    out.adm = adm ? adm[1] : '';

    out.solicitante = findSolicitante(text, lines);
    out.nome = emailField(lines, 'nome');
    out.plano_novo = emailField(lines, 'plano_novo');
    out.endereco = formatEndereco(emailField(lines, 'endereco', 'endereco'));
    const prospect = emailField(lines, 'prospect').match(/\d+/);
    out.prospect = prospect ? prospect[0] : '';

    // Nome e telefone de quem recebe o técnico: juntos ("Contato para Agendar
    // instalação: Franciele - 1532769323") ou separados ("Nome/Telefone Contato Técnico").
    const contato = emailField(lines, 'contato', 'contato');
    const contatoNome = emailField(lines, 'contatoNome', 'contato');
    out.responsavel = contactName(contato) || contactName(contatoNome);
    let phones = phonesIn(contato);
    if (!phones.length) phones = phonesIn(contatoNome + ' ' + emailField(lines, 'contatoTel', 'contato'));
    out.tel = phones.join(' / ');

    // Normalmente preenchidos à mão: só sobrescreve se o e-mail trouxer.
    ['plano_atual', 'complemento', 'horario'].forEach((key) => {
      const value = emailField(lines, key);
      if (value) out[key] = value;
    });
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

  function buildObs(tel) {
    const phones = tel.split('/').map((t) => t.trim()).filter(Boolean);
    const parts = Array.from(document.querySelectorAll('input[name="obs"]:checked')).map((el) => (
      el.value === OBS_LIGAR && phones.length === 1 ? el.value + ' - ' + phones[0] : el.value
    ));
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

  // 'plano' / 'instalacao' quando o texto colado é um e-mail; '' para a ficha do SIS.
  function emailMode() {
    const t = selected('tratativa');
    return t in EMAIL_MODES ? t : '';
  }

  function setMode(mode) {
    const email = !!mode;
    $('fields-sis').classList.toggle('hidden', email);
    $('fields-plano').classList.toggle('hidden', !email);
    $('gpon-row').classList.toggle('hidden', email);
    $('equip-row').classList.toggle('hidden', !email);
    $('intro-sis').classList.toggle('hidden', email);
    $('intro-email').classList.toggle('hidden', !email);
    $('intro-email-tipo').textContent = mode === 'instalacao' ? 'instalação' : 'mudança de plano';
    $('sis-label').textContent = email ? 'Texto do e-mail' : 'Texto da página do SIS';
    $('f-sis').placeholder = email ? 'Cole aqui o conteúdo do e-mail da solicitação...' : 'Cole aqui o conteúdo da ficha do cliente...';
    if (!email) return;
    document.querySelectorAll('#fields-plano [data-field]').forEach((el) => {
      el.classList.toggle('hidden', !EMAIL_MODES[mode].includes(el.dataset.field));
    });
    document.querySelector('label[for="p-plano_novo"]').textContent = mode === 'instalacao' ? 'Plano' : 'Plano novo';
  }

  function renderEmail(mode) {
    // Aqui as Obs padrão valem sempre (não há "cliente dedicado").
    $('obs-presets').classList.remove('hidden');

    const v = {};
    EMAIL_MODES[mode].forEach((id) => {
      const el = $('p-' + id);
      v[id] = el.value.trim();
      markMissing(el, !v[id] && !emailOpcionais.includes(id));
    });
    const simNao = (name) => (selected(name) === 'sim' ? 'SIM' : 'NÃO');
    const obs = buildObs(v.tel);
    const pending = [];

    if (mode === 'instalacao') {
      $('preview').value = [
        'ATENDIMENTO PREMIUM',
        '',
        'Obs:' + (obs ? ' ' + obs : ''),
        '',
        'Tipo de instalação: ',
        'Roteador desbloqueado: ' + simNao('roteador'),
        'Necessidade de RB: ' + simNao('rb'),
        'Necessidade de ATA: ' + simNao('ata'),
        '',
        'Nome da Empresa: ' + v.nome,
        'Plano: ' + v.plano_novo,
        'Prospect: ' + v.prospect,
        '',
        'Endereço: ' + v.endereco,
        'Complemento: ' + v.complemento,
        '',
        'Horario de atendimento: ' + (v.horario || 'Administrativo'),
        'Responsavel: ' + (v.responsavel || DEFAULT_RESPONSAVEL),
        'CONTATO: ' + phoneLines(v.tel),
        '',
        'SOLICITAÇÃO: ' + SOLICITACAO.instalacao,
      ].join('\n');
      if (!v.prospect) pending.push('prospect');
    } else {
      $('preview').value = [
        'ATENDIMENTO PREMIUM',
        '',
        'Obs:' + (obs ? ' ' + obs : ''),
        '',
        'Roteador desbloqueado: ' + simNao('roteador'),
        'Necessidade de RB: ' + simNao('rb'),
        'Necessidade de ATA: ' + simNao('ata'),
        '',
        'Nome de quem solicitou a VT: ' + (v.solicitante ? v.solicitante + SOLICITANTE_SUFIXO : ''),
        '',
        'Nome da Empresa: ' + v.nome,
        'ADM: ' + v.adm,
        'Ativo do equipamento: ' + v.ativo,
        'Plano atual: ' + v.plano_atual,
        'Plano novo: ' + v.plano_novo,
        '',
        'Endereço: ' + v.endereco,
        'Complemento: ' + v.complemento,
        '',
        'Horário de atendimento: ' + (v.horario || 'Administrativo'),
        '',
        'Responsável: ' + (v.responsavel || DEFAULT_RESPONSAVEL),
        'Contato: ' + phoneLines(v.tel),
        '',
        'SOLICITAÇÃO: ' + SOLICITACAO.plano,
      ].join('\n');
      if (!v.plano_atual) pending.push('plano atual');
      if (!v.ativo) pending.push('ativo');
    }
    $('pending').textContent = pending.length ? 'Falta: ' + pending.join(', ') : '';
  }

  function render() {
    const mode = emailMode();
    if (mode) {
      renderEmail(mode);
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

    const obs = buildObs(v.tel);
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
    if (emailMode()) {
      const parsed = parseEmail($('f-sis').value);
      emailIds.forEach((id) => {
        // Plano atual, ativo, complemento e horário só vêm se o e-mail trouxer: não apaga o que foi digitado.
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

  // Modo atual ('' = SIS, 'plano', 'instalacao'); null até a primeira sincronização.
  // A ficha do SIS e o e-mail usam a mesma caixa de texto, mas cada um guarda o seu
  // texto: trocar de tratativa nunca lê a ficha como e-mail (nem o contrário).
  // Plano e Instalação compartilham o mesmo e-mail.
  let modo = null;
  const texts = { sis: '', email: '' };
  const kindOf = (mode) => (mode ? 'email' : 'sis');

  // Aplica a tratativa marcada: troca modelo, campos e texto se o modo mudou.
  // Também roda ao abrir a página, já que o navegador pode restaurar botões e texto.
  function syncMode() {
    const mode = emailMode();
    if (mode === modo) return false;
    if (modo !== null && kindOf(mode) !== kindOf(modo)) {
      texts[kindOf(modo)] = $('f-sis').value;
      $('f-sis').value = texts[kindOf(mode)];
    }
    modo = mode;
    setMode(mode);
    reparse();
    return true;
  }

  function clearAll() {
    texts.sis = '';
    texts.email = '';
    ['f-adm', 'f-sis', 'f-obs', 'f-horario'].forEach((id) => { $(id).value = ''; });
    emailIds.forEach((id) => { $('p-' + id).value = ''; });
    $('f-adm').dataset.auto = '1';
    document.querySelectorAll('input[name="tratativa"], input[name="gpon"], input[name="obs"]').forEach((r) => { r.checked = false; });
    ['dedicado', 'roteador', 'rb', 'ata'].forEach((name) => {
      document.querySelector('input[name="' + name + '"][value="nao"]').checked = true;
    });
    $('keep-endereco').checked = true;
    if (!syncMode()) reparse();
    $('f-sis').focus();
  }

  $('f-sis').addEventListener('input', reparse);
  $('f-adm').addEventListener('input', () => { $('f-adm').dataset.auto = ''; });
  document.querySelectorAll('.sg-input').forEach((el) => el.addEventListener('input', render));
  // Um único fluxo para todos os botões: troca de modo (se houver) ou só redesenha o script.
  document.querySelectorAll('input[type="radio"], input[name="obs"]').forEach((el) => el.addEventListener('change', () => {
    if (!syncMode()) render();
  }));
  $('keep-endereco').addEventListener('change', (e) => {
    $('f-endereco').value = e.target.checked ? sisEndereco : '';
    render();
    if (!e.target.checked) $('f-endereco').focus();
  });
  $('copy-btn').addEventListener('click', copy);
  $('clear-btn').addEventListener('click', clearAll);

  syncMode();
})();
