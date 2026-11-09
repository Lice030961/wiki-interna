// Gerador de Script de SA — roda 100% no navegador. O texto colado (ficha do SIS
// ou e-mail de mudança de plano/instalação) nunca é enviado ao servidor nem salvo.
(function () {
  const $ = (id) => document.getElementById(id);
  // Fibra/Rádio é automático: Rádio quando a ficha do SIS tem a linha Base (e não tem Hostname/CTO).
  let radioSis = false;
  const fieldIds = ['nome', 'pppoe', 'plano', 'ativo', 'compat', 'cto', 'base', 'endereco', 'responsavel', 'tel'];
  // Tratativas cujo texto colado é o e-mail da solicitação (campos "p-...") e os campos de cada uma.
  const EMAIL_MODES = {
    plano: ['adm', 'solicitante', 'nome', 'plano_atual', 'ativo', 'compat', 'plano_novo', 'tel',
      'endereco', 'complemento', 'horario', 'responsavel'],
    instalacao: ['nome', 'plano_novo', 'prospect', 'compat', 'tel', 'endereco', 'complemento', 'horario', 'responsavel'],
  };
  const emailIds = [...new Set(Object.values(EMAIL_MODES).flat())];
  // Podem ficar vazios: têm valor padrão ou são preenchidos à mão só quando existem.
  const emailOpcionais = ['complemento', 'horario', 'responsavel'];

  // Parser (static/js/sa_parser.js, carregado antes): funções puras, testadas em tests_js/.
  const parser = createSAParser(JSON.parse(($('olt-data') || {}).textContent || '{}'));
  const {
    DEFAULT_RESPONSAVEL, OBS_LIGAR, SOLICITACAO, SOLICITANTE_SUFIXO,
    parse, parseEmail, parseProspect, isProspect, isDedicado,
  } = parser;


  function selected(name) {
    const el = document.querySelector('input[name="' + name + '"]:checked');
    return el ? el.value : '';
  }

  // Rádio: "SEM ACESSO - BASE DOWN" (a base é a torre) no lugar de "GPON DOWN".
  function buildSolicitacao(dedicado, tratativa, gpon, radio) {
    if (!tratativa) return '';
    let s = SOLICITACAO[tratativa];
    if (!dedicado && tratativa !== 'mudanca' && gpon) s += (radio ? ' - BASE ' : ' - GPON ') + gpon;
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
    $('intro-email').classList.toggle('hidden', mode !== 'plano');
    $('intro-prospect').classList.toggle('hidden', mode !== 'instalacao');
    $('sis-label').textContent = mode === 'instalacao' ? 'Texto do Prospect (ou e-mail)'
      : email ? 'Texto do e-mail' : 'Texto da página do SIS';
    $('f-sis').placeholder = mode === 'instalacao' ? 'Cole aqui a página do Prospect...'
      : email ? 'Cole aqui o conteúdo do e-mail da solicitação...' : 'Cole aqui o conteúdo da ficha do cliente...';
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
        'Compatibilidade: ' + v.compat,
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
        'Compatibilidade: ' + v.compat,
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
    if (!v.compat) pending.push('compatibilidade');
    $('pending').textContent = pending.length ? 'Falta: ' + pending.join(', ') : '';
  }

  // Avisos da Compatibilidade (cidade com dois fabricantes, OLT legado, cidade sem OLT),
  // fora do script: o técnico não vê, mas o analista confere antes de enviar.
  let oltAvisos = [];

  function renderAvisos(avisos) {
    const box = $('olt-aviso');
    box.replaceChildren(...avisos.map((msg) => {
      const p = document.createElement('p');
      p.textContent = '⚠️ ' + msg;
      return p;
    }));
    box.classList.toggle('hidden', !avisos.length);
  }

  function render() {
    // Os avisos são de OLT/CTO: no rádio (só nos modos do SIS) não se aplicam.
    renderAvisos(!emailMode() && radioSis ? [] : oltAvisos);
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

    const radio = radioSis;
    $('gpon-group').classList.toggle('hidden', !needsGpon || gponFixo);
    $('gpon-legend').textContent = radio ? 'Base' : 'GPON';
    // Rádio: Base no lugar de Compatibilidade e CTO.
    $('campo-compat').classList.toggle('hidden', radio);
    $('campo-cto').classList.toggle('hidden', radio);
    $('campo-base').classList.toggle('hidden', !radio);
    $('f-ativo').disabled = dedicado;
    $('f-compat').disabled = dedicado || radio;
    $('f-cto').disabled = dedicado || radio;
    $('f-base').disabled = !radio;
    // As Obs padrão (IGREJA, LOS VERMELHA...) não se aplicam a dedicado: só texto livre.
    $('obs-presets').classList.toggle('hidden', dedicado);
    if (dedicado) document.querySelectorAll('input[name="obs"]').forEach((el) => { el.checked = false; });

    const v = {};
    fieldIds.forEach((id) => { v[id] = $('f-' + id).value.trim(); });
    // Dedicado não tem ONU, OLT nem CTO.
    if (dedicado) {
      v.ativo = '-';
      v.compat = '-';
      v.cto = '-';
    }
    if (!v.responsavel) v.responsavel = DEFAULT_RESPONSAVEL;

    ['adm'].concat(fieldIds).forEach((id) => {
      const el = $('f-' + id);
      // CTO com "?" = projeto sem sigla cadastrada.
      markMissing(el, !el.disabled && id !== 'responsavel' && (!el.value.trim() || (id === 'cto' && el.value.includes('?'))));
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
      ...(radio ? ['Base: ' + v.base] : ['Compatibilidade: ' + v.compat, 'CTO: ' + v.cto]),
      '',
      'Endereço: ' + v.endereco,
      'Horário de atendimento: ' + ($('f-horario').value.trim() || 'Administrativo'),
      'Responsável: ' + v.responsavel,
      'CONTATO:',
      'Tel: ' + phoneLines(v.tel),
      '',
      'SOLICITAÇÃO: ' + buildSolicitacao(dedicado, tratativa, gpon, radio),
    ].join('\n');

    const pending = [];
    if (!tratativa) pending.push('tratativa');
    if (needsGpon && tratativa && !gpon) pending.push(radio ? 'BASE UP/DOWN' : 'GPON UP/DOWN');
    if (!dedicado && !v.ativo) pending.push('ativo (abra o "Mostrar" no SIS)');
    if (radio) {
      if (!v.base) pending.push('base (rádio)');
    } else {
      if (!dedicado && !v.compat) pending.push('compatibilidade');
      if (!dedicado && (!v.cto || v.cto.includes('?'))) pending.push('CTO');
    }
    $('pending').textContent = pending.length ? 'Falta: ' + pending.join(', ') : '';
  }

  // Com vários links no mesmo ADM, o SIS costuma repetir o mesmo endereço em todos;
  // desmarcar "Manter endereço" deixa o campo vazio para preencher à mão.
  let sisEndereco = '';

  function reparse() {
    const text = $('f-sis').value;
    if (emailMode()) {
      // Na Instalação o texto pode ser a página do Prospect ou o e-mail.
      const parsed = emailMode() === 'instalacao' && isProspect(text) ? parseProspect(text) : parseEmail(text);
      oltAvisos = text.trim() ? parsed.avisos : [];
      emailIds.forEach((id) => {
        // Plano atual, ativo, complemento e horário só vêm se o e-mail trouxer: não apaga o que foi digitado.
        if (id in parsed) $('p-' + id).value = parsed[id];
      });
      render();
      return;
    }
    const parsed = parse(text);
    oltAvisos = text.trim() ? parsed.avisos : [];
    sisEndereco = parsed.endereco;
    if (!$('keep-endereco').checked) parsed.endereco = '';
    fieldIds.forEach((id) => { $('f-' + id).value = parsed[id] || ''; });
    // Base no SIS = Rádio; Hostname/CTO = Fibra.
    radioSis = parsed.radio;
    // Plano dedicado marca "Cliente dedicado" (Ativo, Compatibilidade e CTO "-", sem GPON); dá para desmarcar.
    if (isDedicado(parsed.plano)) document.querySelector('input[name="dedicado"][value="sim"]').checked = true;
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
    radioSis = false;
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
