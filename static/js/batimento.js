// Batimento de SAs — roda 100% no navegador. A planilha do Power BI é lida aqui
// (SheetJS; o ExcelJS não abre o export do Power BI) e nunca é enviada ao servidor
// nem salva. O ExcelJS só gera o .xlsx baixado, porque grava o menu suspenso.
(function () {
  // A cópia vai da primeira coluna até esta (inclusive); dali pra frente é do analista.
  const LAST_COL = 'classificacao_aging';
  const REQUIRED = ['numero_compromisso', 'regional', 'status', 'tipo_trabalho', 'termino_servico', LAST_COL];
  const DATE_COLS = ['dt_abertura', 'inicio_agendado', 'inicio_servico', 'termino_servico'];
  // Ordem dos filtros (valores fora da lista vão no fim, em ordem alfabética). Todos os
  // status daqui aparecem sempre, mesmo sem SA na planilha: são as etapas do Salesforce
  // e o filtro tem que estar pronto para qualquer uma.
  const STATUS_ORDER = ['Agendado', 'Em deslocamento', 'Chegada no Local', 'Em execução', 'On Hold', 'Suspensa', 'Canceled', 'Concluída'];
  const TIPO_ORDER = ['Manutenção', 'Serviços Adicionais', 'Mudança de endereço', 'Alteração de Plano',
    'Ativação', 'Migração', 'Retirada de Equipamento'];
  // Tipos marcados ao abrir a planilha (o resto começa desmarcado).
  const TIPO_ON = ['manutencao', 'servicos adicionais', 'mudanca de endereco'];
  // Subtipo de Serviços Adicionais que às vezes não interessa: tem opção própria, desligada.
  const CHIP_SUBTIPO = 'entrega de chip';
  const isChip = (r) => norm(r.subtipo_trabalho) === CHIP_SUBTIPO;
  // Opções do menu suspenso de STATUS no .xlsx baixado.
  const STATUS_MENU = ['Agendada', 'Despachado', 'Em Deslocamento', 'Em execução', 'Aberto NOC',
    'Aberto Eng de Redes', 'Pendente', 'Suspensa', 'Massiva', 'Cancelada', 'Canceled', 'Normalizado',
    'Reagendado', 'Sobra', 'Sinalizado ao COP', 'Comercial'];
  // Status encerrados: começam desmarcados e, marcados, ganham cada um um slider "desde N dias atrás" (0 = hoje ... MAX_DAYS), pelo termino_servico.
  const MAX_DAYS = 7;
  const DEFAULT_DAYS = 1;
  // ExcelJS 4.4.0 (static/vendor/), carregado só no "Baixar .xlsx". O endereço vem do template
  // ({% static %} põe o hash do arquivo em produção).
  const EXCELJS_URL = (document.currentScript && document.currentScript.dataset.exceljs) || '/static/vendor/exceljs.min.js';

  const $ = (id) => document.getElementById(id);
  const norm = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').trim().toLowerCase();
  const isClosed = (status) => /^(cancel|conclu)/.test(norm(status));
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  let headers = []; // colunas copiadas (até LAST_COL)
  let rows = []; // objetos {coluna: valor}
  let days = {}; // status encerrado -> dias para trás
  let sliderKey = null; // status com slider na tela (só recria quando muda)
  let visible = [];

  // ── Leitura ────────────────────────────────────────────────────────────────

  // Datas do Excel chegam como número de série (dias desde 1899-12-30, sem fuso);
  // exports antigos trazem texto americano "4/16/2026 3:37:40 PM". Devolve {y, m, d, H, M, S} ou null.
  function parseDate(v) {
    if (typeof v === 'number') {
      const t = new Date(Math.round((v - 25569) * 86400) * 1000);
      return { y: t.getUTCFullYear(), m: t.getUTCMonth() + 1, d: t.getUTCDate(),
        H: t.getUTCHours(), M: t.getUTCMinutes(), S: t.getUTCSeconds() };
    }
    const s = String(v || '').trim();
    let r = s.match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?/);
    if (r) return { y: +r[1], m: +r[2], d: +r[3], H: +(r[4] || 0), M: +(r[5] || 0), S: +(r[6] || 0) };
    r = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?)?/i);
    if (!r) return null;
    let H = +(r[4] || 0);
    const ampm = (r[7] || '').toUpperCase();
    if (ampm === 'PM' && H < 12) H += 12;
    if (ampm === 'AM' && H === 12) H = 0;
    // Com AM/PM é formato americano (mês primeiro); sem, brasileiro.
    const [m, d] = ampm ? [+r[1], +r[2]] : [+r[2], +r[1]];
    return { y: +r[3], m, d, H, M: +(r[5] || 0), S: +(r[6] || 0) };
  }

  const pad = (n) => String(n).padStart(2, '0');
  const fmtDate = (p) => `${pad(p.d)}/${pad(p.m)}/${p.y} ${pad(p.H)}:${pad(p.M)}:${pad(p.S)}`;
  const dayNumber = (p) => Date.UTC(p.y, p.m - 1, p.d) / 86400000;

  // Texto que vai para a planilha, já no formato do batimento.
  function display(col, v) {
    if (v === '' || v == null) return '';
    if (DATE_COLS.includes(col)) {
      const p = parseDate(v);
      return p ? fmtDate(p) : String(v);
    }
    // "+10 Dias" vira fórmula ao colar; fica "10 Dias" (D+X e MX não mudam).
    if (col === LAST_COL) return String(v).trim().replace(/^[=+]+/, '');
    return String(v).trim();
  }

  async function load(file) {
    showError('');
    $('file-name').textContent = file.name;
    $('file-info').textContent = 'Lendo…';
    try {
      const wb = XLSX.read(await file.arrayBuffer());
      const sheet = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], { header: 1, raw: true, defval: '' });
      const headerIdx = sheet.slice(0, 10).findIndex((r) => r.some((v) => String(v).trim() === 'numero_compromisso'));
      if (headerIdx < 0) throw new Error('Não achei o cabeçalho (numero_compromisso) — é o export do Power BI?');

      const allCols = sheet[headerIdx].map((v) => String(v).trim());
      const missing = REQUIRED.filter((c) => !allCols.includes(c));
      if (missing.length) throw new Error('Faltam colunas na planilha: ' + missing.join(', '));

      headers = allCols.slice(0, allCols.indexOf(LAST_COL) + 1);
      rows = sheet.slice(headerIdx + 1)
        .map((r) => Object.fromEntries(allCols.map((col, i) => [col, r[i] ?? ''])))
        // Linhas em branco e o rodapé "Filtros aplicados" não têm SA.
        .filter((r) => String(r.numero_compromisso).trim());
      $('file-info').textContent = `${rows.length} SAs na planilha`;
      buildFilters();
      render();
    } catch (e) {
      rows = [];
      $('file-info').textContent = 'Export do Power BI';
      $('filters').classList.add('hidden');
      showError(e.message || 'Não consegui ler o arquivo.');
      render();
    }
  }

  function showError(msg) {
    $('error').textContent = msg;
    $('error').classList.toggle('hidden', !msg);
  }

  // ── Filtros ────────────────────────────────────────────────────────────────

  function ordered(values, order) {
    const known = order.filter((o) => values.some((v) => norm(v) === norm(o)))
      .map((o) => values.find((v) => norm(v) === norm(o)));
    const rest = values.filter((v) => !known.includes(v)).sort((a, b) => a.localeCompare(b, 'pt-BR'));
    return [...known, ...rest];
  }

  function buildGroup(id, col, order, isOff, always = []) {
    const counts = new Map();
    rows.forEach((r) => {
      const v = String(r[col] || '').trim() || '(vazio)';
      counts.set(v, (counts.get(v) || 0) + 1);
    });
    always.forEach((a) => {
      if (![...counts.keys()].some((v) => norm(v) === norm(a))) counts.set(a, 0);
    });
    $(id).innerHTML = ordered([...counts.keys()], order).map((v) => `
      <label class="flex items-center gap-2.5 px-2 h-8 rounded-xl text-sm text-ink cursor-pointer hover:bg-card">
        <input type="checkbox" data-col="${col}" value="${esc(v)}" ${isOff(v) ? '' : 'checked'}
               class="w-4 h-4 accent-brand-red" />
        <span class="flex-1 truncate">${esc(v)}</span>
        <span class="text-xs text-mute">${counts.get(v)}</span>
      </label>`).join('');
  }

  function buildFilters() {
    buildGroup('g-regional', 'regional', [], () => false);
    buildGroup('g-status', 'status', STATUS_ORDER, isClosed, STATUS_ORDER);
    buildGroup('g-tipo', 'tipo_trabalho', TIPO_ORDER, (v) => !TIPO_ON.includes(norm(v)), TIPO_ORDER);
    // "Entrega de Chip" logo abaixo de Serviços Adicionais.
    const sa = [...document.querySelectorAll('input[data-col="tipo_trabalho"]')]
      .find((i) => norm(i.value) === 'servicos adicionais');
    sa.closest('label').insertAdjacentHTML('afterend', `
      <label id="chip-row" class="flex items-center gap-2.5 pl-8 pr-2 h-8 rounded-xl text-sm text-body cursor-pointer hover:bg-card">
        <input id="f-chip" type="checkbox" class="w-4 h-4 accent-brand-red" />
        <span class="flex-1 truncate">Entrega de Chip</span>
        <span class="text-xs text-mute">${rows.filter(isChip).length}</span>
      </label>`);
    days = {};
    sliderKey = null;
    $('filters').classList.remove('hidden');
  }

  const daysOf = (status) => days[status] ?? DEFAULT_DAYS;

  function daysLabel(n) {
    if (n === 0) return 'só hoje';
    const now = new Date();
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() - n);
    const date = `${pad(d.getDate())}/${pad(d.getMonth() + 1)}`;
    return n === 1 ? `desde ontem (${date})` : `desde ${date} (${n} dias)`;
  }

  // Um slider por status encerrado marcado.
  function renderSliders(closed) {
    const key = closed.join('|');
    if (key === sliderKey) return;
    sliderKey = key;
    $('g-period').innerHTML = closed.map((st) => `
      <div>
        <div class="flex items-baseline justify-between gap-2 mb-1">
          <span class="text-sm font-bold text-ink">${esc(st)}</span>
          <span data-days-label="${esc(st)}" class="text-xs font-semibold text-brand-red">${daysLabel(daysOf(st))}</span>
        </div>
        <input type="range" min="0" max="${MAX_DAYS}" step="1" value="${daysOf(st)}" data-days="${esc(st)}"
               class="w-full accent-brand-red cursor-pointer" />
        <div class="flex justify-between text-[11px] text-mute"><span>Hoje</span><span>${MAX_DAYS} dias</span></div>
      </div>`).join('');
  }

  function selected(col) {
    return new Set([...document.querySelectorAll(`input[data-col="${col}"]:checked`)].map((i) => i.value));
  }

  function filtered() {
    const reg = selected('regional');
    const st = selected('status');
    const tipo = selected('tipo_trabalho');
    const chip = $('f-chip').checked;
    const now = new Date();
    const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()) / 86400000;
    const key = (r, col) => String(r[col] || '').trim() || '(vazio)';
    return rows.filter((r) => {
      if (!reg.has(key(r, 'regional')) || !st.has(key(r, 'status')) || !tipo.has(key(r, 'tipo_trabalho'))) return false;
      if (!chip && isChip(r)) return false;
      if (!isClosed(r.status)) return true;
      const end = parseDate(r.termino_servico);
      return !!end && dayNumber(end) >= today - daysOf(key(r, 'status'));
    });
  }

  // ── Saída ──────────────────────────────────────────────────────────────────

  function render() {
    const hasData = rows.length > 0;
    const closed = hasData ? [...selected('status')].filter(isClosed) : [];
    $('period-group').classList.toggle('hidden', !closed.length);
    renderSliders(closed);
    // Entrega de Chip só vale com Serviços Adicionais marcado.
    const chipRow = $('chip-row');
    if (chipRow) {
      const saOn = [...selected('tipo_trabalho')].some((v) => norm(v) === 'servicos adicionais');
      $('f-chip').disabled = !saOn;
      chipRow.classList.toggle('opacity-40', !saOn);
    }

    visible = hasData ? filtered() : [];
    $('count').textContent = hasData ? `· ${visible.length} de ${rows.length}` : '';
    $('copy-btn').disabled = $('download-btn').disabled = !visible.length;
    $('empty').classList.toggle('hidden', visible.length > 0);
    $('empty').textContent = hasData ? 'Nenhuma SA com esses filtros.' : 'Nenhuma planilha carregada.';
    $('table-wrap').classList.toggle('hidden', !visible.length);
    if (!visible.length) { $('table').innerHTML = ''; return; }

    const th = (t, extra = '') => `<th class="sticky top-0 bg-card px-3 h-9 text-left font-bold text-mute border-b-2 border-hairline ${extra}">${esc(t)}</th>`;
    const head = '<tr>' + headers.map((h) => th(h)).join('') + th('STATUS', 'text-ash') + th('Obs', 'text-ash') + '</tr>';
    const body = visible.map((r) => '<tr class="border-b border-hairline last:border-0">'
      + headers.map((h) => `<td class="px-3 h-8">${esc(display(h, r[h]))}</td>`).join('')
      + '<td class="px-3 bg-card/60"></td><td class="px-3 bg-card/60"></td></tr>').join('');
    $('table').innerHTML = `<thead>${head}</thead><tbody>${body}</tbody>`;
  }

  async function copy() {
    const lines = visible.map((r) => headers.map((h) => display(h, r[h])));
    const text = lines.map((l) => l.map((c) => c.replace(/[\t\r\n]+/g, ' ')).join('\t')).join('\r\n');
    const html = '<table>' + lines.map((l) => '<tr>' + l.map((c) => `<td>${esc(c)}</td>`).join('') + '</tr>').join('') + '</table>';
    try {
      await navigator.clipboard.write([new ClipboardItem({
        'text/plain': new Blob([text], { type: 'text/plain' }),
        'text/html': new Blob([html], { type: 'text/html' }),
      })]);
    } catch (e) {
      await navigator.clipboard.writeText(text);
    }
    flash($('copy-btn'), 'Copiado!');
  }

  // ExcelJS (~1 MB) só é baixado quando alguém pede o .xlsx.
  function loadExcelJS() {
    if (window.ExcelJS) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = EXCELJS_URL;
      s.onload = resolve;
      s.onerror = () => reject(new Error('Não consegui carregar o gerador de .xlsx.'));
      document.head.appendChild(s);
    });
  }

  async function download() {
    try {
      await loadExcelJS();
    } catch (e) {
      showError(e.message);
      return;
    }
    const now = new Date();
    const wb = new ExcelJS.Workbook();
    const ws = wb.addWorksheet(`${pad(now.getDate())}.${pad(now.getMonth() + 1)}.${now.getFullYear()}`);
    visible.forEach((r) => {
      ws.addRow(headers.map((h) => {
        if (DATE_COLS.includes(h)) {
          const p = parseDate(r[h]);
          return p ? new Date(Date.UTC(p.y, p.m - 1, p.d, p.H, p.M, p.S)) : display(h, r[h]);
        }
        const v = display(h, r[h]);
        return /^\d+$/.test(v) && h !== LAST_COL ? Number(v) : v;
      }).concat(['', '']));
    });
    headers.forEach((h, i) => { if (DATE_COLS.includes(h)) ws.getColumn(i + 1).numFmt = 'dd/mm/yyyy hh:mm:ss'; });
    const statusCol = headers.length + 1;
    ws.getColumn(statusCol).width = 18;
    ws.getColumn(statusCol + 1).width = 40;
    for (let n = 1; n <= visible.length; n++) {
      ws.getCell(n, statusCol).dataValidation = {
        type: 'list', allowBlank: true, formulae: [`"${STATUS_MENU.join(',')}"`],
      };
    }
    const buf = await wb.xlsx.writeBuffer();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([buf], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }));
    a.download = `Batimento ${ws.name}.xlsx`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  function flash(btn, msg) {
    const original = btn.textContent;
    btn.textContent = msg;
    setTimeout(() => { btn.textContent = original; }, 1500);
  }

  // ── Eventos ────────────────────────────────────────────────────────────────

  $('f-file').addEventListener('change', (e) => { if (e.target.files[0]) load(e.target.files[0]); });
  const drop = $('drop');
  ['dragenter', 'dragover'].forEach((ev) => drop.addEventListener(ev, (e) => {
    e.preventDefault();
    drop.classList.add('border-brand-yellow');
  }));
  ['dragleave', 'drop'].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove('border-brand-yellow')));
  drop.addEventListener('drop', (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) load(file);
  });
  $('filters').addEventListener('change', render);
  $('g-period').addEventListener('input', (e) => {
    const st = e.target.dataset.days;
    if (st == null) return;
    days[st] = +e.target.value;
    document.querySelector(`[data-days-label="${CSS.escape(st)}"]`).textContent = daysLabel(days[st]);
    render();
  });
  $('copy-btn').addEventListener('click', copy);
  $('download-btn').addEventListener('click', download);
})();
