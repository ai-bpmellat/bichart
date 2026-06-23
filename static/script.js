/* script.js — PSP BI Conversational Report Builder (vanilla JS, no frameworks) */

const state = {
  language: 'fa',  // 'fa' (Persian) or 'en' — controls AI response language
};

const langToggleBtn = document.getElementById('lang-toggle-btn');
const chatArea = document.getElementById('chat-area');
const welcomeBlock = document.getElementById('welcome-block');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');

window.addEventListener('DOMContentLoaded', () => {
  langToggleBtn.textContent = state.language.toUpperCase();
  messageInput.focus();
});

langToggleBtn.addEventListener('click', toggleLanguage);

sendBtn.addEventListener('click', sendMessage);
messageInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
messageInput.addEventListener('input', () => {
  messageInput.style.height = 'auto';
  messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
  messageInput.dir = isRtlText(messageInput.value) ? 'rtl' : 'ltr';
});

function toggleLanguage() {
  state.language = state.language === 'fa' ? 'en' : 'fa';
  langToggleBtn.textContent = state.language.toUpperCase();
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------
async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text) return;

  welcomeBlock.remove();

  const turn = document.createElement('div');
  turn.className = 'turn';
  turn.innerHTML = `
    <div class="user-line"><div class="user-bubble"${dirAttr(text)}>${escapeHtml(text)}</div></div>
    <div class="strip loading-strip-holder"></div>
  `;
  chatArea.appendChild(turn);

  const loadingHolder = turn.querySelector('.loading-strip-holder');
  loadingHolder.classList.remove('strip');
  loadingHolder.innerHTML = `
    <div class="loading-strip">
      <span class="dot-pulse"></span><span class="dot-pulse"></span><span class="dot-pulse"></span>
      <span>Generating SQL and running your report…</span>
    </div>
  `;

  messageInput.value = '';
  messageInput.style.height = 'auto';
  sendBtn.disabled = true;
  chatArea.scrollTop = chatArea.scrollHeight;

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, language: state.language }),
    });
    const json = await res.json();

    if (!res.ok) {
      renderError(loadingHolder, json, text);
      return;
    }
    renderResult(loadingHolder, json, text);
  } catch (e) {
    renderError(loadingHolder, { error: 'Network error reaching the server.' }, text);
  } finally {
    sendBtn.disabled = false;
    chatArea.scrollTop = chatArea.scrollHeight;
  }
}

function renderError(container, json, originalQuestion) {
  container.innerHTML = `
    <div class="strip">
      <div class="strip-section">
        <div class="strip-label">Error</div>
        <div class="error-strip">${escapeHtml(json.error || 'Something went wrong.')}</div>
      </div>
      ${json.sql ? `
      <div class="strip-section">
        <div class="strip-label">Attempted SQL</div>
        <div class="sql-block visible">${escapeHtml(json.sql)}</div>
      </div>` : ''}
    </div>
  `;
}

function renderResult(container, json, originalQuestion) {
  const { sql, explanation, data, row_count, analysis } = json;
  const stripId = 'strip-' + Math.random().toString(36).slice(2, 9);

  container.innerHTML = `
    <div class="strip" id="${stripId}">
      <div class="strip-section">
        <div class="strip-label sql-toggle">
          <span><span class="chevron">▸</span> Generated SQL</span>
        </div>
        <div class="sql-block" dir="ltr">${escapeHtml(sql)}</div>
        ${explanation ? `<div class="sql-explanation"${dirAttr(explanation)}>${escapeHtml(explanation)}</div>` : ''}
      </div>
      <div class="strip-section">
        <div class="strip-label">Result</div>
        <div class="data-table-wrap"></div>
        <div class="row-count">${row_count} row${row_count === 1 ? '' : 's'} returned</div>
        <div class="chart-wrap"></div>
      </div>
      <div class="strip-section">
        <div class="strip-label">Analysis &amp; prediction</div>
        <div class="analysis-text"${dirAttr(analysis)}>${escapeHtml(analysis).replace(/\n/g, '<br>')}</div>
      </div>
    </div>
  `;

  const stripEl = document.getElementById(stripId);
  const toggle = stripEl.querySelector('.sql-toggle');
  const sqlBlock = stripEl.querySelector('.sql-block');
  toggle.addEventListener('click', () => {
    toggle.classList.toggle('open');
    sqlBlock.classList.toggle('visible');
  });

  mountPaginatedTable(stripEl.querySelector('.data-table-wrap'), data || []);

  const chartWrap = stripEl.querySelector('.chart-wrap');
  maybeRenderChart(chartWrap, data);
}

const TABLE_PAGE_SIZES = [50, 100, 250, 500, 1000];
const DEFAULT_TABLE_PAGE_SIZE = 250;

const COLUMN_LABELS = {
  category: 'دسته\u200cبندی',
  category_id: 'شناسه دسته\u200cبندی',
  category_name: 'دسته\u200cبندی',
  merchant_name: 'نام پذیرنده',
  customer_name: 'نام مشتری',
  city: 'شهر',
  channel: 'کانال',
  status: 'وضعیت',
  amount: 'مبلغ',
  transaction_count: 'تعداد تراکنش',
  total_amount: 'مجموع مبلغ',
  full_date: 'تاریخ',
  terminal_serial: 'سریال ترمینال',
  merchant_code: 'کد پذیرنده',
};

function columnLabel(key) {
  return COLUMN_LABELS[key] || key;
}

function buildTableHtml(rows) {
  if (!rows || rows.length === 0) {
    return '<div style="color:var(--ink-soft);font-size:13px;padding:12px;">No rows returned.</div>';
  }
  const cols = Object.keys(rows[0]);
  const headerRow = cols
    .map((c) => {
      const label = columnLabel(c);
      return `<th${dirAttr(label)}>${escapeHtml(label)}</th>`;
    })
    .join('');
  const bodyRows = rows
    .map((row) =>
      `<tr>${cols
        .map((c) => {
          const text = formatCell(row[c]);
          return `<td${dirAttr(text)}>${escapeHtml(text)}</td>`;
        })
        .join('')}</tr>`
    )
    .join('');
  return `<table class="data-table"><thead><tr>${headerRow}</tr></thead><tbody>${bodyRows}</tbody></table>`;
}

function mountPaginatedTable(container, data) {
  if (!data || data.length === 0) {
    container.innerHTML = buildTableHtml([]);
    return;
  }

  let page = 1;
  let pageSize = DEFAULT_TABLE_PAGE_SIZE;

  function render() {
    const total = data.length;
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    if (page > totalPages) page = totalPages;
    const start = (page - 1) * pageSize;
    const pageRows = data.slice(start, start + pageSize);
    const end = start + pageRows.length;

    const sizeOptions = TABLE_PAGE_SIZES.map(
      (n) => `<option value="${n}"${n === pageSize ? ' selected' : ''}>${n}</option>`
    ).join('');

    container.innerHTML = `
      <div class="table-toolbar">
        <span class="table-range">Rows ${start + 1}–${end} of ${total.toLocaleString()}</span>
        <label class="table-page-size">Per page
          <select class="table-page-size-select">${sizeOptions}</select>
        </label>
        <div class="table-pager">
          <button type="button" class="table-prev" ${page <= 1 ? 'disabled' : ''}>Prev</button>
          <span>Page ${page} / ${totalPages}</span>
          <button type="button" class="table-next" ${page >= totalPages ? 'disabled' : ''}>Next</button>
        </div>
      </div>
      <div class="data-table-scroll">${buildTableHtml(pageRows)}</div>
    `;

    container.querySelector('.table-page-size-select').addEventListener('change', (e) => {
      pageSize = Number(e.target.value);
      page = 1;
      render();
    });
    container.querySelector('.table-prev').addEventListener('click', () => {
      if (page > 1) {
        page -= 1;
        render();
      }
    });
    container.querySelector('.table-next').addEventListener('click', () => {
      if (page < totalPages) {
        page += 1;
        render();
      }
    });
  }

  render();
}

function buildTable(data) {
  return buildTableHtml(data);
}

function formatCell(val) {
  if (val === null || val === undefined) return '';
  if (typeof val === 'number') {
    return Number.isInteger(val) ? val.toLocaleString() : val.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  return String(val);
}

// ---------------------------------------------------------------------------
// Minimal canvas bar chart — no chart library, per the "vanilla JS" brief.
// Renders only when there's an obvious (label, numeric) column pair, e.g.
// merchant_name + total, or day + amount. Skips silently otherwise.
// ---------------------------------------------------------------------------
function maybeRenderChart(container, data) {
  if (!data || data.length < 2 || data.length > 50) return;

  const cols = Object.keys(data[0]);
  const numericCol = cols.find((c) => typeof data[0][c] === 'number' && !/_id$|^id$/i.test(c));
  const labelCol = cols.find((c) => c !== numericCol && typeof data[0][c] !== 'number');

  if (!numericCol || !labelCol) return;

  const values = data.map((r) => Number(r[numericCol]) || 0);
  const labels = data.map((r) => String(r[labelCol]));
  const max = Math.max(...values, 1);

  const barHeight = 22;
  const gap = 8;
  const valuePad = 72;
  const barAreaMin = 180;
  const height = data.length * (barHeight + gap) + 10;

  const canvas = document.createElement('canvas');
  canvas.style.maxWidth = '100%';
  container.appendChild(canvas);

  const ctx = canvas.getContext('2d');
  const labelFont = labels.some(isRtlText)
    ? '11px "IBM Plex Sans Arabic", Tahoma, sans-serif'
    : '11px "IBM Plex Mono", monospace';
  ctx.font = labelFont;
  ctx.textBaseline = 'middle';

  const maxLabelWidth = Math.max(...labels.map((l) => ctx.measureText(l).width), 0);
  const leftPad = Math.ceil(maxLabelWidth) + 16;
  const width = Math.max(680, leftPad + barAreaMin + valuePad);
  canvas.width = width;
  canvas.height = height;
  const barAreaWidth = width - leftPad - valuePad;

  data.forEach((_, i) => {
    const y = i * (barHeight + gap) + 5;
    const barWidth = (barAreaWidth * values[i]) / max;

    // label — full text, no truncation
    ctx.fillStyle = '#5b6168';
    ctx.font = isRtlText(labels[i]) ? labelFont : '11px "IBM Plex Mono", monospace';
    ctx.fillText(labels[i], 0, y + barHeight / 2);

    // bar
    ctx.fillStyle = '#1f6f54';
    ctx.fillRect(leftPad, y, Math.max(barWidth, 2), barHeight);

    // value
    ctx.font = '11px "IBM Plex Mono", monospace';
    ctx.fillStyle = '#1c2024';
    ctx.fillText(
      values[i].toLocaleString(undefined, { maximumFractionDigits: 0 }),
      leftPad + barWidth + 8,
      y + barHeight / 2
    );
  });
}

// ---------------------------------------------------------------------------
// Utils
// ---------------------------------------------------------------------------
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  const div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
}

// Detects Persian/Arabic script so we can apply RTL direction only to the
// text blocks that actually need it (user question, explanation, analysis),
// while SQL, column headers, and numbers stay LTR.
const RTL_SCRIPT_RE = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/;
function isRtlText(str) {
  if (!str) return false;
  return RTL_SCRIPT_RE.test(str);
}
function dirAttr(str) {
  return isRtlText(str) ? ' dir="rtl"' : ' dir="ltr"';
}
