/* script.js — PSP BI Conversational Report Builder (vanilla JS, no frameworks) */

const state = {
  language: 'fa',  // 'fa' (Persian) or 'en' — controls AI response language
  provider: 'avalai',  // default AvalAI; persisted per user on server
  username: null,
};

const langToggleBtn = document.getElementById('lang-toggle-btn');
const logoutBtn = document.getElementById('logout-btn');
const usersMgmtBtn = document.getElementById('users-mgmt-btn');
const providerOllamaBtn = document.getElementById('provider-ollama-btn');
const providerAvalaiBtn = document.getElementById('provider-avalai-btn');
const chatArea = document.getElementById('chat-area');
const welcomeBlock = document.getElementById('welcome-block');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const historyList = document.getElementById('history-list');
const historyEmpty = document.getElementById('history-empty');
const historyRefreshBtn = document.getElementById('history-refresh-btn');
const settingsModelBtn = document.getElementById('settings-model-btn');
const settingsLangBtn = document.getElementById('settings-lang-btn');
const settingsModelValue = document.getElementById('settings-model-value');
const settingsLangValue = document.getElementById('settings-lang-value');
const sidebarCollapseBtn = document.getElementById('sidebar-collapse-btn');
const dashboardBody = document.querySelector('.dashboard-body');

window.addEventListener('DOMContentLoaded', async () => {
  if (typeof Chart !== 'undefined') {
    Chart.defaults.font.family = chartFontFamily();
    Chart.defaults.color = '#1c2024';
  }
  messageInput.focus();

  try {
    const res = await apiFetch('/api/me');
    const me = await res.json();
    state.username = me.username || null;
    if (me.role === 'admin' && usersMgmtBtn) {
      usersMgmtBtn.hidden = false;
    }
    const prefs = me.preferences || {};
    if (prefs.provider === 'ollama' || prefs.provider === 'avalai') {
      state.provider = prefs.provider;
    }
    if (prefs.language === 'fa' || prefs.language === 'en') {
      state.language = prefs.language;
    }
  } catch (_) {
    /* redirected on 401 */
  }

  applyProviderUI(state.provider);
  applyLanguageUI(state.language);
  await loadHistorySidebar();
});

langToggleBtn.addEventListener('click', () => toggleLanguage(true));
logoutBtn.addEventListener('click', logout);
providerOllamaBtn.addEventListener('click', () => setProvider('ollama', true));
providerAvalaiBtn.addEventListener('click', () => setProvider('avalai', true));
if (settingsModelBtn) {
  settingsModelBtn.addEventListener('click', () => {
    setProvider(state.provider === 'avalai' ? 'ollama' : 'avalai', true);
  });
}
if (settingsLangBtn) {
  settingsLangBtn.addEventListener('click', () => toggleLanguage(true));
}
if (historyRefreshBtn) {
  historyRefreshBtn.addEventListener('click', () => loadHistorySidebar());
}
if (sidebarCollapseBtn && dashboardBody) {
  sidebarCollapseBtn.addEventListener('click', () => {
    dashboardBody.classList.toggle('sidebar-collapsed');
    sidebarCollapseBtn.textContent = dashboardBody.classList.contains('sidebar-collapsed') ? '»' : '«';
  });
}

document.querySelectorAll('.quick-tile').forEach((btn) => {
  btn.addEventListener('click', () => {
    const q = btn.getAttribute('data-q');
    if (!q) return;
    messageInput.value = q;
    messageInput.dir = isRtlText(q) ? 'rtl' : 'ltr';
    sendMessage();
  });
});

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

function applyLanguageUI(language) {
  state.language = language;
  langToggleBtn.textContent = state.language.toUpperCase();
  if (settingsLangValue) {
    settingsLangValue.textContent = `${state.language.toUpperCase()} ›`;
  }
  if (typeof Chart !== 'undefined') {
    Chart.defaults.font.family = chartFontFamily();
  }
}

function applyProviderUI(provider) {
  state.provider = provider;
  providerOllamaBtn.classList.toggle('is-active', provider === 'ollama');
  providerAvalaiBtn.classList.toggle('is-active', provider === 'avalai');
  if (settingsModelValue) {
    settingsModelValue.textContent = `${providerLabel()} ›`;
  }
  refreshAvalaiCredit();
}

function toggleLanguage(persist) {
  applyLanguageUI(state.language === 'fa' ? 'en' : 'fa');
  if (persist) savePreferences();
}

async function apiFetch(url, options) {
  const res = await fetch(url, options);
  if (res.status === 401) {
    window.location.href = '/login';
    throw new Error('unauthorized');
  }
  return res;
}

async function logout() {
  try {
    await fetch('/api/logout', { method: 'POST' });
  } catch (_) {
    /* redirect anyway */
  }
  window.location.href = '/login';
}

function setProvider(provider, persist) {
  applyProviderUI(provider);
  if (persist) savePreferences();
}

async function savePreferences() {
  try {
    await apiFetch('/api/preferences', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider: state.provider,
        language: state.language,
      }),
    });
  } catch (_) {
    /* non-fatal */
  }
}

function providerLabel() {
  return state.provider === 'avalai' ? 'AvalAI' : 'Ollama';
}

function formatHistoryTime(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleString(state.language === 'fa' ? 'fa-IR' : 'en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      day: '2-digit',
      month: 'short',
    });
  } catch (_) {
    return iso;
  }
}

async function loadHistorySidebar() {
  if (!historyList) return;
  try {
    const res = await apiFetch('/api/history');
    const json = await res.json();
    const items = (json.history || []).slice().reverse();
    historyList.querySelectorAll('.history-item').forEach((el) => el.remove());
    if (!items.length) {
      if (historyEmpty) historyEmpty.hidden = false;
      return;
    }
    if (historyEmpty) historyEmpty.hidden = true;
    items.forEach((entry) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'history-item';
      const q = entry.user_question || '';
      btn.innerHTML = `
        <div class="history-q">${escapeHtml(q)}</div>
        <div class="history-meta">${escapeHtml(formatHistoryTime(entry.timestamp))}${entry.provider ? ' · ' + escapeHtml(entry.provider) : ''}</div>
      `;
      btn.addEventListener('click', () => {
        messageInput.value = q;
        messageInput.dir = isRtlText(q) ? 'rtl' : 'ltr';
        messageInput.focus();
      });
      historyList.appendChild(btn);
    });
  } catch (_) {
    /* ignore */
  }
}

async function refreshAvalaiCredit() {
  const existing = document.getElementById('provider-credit-label');
  if (existing) existing.remove();
  if (state.provider !== 'avalai' || !providerAvalaiBtn) return;
  try {
    const res = await apiFetch('/api/avalai/credit');
    const json = await res.json();
    if (!res.ok) return;
    const label = document.createElement('span');
    label.id = 'provider-credit-label';
    label.className = 'provider-credit';
    const balance = json.credit ?? json.balance ?? json.remaining ?? JSON.stringify(json);
    label.textContent = state.language === 'fa' ? `اعتبار: ${balance}` : `Credit: ${balance}`;
    label.title = typeof balance === 'object' ? JSON.stringify(json) : String(balance);
    providerAvalaiBtn.parentElement.appendChild(label);
  } catch (_) {
    /* credit display is optional */
  }
}

function chatUiText(key) {
  const provider = providerLabel();
  const fa = {
    loadingReport: `در حال تولید SQL و اجرای گزارش با ${provider}…`,
    analysisTitle: 'تحلیل و پیش\u200cبینی',
    analyzeBtn: 'تحلیل نتایج',
    analyzing: `در حال تحلیل با ${provider}…`,
    analyzePrompt: 'برای تحلیل هوشمند نتایج، روی دکمه زیر کلیک کنید.',
    analyzeAgain: 'تحلیل مجدد',
  };
  const en = {
    loadingReport: `Generating SQL and running your report with ${provider}…`,
    analysisTitle: 'Analysis & prediction',
    analyzeBtn: 'Analyze results',
    analyzing: `Analyzing with ${provider}…`,
    analyzePrompt: 'Click the button below for AI analysis of these results.',
    analyzeAgain: 'Re-analyze',
  };
  const t = state.language === 'fa' ? fa : en;
  return t[key];
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------
async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text) return;

  if (welcomeBlock && welcomeBlock.isConnected) welcomeBlock.remove();

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
      <span>${escapeHtml(chatUiText('loadingReport'))}</span>
    </div>
  `;

  messageInput.value = '';
  messageInput.style.height = 'auto';
  sendBtn.disabled = true;
  chatArea.scrollTop = chatArea.scrollHeight;

  try {
    const res = await apiFetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, language: state.language, provider: state.provider }),
    });
    let json;
    try {
      json = await res.json();
    } catch (_) {
      renderError(loadingHolder, { error: `Server error (${res.status}). Check server logs.` }, text);
      return;
    }

    if (!res.ok) {
      renderError(loadingHolder, json, text);
      return;
    }
    renderResult(loadingHolder, json, text);
    loadHistorySidebar();
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
      ${json.timings ? renderTimingsSection(json.timings) : ''}
      ${json.sql ? `
      <div class="strip-section">
        <div class="strip-label">Attempted SQL</div>
        <div class="sql-block visible">${escapeHtml(json.sql)}</div>
      </div>` : ''}
    </div>
  `;
}

const TIMING_STEPS = [
  { key: 'sql_generation', labelFa: 'تولید SQL', labelEn: 'SQL generation' },
  { key: 'sql_normalize', labelFa: 'نرمال\u200cسازی SQL', labelEn: 'SQL normalization' },
  { key: 'sql_safety', labelFa: 'بررسی امنیت SQL', labelEn: 'SQL safety check' },
  { key: 'sql_execution', labelFa: 'اجرای پایگاه\u200cداده', labelEn: 'Database execution' },
  { key: 'memory_save', labelFa: 'ذخیره حافظه', labelEn: 'Memory save' },
  { key: 'analysis', labelFa: 'تحلیل', labelEn: 'Analysis' },
  { key: 'total', labelFa: 'مجموع', labelEn: 'Total' },
];

function timingsUiText(key) {
  const fa = { sectionTitle: 'زمان\u200cبندی سرویس\u200cها' };
  const en = { sectionTitle: 'Service timings' };
  const t = state.language === 'fa' ? fa : en;
  return t[key];
}

function formatMs(ms) {
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)} s`;
  return `${Number(ms).toFixed(1)} ms`;
}

function renderTimingsSection(timings) {
  if (!timings || typeof timings !== 'object') return '';

  const rows = TIMING_STEPS.filter((s) => timings[s.key] !== undefined).map((s) => {
    const label = state.language === 'fa' ? s.labelFa : s.labelEn;
    const ms = timings[s.key];
    const isTotal = s.key === 'total';
    const pct = !isTotal && timings.total ? Math.min(100, (ms / timings.total) * 100) : null;
    return `
      <div class="timing-row${isTotal ? ' timing-row--total' : ''}">
        <span class="timing-label"${dirAttr(label)}>${escapeHtml(label)}</span>
        <span class="timing-bar-wrap">
          ${pct !== null ? `<span class="timing-bar" style="width:${pct.toFixed(1)}%"></span>` : ''}
        </span>
        <span class="timing-value">${escapeHtml(formatMs(ms))}</span>
      </div>
    `;
  }).join('');

  const title = timingsUiText('sectionTitle');
  return `
    <div class="strip-section">
      <div class="strip-label"${dirAttr(title)}>${escapeHtml(title)}</div>
      <div class="timings-panel"${dirAttr(title)}>${rows}</div>
    </div>
  `;
}

function renderResult(container, json, originalQuestion) {
  const { sql, explanation, data, row_count, timings } = json;
  const language = json.language || state.language;
  const stripId = 'strip-' + Math.random().toString(36).slice(2, 9);
  const analysisTitle = chatUiText('analysisTitle');

  container.innerHTML = `
    <div class="strip" id="${stripId}">
      ${renderTimingsSection(timings)}
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
      <div class="strip-section analysis-section">
        <div class="analysis-header">
          <div class="analysis-title-wrap">
            <span class="analysis-icon" aria-hidden="true">◆</span>
            <div class="strip-label analysis-label"${dirAttr(analysisTitle)}>${escapeHtml(analysisTitle)}</div>
          </div>
          <button type="button" class="analyze-btn primary-btn">${escapeHtml(chatUiText('analyzeBtn'))}</button>
        </div>
        <div class="analysis-body-card">
          <div class="analysis-placeholder analysis-state-msg"${dirAttr(chatUiText('analyzePrompt'))}>${escapeHtml(chatUiText('analyzePrompt'))}</div>
          <div class="analysis-text" hidden></div>
        </div>
        <div class="analysis-timings"></div>
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

  const analyzeBtn = stripEl.querySelector('.analyze-btn');
  const resultProvider = json.provider || state.provider;
  analyzeBtn.addEventListener('click', () => {
    requestAnalysis(stripEl, originalQuestion, data || [], language, analyzeBtn, resultProvider);
  });
}

async function requestAnalysis(stripEl, question, data, language, btn, provider) {
  const placeholder = stripEl.querySelector('.analysis-placeholder');
  const textEl = stripEl.querySelector('.analysis-text');
  const timingsEl = stripEl.querySelector('.analysis-timings');
  const hadAnalysis = !textEl.hidden && textEl.textContent.trim();

  btn.disabled = true;
  btn.textContent = chatUiText('analyzing');
  placeholder.hidden = false;
  placeholder.className = 'analysis-placeholder analysis-state-msg analysis-loading';
  placeholder.textContent = chatUiText('analyzing');
  textEl.hidden = true;

  try {
    const res = await apiFetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: question,
        data: data.slice(0, 20),
        language,
        provider: provider || state.provider,
      }),
    });
    const json = await res.json();

    if (!res.ok) {
      placeholder.hidden = false;
      placeholder.className = 'analysis-placeholder analysis-state-msg analysis-error';
      placeholder.textContent = json.error || 'Analysis failed.';
      timingsEl.innerHTML = json.timings ? renderTimingsSection(json.timings) : '';
      return;
    }

    placeholder.hidden = true;
    textEl.hidden = false;
    textEl.className = 'analysis-text analysis-text--ready';
    textEl.setAttribute('dir', isRtlText(json.analysis) ? 'rtl' : 'ltr');
    textEl.innerHTML = formatAnalysisHtml(json.analysis);
    timingsEl.innerHTML = json.timings ? renderTimingsSection(json.timings) : '';
    btn.textContent = chatUiText('analyzeAgain');
  } catch (e) {
    placeholder.hidden = false;
    placeholder.className = 'analysis-placeholder analysis-state-msg analysis-error';
    placeholder.textContent = state.language === 'fa'
      ? 'خطا در ارتباط با سرور برای تحلیل.'
      : 'Network error during analysis.';
  } finally {
    btn.disabled = false;
    if (!hadAnalysis && textEl.hidden) {
      btn.textContent = chatUiText('analyzeBtn');
    }
  }
}

const TABLE_PAGE_SIZES = [50, 100, 250, 500, 1000];
const DEFAULT_TABLE_PAGE_SIZE = 250;

const COLUMN_LABELS = {
  category: 'دسته\u200cبندی',
  category_id: 'شناسه دسته\u200cبندی',
  category_name: 'نام دسته\u200cبندی',
  merchant_name: 'نام پذیرنده',
  merchant_id: 'شناسه پذیرنده',
  customer_name: 'نام مشتری',
  city: 'شهر',
  channel: 'کانال',
  status: 'وضعیت',
  amount: 'مبلغ',
  transaction_count: 'تعداد تراکنش',
  total_amount: 'مجموع مبلغ',
  total_sales: 'مجموع فروش',
  total_volume: 'مجموع حجم تراکنش',
  full_date: 'تاریخ',
  transaction_month: 'ماه تراکنش',
  terminal_serial: 'سریال ترمینال',
  merchant_code: 'کد پذیرنده',
  avg_growth: 'میانگین نرخ رشد',
  growth_rate: 'نرخ رشد',
  row_count: 'تعداد ردیف',
};

function columnLabel(key) {
  if (!key) return '';
  if (COLUMN_LABELS[key]) return COLUMN_LABELS[key];
  // Keep Persian SQL aliases and quoted headers as-is (full name, not shortened).
  if (isRtlText(key) || key.includes('\u200c')) return key;
  return key.replace(/_/g, ' ');
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
// Professional charts (Chart.js) — type selector, Persian labels, full names
// ---------------------------------------------------------------------------
const CHART_MAX_ITEMS = 25;
const CHART_PALETTE = [
  '#1f6f54', '#2d8f6f', '#3aaf88', '#4ec4a0', '#c45c26',
  '#d4842d', '#e8a84b', '#5b7cfa', '#7c5cfc', '#9b6bff',
  '#a13d2f', '#c75545', '#6b5b95', '#8b7ab8', '#88b04b',
  '#6d9a3c', '#2a9d8f', '#264653', '#e76f51', '#f4a261',
];

const CHART_TYPE_OPTIONS = [
  { id: 'bar', labelFa: 'میله\u200cای عمودی', labelEn: 'Vertical bar' },
  { id: 'barHorizontal', labelFa: 'میله\u200cای افقی', labelEn: 'Horizontal bar' },
  { id: 'line', labelFa: 'خطی', labelEn: 'Line' },
  { id: 'pie', labelFa: 'دایره\u200cای (پای)', labelEn: 'Pie' },
  { id: 'doughnut', labelFa: 'حلقه\u200cای', labelEn: 'Doughnut' },
];

function chartUiText(key) {
  const fa = {
    chartType: 'نوع نمودار',
    showingTop: (n, total) => `نمایش ${n} مورد از ${total} (مرتب\u200cشده بر اساس مقدار)`,
    allRows: (n) => `نمایش ${n} مورد`,
    noChart: 'نمودار برای این داده در دسترس نیست.',
    noRows: 'داده\u200cای برای نمودار وجود ندارد.',
    chartLibMissing: 'کتابخانه نمودار بارگذاری نشد. اتصال اینترنت را بررسی کنید.',
    noColumns: 'ستون متنی (برچسب) و عددی (مقدار) برای رسم نمودار پیدا نشد.',
    labelColumn: 'ستون برچسب',
    valueColumn: 'ستون مقدار',
  };
  const en = {
    chartType: 'Chart type',
    showingTop: (n, total) => `Showing top ${n} of ${total} (sorted by value)`,
    allRows: (n) => `Showing ${n} items`,
    noChart: 'Chart not available for this data.',
    noRows: 'No data available for chart.',
    chartLibMissing: 'Chart library failed to load. Check your internet connection.',
    noColumns: 'Could not find a text label column and numeric value column to chart.',
    labelColumn: 'Label column',
    valueColumn: 'Value column',
  };
  const t = state.language === 'fa' ? fa : en;
  return typeof t[key] === 'function' ? t[key] : t[key];
}

function isNumericValue(val) {
  if (val === null || val === undefined || val === '') return false;
  if (typeof val === 'number' && Number.isFinite(val)) return true;
  if (typeof val === 'string' && val.trim() !== '' && !Number.isNaN(Number(val))) return true;
  return false;
}

function toNumeric(val) {
  return Number(val) || 0;
}

function isIdLikeColumn(name) {
  return /_id$|^id$/i.test(name) || /date_key/i.test(name);
}

function pickNumericColumn(cols, row) {
  const numeric = cols.filter((c) => isNumericValue(row[c]) && !isIdLikeColumn(c));
  if (!numeric.length) return null;
  const priority = /total|sum|amount|count|sales|volume|growth|مبلغ|تعداد|مجموع|رشد|فروش/i;
  return numeric.find((c) => priority.test(c)) || numeric[0];
}

function pickLabelColumn(cols, row, numericCol) {
  const textCols = cols.filter(
    (c) => c !== numericCol && !isNumericValue(row[c])
  );
  if (!textCols.length) return null;
  const priority = /name|category|merchant|city|channel|date|month|صنف|پذیرنده|دسته|شهر|ماه|تاریخ/i;
  return textCols.find((c) => priority.test(c)) || textCols[0];
}

function chartFontFamily() {
  return state.language === 'fa'
    ? '"IBM Plex Sans Arabic", Tahoma, "Segoe UI", sans-serif'
    : '"IBM Plex Sans", "Segoe UI", sans-serif';
}

function prepareChartRows(data, labelColHint = null, numericColHint = null) {
  const cols = Object.keys(data[0]);
  const numericCol = numericColHint || pickNumericColumn(cols, data[0]);
  const labelCol = labelColHint || pickLabelColumn(cols, data[0], numericCol);
  if (!numericCol || !labelCol) return null;

  const sorted = [...data].sort(
    (a, b) => toNumeric(b[numericCol]) - toNumeric(a[numericCol])
  );
  const limited = sorted.length > CHART_MAX_ITEMS ? sorted.slice(0, CHART_MAX_ITEMS) : sorted;

  return {
    labelCol,
    numericCol,
    labels: limited.map((r) => String(r[labelCol] ?? '')),
    values: limited.map((r) => toNumeric(r[numericCol])),
    totalRows: data.length,
    shownRows: limited.length,
  };
}

function listChartColumns(data) {
  return Object.keys(data[0] || {});
}

function isLabelColumnCandidate(col, row, numericCol) {
  return col !== numericCol && !isNumericValue(row[col]) && !isIdLikeColumn(col);
}

function isNumericColumnCandidate(col, row) {
  return isNumericValue(row[col]) && !isIdLikeColumn(col);
}

function fillColumnSelect(select, cols, row, selectedKey, mode, numericCol) {
  select.innerHTML = '';
  const filtered =
    mode === 'label'
      ? cols.filter((c) => isLabelColumnCandidate(c, row, numericCol))
      : cols.filter((c) => isNumericColumnCandidate(c, row));
  const options = filtered.length ? filtered : cols;
  options.forEach((key) => {
    const opt = document.createElement('option');
    opt.value = key;
    opt.textContent = columnLabel(key);
    if (key === selectedKey) opt.selected = true;
    select.appendChild(opt);
  });
}

function buildChartColors(count) {
  return Array.from({ length: count }, (_, i) => CHART_PALETTE[i % CHART_PALETTE.length]);
}

function categoryAxisTickCallback(labels) {
  return (value, index) => {
    if (labels[index] !== undefined && labels[index] !== null && labels[index] !== '') {
      return String(labels[index]);
    }
    if (typeof value === 'string' && value !== '' && Number.isNaN(Number(value))) {
      return value;
    }
    return '';
  };
}

function createChartInstance(canvas, type, chartData) {
  const { labels, values, labelCol, numericCol } = chartData;
  const labelTitle = columnLabel(labelCol);
  const valueTitle = columnLabel(numericCol);
  const colors = buildChartColors(labels.length);
  const font = chartFontFamily();
  const isHorizontal = type === 'barHorizontal';
  const isPie = type === 'pie' || type === 'doughnut';
  const isLine = type === 'line';
  const chartType = isPie ? type : isLine ? 'line' : 'bar';
  const categoryTickCb = categoryAxisTickCallback(labels);

  const dataset = {
    label: valueTitle,
    data: values,
    backgroundColor: isLine ? 'rgba(31, 111, 84, 0.15)' : colors,
    borderColor: isLine ? '#1f6f54' : colors.map((c) => c),
    borderWidth: isLine ? 2.5 : 1,
    borderRadius: isPie || isLine ? 0 : 4,
    fill: isLine,
    tension: 0.3,
    pointRadius: isLine ? 4 : 0,
    pointHoverRadius: isLine ? 6 : 0,
  };

  const rtl = state.language === 'fa' || labels.some(isRtlText);

  return new Chart(canvas, {
    type: chartType,
    data: { labels, datasets: [dataset] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: isHorizontal ? 'y' : 'x',
      layout: { padding: { top: 8, right: rtl ? 12 : 8, bottom: 8, left: rtl ? 8 : 12 } },
      plugins: {
        legend: {
          display: isPie,
          position: 'bottom',
          rtl,
          labels: {
            font: { family: font, size: 12 },
            color: '#1c2024',
            padding: 14,
            boxWidth: 14,
            boxHeight: 14,
            usePointStyle: true,
            generateLabels(chart) {
              const ds = chart.data.datasets[0];
              return chart.data.labels.map((text, i) => ({
                text: String(text),
                fillStyle: Array.isArray(ds.backgroundColor)
                  ? ds.backgroundColor[i]
                  : ds.backgroundColor,
                strokeStyle: Array.isArray(ds.borderColor) ? ds.borderColor[i] : ds.borderColor,
                lineWidth: 1,
                hidden: false,
                index: i,
              }));
            },
          },
        },
        tooltip: {
          rtl,
          titleFont: { family: font, size: 13 },
          bodyFont: { family: font, size: 12 },
          callbacks: {
            title: (items) => String(items[0]?.label ?? ''),
            label: (ctx) => {
              const p = ctx.parsed;
              const val =
                typeof p === 'number' ? p : p?.y ?? p?.x ?? ctx.raw ?? 0;
              return `${valueTitle}: ${Number(val).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
            },
          },
        },
      },
      scales: isPie
        ? {}
        : {
            x: {
              type: isHorizontal ? 'linear' : 'category',
              display: true,
              position: isHorizontal ? 'top' : 'bottom',
              title: {
                display: true,
                text: isHorizontal ? valueTitle : labelTitle,
                font: { family: font, size: 13, weight: '600' },
                color: '#15523e',
                padding: { top: 8 },
              },
              ticks: {
                font: { family: font, size: 11 },
                color: '#5b6168',
                autoSkip: false,
                maxRotation: isHorizontal ? 0 : 45,
                minRotation: 0,
                callback: isHorizontal
                  ? (v) => Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })
                  : categoryTickCb,
              },
              grid: { color: 'rgba(216, 211, 197, 0.5)' },
            },
            y: {
              type: isHorizontal ? 'category' : 'linear',
              display: true,
              title: {
                display: true,
                text: isHorizontal ? labelTitle : valueTitle,
                font: { family: font, size: 13, weight: '600' },
                color: '#15523e',
              },
              ticks: {
                font: { family: font, size: 11 },
                color: '#5b6168',
                autoSkip: false,
                callback: isHorizontal
                  ? categoryTickCb
                  : (v) => Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 }),
              },
              grid: { color: 'rgba(216, 211, 197, 0.5)' },
            },
          },
    },
  });
}

function showChartUnavailable(container, message) {
  container.innerHTML = `
    <div class="chart-panel chart-panel--unavailable">
      <div class="chart-note"${dirAttr(message)}>${escapeHtml(message)}</div>
    </div>
  `;
}

function maybeRenderChart(container, data) {
  if (!data || data.length < 1) {
    showChartUnavailable(container, chartUiText('noRows'));
    return;
  }
  if (typeof Chart === 'undefined') {
    showChartUnavailable(container, chartUiText('chartLibMissing'));
    return;
  }

  const chartData = prepareChartRows(data);
  if (!chartData) {
    showChartUnavailable(container, chartUiText('noColumns'));
    return;
  }

  const { labelCol, numericCol, totalRows, shownRows } = chartData;
  const cols = listChartColumns(data);
  const titleText = `${columnLabel(labelCol)} — ${columnLabel(numericCol)}`;
  const typeOptions = CHART_TYPE_OPTIONS.map(
    (o) =>
      `<option value="${o.id}">${state.language === 'fa' ? o.labelFa : o.labelEn}</option>`
  ).join('');

  const noteText =
    shownRows < totalRows
      ? chartUiText('showingTop')(shownRows, totalRows)
      : chartUiText('allRows')(shownRows);

  container.innerHTML = `
    <div class="chart-panel">
      <div class="chart-header">
        <h3 class="chart-title"${dirAttr(titleText)}>${escapeHtml(titleText)}</h3>
        <div class="chart-controls">
          <label${dirAttr(chartUiText('labelColumn'))}>
            <span>${escapeHtml(chartUiText('labelColumn'))}</span>
            <select class="chart-label-col-select chart-type-select"></select>
          </label>
          <label${dirAttr(chartUiText('valueColumn'))}>
            <span>${escapeHtml(chartUiText('valueColumn'))}</span>
            <select class="chart-value-col-select chart-type-select"></select>
          </label>
          <label${dirAttr(chartUiText('chartType'))}>
            <span>${escapeHtml(chartUiText('chartType'))}</span>
            <select class="chart-type-select" aria-label="${escapeHtml(chartUiText('chartType'))}">
              ${typeOptions}
            </select>
          </label>
        </div>
      </div>
      <div class="chart-canvas-wrap">
        <canvas></canvas>
      </div>
      <div class="chart-note"${dirAttr(noteText)}>${escapeHtml(noteText)}</div>
    </div>
  `;

  const canvasWrap = container.querySelector('.chart-canvas-wrap');
  const canvas = container.querySelector('canvas');
  const select = container.querySelector('.chart-type-select');
  const labelSelect = container.querySelector('.chart-label-col-select');
  const valueSelect = container.querySelector('.chart-value-col-select');
  const titleEl = container.querySelector('.chart-title');

  fillColumnSelect(labelSelect, cols, data[0], labelCol, 'label', numericCol);
  fillColumnSelect(valueSelect, cols, data[0], numericCol, 'value', labelCol);

  const defaultType =
    (state.language === 'fa' || chartData.labels.some(isRtlText)) && chartData.shownRows > 6
      ? 'barHorizontal'
      : 'bar';
  select.value = defaultType;
  let chartInstance = createChartInstance(canvas, defaultType, chartData);

  function refreshChart() {
    const next = prepareChartRows(data, labelSelect.value, valueSelect.value);
    if (!next) return;
    Object.assign(chartData, next);
    titleEl.textContent = `${columnLabel(next.labelCol)} — ${columnLabel(next.numericCol)}`;
    titleEl.setAttribute('dir', isRtlText(titleEl.textContent) ? 'rtl' : 'ltr');
    chartInstance.destroy();
    resizeWrap(select.value);
    chartInstance = createChartInstance(canvas, select.value, chartData);
  }

  labelSelect.addEventListener('change', () => {
    fillColumnSelect(valueSelect, cols, data[0], valueSelect.value, 'value', labelSelect.value);
    refreshChart();
  });
  valueSelect.addEventListener('change', refreshChart);

  function resizeWrap(type) {
    const horizontal = type === 'barHorizontal';
    const pie = type === 'pie' || type === 'doughnut';
    canvasWrap.classList.toggle('chart-canvas-wrap--horizontal', horizontal);
    const rows = chartData.shownRows;
    if (horizontal) {
      canvasWrap.style.height = `${Math.min(720, Math.max(320, rows * 28 + 80))}px`;
    } else if (pie) {
      canvasWrap.style.height = '380px';
    } else {
      canvasWrap.style.height = `${Math.min(520, Math.max(280, rows * 12 + 120))}px`;
    }
  }

  select.addEventListener('change', () => {
    const type = select.value;
    chartInstance.destroy();
    resizeWrap(type);
    chartInstance = createChartInstance(canvas, type, chartData);
  });

  resizeWrap(defaultType);
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

/** Turn plain-text analysis into styled HTML with bold headings and highlights. */
function formatAnalysisHtml(text) {
  if (!text) return '';

  const headerRe =
    /^(#{1,3}\s+.+|.+[:：]\s*$|[\d۰-۹]+[.)]\s+.+|(نتیجه|پیش‌بینی|خلاصه|تحلیل|جمع‌بندی|توصیه|نکته|مشاهده|روند|مقایسه|پیشنهاد).+)/i;

  const parts = [];
  let inList = false;

  const closeList = () => {
    if (inList) {
      parts.push('</ul>');
      inList = false;
    }
  };

  const highlightNumbers = (html) =>
    html.replace(/(\d[\d,.۰-۹]*%?)/g, '<span class="analysis-num">$1</span>');

  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim();
    if (!line) {
      closeList();
      continue;
    }

    let escaped = escapeHtml(line);
    escaped = escaped.replace(/\*\*(.+?)\*\*/g, '<strong class="analysis-strong">$1</strong>');

    if (/^[-•*▪]\s+/.test(line)) {
      if (!inList) {
        parts.push('<ul class="analysis-list">');
        inList = true;
      }
      const item = highlightNumbers(escaped.replace(/^[-•*▪]\s+/, ''));
      parts.push(`<li>${item}</li>`);
      continue;
    }

    closeList();

    const plainForHeader = line.replace(/^#{1,3}\s+/, '');
    const isHeader =
      /^#{1,3}\s/.test(line) ||
      (plainForHeader.length < 90 && /[:：]\s*$/.test(plainForHeader)) ||
      headerRe.test(plainForHeader);

    if (isHeader) {
      const title = highlightNumbers(escaped.replace(/^#{1,3}\s+/, ''));
      parts.push(`<h4 class="analysis-heading">${title}</h4>`);
    } else {
      parts.push(`<p class="analysis-paragraph">${highlightNumbers(escaped)}</p>`);
    }
  }

  closeList();
  return parts.join('');
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
