/* script.js — PSP BI Conversational Report Builder (vanilla JS, no frameworks) */

const state = {
  customer: null,       // { customer_id, customer_name, role }
  accessKey: null,
  language: 'fa',        // 'fa' (Persian) or 'en' — controls AI response language
};

// ---------------------------------------------------------------------------
// DOM refs
// ---------------------------------------------------------------------------
const loginGate = document.getElementById('login-gate');
const mainApp = document.getElementById('main-app');
const accessKeyInput = document.getElementById('access-key-input');
const loginBtn = document.getElementById('login-btn');
const loginError = document.getElementById('login-error');
const demoKeysList = document.getElementById('demo-keys-list');
const customerNameLabel = document.getElementById('customer-name-label');
const logoutBtn = document.getElementById('logout-btn');
const langToggleBtn = document.getElementById('lang-toggle-btn');
const chatArea = document.getElementById('chat-area');
const welcomeBlock = document.getElementById('welcome-block');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
window.addEventListener('DOMContentLoaded', () => {
  loadDemoKeys();
  const saved = sessionStorage.getItem('psp_bi_access_key');
  if (saved) {
    attemptLogin(saved);
  }
});

loginBtn.addEventListener('click', () => attemptLogin(accessKeyInput.value.trim()));
accessKeyInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') attemptLogin(accessKeyInput.value.trim());
});
logoutBtn.addEventListener('click', logout);
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
// Auth
// ---------------------------------------------------------------------------
async function loadDemoKeys() {
  try {
    const res = await fetch('/api/customers');
    const json = await res.json();
    demoKeysList.innerHTML = '';
    json.customers.forEach((c) => {
      const item = document.createElement('div');
      item.className = 'demo-key-item';
      item.innerHTML = `
        <span class="dk-name"${dirAttr(c.customer_name)}>${escapeHtml(c.customer_name)}<span class="dk-role">${c.role}</span></span>
        <span class="dk-key">${c.access_key}</span>
      `;
      item.addEventListener('click', () => {
        accessKeyInput.value = c.access_key;
      });
      demoKeysList.appendChild(item);
    });
  } catch (e) {
    demoKeysList.innerHTML = '<span style="color:#a13d2f;font-size:12px;">Could not load demo accounts — is the server running?</span>';
  }
}

async function attemptLogin(key) {
  if (!key) {
    showLoginError('Please enter an access key.');
    return;
  }
  loginBtn.disabled = true;
  loginBtn.textContent = 'Signing in…';
  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ access_key: key }),
    });
    const json = await res.json();
    if (!res.ok) {
      showLoginError(json.error || 'Invalid access key.');
      return;
    }
    state.customer = json.customer;
    state.accessKey = key;
    sessionStorage.setItem('psp_bi_access_key', key);
    enterApp();
  } catch (e) {
    showLoginError('Could not reach the server. Is the backend running?');
  } finally {
    loginBtn.disabled = false;
    loginBtn.textContent = 'Sign in';
  }
}

function showLoginError(msg) {
  loginError.textContent = msg;
  loginError.hidden = false;
}

function logout() {
  state.customer = null;
  state.accessKey = null;
  sessionStorage.removeItem('psp_bi_access_key');
  chatArea.innerHTML = '';
  chatArea.appendChild(welcomeBlock);
  mainApp.hidden = true;
  loginGate.hidden = false;
  accessKeyInput.value = '';
}

function enterApp() {
  loginGate.hidden = true;
  mainApp.hidden = false;
  customerNameLabel.textContent = `${state.customer.customer_name} · ${state.customer.role}`;
  customerNameLabel.dir = isRtlText(state.customer.customer_name) ? 'rtl' : 'ltr';
  langToggleBtn.textContent = state.language.toUpperCase();
  messageInput.focus();
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
      body: JSON.stringify({ message: text, access_key: state.accessKey, language: state.language }),
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
        <div class="data-table-wrap">${buildTable(data)}</div>
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

  // Try to render a simple chart if the data looks chartable
  const chartWrap = stripEl.querySelector('.chart-wrap');
  maybeRenderChart(chartWrap, data);
}

function buildTable(data) {
  if (!data || data.length === 0) {
    return '<div style="color:var(--ink-soft);font-size:13px;padding:8px 0;">No rows returned.</div>';
  }
  const cols = Object.keys(data[0]);
  const headerRow = cols.map((c) => `<th>${escapeHtml(c)}</th>`).join('');
  // Rendering every row as a raw <tr> works but gets sluggish well past a
  // few thousand DOM nodes, so the table itself displays up to DISPLAY_ROW_CAP
  // rows while the full result set (up to sql_safety.MAX_ROWS on the backend)
  // is still used for the row-count badge and available in `data` for charts.
  const DISPLAY_ROW_CAP = 2000;
  const bodyRows = data
    .slice(0, DISPLAY_ROW_CAP)
    .map((row) => `<tr>${cols.map((c) => `<td>${escapeHtml(formatCell(row[c]))}</td>`).join('')}</tr>`)
    .join('');
  const truncationNote = data.length > DISPLAY_ROW_CAP
    ? `<div style="color:var(--ink-soft);font-size:11.5px;padding:6px 0 0;">Showing first ${DISPLAY_ROW_CAP.toLocaleString()} of ${data.length.toLocaleString()} rows.</div>`
    : '';
  return `<table class="data-table"><thead><tr>${headerRow}</tr></thead><tbody>${bodyRows}</tbody></table>${truncationNote}`;
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
  if (!data || data.length < 2 || data.length > 30) return;

  const cols = Object.keys(data[0]);
  const numericCol = cols.find((c) => typeof data[0][c] === 'number' && !/_id$|^id$/i.test(c));
  const labelCol = cols.find((c) => c !== numericCol && typeof data[0][c] !== 'number');

  if (!numericCol || !labelCol) return;

  const values = data.map((r) => Number(r[numericCol]) || 0);
  const labels = data.map((r) => String(r[labelCol]));
  const max = Math.max(...values, 1);

  const width = 680;
  const barHeight = 22;
  const gap = 8;
  const leftPad = 140;
  const height = data.length * (barHeight + gap) + 10;

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  canvas.style.maxWidth = '100%';
  container.appendChild(canvas);

  const ctx = canvas.getContext('2d');
  ctx.font = '11px "IBM Plex Mono", monospace';
  ctx.textBaseline = 'middle';

  data.forEach((_, i) => {
    const y = i * (barHeight + gap) + 5;
    const barWidth = ((width - leftPad - 60) * values[i]) / max;

    // label
    ctx.fillStyle = '#5b6168';
    const label = labels[i].length > 18 ? labels[i].slice(0, 17) + '…' : labels[i];
    ctx.fillText(label, 0, y + barHeight / 2);

    // bar
    ctx.fillStyle = '#1f6f54';
    ctx.fillRect(leftPad, y, Math.max(barWidth, 2), barHeight);

    // value
    ctx.fillStyle = '#1c2024';
    ctx.fillText(values[i].toLocaleString(undefined, { maximumFractionDigits: 0 }), leftPad + barWidth + 8, y + barHeight / 2);
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