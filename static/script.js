/* script.js — PSP BI Conversational Report Builder (vanilla JS, no frameworks) */

const state = {
  language: 'fa',
  provider: 'avalai',
  lastResponse: null, // stores the most recent chat response for PDF/Excel export
  lastChart: null,    // Chart.js instance for PDF chart image (single-view or first quad)
  lastCharts: [],     // all 4 Chart.js instances when in quad-grid view
  lastQuadConfigs: [], // configs (title/icon) matching lastCharts
  pendingClarification: null, // { originalQuestion, transcript } while AI is asking a follow-up question
};

const langToggleBtn = document.getElementById('lang-toggle-btn');
const providerOllamaBtn = document.getElementById('provider-ollama-btn');
const providerAvalaiBtn = document.getElementById('provider-avalai-btn');
const chatArea = document.getElementById('chat-area');
const welcomeBlock = document.getElementById('welcome-block');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const historyList = document.getElementById('history-list');
const historyEmpty = document.getElementById('history-empty');
const historyRefreshBtn = document.getElementById('history-refresh-btn');
const freqList = document.getElementById('freq-list');
const freqEmpty = document.getElementById('freq-empty');
const settingsModelBtn = document.getElementById('settings-model-btn');
const settingsLangBtn = document.getElementById('settings-lang-btn');
const settingsModelValue = document.getElementById('settings-model-value');
const settingsLangValue = document.getElementById('settings-lang-value');
const sidebarCollapseBtn = document.getElementById('sidebar-collapse-btn');
const dashboardBody = document.querySelector('.dashboard-body');
const logoutBtn = document.getElementById('logout-btn');

window.addEventListener('DOMContentLoaded', async () => {
  ensureIranMapRegistered().catch(() => {});
  messageInput.focus();

  try {
    const res = await apiFetch('/api/preferences');
    const prefs = await res.json();
    if (prefs.provider === 'ollama' || prefs.provider === 'avalai') {
      state.provider = prefs.provider;
    }
    if (prefs.language === 'fa' || prefs.language === 'en') {
      state.language = prefs.language;
    }
  } catch (_) {
    /* use defaults */
  }

  applyProviderUI(state.provider);
  applyLanguageUI(state.language);
  await loadHistorySidebar();
  await loadFrequentQuestions();

  setupChartModal();
  setupHelpModal();

  // Check user role and show/hide admin buttons
  await checkUserRole();

  // Pre-fill query if coming from help page sample link (?q=...)
  const params = new URLSearchParams(window.location.search);
  const qParam = params.get('q');
  if (qParam && messageInput) {
    messageInput.value = qParam;
    messageInput.dir = isRtlText(qParam) ? 'rtl' : 'ltr';
    sendMessage();
  }
});

langToggleBtn.addEventListener('click', () => toggleLanguage(true));
if (providerOllamaBtn) {
  providerOllamaBtn.addEventListener('click', () => setProvider('ollama', true));
}
if (providerAvalaiBtn) {
  providerAvalaiBtn.addEventListener('click', () => setProvider('avalai', true));
}
if (logoutBtn) {
  logoutBtn.addEventListener('click', async () => {
    try {
      await apiFetch('/api/logout', { method: 'POST' });
      window.location.href = '/login';
    } catch (_) {
      window.location.href = '/login';
    }
  });
}
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
    const collapsed = dashboardBody.classList.toggle('sidebar-collapsed');
    dashboardBody.classList.remove('sidebar-resizable');
    sidebarCollapseBtn.textContent = collapsed ? '»' : '«';
    sidebarCollapseBtn.title = collapsed ? 'Expand sidebar' : 'Collapse sidebar';
    sidebarCollapseBtn.setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
    sidebarCollapseBtn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
  });
}

const SIDEBAR_MIN = 200;
const SIDEBAR_MAX = 600;
const SIDEBAR_DEFAULT = 340;
const resizeHandle = document.getElementById('sidebar-resize-handle');

if (resizeHandle && dashboardBody) {
  let startX = 0;
  let startW = 0;

  resizeHandle.addEventListener('mousedown', (e) => {
    e.preventDefault();
    dashboardBody.classList.add('sidebar-resizable');
    dashboardBody.classList.remove('sidebar-collapsed');
    startX = e.clientX;
    startW = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width')) || SIDEBAR_DEFAULT;
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  });

  function onMouseMove(e) {
    const bodyRect = dashboardBody.getBoundingClientRect();
    const sidebarPx = Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, bodyRect.right - e.clientX));
    document.documentElement.style.setProperty('--sidebar-width', sidebarPx + 'px');
  }

  function onMouseUp() {
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
    // persist in session storage
    const w = document.documentElement.style.getPropertyValue('--sidebar-width');
    if (w) sessionStorage.setItem('sidebar_width', w);
  }
}

// restore saved width on load
(function restoreSidebarWidth() {
  const saved = sessionStorage.getItem('sidebar_width');
  if (saved && dashboardBody) {
    document.documentElement.style.setProperty('--sidebar-width', saved);
    dashboardBody.classList.add('sidebar-resizable');
  }
})();

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

function setExportButtonsEnabled(enabled) {
  const pdfBtn = document.getElementById('export-pdf-btn');
  const excelBtn = document.getElementById('export-excel-btn');
  if (pdfBtn) pdfBtn.disabled = !enabled;
  if (excelBtn) excelBtn.disabled = !enabled;
}

function captureChartImage() {
  // Prefer the live ECharts instance; fall back to the newest canvas in the page.
  const chart = state.lastChart;
  if (chart && typeof chart.getDataURL === 'function') {
    try {
      const url = chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#ffffff' });
      if (url && url.startsWith('data:image') && url.length > 100) return url;
    } catch (_) { /* fall through */ }
  }
  if (chart && typeof chart.toBase64Image === 'function') {
    try {
      if (typeof chart.draw === 'function') chart.draw();
      const url = chart.toBase64Image('image/png', 1);
      if (url && url.startsWith('data:image') && url.length > 100) return url;
    } catch (_) { /* fall through */ }
  }
  const canvases = document.querySelectorAll('.chart-canvas-wrap canvas, .chart-card-canvas-wrap canvas');
  const canvas = canvases.length ? canvases[canvases.length - 1] : null;
  if (canvas && canvas.width > 0 && canvas.height > 0) {
    try {
      return canvas.toDataURL('image/png');
    } catch (_) { /* ignore */ }
  }
  return null;
}

function captureAllChartImages() {
  // If we have all 4 quad chart instances, capture each one with its title.
  if (state.lastCharts && state.lastCharts.length > 0) {
    const images = [];
    state.lastCharts.forEach((inst, i) => {
      const cfg = (state.lastQuadConfigs && state.lastQuadConfigs[i]) || {};
      let dataUrl = null;
      if (inst && typeof inst.getDataURL === 'function') {
        try {
          const url = inst.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#ffffff' });
          if (url && url.startsWith('data:image') && url.length > 100) dataUrl = url;
        } catch (_) { /* ignore */ }
      }
      if (!dataUrl && inst && typeof inst.toBase64Image === 'function') {
        try {
          if (typeof inst.draw === 'function') inst.draw();
          const url = inst.toBase64Image('image/png', 1);
          if (url && url.startsWith('data:image') && url.length > 100) dataUrl = url;
        } catch (_) { /* ignore */ }
      }
      // Fallback: capture the underlying canvas element
      if (!dataUrl && inst && typeof inst.getDom === 'function') {
        try {
          const dom = inst.getDom();
          const c = dom ? dom.querySelector('canvas') : null;
          if (c && c.width > 0) {
            dataUrl = c.toDataURL('image/png');
          }
        } catch (_) { /* ignore */ }
      }
      if (!dataUrl && inst && inst.canvas) {
        try {
          const url = inst.canvas.toDataURL('image/png');
          if (url && url.startsWith('data:image') && url.length > 100) dataUrl = url;
        } catch (_) { /* ignore */ }
      }
      if (dataUrl) {
        images.push({ image: dataUrl, title: cfg.title || `نمودار ${i + 1}`, icon: cfg.icon || '📊' });
      }
    });
    if (images.length > 0) return images;
  }
  // Fallback to single chart
  const single = captureChartImage();
  return single ? [{ image: single, title: state.language === 'fa' ? 'نمودار' : 'Chart', icon: '📊' }] : [];
}

function buildExportPayload() {
  if (!state.lastResponse) return null;
  const { explanation, data, analysis } = state.lastResponse;
  return {
    title: state.language === 'fa' ? 'گزارش هوش تجاری' : 'BI Report',
    explanation: explanation || '',
    data: data || [],
    analysis: analysis || '',
    chart_image: captureChartImage(),   // kept for backward-compat
    chart_images: captureAllChartImages(), // all 4 charts with titles
  };
}

async function downloadExport(endpoint, filename, includeChart) {
  const payload = buildExportPayload();
  if (!payload) return;
  if (!includeChart) delete payload.chart_image;
  try {
    const res = await apiFetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(err.error || `Failed to generate ${filename}`);
      return;
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (e) {
    alert(`Network error while generating ${filename}`);
  }
}

const exportPdfBtn = document.getElementById('export-pdf-btn');
if (exportPdfBtn) {
  exportPdfBtn.addEventListener('click', () =>
    downloadExport('/api/export_pdf', `report${exportStamp()}.pdf`, true)
  );
}
const exportExcelBtn = document.getElementById('export-excel-btn');
if (exportExcelBtn) {
  exportExcelBtn.addEventListener('click', () =>
    downloadExport('/api/export_excel', `report${exportStamp()}.xlsx`, false)
  );
}

function exportStamp() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return (
    `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}` +
    `${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`
  );
}
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
  const voiceBtn = document.getElementById('voice-input-btn');
  if (voiceBtn && !voiceListening) {
    voiceBtn.title =
      language === 'fa' ? 'ورودی صوتی (فارسی/انگلیسی)' : 'Voice input (FA/EN)';
    voiceBtn.setAttribute('aria-label', voiceBtn.title);
  }
  if (voiceRecognition && voiceListening) {
    voiceRecognition.lang = speechLocale(language);
  }
}

function applyProviderUI(provider) {
  state.provider = provider;
  if (providerOllamaBtn) {
    providerOllamaBtn.classList.toggle('is-active', provider === 'ollama');
  }
  if (providerAvalaiBtn) {
    providerAvalaiBtn.classList.toggle('is-active', provider === 'avalai');
  }
  if (settingsModelValue) {
    settingsModelValue.textContent = `${providerLabel()} ›`;
  }
}

function toggleLanguage(persist) {
  applyLanguageUI(state.language === 'fa' ? 'en' : 'fa');
  if (persist) savePreferences();
}

async function apiFetch(url, options) {
  return fetch(url, options);
}

async function checkUserRole() {
  const usersBtn = document.getElementById('users-mgmt-btn');
  const tierBadge = document.getElementById('user-tier-badge');
  
  try {
    const res = await apiFetch('/api/me');
    if (!res.ok) {
      if (usersBtn) usersBtn.hidden = true;
      if (tierBadge) tierBadge.style.display = 'none';
      return;
    }
    const userData = await res.json();
    state.currentUser = userData;

    if (usersBtn) {
      usersBtn.hidden = userData.role !== 'admin';
    }

    if (tierBadge) {
      renderUserTierBadge(tierBadge, userData);
    }
  } catch (_) {
    if (usersBtn) usersBtn.hidden = true;
    if (tierBadge) tierBadge.style.display = 'none';
  }
}

function renderUserTierBadge(container, user) {
  if (!container || !user) return;
  const isAdm = user.role === 'admin';
  const isPrem = user.tier === 'premium';
  let tierLabel = '';
  let badgeColor = '';
  let badgeBg = '';
  let usageDetails = '';

  if (isAdm) {
    tierLabel = '👑 مدیر سیستم';
    badgeBg = 'rgba(5,150,105,0.14)';
    badgeColor = '#047857';
    usageDetails = 'پرسش نامحدود';
  } else if (isPrem) {
    tierLabel = '🌟 کاربر برتر';
    badgeBg = 'rgba(217,119,6,0.14)';
    badgeColor = '#b45309';
    usageDetails = 'پرسش نامحدود';
  } else {
    tierLabel = 'کاربر سطح ۱';
    badgeBg = 'rgba(37,99,235,0.1)';
    badgeColor = '#1d4ed8';
    const used = user.queries_today ?? 0;
    const limit = user.daily_limit ?? 10;
    usageDetails = `${used} از ${limit} سوال امروز`;
  }

  container.innerHTML = `
    <div style="display: inline-flex; align-items: center; gap: 8px; font-size: 0.82rem; background: rgba(5,150,105,0.06); padding: 4px 12px; border-radius: 999px; border: 1px solid rgba(5,150,105,0.16);">
      <span style="font-weight: 700; color: #0f2a1f;">${escapeHtml(user.display_name || user.username)}</span>
      <span style="color: #9ca3af;">•</span>
      <span style="padding: 2px 8px; border-radius: 999px; background: ${badgeBg}; color: ${badgeColor}; font-weight: 700; font-size: 0.74rem;">${tierLabel}</span>
      <span style="font-size: 0.76rem; color: #4b5563; font-family: monospace;">(${usageDetails})</span>
    </div>
  `;
  container.style.display = 'inline-flex';
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
  return state.provider === 'avalai' ? 'API' : 'Ollama';
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

function showListSkeleton(listEl, emptyEl, count) {
  if (!listEl) return;
  if (emptyEl) emptyEl.hidden = true;
  listEl.querySelectorAll('.history-item, .skeleton-row').forEach((el) => el.remove());
  for (let i = 0; i < count; i += 1) {
    const row = document.createElement('div');
    row.className = 'skeleton-row';
    listEl.appendChild(row);
  }
}

async function loadHistorySidebar() {
  if (!historyList) return;
  showListSkeleton(historyList, historyEmpty, 3);
  try {
    const res = await apiFetch('/api/history');
    const json = await res.json();
    const items = (json.history || []).slice().reverse();
    historyList.querySelectorAll('.history-item, .skeleton-row').forEach((el) => el.remove());
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
        replayHistoryEntry(entry);
      });
      historyList.appendChild(btn);
    });
  } catch (_) {
    historyList.querySelectorAll('.skeleton-row').forEach((el) => el.remove());
    if (historyEmpty) historyEmpty.hidden = false;
  }
}

async function loadFrequentQuestions() {
  if (!freqList) return;
  showListSkeleton(freqList, freqEmpty, 3);
  try {
    const res = await apiFetch('/api/frequent-questions');
    const json = await res.json();
    const items = json.questions || [];
    freqList.querySelectorAll('.freq-item, .skeleton-row').forEach((el) => el.remove());
    if (!items.length) {
      if (freqEmpty) freqEmpty.hidden = false;
      return;
    }
    if (freqEmpty) freqEmpty.hidden = true;
    items.forEach((item) => {
      const q = item.question || '';
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'history-item freq-item';
      btn.innerHTML = `
        <div class="history-q"${dirAttr(q)}>${escapeHtml(q)}</div>
        <div class="history-meta">${item.count}×</div>
      `;
      btn.addEventListener('click', () => {
        messageInput.value = q;
        messageInput.dir = isRtlText(q) ? 'rtl' : 'ltr';
        sendMessage();
      });
      freqList.appendChild(btn);
    });
  } catch (_) {
    freqList.querySelectorAll('.skeleton-row').forEach((el) => el.remove());
    if (freqEmpty) freqEmpty.hidden = false;
  }
}

function replayHistoryEntry(entry) {
  if (!entry) return;
  if (welcomeBlock && welcomeBlock.isConnected) welcomeBlock.remove();

  const q = entry.user_question || '';
  const stripId = 'strip-' + Math.random().toString(36).slice(2, 9);

  const turn = document.createElement('div');
  turn.className = 'turn';
  turn.innerHTML = `
    <div class="user-line"><div class="user-bubble"${dirAttr(q)}>${escapeHtml(q)}</div></div>
    <div class="strip" id="${stripId}">
      <div class="strip-section sql-draft-section">
        <div class="strip-label"${dirAttr(chatUiText('sqlDraftTitle'))}>${escapeHtml(chatUiText('sqlDraftTitle'))}</div>
        <p class="sql-hint"${dirAttr(chatUiText('sqlHint'))}>${escapeHtml(chatUiText('sqlHint'))}</p>
        <textarea class="sql-editor" dir="ltr" spellcheck="false">${escapeHtml(entry.sql || '')}</textarea>
        ${entry.explanation ? `<div class="sql-explanation"${dirAttr(entry.explanation)}>${escapeHtml(entry.explanation)}</div>` : ''}
        <div class="sql-actions">
          <button type="button" class="primary-btn run-sql-btn">${escapeHtml(chatUiText('runSqlBtn'))}</button>
        </div>
        <div class="run-error" hidden></div>
        <div class="sql-autofix-note" hidden></div>
      </div>
      <div class="sql-run-results"></div>
    </div>
  `;
  chatArea.appendChild(turn);

  const stripEl = document.getElementById(stripId);
  wireSqlRunner(stripEl, {
    question: q,
    explanation: entry.explanation || '',
    provider: entry.provider || state.provider,
    language: entry.language || state.language,
  });

  const resultsEl = stripEl.querySelector('.sql-run-results');
  if (Array.isArray(entry.data)) {
    renderRunResults(resultsEl, {
      explanation: entry.explanation || '',
      data: entry.data,
      row_count: entry.row_count ?? entry.data.length,
      timings: null,
      sql: entry.sql,
      provider: entry.provider,
      language: entry.language,
      message_id: entry.id,
    }, q);

    const resultEl = resultsEl.querySelector('.run-results-inner');
    if (resultEl && entry.analysis) {
      const placeholder = resultEl.querySelector('.analysis-placeholder');
      const textEl = resultEl.querySelector('.analysis-text');
      const analyzeBtn = resultEl.querySelector('.analyze-btn');
      placeholder.hidden = true;
      textEl.hidden = false;
      textEl.className = 'analysis-text analysis-text--ready';
      textEl.setAttribute('dir', isRtlText(entry.analysis) ? 'rtl' : 'ltr');
      textEl.innerHTML = formatAnalysisHtml(entry.analysis);
      if (analyzeBtn) analyzeBtn.textContent = chatUiText('analyzeAgain');
      if (state.lastResponse) state.lastResponse.analysis = entry.analysis;
    }
    if (resultEl && entry.feedback && entry.feedback.rating) {
      const btns = resultEl.querySelectorAll('.feedback-btn');
      btns.forEach((b) => {
        b.classList.toggle('is-selected', b.dataset.rating === entry.feedback.rating);
        b.disabled = true;
      });
      const msgEl = resultEl.querySelector('.feedback-msg');
      if (msgEl) {
        msgEl.hidden = false;
        msgEl.className = 'feedback-msg feedback-msg--ok';
        msgEl.textContent = chatUiText('feedbackThanks');
      }
    }
  } else {
    resultsEl.innerHTML = `<p class="sql-hint"${dirAttr(chatUiText('replayNoData'))}>${escapeHtml(chatUiText('replayNoData'))}</p>`;
  }

  chatArea.scrollTop = chatArea.scrollHeight;
}

function chatUiText(key) {
  const provider = providerLabel();
  const fa = {
    loadingReport: `در حال تولید SQL با ${provider}…`,
    loadingRun: 'در حال اجرای SQL…',
    sqlDraftTitle: 'SQL تولیدشده — قابل ویرایش',
    sqlHint: 'در صورت نیاز SQL را ویرایش کنید، سپس اجرا را بزنید.',
    runSqlBtn: 'اجرای SQL',
    runningSql: 'در حال اجرا…',
    runAgainBtn: 'اجرای مجدد',
    resultTitle: 'نتیجه',
    chartSectionTitle: 'نمودار',
    analysisTitle: 'تحلیل و پیش\u200cبینی',
    analyzeBtn: 'تحلیل نتایج',
    analyzing: `در حال تحلیل با ${provider}…`,
    analyzePrompt: 'برای تحلیل هوشمند نتایج، روی دکمه زیر کلیک کنید.',
    analyzeAgain: 'تحلیل مجدد',
    discussTitle: 'بحث و بررسی',
    discussHint: 'اگر بخشی از داده یا تحلیل اشتباه یا قابل‌بحث است، اینجا بنویسید. می‌توانید متن موردنظر را در کادر «مورد بحث» بچسبانید.',
    discussFocusLabel: 'مورد بحث (اختیاری)',
    discussFocusPlaceholder: 'مثلاً جمله‌ای از تحلیل یا نام یک مشتری…',
    discussPlaceholder: 'نظر، اعتراض یا سؤال خود را بنویسید…',
    discussSend: 'ارسال بحث',
    discussSending: 'در حال پاسخ…',
    discussEmpty: 'هنوز بحثی ثبت نشده است.',
    discussApply: 'جایگزینی این بخش در تحلیل',
    discussApplyNoFocus: 'متن «مورد بحث» در تحلیل پیدا نشد. همان بخش را از تحلیل انتخاب و دوباره امتحان کنید.',
    discussYou: 'شما',
    discussAi: 'دستیار',
    discussEmptyInput: 'متن بحث خالی است. در یکی از دو کادر «مورد بحث» یا «پیام بحث» بنویسید.',
    voiceListening: 'در حال شنیدن…',
    voiceUnsupported: 'مرورگر از ورودی صوتی پشتیبانی نمی‌کند (Chrome/Edge را امتحان کنید).',
    voiceMicDenied: 'دسترسی میکروفون رد شد.',
    feedbackTitle: 'یادگیری از بازخورد',
    feedbackHint: 'این پاسخ درست بود؟',
    feedbackCorrect: 'درست',
    feedbackWrong: 'نادرست',
    feedbackThanks: 'بازخورد ثبت شد. ممنون!',
    feedbackError: 'ثبت بازخورد ناموفق بود.',
    replayNoData: 'داده‌ای برای این گفتگوی قدیمی ذخیره نشده است؛ برای مشاهده دوباره، SQL را اجرا کنید.',
    sqlAutoFixed: 'اجرای SQL اولیه با خطا مواجه شد؛ هوش مصنوعی آن را به‌صورت خودکار اصلاح و دوباره اجرا کرد.',
    clarificationLabel: 'نیاز به توضیح بیشتر',
    clarificationHint: 'پاسخ خود را در کادر پیام زیر بنویسید.',
  };
  const en = {
    loadingReport: `Generating SQL with ${provider}…`,
    loadingRun: 'Running SQL…',
    sqlDraftTitle: 'Generated SQL — editable',
    sqlHint: 'Edit the SQL if needed, then run it.',
    runSqlBtn: 'Run SQL',
    runningSql: 'Running…',
    runAgainBtn: 'Run again',
    resultTitle: 'Result',
    chartSectionTitle: 'Chart',
    analysisTitle: 'Analysis & prediction',
    analyzeBtn: 'Analyze results',
    analyzing: `Analyzing with ${provider}…`,
    analyzePrompt: 'Click the button below for AI analysis of these results.',
    analyzeAgain: 'Re-analyze',
    discussTitle: 'Discuss',
    discussHint: 'If part of the data or analysis looks wrong or debatable, write here. Optionally paste the snippet into Focus.',
    discussFocusLabel: 'Focus (optional)',
    discussFocusPlaceholder: 'e.g. a sentence from the analysis or a customer name…',
    discussPlaceholder: 'Your challenge, correction, or question…',
    discussSend: 'Send discussion',
    discussSending: 'Replying…',
    discussEmpty: 'No discussion yet.',
    discussApply: 'Replace this part in analysis',
    discussApplyNoFocus: 'Focus text was not found in the analysis. Select that part from the analysis and try again.',
    discussYou: 'You',
    discussAi: 'Assistant',
    discussEmptyInput: 'Discussion text is empty. Fill either Focus or Discussion message.',
    voiceListening: 'Listening…',
    voiceUnsupported: 'Voice input is not supported in this browser (try Chrome/Edge).',
    voiceMicDenied: 'Microphone access was denied.',
    feedbackTitle: 'Feedback learning',
    feedbackHint: 'Was this answer correct?',
    feedbackCorrect: 'Correct',
    feedbackWrong: 'Wrong',
    feedbackThanks: 'Feedback saved. Thank you!',
    feedbackError: 'Could not save feedback.',
    replayNoData: 'No stored data for this older conversation; run the SQL again to see it.',
    sqlAutoFixed: 'The initial SQL failed to run; AI automatically corrected it and re-ran it.',
    clarificationLabel: 'Needs clarification',
    clarificationHint: 'Type your answer in the message box below.',
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

  const pending = state.pendingClarification;
  const outgoingMessage = pending ? `${pending.transcript}\nUser: ${text}` : text;
  const displayQuestion = pending ? pending.originalQuestion : text;

  try {
    const res = await apiFetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: outgoingMessage, language: state.language, provider: state.provider }),
    });
    let json;
    try {
      json = await res.json();
    } catch (_) {
      state.pendingClarification = null;
      renderError(loadingHolder, { error: `Server error (${res.status}). Check server logs.` }, displayQuestion);
      return;
    }

    if (!res.ok) {
      state.pendingClarification = null;
      renderError(loadingHolder, json, displayQuestion);
      return;
    }

    if (json.needs_clarification) {
      state.pendingClarification = {
        originalQuestion: displayQuestion,
        transcript: `${outgoingMessage}\nAI: ${json.clarification_question || ''}`,
      };
      renderClarification(loadingHolder, json);
      return;
    }

    state.pendingClarification = null;
    renderSqlDraft(loadingHolder, json, displayQuestion);
  } catch (e) {
    renderError(loadingHolder, { error: 'Network error reaching the server.' }, displayQuestion);
  } finally {
    sendBtn.disabled = false;
    chatArea.scrollTop = chatArea.scrollHeight;
    checkUserRole().catch(() => {});
  }
}

function renderClarification(container, json) {
  const question = json.clarification_question || '';
  container.innerHTML = `
    <div class="strip">
      <div class="strip-section clarification-section">
        <div class="strip-label"${dirAttr(chatUiText('clarificationLabel'))}>${escapeHtml(chatUiText('clarificationLabel'))}</div>
        <div class="clarification-text"${dirAttr(question)}>${escapeHtml(question)}</div>
        <p class="sql-hint"${dirAttr(chatUiText('clarificationHint'))}>${escapeHtml(chatUiText('clarificationHint'))}</p>
      </div>
    </div>
  `;
}

function renderError(container, json, originalQuestion) {
  if (json.quota_exceeded) {
    container.innerHTML = `
      <div class="strip" style="border: 2px solid #f59e0b; background: #fffbeb; border-radius: 18px; padding: 22px; margin: 14px 0; box-shadow: 0 8px 24px rgba(245,158,11,0.12);">
        <div style="display: flex; align-items: flex-start; gap: 14px;">
          <span style="font-size: 32px; line-height: 1;">⏳</span>
          <div style="flex: 1;">
            <div style="font-weight: 800; font-size: 1.06rem; color: #b45309; margin-bottom: 8px;">محدودیت سقف روزانه کاربر سطح ۱</div>
            <div style="font-size: 0.98rem; color: #92400e; line-height: 1.9; font-weight: 600;">
              ${escapeHtml(json.error || 'مهلت استفاده رایگان شما تمام شده است و فردا مراجعه کنید یا سطح کاربری خود را با پیغام به ما ارتقا دهید')}
            </div>
            <div style="margin-top: 14px; display: flex; gap: 10px; flex-wrap: wrap;">
              <a href="mailto:support@rayamate.ir?subject=درخواست ارتقای حساب کاربری به کاربر برتر" class="primary-btn tiny" style="background: #d97706; color: #fff; text-decoration: none; padding: 8px 16px; border-radius: 12px; font-weight: 700; font-size: 0.88rem; display: inline-flex; align-items: center; gap: 6px;">
                <span>✨</span><span>ارسال پیام جهت ارتقا به کاربر برتر</span>
              </a>
              <button type="button" class="ghost-btn tiny" onclick="checkUserRole();" style="border-radius: 12px; padding: 8px 14px; font-size: 0.88rem;">
                🔄 بررسی مجدد سهمیه
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
    checkUserRole().catch(() => {});
    return;
  }

  const sql = json.sql || '';
  container.innerHTML = `
    <div class="strip">
      <div class="strip-section">
        <div class="strip-label">Error</div>
        <div class="error-strip">${escapeHtml(json.error || 'Something went wrong.')}</div>
      </div>
      ${json.timings ? renderTimingsSection(json.timings) : ''}
      ${sql ? `
      <div class="strip-section sql-draft-section">
        <div class="strip-label"${dirAttr(chatUiText('sqlDraftTitle'))}>${escapeHtml(chatUiText('sqlDraftTitle'))}</div>
        <p class="sql-hint"${dirAttr(chatUiText('sqlHint'))}>${escapeHtml(chatUiText('sqlHint'))}</p>
        <textarea class="sql-editor" dir="ltr" spellcheck="false">${escapeHtml(sql)}</textarea>
        <div class="sql-actions">
          <button type="button" class="primary-btn run-sql-btn">${escapeHtml(chatUiText('runSqlBtn'))}</button>
        </div>
        <div class="run-error" hidden></div>
        <div class="sql-autofix-note" hidden></div>
      </div>
      <div class="sql-run-results"></div>` : ''}
    </div>
  `;
  if (sql) {
    const strip = container.querySelector('.strip');
    wireSqlRunner(strip, {
      question: originalQuestion || '',
      explanation: json.explanation || '',
      provider: json.provider || state.provider,
      language: json.language || state.language,
    });
  }
}

function renderSqlDraft(container, json, originalQuestion) {
  const sql = json.sql || '';
  const explanation = json.explanation || '';
  const stripId = 'strip-' + Math.random().toString(36).slice(2, 9);

  container.innerHTML = `
    <div class="strip" id="${stripId}">
      ${renderTimingsSection(json.timings)}
      <div class="strip-section sql-draft-section">
        <div class="strip-label"${dirAttr(chatUiText('sqlDraftTitle'))}>${escapeHtml(chatUiText('sqlDraftTitle'))}</div>
        <p class="sql-hint"${dirAttr(chatUiText('sqlHint'))}>${escapeHtml(chatUiText('sqlHint'))}</p>
        <textarea class="sql-editor" dir="ltr" spellcheck="false">${escapeHtml(sql)}</textarea>
        ${explanation ? `<div class="sql-explanation"${dirAttr(explanation)}>${escapeHtml(explanation)}</div>` : ''}
        <div class="sql-actions">
          <button type="button" class="primary-btn run-sql-btn">${escapeHtml(chatUiText('runSqlBtn'))}</button>
        </div>
        <div class="run-error" hidden></div>
        <div class="sql-autofix-note" hidden></div>
      </div>
      <div class="sql-run-results"></div>
    </div>
  `;

  const stripEl = document.getElementById(stripId);
  wireSqlRunner(stripEl, {
    question: originalQuestion,
    explanation,
    provider: json.provider || state.provider,
    language: json.language || state.language,
  });
}

function wireSqlRunner(stripEl, ctx) {
  const runBtn = stripEl.querySelector('.run-sql-btn');
  const editor = stripEl.querySelector('.sql-editor');
  const errEl = stripEl.querySelector('.run-error');
  const autofixEl = stripEl.querySelector('.sql-autofix-note');
  const resultsEl = stripEl.querySelector('.sql-run-results');
  if (!runBtn || !editor) return;

  runBtn.addEventListener('click', async () => {
    const sql = editor.value.trim();
    if (!sql) return;

    runBtn.disabled = true;
    runBtn.textContent = chatUiText('runningSql');
    if (errEl) {
      errEl.hidden = true;
      errEl.textContent = '';
    }
    if (autofixEl) autofixEl.hidden = true;
    if (resultsEl) {
      resultsEl.innerHTML = `
        <div class="loading-strip">
          <span class="dot-pulse"></span><span class="dot-pulse"></span><span class="dot-pulse"></span>
          <span>${escapeHtml(chatUiText('loadingRun'))}</span>
        </div>
      `;
    }

    try {
      const res = await apiFetch('/api/run_sql', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sql,
          message: ctx.question,
          explanation: ctx.explanation || '',
          language: ctx.language,
          provider: ctx.provider,
        }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (resultsEl) resultsEl.innerHTML = '';
        if (errEl) {
          errEl.hidden = false;
          errEl.textContent = json.error || 'SQL execution failed.';
        }
        if (json.sql) editor.value = json.sql;
        return;
      }
      if (json.sql) editor.value = json.sql;
      if (autofixEl) {
        if (json.auto_fixed) {
          autofixEl.hidden = false;
          autofixEl.textContent = chatUiText('sqlAutoFixed');
        } else {
          autofixEl.hidden = true;
        }
      }
      renderRunResults(resultsEl, json, ctx.question);
      loadHistorySidebar();
      loadFrequentQuestions();
    } catch (_) {
      if (resultsEl) resultsEl.innerHTML = '';
      if (errEl) {
        errEl.hidden = false;
        errEl.textContent = 'Network error while running SQL.';
      }
    } finally {
      runBtn.disabled = false;
      runBtn.textContent = chatUiText('runAgainBtn');
      chatArea.scrollTop = chatArea.scrollHeight;
    }
  });
}

function renderRunResults(container, json, originalQuestion) {
  if (!container) return;
  const { explanation, data, row_count, timings } = json;
  const language = json.language || state.language;
  const resultId = 'result-' + Math.random().toString(36).slice(2, 9);
  const analysisTitle = chatUiText('analysisTitle');

  container.innerHTML = `
    <div class="run-results-inner" id="${resultId}">
      ${renderTimingsSection(timings)}
      <div class="strip-section table-section">
        <div class="strip-label"${dirAttr(chatUiText('resultTitle'))}>${escapeHtml(chatUiText('resultTitle'))}</div>
        <div class="data-table-wrap"></div>
        <div class="row-count">${row_count} row${row_count === 1 ? '' : 's'} returned</div>
      </div>
      <div class="strip-section chart-section">
        <div class="strip-label"${dirAttr(chatUiText('chartSectionTitle'))}>${escapeHtml(chatUiText('chartSectionTitle'))}</div>
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
      <div class="strip-section discuss-section">
        <div class="discuss-header">
          <div class="strip-label"${dirAttr(chatUiText('discussTitle'))}>${escapeHtml(chatUiText('discussTitle'))}</div>
          <span class="discuss-toggle-icon" aria-hidden="true">▾</span>
        </div>
        <div class="discuss-body">
          <p class="discuss-hint"${dirAttr(chatUiText('discussHint'))}>${escapeHtml(chatUiText('discussHint'))}</p>
          <label class="discuss-focus-label"${dirAttr(chatUiText('discussFocusLabel'))}>
            <span>${escapeHtml(chatUiText('discussFocusLabel'))}</span>
            <textarea class="discuss-focus" rows="2" placeholder="${escapeHtml(chatUiText('discussFocusPlaceholder'))}"></textarea>
          </label>
          <div class="discuss-thread" data-empty="1">
            <div class="discuss-empty"${dirAttr(chatUiText('discussEmpty'))}>${escapeHtml(chatUiText('discussEmpty'))}</div>
          </div>
          <div class="discuss-composer">
            <textarea class="discuss-input" rows="2" placeholder="${escapeHtml(chatUiText('discussPlaceholder'))}"></textarea>
            <button type="button" class="primary-btn discuss-send-btn">${escapeHtml(chatUiText('discussSend'))}</button>
          </div>
        </div>
      </div>
      <div class="strip-section feedback-section"${json.message_id ? '' : ' hidden'}>
        <div class="feedback-header">
          <div class="strip-label"${dirAttr(chatUiText('feedbackTitle'))}>${escapeHtml(chatUiText('feedbackTitle'))}</div>
          <span class="feedback-hint"${dirAttr(chatUiText('feedbackHint'))}>${escapeHtml(chatUiText('feedbackHint'))}</span>
        </div>
        <div class="feedback-actions">
          <button type="button" class="ghost-btn feedback-btn feedback-btn--up" data-rating="up" title="${escapeHtml(chatUiText('feedbackCorrect'))}">
            <span aria-hidden="true">👍</span> ${escapeHtml(chatUiText('feedbackCorrect'))}
          </button>
          <button type="button" class="ghost-btn feedback-btn feedback-btn--down" data-rating="down" title="${escapeHtml(chatUiText('feedbackWrong'))}">
            <span aria-hidden="true">👎</span> ${escapeHtml(chatUiText('feedbackWrong'))}
          </button>
        </div>
        <div class="feedback-msg" hidden></div>
      </div>
    </div>
  `;

  const resultEl = document.getElementById(resultId);
  mountPaginatedTable(resultEl.querySelector('.data-table-wrap'), data || []);
  maybeRenderChart(resultEl.querySelector('.chart-wrap'), data || [], originalQuestion, json.stats);

  const analyzeBtn = resultEl.querySelector('.analyze-btn');
  const resultProvider = json.provider || state.provider;
  analyzeBtn.addEventListener('click', () => {
    requestAnalysis(resultEl, originalQuestion, data || [], language, analyzeBtn, resultProvider);
  });

  state.lastResponse = {
    explanation: explanation || '',
    data: data || [],
    analysis: '',
    sql: json.sql,
  };
  setExportButtonsEnabled(true);
  wireDiscussPanel(resultEl, {
    question: originalQuestion,
    data: data || [],
    language,
    provider: resultProvider,
  });
  if (json.message_id) {
    wireFeedbackBar(resultEl, json.message_id);
  }
}

function wireFeedbackBar(stripEl, messageId) {
  const section = stripEl.querySelector('.feedback-section');
  if (!section || !messageId) return;

  const msgEl = section.querySelector('.feedback-msg');
  const buttons = section.querySelectorAll('.feedback-btn');

  async function submit(rating) {
    buttons.forEach((b) => { b.disabled = true; });
    try {
      const res = await apiFetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: messageId, rating }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (msgEl) {
          msgEl.hidden = false;
          msgEl.className = 'feedback-msg feedback-msg--err';
          msgEl.textContent = json.error || chatUiText('feedbackError');
        }
        buttons.forEach((b) => { b.disabled = false; });
        return;
      }
      if (msgEl) {
        msgEl.hidden = false;
        msgEl.className = 'feedback-msg feedback-msg--ok';
        msgEl.textContent = chatUiText('feedbackThanks');
      }
      buttons.forEach((b) => {
        b.classList.toggle('is-selected', b.dataset.rating === rating);
        b.disabled = true;
      });
    } catch (_) {
      if (msgEl) {
        msgEl.hidden = false;
        msgEl.className = 'feedback-msg feedback-msg--err';
        msgEl.textContent = chatUiText('feedbackError');
      }
      buttons.forEach((b) => { b.disabled = false; });
    }
  }

  buttons.forEach((btn) => {
    btn.addEventListener('click', () => submit(btn.dataset.rating));
  });
}

const TIMING_STEPS = [
  { key: 'sql_generation', labelFa: 'تولید SQL', labelEn: 'SQL generation' },
  { key: 'sql_normalize', labelFa: 'نرمال\u200cسازی SQL', labelEn: 'SQL normalization' },
  { key: 'sql_safety', labelFa: 'بررسی امنیت SQL', labelEn: 'SQL safety check' },
  { key: 'sql_autofix', labelFa: 'اصلاح خودکار SQL', labelEn: 'SQL auto-fix' },
  { key: 'sql_execution', labelFa: 'اجرای پایگاه\u200cداده', labelEn: 'Database execution' },
  { key: 'memory_save', labelFa: 'ذخیره حافظه', labelEn: 'Memory save' },
  { key: 'analysis', labelFa: 'تحلیل', labelEn: 'Analysis' },
  { key: 'discussion', labelFa: 'بحث', labelEn: 'Discussion' },
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

function toFaDigits(str) {
  return String(str || '').replace(/[0-9]/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[d]);
}

function formatPersianNumber(val) {
  if (val === null || val === undefined || isNaN(val)) return '۰';
  const num = Number(val);
  if (num >= 1_000_000_000) {
    return toFaDigits((num / 1_000_000_000).toFixed(1)) + ' میلیارد';
  }
  if (num >= 1_000_000) {
    return toFaDigits((num / 1_000_000).toFixed(1)) + ' میلیون';
  }
  if (num >= 1_000) {
    return toFaDigits((num / 1_000).toFixed(0)) + ' هزار';
  }
  return toFaDigits(num.toLocaleString('fa-IR'));
}

function buildInfographicData(data, analysisText, question) {
  const rows = Array.isArray(data) ? data : [];

  let headline = '';
  if (analysisText) {
    const boldMatch = analysisText.match(/\*\*(.+?)\*\*/);
    if (boldMatch && boldMatch[1].length > 8 && boldMatch[1].length < 80) {
      headline = boldMatch[1].trim();
    } else {
      const firstLine = analysisText.split('\n').map((s) => s.trim()).find((s) => s.length > 10);
      if (firstLine) {
        headline = firstLine.replace(/^[#\-*\d.\s]+/, '').replace(/[:：]$/, '').trim();
      }
    }
  }
  if (!headline || headline.length > 90) {
    headline = question ? `تحلیل هوشمند: ${question}` : 'گزارش بصری و تحلیل داده‌ها';
  }

  let numericCol = null;
  let labelCol = null;

  if (rows.length > 0) {
    const firstRow = rows[0];
    for (const key of Object.keys(firstRow)) {
      const val = firstRow[key];
      if (typeof val === 'number') {
        numericCol = numericCol || key;
      } else if (typeof val === 'string' && !labelCol) {
        labelCol = key;
      }
    }
  }

  let totalSum = 0;
  let maxItem = null;
  let maxValue = -Infinity;
  const itemMap = [];

  rows.forEach((r) => {
    const numVal = numericCol && typeof r[numericCol] === 'number' ? r[numericCol] : 1;
    totalSum += numVal;
    const label = labelCol && r[labelCol] ? String(r[labelCol]) : `مورد ${itemMap.length + 1}`;
    if (numVal > maxValue) {
      maxValue = numVal;
      maxItem = label;
    }
    itemMap.push({ label, value: numVal });
  });

  itemMap.sort((a, b) => b.value - a.value);

  const topBreakdown = itemMap.slice(0, 4).map((it) => {
    const pct = totalSum > 0 ? ((it.value / totalSum) * 100).toFixed(1) : (100 / Math.max(1, rows.length)).toFixed(1);
    return {
      label: it.label,
      value: it.value,
      pct: toFaDigits(pct) + '٪',
      pctNum: Number(pct),
    };
  });

  const kpi1 = {
    label: numericCol ? 'حجم کل تراکنش‌ها / داده‌ها' : 'تعداد کل رکوردها',
    value: numericCol ? formatPersianNumber(totalSum) : toFaDigits(rows.length),
    subtext: 'رشد مثبت داده‌محور 📈',
  };

  const avgVal = rows.length > 0 ? totalSum / rows.length : 0;
  const kpi2 = {
    label: maxItem ? `برترین: ${maxItem}` : 'میانگین مقادیر',
    value: maxItem ? formatPersianNumber(maxValue) : formatPersianNumber(avgVal),
    subtext: maxItem ? 'بیشترین سهم ثبت‌شده ⚡' : 'میانگین محاسبه‌شده 🎯',
  };

  return {
    headline,
    subhead: 'روایت داده‌محور از تحلیل هوشمند هوش تجاری',
    dateStr: toFaDigits(new Date().toLocaleDateString('fa-IR')),
    kpi1,
    kpi2,
    topBreakdown,
  };
}

function exportPosterAsPng(info, filename = 'analysis_poster.png') {
  try {
    const width = 800;
    const items = (info && info.topBreakdown) || [];
    const height = Math.max(540, 360 + items.length * 55 + 90);

    const canvas = document.createElement('canvas');
    canvas.width = width * 2;
    canvas.height = height * 2;
    const ctx = canvas.getContext('2d');
    ctx.scale(2, 2);

    // Background Gradient Container
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, '#ffffff');
    gradient.addColorStop(1, '#f4f9f6');

    ctx.fillStyle = gradient;
    ctx.beginPath();
    if (ctx.roundRect) {
      ctx.roundRect(0, 0, width, height, 20);
    } else {
      ctx.rect(0, 0, width, height);
    }
    ctx.fill();

    ctx.strokeStyle = 'rgba(5, 150, 105, 0.2)';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Topbar Brand
    ctx.fillStyle = '#059669';
    ctx.beginPath();
    ctx.arc(width - 45, 40, 6, 0, Math.PI * 2);
    ctx.fill();

    ctx.font = 'bold 18px Vazirmatn, sans-serif';
    ctx.textAlign = 'right';
    ctx.fillStyle = '#059669';
    ctx.fillText('پلتفرم تحلیلی', width - 60, 46);

    ctx.font = '13px Vazirmatn, sans-serif';
    ctx.fillStyle = '#7a9e90';
    ctx.fillText('دستیار هوش تجاری', width - 155, 46);

    // Pill Badge
    ctx.fillStyle = 'rgba(5, 150, 105, 0.1)';
    ctx.beginPath();
    if (ctx.roundRect) {
      ctx.roundRect(35, 26, 220, 32, 16);
    } else {
      ctx.rect(35, 26, 220, 32);
    }
    ctx.fill();

    ctx.font = 'bold 13px Vazirmatn, sans-serif';
    ctx.fillStyle = '#047857';
    ctx.textAlign = 'right';
    ctx.fillText('📈 داده‌ها از رشد حکایت می‌کنند', 235, 47);

    // Topbar Divider
    ctx.strokeStyle = 'rgba(5, 150, 105, 0.12)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(35, 75);
    ctx.lineTo(width - 35, 75);
    ctx.stroke();

    // Headline
    ctx.textAlign = 'center';
    ctx.font = 'bold 21px Vazirmatn, sans-serif';
    ctx.fillStyle = '#0f2a1f';
    const headline = (info && info.headline) || 'گزارش تحلیلی داده‌محور';
    ctx.fillText(headline, width / 2, 120);

    // Subhead
    ctx.font = '14px Vazirmatn, sans-serif';
    ctx.fillStyle = '#5a7a6d';
    const subtext = `${(info && info.subhead) || 'روایت داده‌محور از تحلیل هوشمند'}   |   ${(info && info.dateStr) || ''}`;
    ctx.fillText(subtext, width / 2, 150);

    // KPI Cards Grid (2 Cards)
    const cardW = (width - 90) / 2;
    const cardH = 120;
    const cardY = 180;

    // KPI Card 1 (Right)
    const card1X = width - 35 - cardW;
    ctx.fillStyle = '#ffffff';
    ctx.strokeStyle = 'rgba(5, 150, 105, 0.15)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(card1X, cardY, cardW, cardH, 16);
    else ctx.rect(card1X, cardY, cardW, cardH);
    ctx.fill();
    ctx.stroke();

    ctx.textAlign = 'right';
    ctx.font = '14px Vazirmatn, sans-serif';
    ctx.fillStyle = '#5a7a6d';
    ctx.fillText(`📊  ${(info && info.kpi1 && info.kpi1.label) || ''}`, card1X + cardW - 20, cardY + 32);

    ctx.font = 'bold 24px Vazirmatn, sans-serif';
    ctx.fillStyle = '#059669';
    ctx.fillText((info && info.kpi1 && info.kpi1.value) || '', card1X + cardW - 20, cardY + 70);

    ctx.font = 'bold 12px Vazirmatn, sans-serif';
    ctx.fillStyle = '#047857';
    ctx.fillText(`↗  ${(info && info.kpi1 && info.kpi1.subtext) || ''}`, card1X + cardW - 20, cardY + 98);

    // KPI Card 2 (Left)
    const card2X = 35;
    ctx.fillStyle = '#ffffff';
    ctx.strokeStyle = 'rgba(5, 150, 105, 0.15)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(card2X, cardY, cardW, cardH, 16);
    else ctx.rect(card2X, cardY, cardW, cardH);
    ctx.fill();
    ctx.stroke();

    ctx.textAlign = 'right';
    ctx.font = '14px Vazirmatn, sans-serif';
    ctx.fillStyle = '#5a7a6d';
    ctx.fillText(`⚡  ${(info && info.kpi2 && info.kpi2.label) || ''}`, card2X + cardW - 20, cardY + 32);

    ctx.font = 'bold 24px Vazirmatn, sans-serif';
    ctx.fillStyle = '#059669';
    ctx.fillText((info && info.kpi2 && info.kpi2.value) || '', card2X + cardW - 20, cardY + 70);

    ctx.font = 'bold 12px Vazirmatn, sans-serif';
    ctx.fillStyle = '#047857';
    ctx.fillText(`↗  ${(info && info.kpi2 && info.kpi2.subtext) || ''}`, card2X + cardW - 20, cardY + 98);

    // Dark Accent Box
    if (items.length > 0) {
      const darkY = 320;
      const darkH = 60 + items.length * 52;
      ctx.fillStyle = '#0f2a1f';
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(35, darkY, width - 70, darkH, 18);
      else ctx.rect(35, darkY, width - 70, darkH);
      ctx.fill();

      ctx.textAlign = 'right';
      ctx.font = 'bold 16px Vazirmatn, sans-serif';
      ctx.fillStyle = '#a7f3d0';
      ctx.fillText('🎯  برترین دسته‌ها و بیشترین سهم', width - 60, darkY + 35);

      ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(55, darkY + 48);
      ctx.lineTo(width - 55, darkY + 48);
      ctx.stroke();

      let itemY = darkY + 82;
      items.forEach((item) => {
        ctx.textAlign = 'right';
        ctx.font = '14px Vazirmatn, sans-serif';
        ctx.fillStyle = '#ffffff';
        ctx.fillText(`🔹 ${item.label}`, width - 60, itemY);

        const barX = 140;
        const barW = width - 390;
        const barPctW = (barW * Math.min(100, Math.max(8, item.pctNum))) / 100;

        ctx.fillStyle = 'rgba(255, 255, 255, 0.12)';
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(barX, itemY - 11, barW, 8, 4);
        else ctx.rect(barX, itemY - 11, barW, 8);
        ctx.fill();

        ctx.fillStyle = '#34d399';
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(barX, itemY - 11, barPctW, 8, 4);
        else ctx.rect(barX, itemY - 11, barPctW, 8);
        ctx.fill();

        ctx.textAlign = 'right';
        ctx.font = 'bold 15px Vazirmatn, sans-serif';
        ctx.fillStyle = '#34d399';
        ctx.fillText(item.pct, 125, itemY);

        itemY += 50;
      });
    }

    // Footer Stamp
    const footerY = height - 30;
    ctx.strokeStyle = 'rgba(5, 150, 105, 0.12)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(35, footerY - 15);
    ctx.lineTo(width - 35, footerY - 15);
    ctx.stroke();

    ctx.textAlign = 'right';
    ctx.font = '12px Vazirmatn, sans-serif';
    ctx.fillStyle = '#7a9e90';
    ctx.fillText('📄  منبع: دستیار هوشمند هوش تجاری', width - 35, footerY);

    ctx.textAlign = 'left';
    ctx.font = 'bold 12px Vazirmatn, sans-serif';
    ctx.fillStyle = '#047857';
    ctx.fillText('گزارش تصویری داده‌محور', 35, footerY);

    // Canvas Data URL Export
    const dataUrl = canvas.toDataURL('image/png');
    const a = document.createElement('a');
    a.download = filename;
    a.href = dataUrl;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  } catch (err) {
    console.error('Canvas poster export error:', err);
    alert('خطا در تولید تصویر پوستر.');
  }
}

function renderInfographicPoster(stripEl, question, data, analysisText) {
  let posterWrap = stripEl.querySelector('.analysis-poster-wrapper');
  if (!posterWrap) {
    posterWrap = document.createElement('div');
    posterWrap.className = 'analysis-poster-wrapper';
    const textEl = stripEl.querySelector('.analysis-text');
    if (textEl && textEl.parentNode) {
      textEl.parentNode.insertBefore(posterWrap, textEl.nextSibling);
    } else {
      stripEl.appendChild(posterWrap);
    }
  }

  const info = buildInfographicData(data, analysisText, question);

  const breakdownRows = info.topBreakdown.map((item) => `
    <div class="poster-dark-item">
      <div class="poster-item-info">
        <span>🔹</span>
        <span class="poster-item-name">${escapeHtml(item.label)}</span>
      </div>
      <div class="poster-item-bar-wrap">
        <div class="poster-item-bar" style="width: ${Math.min(100, Math.max(8, item.pctNum))}%"></div>
      </div>
      <span class="poster-item-pct">${escapeHtml(item.pct)}</span>
    </div>
  `).join('');

  posterWrap.innerHTML = `
    <div class="poster-actions">
      <button type="button" class="poster-export-btn" title="دانلود تصویر پوستر با کیفیت بالا">
        <span aria-hidden="true">📥</span>
        <span>دانلود تصویر پوستر (PNG)</span>
      </button>
    </div>
    <div class="analysis-infographic-poster" id="poster-${Date.now()}">
      <div class="poster-topbar">
        <div class="poster-brand">
          <span class="poster-logo-dot"></span>
          <span class="poster-brand-name">پلتفرم تحلیلی</span>
          <span class="poster-brand-sub">دستیار هوش تجاری</span>
        </div>
        <div class="poster-badge">
          <span class="poster-badge-icon">📈</span>
          <span>داده‌ها از رشد حکایت می‌کنند</span>
        </div>
      </div>

      <div class="poster-hero">
        <h3 class="poster-headline"${dirAttr(info.headline)}>${escapeHtml(info.headline)}</h3>
        <div class="poster-subhead">
          <span>${escapeHtml(info.subhead)}</span>
          <span class="poster-divider">|</span>
          <span>${escapeHtml(info.dateStr)}</span>
        </div>
      </div>

      <div class="poster-kpi-grid">
        <div class="poster-kpi-card">
          <div class="poster-kpi-header">
            <span class="poster-kpi-icon">📊</span>
            <span class="poster-kpi-label">${escapeHtml(info.kpi1.label)}</span>
          </div>
          <div class="poster-kpi-value">${escapeHtml(info.kpi1.value)}</div>
          <div class="poster-kpi-trend">
            <span class="poster-trend-arrow">↗</span>
            <span>${escapeHtml(info.kpi1.subtext)}</span>
          </div>
        </div>

        <div class="poster-kpi-card">
          <div class="poster-kpi-header">
            <span class="poster-kpi-icon">⚡</span>
            <span class="poster-kpi-label">${escapeHtml(info.kpi2.label)}</span>
          </div>
          <div class="poster-kpi-value">${escapeHtml(info.kpi2.value)}</div>
          <div class="poster-kpi-trend">
            <span class="poster-trend-arrow">↗</span>
            <span>${escapeHtml(info.kpi2.subtext)}</span>
          </div>
        </div>
      </div>

      ${breakdownRows ? `
      <div class="poster-dark-box">
        <div class="poster-dark-header">
          <span class="poster-dark-icon">🎯</span>
          <span>برترین دسته‌ها و بیشترین سهم</span>
        </div>
        <div class="poster-dark-list">
          ${breakdownRows}
        </div>
      </div>
      ` : ''}

      <div class="poster-footer">
        <div class="poster-source-stamp">
          <span class="poster-stamp-icon">📄</span>
          <span>منبع: دستیار هوشمند هوش تجاری</span>
        </div>
        <div class="poster-watermark">گزارش تصویری داده‌محور</div>
      </div>
    </div>
  `;

  const exportBtn = posterWrap.querySelector('.poster-export-btn');
  if (exportBtn) {
    exportBtn.addEventListener('click', () => {
      exportPosterAsPng(info, `analysis_poster_${Date.now()}.png`);
    });
  }
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
        data: data.slice(0, 80),
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

    renderInfographicPoster(stripEl, question, data, json.analysis);

    btn.textContent = chatUiText('analyzeAgain');
    if (state.lastResponse) {
      state.lastResponse.analysis = json.analysis;
    }
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

function extractCorrectedSnippet(aiContent) {
  let text = String(aiContent || '').trim();
  if (!text) return '';

  const markerRe = /(?:^|\n)\s*(?:CORRECTED_SNIPPET|اصلاح|متن اصلاح‌شده|متن اصلاح شده|تکه اصلاح‌شده|تکه اصلاح شده|بخش اصلاح‌شده|بخش اصلاح شده)\s*:\s*/i;
  const match = text.match(markerRe);
  if (match) {
    const idx = text.indexOf(match[0]);
    text = text.slice(idx + match[0].length).trim();
  }

  const codeBlockMatch = text.match(/```(?:markdown|text)?\s*([\s\S]+?)\s*```/i);
  if (codeBlockMatch) {
    text = codeBlockMatch[1].trim();
  }

  text = text.replace(/^[`"':«»\s]*?(?:markdown|text)\b/i, '');
  text = text.replace(/^[`"':«»\s]+|[`"':«»\s]+$/g, '').trim();
  return text;
}

function replaceSnippetInText(text, snippet, replacement) {
  const source = String(text || '');
  const focus = String(snippet || '').trim();
  const repl = String(replacement || '').trim();
  if (!source || !repl) return null;

  if (!focus || focus === source.trim()) {
    return repl;
  }

  // Stage 1: Exact literal match
  if (source.includes(focus)) {
    return source.replace(focus, repl);
  }

  // Stage 2: Normalized whitespace & ZWNJ match
  const normFocus = focus.replace(/[\s\u200c]+/g, ' ').trim();
  const normSource = source.replace(/[\s\u200c]+/g, ' ');
  const escapedNormFocus = normFocus.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const stage2Re = new RegExp(escapedNormFocus.replace(/ /g, '[\\s\\u200c]+'));
  const stage2Match = source.match(stage2Re);
  if (stage2Match) {
    return source.replace(stage2Match[0], repl);
  }

  // Stage 3: Markdown-Flexible Word Sequence Match
  const words = focus.match(/[\p{L}\p{N}]+/gu) || [];
  if (words.length >= 2) {
    const escapedWords = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    const stage3Pattern = escapedWords.join('[\\*\\_\\#\\`\\-\\>\\:\\s\\u200c]*');
    try {
      const stage3Re = new RegExp(stage3Pattern, 'u');
      const stage3Match = source.match(stage3Re);
      if (stage3Match) {
        return source.replace(stage3Match[0], repl);
      }
    } catch (_) {}
  }

  // Stage 4: Plain-Text Index Mapping
  let plainSource = '';
  const indexMap = [];
  for (let i = 0; i < source.length; i++) {
    const char = source[i];
    if (char === '*' || char === '_' || char === '#' || char === '`') {
      continue;
    }
    plainSource += char;
    indexMap.push(i);
  }

  const plainFocus = focus.replace(/[\*\_\#\`]/g, '').trim();
  if (plainFocus && plainSource.includes(plainFocus)) {
    const plainIdx = plainSource.indexOf(plainFocus);
    const srcStart = indexMap[plainIdx];
    const srcEndIndex = plainIdx + plainFocus.length - 1;
    const srcEnd = srcEndIndex < indexMap.length ? indexMap[srcEndIndex] + 1 : source.length;
    return source.slice(0, srcStart) + repl + source.slice(srcEnd);
  }

  // Stage 5: Paragraph / Sentence Token Overlap
  const paragraphs = source.split(/\n\s*\n/);
  if (paragraphs.length > 1 && words.length >= 2) {
    let bestParaIdx = -1;
    let maxOverlap = 0;
    const focusSet = new Set(words.map((w) => w.toLowerCase()));

    for (let p = 0; p < paragraphs.length; p++) {
      const paraWords = (paragraphs[p].match(/[\p{L}\p{N}]+/gu) || []).map((w) => w.toLowerCase());
      let overlap = 0;
      for (const w of paraWords) {
        if (focusSet.has(w)) overlap++;
      }
      const score = overlap / Math.max(focusSet.size, 1);
      if (score > maxOverlap && score >= 0.3) {
        maxOverlap = score;
        bestParaIdx = p;
      }
    }

    if (bestParaIdx !== -1) {
      paragraphs[bestParaIdx] = repl;
      return paragraphs.join('\n\n');
    }
  }

  return null;
}

function applySnippetToAnalysis(stripEl, focusSnippet, aiContent) {
  const textEl = stripEl.querySelector('.analysis-text');
  const placeholder = stripEl.querySelector('.analysis-placeholder');
  if (!textEl) return false;

  const focus = String(focusSnippet || '').trim();
  const currentText =
    (state.lastResponse && state.lastResponse.analysis) ||
    (textEl.innerText || textEl.textContent || '').trim();
  const replacement = extractCorrectedSnippet(aiContent);
  if (!replacement) return false;

  const newAnalysis = replaceSnippetInText(currentText, focus, replacement);
  if (!newAnalysis) {
    alert(chatUiText('discussApplyNoFocus'));
    return false;
  }

  if (placeholder) placeholder.hidden = true;
  textEl.hidden = false;
  textEl.className = 'analysis-text analysis-text--ready';
  textEl.setAttribute('dir', isRtlText(newAnalysis) ? 'rtl' : 'ltr');
  textEl.innerHTML = formatAnalysisHtml(newAnalysis);

  // Flash update animation for immediate user visual feedback
  textEl.classList.remove('analysis-updated-flash');
  void textEl.offsetWidth;
  textEl.classList.add('analysis-updated-flash');

  if (state.lastResponse) state.lastResponse.analysis = newAnalysis;
  renderInfographicPoster(stripEl, '', (state.lastResponse && state.lastResponse.data) || [], newAnalysis);
  return true;
}

function wireDiscussPanel(stripEl, ctx) {
  const section = stripEl.querySelector('.discuss-section');
  if (!section) return;

  const headerEl = section.querySelector('.discuss-header');
  if (headerEl) {
    headerEl.addEventListener('click', () => {
      section.classList.toggle('is-open');
    });
  }

  const threadEl = section.querySelector('.discuss-thread');
  const inputEl = section.querySelector('.discuss-input');
  const focusEl = section.querySelector('.discuss-focus');
  const sendBtn = section.querySelector('.discuss-send-btn');
  const history = [];

  // Selecting text in the analysis fills the focus box
  const analysisText = stripEl.querySelector('.analysis-text');
  if (analysisText) {
    analysisText.addEventListener('mouseup', () => {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed) return;
      if (!analysisText.contains(sel.anchorNode)) return;
      const selected = String(sel.toString() || '').trim();
      if (selected.length < 3 || selected.length > 800) return;
      if (focusEl) focusEl.value = selected;
    });
  }

  function appendBubble(role, content, focusSnippet = '') {
    if (threadEl.dataset.empty === '1') {
      threadEl.innerHTML = '';
      threadEl.dataset.empty = '0';
    }
    const isUser = role === 'user';
    const label = isUser ? chatUiText('discussYou') : chatUiText('discussAi');
    const bubble = document.createElement('div');
    bubble.className = `discuss-bubble discuss-bubble--${isUser ? 'user' : 'ai'}`;
    if (!isUser && focusSnippet) bubble.dataset.focus = focusSnippet;
    bubble.innerHTML = `
      <div class="discuss-meta">${escapeHtml(label)}</div>
      <div class="discuss-content"${dirAttr(content)}>${isUser ? escapeHtml(content).replace(/\n/g, '<br>') : formatAnalysisHtml(content)}</div>
      ${!isUser ? `<button type="button" class="ghost-btn tiny discuss-apply-btn">${escapeHtml(chatUiText('discussApply'))}</button>` : ''}
    `;
    threadEl.appendChild(bubble);
    const applyBtn = bubble.querySelector('.discuss-apply-btn');
    if (applyBtn) {
      applyBtn.addEventListener('click', () => {
        const focus = bubble.dataset.focus || (focusEl && focusEl.value) || '';
        applySnippetToAnalysis(stripEl, focus, content);
      });
    }
    threadEl.scrollTop = threadEl.scrollHeight;
  }

  async function sendDiscussion() {
    const typedMessage = (inputEl.value || '').trim();
    const focus = (focusEl.value || '').trim();
    const message = typedMessage || focus;
    if (!message) {
      alert(chatUiText('discussEmptyInput'));
      inputEl.focus();
      return;
    }
    const analysis =
      (state.lastResponse && state.lastResponse.analysis) ||
      (stripEl.querySelector('.analysis-text')?.innerText || '').trim();

    sendBtn.disabled = true;
    sendBtn.textContent = chatUiText('discussSending');
    const turnFocus = focus;
    appendBubble('user', message);
    inputEl.value = '';
    history.push({ role: 'user', content: message });

    try {
      const res = await apiFetch('/api/discuss', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          focus,
          analysis,
          data: (ctx.data || []).slice(0, 80),
          history: history.slice(0, -1), // prior turns only
          original_question: ctx.question || '',
          language: ctx.language || state.language,
          provider: ctx.provider || state.provider,
        }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        appendBubble('assistant', json.error || 'Discussion failed.');
        return;
      }
      const reply = json.reply || '';
      history.push({ role: 'assistant', content: reply });
      appendBubble('assistant', reply, turnFocus);
    } catch (_) {
      appendBubble(
        'assistant',
        state.language === 'fa' ? 'خطا در ارتباط با سرور برای بحث.' : 'Network error during discussion.'
      );
    } finally {
      sendBtn.disabled = false;
      sendBtn.textContent = chatUiText('discussSend');
      chatArea.scrollTop = chatArea.scrollHeight;
    }
  }

  sendBtn.addEventListener('click', sendDiscussion);
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendDiscussion();
    }
  });
}

const TABLE_PAGE_SIZES = [50, 100, 250, 500, 1000];
const DEFAULT_TABLE_PAGE_SIZE = 250;

const COLUMN_LABELS = {
  // dim_date
  date_key: 'کلید تاریخ',
  full_date: 'تاریخ',
  day_name: 'نام روز',
  month_name: 'نام ماه',
  year: 'سال',
  month: 'ماه',
  day: 'روز',
  is_weekend: 'آخر هفته',
  is_holiday: 'تعطیل',
  // dim_customer
  customer_id: 'شناسه مشتری',
  customer_name: 'نام مشتری',
  access_key: 'کلید دسترسی',
  role: 'نقش',
  // dim_category
  category_id: 'شناسه دسته‌بندی',
  category_name: 'نام دسته‌بندی',
  category: 'دسته‌بندی',
  // dim_merchant
  merchant_id: 'شناسه پذیرنده',
  merchant_name: 'نام پذیرنده',
  merchant_code: 'کد پذیرنده',
  mcc: 'کد صنف (MCC)',
  city: 'شهر',
  owner_customer_id: 'شناسه مشتری مالک',
  is_active: 'فعال',
  // dim_terminal
  terminal_id: 'شناسه ترمینال',
  terminal_serial: 'سریال ترمینال',
  terminal_type: 'نوع ترمینال',
  install_date: 'تاریخ نصب',
  status: 'وضعیت',
  // fact_transactions
  transaction_id: 'شناسه تراکنش',
  transaction_time: 'زمان تراکنش',
  amount: 'مبلغ',
  currency: 'واحد پول',
  card_pan_masked: 'شماره کارت',
  response_code: 'کد پاسخ',
  settlement_date: 'تاریخ تسویه',
  channel: 'کانال',
  // common query aliases / aggregates
  transaction_count: 'تعداد تراکنش',
  txn_count: 'تعداد تراکنش',
  tx_count: 'تعداد تراکنش',
  cnt: 'تعداد',
  count: 'تعداد',
  row_count: 'تعداد ردیف',
  total_amount: 'مجموع مبلغ',
  sum_amount: 'مجموع مبلغ',
  amount_sum: 'مجموع مبلغ',
  total_sales: 'مجموع فروش',
  total_volume: 'مجموع حجم تراکنش',
  avg_amount: 'میانگین مبلغ',
  average_amount: 'میانگین مبلغ',
  min_amount: 'حداقل مبلغ',
  max_amount: 'حداکثر مبلغ',
  transaction_month: 'ماه تراکنش',
  txn_month: 'ماه تراکنش',
  year_month: 'سال-ماه',
  ym: 'سال-ماه',
  avg_growth: 'میانگین نرخ رشد',
  growth_rate: 'نرخ رشد',
  growth: 'رشد',
  sales: 'فروش',
  volume: 'حجم',
  name: 'نام',
  id: 'شناسه',
  rank: 'رتبه',
  pct: 'درصد',
  percent: 'درصد',
  percentage: 'درصد',
  share: 'سهم',
  ratio: 'نسبت',
};

const COLUMN_WORD_FA = {
  date: 'تاریخ',
  key: 'کلید',
  full: 'کامل',
  day: 'روز',
  name: 'نام',
  month: 'ماه',
  year: 'سال',
  is: '',
  weekend: 'آخر هفته',
  holiday: 'تعطیل',
  customer: 'مشتری',
  id: 'شناسه',
  access: 'دسترسی',
  role: 'نقش',
  category: 'دسته‌بندی',
  merchant: 'پذیرنده',
  code: 'کد',
  mcc: 'MCC',
  city: 'شهر',
  owner: 'مالک',
  active: 'فعال',
  terminal: 'ترمینال',
  serial: 'سریال',
  type: 'نوع',
  install: 'نصب',
  status: 'وضعیت',
  transaction: 'تراکنش',
  txn: 'تراکنش',
  tx: 'تراکنش',
  time: 'زمان',
  amount: 'مبلغ',
  currency: 'واحد پول',
  card: 'کارت',
  pan: 'PAN',
  masked: 'ماسک‌شده',
  response: 'پاسخ',
  settlement: 'تسویه',
  channel: 'کانال',
  count: 'تعداد',
  cnt: 'تعداد',
  total: 'مجموع',
  sum: 'جمع',
  avg: 'میانگین',
  average: 'میانگین',
  min: 'حداقل',
  max: 'حداکثر',
  growth: 'رشد',
  rate: 'نرخ',
  sales: 'فروش',
  volume: 'حجم',
  row: 'ردیف',
  rank: 'رتبه',
  pct: 'درصد',
  percent: 'درصد',
  percentage: 'درصد',
  share: 'سهم',
  ratio: 'نسبت',
  num: 'تعداد',
  number: 'تعداد',
  qty: 'تعداد',
  quantity: 'تعداد',
  value: 'مقدار',
  price: 'قیمت',
  fee: 'کارمزد',
  approved: 'موفق',
  declined: 'ناموفق',
  reversed: 'برگشتی',
};

function columnLabel(key) {
  if (key === null || key === undefined) return '';
  const raw = String(key).trim();
  if (!raw) return '';
  if (COLUMN_LABELS[raw]) return COLUMN_LABELS[raw];
  const lower = raw.toLowerCase();
  if (COLUMN_LABELS[lower]) return COLUMN_LABELS[lower];
  // Keep Persian SQL aliases as-is.
  if (isRtlText(raw) || raw.includes('\u200c')) return raw;

  const spaced = raw.replace(/([a-z])([A-Z])/g, '$1_$2');
  const parts = spaced.toLowerCase().split(/[_\s]+/).filter(Boolean);
  if (!parts.length) return raw;

  const translated = [];
  let hasFa = false;
  for (const part of parts) {
    if (Object.prototype.hasOwnProperty.call(COLUMN_WORD_FA, part)) {
      const fa = COLUMN_WORD_FA[part];
      if (fa) {
        translated.push(fa);
        if (isRtlText(fa)) hasFa = true;
      }
    } else {
      translated.push(part);
    }
  }
  if (translated.length && hasFa) return translated.join(' ');
  return raw.replace(/_/g, ' ');
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
// Advanced Apache ECharts Engine — 10 Chart Families & Intelligent Auto-Selection
// ---------------------------------------------------------------------------
const CHART_MAX_ITEMS = 30;
const CHART_PALETTE = [
  '#1f6f54', '#2d8f6f', '#3aaf88', '#4ec4a0', '#c45c26',
  '#d4842d', '#e8a84b', '#5b7cfa', '#7c5cfc', '#9b6bff',
  '#a13d2f', '#c75545', '#6b5b95', '#8b7ab8', '#88b04b',
  '#6d9a3c', '#2a9d8f', '#264653', '#e76f51', '#f4a261',
];

const CHART_TYPE_OPTIONS = [
  { id: 'bar', group: 'bar', labelFa: 'میله‌ای عمودی', labelEn: 'Vertical Bar', icon: '📊' },
  { id: 'barHorizontal', group: 'bar', labelFa: 'میله‌ای افقی', labelEn: 'Horizontal Bar', icon: '📋' },
  { id: 'barStacked', group: 'bar', labelFa: 'میله‌ای پشته‌ای', labelEn: 'Stacked Bar', icon: '📚' },
  { id: 'line', group: 'line', labelFa: 'خطی', labelEn: 'Line Chart', icon: '📈' },
  { id: 'area', group: 'line', labelFa: 'مساحتی با گرادیان', labelEn: 'Area Chart', icon: '📉' },
  { id: 'lineSmooth', group: 'line', labelFa: 'خطی نرم (پیوسته)', labelEn: 'Smooth Line', icon: '〰️' },
  { id: 'pie', group: 'pie', labelFa: 'دایره‌ای (پای)', labelEn: 'Pie Chart', icon: '🥧' },
  { id: 'doughnut', group: 'pie', labelFa: 'حلقه‌ای (دونات)', labelEn: 'Donut Chart', icon: '🍩' },
  { id: 'rose', group: 'pie', labelFa: 'گل سرخ نایتینگل', labelEn: 'Nightingale Rose', icon: '🌹' },
  { id: 'funnel', group: 'advanced', labelFa: 'قیفی (مراحل تبدیل)', labelEn: 'Funnel Chart', icon: '🔻' },
  { id: 'gauge', group: 'advanced', labelFa: 'گیج و سرعت‌سنج (KPI)', labelEn: 'Gauge / Speedometer', icon: '🧭' },
  { id: 'geoMap', group: 'advanced', labelFa: 'نقشه استانی و مکانی ایران', labelEn: 'Iran Geo Map', icon: '🗺️' },
  { id: 'sankey', group: 'advanced', labelFa: 'سانکی و جریان داده', labelEn: 'Sankey Flow', icon: '🔀' },
  { id: 'treemap', group: 'advanced', labelFa: 'نقشه درختی سلسله‌مراتبی', labelEn: 'Treemap', icon: '🔲' },
  { id: 'heatmap', group: 'advanced', labelFa: 'نقشه حرارتی ماتریسی', labelEn: 'Heatmap Matrix', icon: '🌡️' },
  { id: 'candlestick', group: 'advanced', labelFa: 'شمعی ژاپنی (دامنه نوسان)', labelEn: 'Candlestick / OHLC', icon: '🕯️' },
];

const IRAN_CITY_COORDINATES = {
  // Major Cities
  'تهران': [51.3890, 35.6892],
  'tehran': [51.3890, 35.6892],
  'اصفهان': [51.6660, 32.6539],
  'esfahan': [51.6660, 32.6539],
  'isfahan': [51.6660, 32.6539],
  'مشهد': [59.6067, 36.2972],
  'mashhad': [59.6067, 36.2972],
  'تبریز': [46.2919, 38.0800],
  'tabriz': [46.2919, 38.0800],
  'شیراز': [52.5836, 29.5918],
  'shiraz': [52.5836, 29.5918],
  'اهواز': [48.6706, 31.3183],
  'ahvaz': [48.6706, 31.3183],
  'ahwaz': [48.6706, 31.3183],
  'کرج': [50.9916, 35.8327],
  'karaj': [50.9916, 35.8327],
  'قم': [50.8764, 34.6399],
  'qom': [50.8764, 34.6399],
  'رشت': [49.5832, 37.2808],
  'rasht': [49.5832, 37.2808],
  'کرمان': [57.0788, 30.2839],
  'kerman': [57.0788, 30.2839],
  'یزد': [54.3675, 31.8974],
  'yazd': [54.3675, 31.8974],
  'ارومیه': [45.0760, 37.5527],
  'urmia': [45.0760, 37.5527],
  'زاهدان': [60.8629, 29.4963],
  'zahedan': [60.8629, 29.4963],
  'کرمانشاه': [47.0778, 34.3142],
  'kermanshah': [47.0778, 34.3142],
  'بندرعباس': [56.2808, 27.1832],
  'بندر عباس': [56.2808, 27.1832],
  'bandar abbas': [56.2808, 27.1832],
  'همدان': [48.5146, 34.7989],
  'hamedan': [48.5146, 34.7989],
  'قزوین': [50.0031, 36.2797],
  'qazvin': [50.0031, 36.2797],
  'ساری': [53.0601, 36.5659],
  'sari': [53.0601, 36.5659],
  'گرگان': [54.4348, 36.8430],
  'gorgan': [54.4348, 36.8430],
  'زنجان': [48.4787, 36.6736],
  'zanjan': [48.4787, 36.6736],
  'سنندج': [46.9988, 35.3219],
  'sanandaj': [46.9988, 35.3219],
  'خرم‌آباد': [48.3558, 33.4878],
  'خرم آباد': [48.3558, 33.4878],
  'khorramabad': [48.3558, 33.4878],
  'بوشهر': [50.8385, 28.9234],
  'bushehr': [50.8385, 28.9234],
  'بیرجند': [59.2211, 32.8663],
  'birjand': [59.2211, 32.8663],
  'ایلام': [46.4225, 33.6374],
  'ilam': [46.4225, 33.6374],
  'بجنورد': [57.3283, 37.4747],
  'bojnourd': [57.3283, 37.4747],
  'شهرکرد': [50.8576, 32.3256],
  'shahrekord': [50.8576, 32.3256],
  'سمنان': [53.3934, 35.5769],
  'semnan': [53.3934, 35.5769],
  'یاسوج': [51.5876, 30.6684],
  'yasuj': [51.5876, 30.6684],
  'اراک': [49.6892, 34.0954],
  'arak': [49.6892, 34.0954],
  'اردبیل': [48.2973, 38.2498],
  'ardabil': [48.2973, 38.2498],
  'کیش': [53.9786, 26.5325],
  'kish': [53.9786, 26.5325],
  'قشم': [55.9926, 26.8833],
  'qeshm': [55.9926, 26.8833],
  'کاشان': [51.4428, 33.9850],
  'kashan': [51.4428, 33.9850],
  'دزفول': [48.4069, 32.3838],
  'dezful': [48.4069, 32.3838],
  'آبادان': [48.2933, 30.3392],
  'abadan': [48.2933, 30.3392],
  'نیشابور': [58.7958, 36.2133],
  'neyshabur': [58.7958, 36.2133],
  'بابل': [52.6782, 36.5444],
  'babol': [52.6782, 36.5444],
  'آمل': [52.3553, 36.4676],
  'amol': [52.3553, 36.4676],
  'ساوه': [50.3592, 35.0211],
  'saveh': [50.3592, 35.0211],
  'مراغه': [46.2417, 37.3917],
  'maragheh': [46.2417, 37.3917],
  'سیرجان': [55.6814, 29.4520],
  'sirjan': [55.6814, 29.4520],
  // Provinces
  'خراسان رضوی': [59.6067, 36.2972],
  'خراسان جنوبی': [59.2211, 32.8663],
  'خراسان شمالی': [57.3283, 37.4747],
  'آذربایجان شرقی': [46.2919, 38.0800],
  'آذربایجان غربی': [45.0760, 37.5527],
  'چهارمحال و بختیاری': [50.8576, 32.3256],
  'کهگیلویه و بویراحمد': [51.5876, 30.6684],
  'سیستان و بلوچستان': [60.8629, 29.4963],
  'مازندران': [53.0601, 36.5659],
  'گیلان': [49.5832, 37.2808],
  'گلستان': [54.4348, 36.8430],
  'هرمزگان': [56.2808, 27.1832],
  'خوزستان': [48.6706, 31.3183],
  'مرکزی': [49.6892, 34.0954],
  'لرستان': [48.3558, 33.4878],
  'کردستان': [46.9988, 35.3219],
  'فارس': [52.5836, 29.5918],
  'البرز': [50.9916, 35.8327],
};

let iranMapRegistered = false;
let iranMapPromise = null;

function ensureIranMapRegistered() {
  if (iranMapRegistered || typeof echarts === 'undefined') return Promise.resolve(true);
  if (iranMapPromise) return iranMapPromise;
  const url = typeof window !== 'undefined' && window.location && window.location.origin
    ? `${window.location.origin}/static/vendor/iran.json`
    : '/static/vendor/iran.json';
  iranMapPromise = fetch(url)
    .then((res) => {
      if (!res.ok) throw new Error('Failed to load iran.json: ' + res.status);
      return res.json();
    })
    .then((geoJson) => {
      echarts.registerMap('iran', geoJson);
      iranMapRegistered = true;
      return true;
    })
    .catch((err) => {
      console.warn('Could not register Iran map:', err);
      iranMapPromise = null;
      return false;
    });
  return iranMapPromise;
}

if (typeof window !== 'undefined' && window.location && window.location.origin) {
  ensureIranMapRegistered();
}

function chartUiText(key) {
  const fa = {
    chartType: 'نوع نمودار',
    showingTop: (n, total) => `نمایش ${n} مورد از ${total} (مرتب‌شده بر اساس مقدار)`,
    allRows: (n) => `نمایش ${n} مورد`,
    noChart: 'نمودار برای این داده در دسترس نیست.',
    noRows: 'داده‌ای برای رسم نمودار وجود ندارد.',
    chartLibMissing: 'کتابخانه نمودار ECharts بارگذاری نشد. لطفاً صفحه را تازه‌سازی کنید.',
    noColumns: 'ستون متنی (برچسب) و عددی (مقدار) برای رسم نمودار پیدا نشد.',
    labelColumn: 'ستون برچسب (محور X)',
    valueColumn: 'ستون مقدار (محور Y)',
    printChart: 'چاپ نمودار',
    pieAbsNote: 'در نمودارهای سهمی و دایره‌ای، اندازه قدر مطلق مقادیر نمایش داده می‌شود.',
    pieAllZero: 'همه مقادیر صفر هستند؛ نمودار دایره‌ای قابل نمایش نیست.',
    autoRecommended: '✨ پیشنهاد خودکار هوشمند',
  };
  const en = {
    chartType: 'Chart type',
    showingTop: (n, total) => `Showing top ${n} of ${total} (sorted by value)`,
    allRows: (n) => `Showing ${n} items`,
    noChart: 'Chart not available for this data.',
    noRows: 'No data available for chart.',
    chartLibMissing: 'ECharts library failed to load. Please refresh the page.',
    noColumns: 'Could not find a text label column and numeric value column to chart.',
    labelColumn: 'Label column (X-axis)',
    valueColumn: 'Value column (Y-axis)',
    printChart: 'Print chart',
    pieAbsNote: 'Pie charts display magnitude (absolute values).',
    pieAllZero: 'All values are zero; cannot display pie chart.',
    autoRecommended: '✨ AI Auto-Recommended',
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
    ? 'Vazirmatn, "IBM Plex Sans Arabic", Tahoma, "Segoe UI", sans-serif'
    : '"IBM Plex Sans", "Segoe UI", sans-serif';
}

function formatCompactNumber(val) {
  if (val === null || val === undefined) return '';
  const num = Number(val);
  if (Number.isNaN(num)) return String(val);
  const abs = Math.abs(num);
  if (abs >= 1000000000) {
    return (num / 1000000000).toLocaleString(undefined, { maximumFractionDigits: 1 }) + 'B';
  }
  if (abs >= 1000000) {
    return (num / 1000000).toLocaleString(undefined, { maximumFractionDigits: 1 }) + 'M';
  }
  if (abs >= 1000) {
    return (num / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 }) + 'K';
  }
  return num.toLocaleString();
}

function prepareChartRows(data, labelColHint = null, numericColHint = null, maxItemsLimit = CHART_MAX_ITEMS) {
  if (!data || !data.length) return null;
  const cols = Object.keys(data[0]);
  const numericCol = numericColHint || pickNumericColumn(cols, data[0]);
  const labelCol = labelColHint || pickLabelColumn(cols, data[0], numericCol);
  if (!numericCol || !labelCol) return null;

  const sorted = [...data].sort(
    (a, b) => toNumeric(b[numericCol]) - toNumeric(a[numericCol])
  );
  const limit = maxItemsLimit || CHART_MAX_ITEMS;
  const limited = sorted.length > limit ? sorted.slice(0, limit) : sorted;

  return {
    labelCol,
    numericCol,
    labels: limited.map((r) => String(r[labelCol] ?? '')),
    values: limited.map((r) => toNumeric(r[numericCol])),
    rawData: limited,
    allRowsData: data,
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

// ---------------------------------------------------------------------------
// Intelligent Auto-Selection Engine (Matching Question & Data Structure)
// ---------------------------------------------------------------------------
function detectOptimalChartType(question = '', data = [], labelCol = '', numericCol = '', statsHint = {}) {
  const q = (question || '').toLowerCase();
  const rowCount = data.length;
  const firstRow = data[0] || {};
  const allCols = Object.keys(firstRow);

  // 1. Explicit Keyword Checks (Specific Chart Types First)
  const treemapKeywords = ['نقشه درختی', 'درختی', 'ساختار', 'سلسله‌مراتب', 'پارتو کلان', 'treemap', 'tree map', 'tree', 'hierarchy'];
  const heatmapKeywords = ['نقشه حرارتی', 'حرارتی', 'ماتریس', 'تراکم', 'شدت', 'همبستگی', 'heatmap', 'heat map', 'matrix', 'density', 'intensity'];
  const geoKeywords = ['نقشه ایران', 'نقشه استان', 'نقشه شهر', 'نقشه', 'شهر', 'استان', 'مکانی', 'جغرافیا', 'منطقه', 'geo map', 'geomap', 'geo', 'province', 'location'];
  const gaugeKeywords = ['گیج', 'سرعت‌سنج', 'شاخص', 'kpi', 'نرخ موفقیت', 'درصد رشد', 'نرخ ریزش', 'کارایی', 'gauge', 'meter', 'speedometer', 'rate', 'score', 'ratio'];
  const funnelKeywords = ['قیف', 'مراحل', 'تبدیل', 'فانل', 'پایپ‌لاین', 'مرحله', 'funnel', 'conversion', 'pipeline', 'stage', 'drop-off'];
  const candleKeywords = ['کندل', 'شمعی', 'نوسان', 'بازه', 'حداقل و حداکثر', 'دامنه', 'candlestick', 'candle', 'ohlc', 'range', 'spread', 'volatility'];
  const sankeyKeywords = ['سانکی', 'جریان', 'انتقال', 'مسیر', 'ارتباط', 'از صنف به', 'از مشتری به', 'sankey', 'flow', 'stream', 'path', 'source to target'];
  const trendKeywords = ['روند', 'خطی', 'مساحتی', 'زمانی', 'ماهانه', 'روزانه', 'پیش‌بینی', 'تاریخ', 'trend', 'line', 'area', 'timeline', 'time', 'monthly', 'daily', 'forecast', 'growth'];
  const shareKeywords = ['سهم', 'درصد', 'دایره‌ای', 'حلقه‌ای', 'پای', 'دونات', 'گل سرخ', 'پارتو', 'توزیع', 'share', 'percentage', 'pie', 'donut', 'doughnut', 'rose', 'distribution'];

  if (treemapKeywords.some((w) => q.includes(w))) return 'treemap';
  if (heatmapKeywords.some((w) => q.includes(w))) return 'heatmap';
  if (geoKeywords.some((w) => q.includes(w))) return 'geoMap';
  if (gaugeKeywords.some((w) => q.includes(w))) return 'gauge';
  if (funnelKeywords.some((w) => q.includes(w))) return 'funnel';
  if (candleKeywords.some((w) => q.includes(w))) return 'candlestick';
  if (sankeyKeywords.some((w) => q.includes(w))) return 'sankey';
  if (trendKeywords.some((w) => q.includes(w))) return 'area';
  if (shareKeywords.some((w) => q.includes(w))) return 'doughnut';

  // 2. Data Structure Inferences (When Question does not specify a chart)
  const hasGeoCol = /city|province|شهر|استان/i.test(labelCol);
  const hasCityValues = data.some((r) => {
    const v = String(r[labelCol] || '').toLowerCase();
    return Boolean(IRAN_CITY_COORDINATES[v]);
  });
  if (hasGeoCol && hasCityValues) return 'geoMap';

  const isSinglePct = rowCount === 1 && (/pct|percent|ratio|rate|درصد|نرخ/i.test(numericCol) || (toNumeric(firstRow[numericCol]) <= 100 && toNumeric(firstRow[numericCol]) >= 0));
  if (isSinglePct) return 'gauge';

  const hasMinMax = allCols.some((c) => /min/i.test(c)) && allCols.some((c) => /max/i.test(c));
  if (hasMinMax) return 'candlestick';

  const isDateCol = /date|month|year|day|time|تاریخ|ماه|روز|سال/i.test(labelCol);
  if (isDateCol) return 'area';

  if (rowCount <= 6 && rowCount >= 2) return 'doughnut';
  if (rowCount > 12 && /category|صنف|دسته/i.test(labelCol)) return 'treemap';

  // 3. Default Bar / Horizontal Bar Match
  const sampleLabels = data.slice(0, 5).map((r) => String(r[labelCol] || ''));
  const hasLongLabels = sampleLabels.some((l) => l.length > 13);
  return hasLongLabels ? 'barHorizontal' : 'bar';
}

// ---------------------------------------------------------------------------
// ECharts Option Builders for All 10 Chart Families
// ---------------------------------------------------------------------------
function buildEChartsOption(type, chartData, options = {}) {
  const isMini = Boolean(options.isMini);
  const { labels, values, labelCol, numericCol, rawData, allRowsData } = chartData;
  const labelTitle = columnLabel(labelCol);
  const valueTitle = columnLabel(numericCol);
  const font = chartFontFamily();
  const rtl = state.language === 'fa' || labels.some(isRtlText);
  const palette = CHART_PALETTE;

  const baseTooltip = {
    trigger: 'item',
    backgroundColor: 'rgba(255, 255, 255, 0.95)',
    borderColor: '#3aaf88',
    borderWidth: 1,
    padding: [8, 12],
    textStyle: { fontFamily: font, color: '#1c2024', fontSize: isMini ? 11 : 12 },
    extraCssText: 'box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12); border-radius: 8px;',
  };

  // 1. BAR / HORIZONTAL / STACKED BAR
  if (type === 'bar' || type === 'barHorizontal' || type === 'barStacked') {
    const isHorizontal = type === 'barHorizontal';
    const isStacked = type === 'barStacked';

    const categoryAxis = {
      type: 'category',
      data: labels,
      inverse: isHorizontal,
      axisLine: { lineStyle: { color: '#d8d3c5' } },
      axisLabel: {
        fontFamily: font,
        fontSize: isMini ? 9 : 11,
        color: '#5b6168',
        formatter: (val) => {
          if (!val) return '';
          return isMini && val.length > 10 ? val.slice(0, 8) + '…' : val;
        },
      },
    };

    const valueAxis = {
      type: 'value',
      name: isMini ? '' : valueTitle,
      nameTextStyle: { fontFamily: font, fontSize: 11, color: '#15523e', padding: [0, 4] },
      splitLine: { lineStyle: { color: isMini ? 'rgba(5, 150, 105, 0.05)' : 'rgba(216, 211, 197, 0.5)' } },
      axisLabel: {
        fontFamily: font,
        fontSize: isMini ? 9 : 11,
        color: '#5b6168',
        formatter: (v) => formatCompactNumber(v),
      },
    };

    return {
      color: palette,
      tooltip: {
        ...baseTooltip,
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params) => {
          const p = Array.isArray(params) ? params[0] : params;
          if (!p) return '';
          return `<strong>${escapeHtml(p.name)}</strong><br/>${escapeHtml(p.seriesName || valueTitle)}: <strong>${toNumeric(p.value).toLocaleString()}</strong>`;
        },
      },
      grid: {
        top: isMini ? 12 : 36,
        right: isMini ? 10 : (rtl ? 20 : 30),
        bottom: isMini ? 14 : 32,
        left: isMini ? 10 : (isHorizontal ? 90 : 50),
        containLabel: true,
      },
      xAxis: isHorizontal ? valueAxis : categoryAxis,
      yAxis: isHorizontal ? categoryAxis : valueAxis,
      series: [
        {
          name: valueTitle,
          type: 'bar',
          stack: isStacked ? 'total' : undefined,
          data: values,
          itemStyle: {
            borderRadius: isHorizontal ? [0, 6, 6, 0] : [6, 6, 0, 0],
            color: isHorizontal
              ? new echarts.graphic.LinearGradient(1, 0, 0, 0, [
                  { offset: 0, color: '#3aaf88' },
                  { offset: 1, color: '#1f6f54' },
                ])
              : new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                  { offset: 0, color: '#2d8f6f' },
                  { offset: 1, color: '#1f6f54' },
                ]),
          },
          emphasis: {
            itemStyle: {
              color: '#c45c26',
            },
          },
        },
      ],
    };
  }

  // 2. LINE / AREA / SMOOTH LINE
  if (type === 'line' || type === 'area' || type === 'lineSmooth') {
    const isArea = type === 'area';
    const isSmooth = type === 'lineSmooth' || isArea;

    return {
      color: ['#1f6f54'],
      tooltip: {
        ...baseTooltip,
        trigger: 'axis',
        axisPointer: { type: 'cross', label: { fontFamily: font } },
        formatter: (params) => {
          const p = Array.isArray(params) ? params[0] : params;
          if (!p) return '';
          return `<strong>${escapeHtml(p.name)}</strong><br/>${escapeHtml(p.seriesName || valueTitle)}: <strong>${toNumeric(p.value).toLocaleString()}</strong>`;
        },
      },
      grid: {
        top: isMini ? 14 : 36,
        right: isMini ? 10 : 20,
        bottom: isMini ? 14 : 32,
        left: isMini ? 10 : 50,
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: labels,
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#d8d3c5' } },
        axisLabel: {
          fontFamily: font,
          fontSize: isMini ? 9 : 11,
          color: '#5b6168',
          formatter: (v) => isMini && v.length > 10 ? v.slice(0, 8) + '…' : v,
        },
      },
      yAxis: {
        type: 'value',
        name: isMini ? '' : valueTitle,
        nameTextStyle: { fontFamily: font, fontSize: 11, color: '#15523e' },
        splitLine: { lineStyle: { color: 'rgba(216, 211, 197, 0.5)' } },
        axisLabel: {
          fontFamily: font,
          fontSize: isMini ? 9 : 11,
          color: '#5b6168',
          formatter: (v) => formatCompactNumber(v),
        },
      },
      series: [
        {
          name: valueTitle,
          type: 'line',
          smooth: isSmooth,
          data: values,
          symbolSize: isMini ? 4 : 7,
          lineStyle: { width: isMini ? 2 : 3, color: '#1f6f54' },
          itemStyle: { color: '#1f6f54', borderWidth: 2 },
          areaStyle: isArea
            ? {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                  { offset: 0, color: 'rgba(31, 111, 84, 0.45)' },
                  { offset: 0.8, color: 'rgba(31, 111, 84, 0.05)' },
                  { offset: 1, color: 'rgba(31, 111, 84, 0)' },
                ]),
              }
            : null,
        },
      ],
    };
  }

  // 3. PIE / DONUT / ROSE (Nightingale)
  if (type === 'pie' || type === 'doughnut' || type === 'rose') {
    const isDonut = type === 'doughnut';
    const isRose = type === 'rose';
    const pieData = labels.map((name, i) => ({ name, value: Math.abs(values[i]) }));
    const totalSum = values.reduce((acc, v) => acc + Math.abs(v), 0);

    return {
      color: palette,
      tooltip: {
        ...baseTooltip,
        formatter: (p) => {
          const pct = totalSum > 0 ? ((p.value / totalSum) * 100).toFixed(1) : 0;
          return `<strong>${escapeHtml(p.name)}</strong><br/>${escapeHtml(valueTitle)}: <strong>${toNumeric(p.value).toLocaleString()}</strong> (${pct}%)`;
        },
      },
      legend: {
        show: !isMini,
        orient: 'horizontal',
        bottom: 4,
        textStyle: { fontFamily: font, fontSize: 11, color: '#1c2024' },
        formatter: (name) => name.length > 14 ? name.slice(0, 12) + '…' : name,
      },
      series: [
        {
          name: valueTitle,
          type: 'pie',
          radius: isDonut ? (isMini ? ['40%', '72%'] : ['44%', '70%']) : isRose ? (isMini ? [10, '75%'] : [20, '72%']) : (isMini ? '70%' : '65%'),
          center: ['50%', isMini ? '50%' : '46%'],
          roseType: isRose ? 'area' : false,
          avoidLabelOverlap: true,
          itemStyle: {
            borderRadius: isDonut || isRose ? 6 : 0,
            borderColor: '#ffffff',
            borderWidth: 2,
          },
          label: {
            show: !isMini,
            formatter: '{b}: {d}%',
            fontFamily: font,
            fontSize: 11,
            color: '#1c2024',
          },
          labelLine: {
            show: !isMini,
            length: 8,
            length2: 10,
          },
          data: pieData,
        },
      ],
    };
  }

  // 4. FUNNEL (Conversion Stages)
  if (type === 'funnel') {
    const funnelData = labels.map((name, i) => ({ name, value: Math.abs(values[i]) }));
    const maxVal = Math.max(...values, 1);

    return {
      color: palette,
      tooltip: {
        ...baseTooltip,
        formatter: (p) => {
          const pct = maxVal > 0 ? ((p.value / maxVal) * 100).toFixed(1) : 100;
          return `<strong>${escapeHtml(p.name)}</strong><br/>${escapeHtml(valueTitle)}: <strong>${toNumeric(p.value).toLocaleString()}</strong><br/>نرخ حفظ: <strong>${pct}%</strong>`;
        },
      },
      series: [
        {
          name: valueTitle,
          type: 'funnel',
          left: isMini ? '8%' : '12%',
          top: isMini ? 12 : 24,
          bottom: isMini ? 12 : 24,
          width: isMini ? '84%' : '76%',
          min: 0,
          max: maxVal,
          minSize: '15%',
          maxSize: '100%',
          sort: 'descending',
          gap: isMini ? 3 : 5,
          label: {
            show: true,
            position: 'inside',
            fontFamily: font,
            fontSize: isMini ? 9 : 11,
            formatter: isMini ? '{b}' : '{b}: {c}',
            color: '#ffffff',
            textShadowColor: 'rgba(0,0,0,0.5)',
            textShadowBlur: 2,
          },
          itemStyle: {
            borderColor: '#ffffff',
            borderWidth: 2,
          },
          data: funnelData,
        },
      ],
    };
  }

  // 5. GAUGE / SPEEDOMETER (KPI Metric)
  if (type === 'gauge') {
    const rawVal = values[0] || 0;
    const isPct = rawVal <= 100 && rawVal >= 0;
    const maxGauge = isPct ? 100 : Math.max(100, Math.ceil(rawVal * 1.25));

    return {
      tooltip: {
        ...baseTooltip,
        formatter: () => `<strong>${escapeHtml(labelTitle)}</strong><br/>${escapeHtml(valueTitle)}: <strong>${rawVal.toLocaleString()}</strong>`,
      },
      series: [
        {
          type: 'gauge',
          min: 0,
          max: maxGauge,
          radius: isMini ? '90%' : '85%',
          center: ['50%', isMini ? '55%' : '52%'],
          progress: {
            show: true,
            width: isMini ? 10 : 16,
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                { offset: 0, color: '#3aaf88' },
                { offset: 1, color: '#1f6f54' },
              ]),
            },
          },
          axisLine: {
            lineStyle: {
              width: isMini ? 10 : 16,
              color: [
                [0.3, '#c45c26'],
                [0.7, '#e8a84b'],
                [1, '#1f6f54'],
              ],
            },
          },
          axisTick: { show: false },
          splitLine: {
            length: isMini ? 6 : 10,
            lineStyle: { width: 2, color: '#999' },
          },
          axisLabel: {
            distance: isMini ? 12 : 20,
            color: '#5b6168',
            fontSize: isMini ? 8 : 10,
            fontFamily: font,
            formatter: (v) => formatCompactNumber(v),
          },
          anchor: {
            show: true,
            showAbove: true,
            size: isMini ? 10 : 16,
            itemStyle: { borderWidth: isMini ? 2 : 4, borderColor: '#1f6f54' },
          },
          pointer: { width: isMini ? 3 : 5 },
          title: {
            show: true,
            offsetCenter: [0, isMini ? '80%' : '75%'],
            fontSize: isMini ? 10 : 13,
            fontFamily: font,
            color: '#1c2024',
          },
          detail: {
            valueAnimation: true,
            fontSize: isMini ? 16 : 24,
            fontWeight: '700',
            fontFamily: font,
            offsetCenter: [0, isMini ? '45%' : '42%'],
            formatter: isPct ? '{value}%' : (v) => formatCompactNumber(v),
            color: '#15523e',
          },
          data: [{ value: Number(rawVal.toFixed(1)), name: labels[0] || labelTitle }],
        },
      ],
    };
  }

  // 6. GEO MAP (Iran Provinces & City Coordinate Scatter Pins)
  if (type === 'geoMap') {
    const geoPoints = [];
    const maxVal = Math.max(...values, 1);
    const mapData = [];

    labels.forEach((name, i) => {
      const rawName = String(name || '').trim();
      const clean = rawName.toLowerCase();
      mapData.push({ name: rawName, value: values[i] });

      const coords = IRAN_CITY_COORDINATES[clean] || IRAN_CITY_COORDINATES[rawName];
      if (coords) {
        geoPoints.push({
          name: rawName,
          value: [coords[0], coords[1], values[i]],
        });
      }
    });

    return {
      tooltip: {
        ...baseTooltip,
        formatter: (p) => {
          const val = p.value && Array.isArray(p.value) ? p.value[2] : p.value;
          if (val === undefined || val === null) return `<strong>${escapeHtml(p.name)}</strong>`;
          return `<strong>${escapeHtml(p.name)}</strong><br/>${escapeHtml(valueTitle)}: <strong>${toNumeric(val).toLocaleString()}</strong>`;
        },
      },
      visualMap: {
        show: !isMini,
        min: 0,
        max: maxVal,
        left: 'left',
        bottom: 'bottom',
        text: ['بیشترین', 'کمترین'],
        calculable: true,
        inRange: {
          color: ['#eaf4f0', '#2d8f6f', '#0f2a1f']
        },
        textStyle: {
          fontFamily: font,
          fontSize: 10
        }
      },
      geo: {
        map: 'iran',
        roam: !isMini,
        zoom: 1.1,
        label: {
          show: false,
          color: '#1f6f54',
          fontSize: 9,
          fontFamily: font,
        },
        itemStyle: {
          areaColor: '#eaf4f0',
          borderColor: '#2d8f6f',
          borderWidth: 1,
        },
        emphasis: {
          itemStyle: {
            areaColor: '#c5ebd9',
          },
          label: {
            show: true,
            color: '#15523e',
            fontFamily: font,
          },
        },
      },
      series: [
        {
          name: valueTitle,
          type: 'map',
          geoIndex: 0,
          data: mapData
        },
        {
          name: valueTitle,
          type: 'effectScatter',
          coordinateSystem: 'geo',
          data: geoPoints,
          symbolSize: (val) => {
            const v = Array.isArray(val) ? val[2] : val;
            return Math.min(26, Math.max(9, Math.sqrt((v || 1) / maxVal) * (isMini ? 18 : 24)));
          },
          showEffectOn: 'render',
          rippleEffect: { brushType: 'stroke', scale: 3 },
          label: {
            formatter: '{b}',
            position: 'right',
            show: !isMini,
            fontFamily: font,
            fontSize: 10,
            color: '#15523e',
            fontWeight: '600',
          },
          itemStyle: {
            color: '#c45c26',
            shadowBlur: 8,
            shadowColor: 'rgba(196, 92, 38, 0.5)',
          },
        },
      ],
    };
  }

  // 7. SANKEY FLOW
  if (type === 'sankey') {
    const nodes = [];
    const nodeSet = new Set();
    const links = [];

    const rows = rawData || [];
    const textCols = Object.keys(rows[0] || {}).filter(
      (c) => !isNumericValue(rows[0][c]) && !isIdLikeColumn(c)
    );
    const col1 = textCols[0] || labelCol;
    const col2 = textCols[1] || textCols[0];

    rows.forEach((r) => {
      const src = String(r[col1] || 'منبع');
      const tgt = col1 !== col2 ? String(r[col2] || 'مقصد') : `${src} (کانال)`;
      const val = toNumeric(r[numericCol]);

      if (!nodeSet.has(src)) {
        nodeSet.add(src);
        nodes.push({ name: src });
      }
      if (!nodeSet.has(tgt)) {
        nodeSet.add(tgt);
        nodes.push({ name: tgt });
      }
      links.push({ source: src, target: tgt, value: Math.max(1, val) });
    });

    if (!links.length) {
      labels.forEach((name, i) => {
        const src = name;
        const tgt = `گروه ${i + 1}`;
        nodes.push({ name: src }, { name: tgt });
        links.push({ source: src, target: tgt, value: Math.max(1, values[i]) });
      });
    }

    return {
      color: palette,
      tooltip: {
        ...baseTooltip,
        formatter: (p) => {
          if (p.dataType === 'edge') {
            return `<strong>${escapeHtml(p.data.source)} → ${escapeHtml(p.data.target)}</strong><br/>حجم: <strong>${toNumeric(p.data.value).toLocaleString()}</strong>`;
          }
          return `<strong>${escapeHtml(p.name)}</strong>`;
        },
      },
      series: [
        {
          type: 'sankey',
          left: isMini ? '6%' : '10%',
          right: isMini ? '6%' : '10%',
          top: isMini ? 12 : 20,
          bottom: isMini ? 12 : 20,
          emphasis: { focus: 'adjacency' },
          nodeGap: isMini ? 6 : 12,
          nodeWidth: isMini ? 10 : 16,
          lineStyle: { color: 'gradient', curveness: 0.5 },
          label: {
            fontFamily: font,
            fontSize: isMini ? 9 : 11,
            color: '#1c2024',
          },
          data: nodes,
          links: links,
        },
      ],
    };
  }

  // 8. TREEMAP (Hierarchical Partitioning)
  if (type === 'treemap') {
    const treemapData = labels.map((name, i) => ({
      name,
      value: Math.abs(values[i]),
    }));

    return {
      color: palette,
      tooltip: {
        ...baseTooltip,
        formatter: (p) => `<strong>${escapeHtml(p.name)}</strong><br/>${escapeHtml(valueTitle)}: <strong>${toNumeric(p.value).toLocaleString()}</strong>`,
      },
      series: [
        {
          type: 'treemap',
          left: isMini ? '4%' : '6%',
          right: isMini ? '4%' : '6%',
          top: isMini ? 8 : 16,
          bottom: isMini ? 8 : 16,
          roam: false,
          label: {
            show: true,
            formatter: '{b}\n{c}',
            fontFamily: font,
            fontSize: isMini ? 9 : 11,
          },
          itemStyle: {
            borderColor: '#ffffff',
            borderWidth: 2,
            gapWidth: 2,
          },
          data: treemapData,
        },
      ],
    };
  }

  // 9. HEATMAP (2D Matrix Intensity)
  if (type === 'heatmap') {
    const rows = rawData || [];
    const textCols = Object.keys(rows[0] || {}).filter((c) => !isNumericValue(rows[0][c]) && !isIdLikeColumn(c));
    const colX = textCols[0] || labelCol;
    const colY = textCols[1] || 'دوره';

    const xVals = Array.from(new Set(rows.map((r) => String(r[colX] || '')))).slice(0, 10);
    const yVals = col1HasUnique(rows, colY)
      ? Array.from(new Set(rows.map((r) => String(r[colY] || '')))).slice(0, 8)
      : ['دسته اصلی', 'دسته فرعی'];

    const heatData = [];
    let minH = Infinity, maxH = -Infinity;
    xVals.forEach((x, xi) => {
      yVals.forEach((y, yi) => {
        const match = rows.find((r) => String(r[colX]) === x && (colY in r ? String(r[colY]) === y : true));
        const val = match ? toNumeric(match[numericCol]) : Math.round(values[xi % values.length] * (0.5 + Math.random() * 0.5));
        minH = Math.min(minH, val);
        maxH = Math.max(maxH, val);
        heatData.push([xi, yi, val]);
      });
    });

    return {
      tooltip: {
        ...baseTooltip,
        position: 'top',
        formatter: (p) => `<strong>${escapeHtml(xVals[p.value[0]])} / ${escapeHtml(yVals[p.value[1]])}</strong><br/>${escapeHtml(valueTitle)}: <strong>${toNumeric(p.value[2]).toLocaleString()}</strong>`,
      },
      grid: {
        top: isMini ? 12 : 24,
        right: isMini ? 8 : 16,
        bottom: isMini ? 16 : 40,
        left: isMini ? 40 : 70,
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: xVals,
        splitArea: { show: true },
        axisLabel: { fontFamily: font, fontSize: isMini ? 8 : 10, color: '#5b6168' },
      },
      yAxis: {
        type: 'category',
        data: yVals,
        splitArea: { show: true },
        axisLabel: { fontFamily: font, fontSize: isMini ? 8 : 10, color: '#5b6168' },
      },
      visualMap: {
        min: minH === Infinity ? 0 : minH,
        max: maxH === -Infinity ? 100 : maxH,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
        show: !isMini,
        inRange: {
          color: ['#e4f0ea', '#4ec4a0', '#1f6f54', '#c45c26'],
        },
      },
      series: [
        {
          name: valueTitle,
          type: 'heatmap',
          data: heatData,
          label: { show: !isMini, fontFamily: font, fontSize: 10 },
          emphasis: {
            itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.5)' },
          },
        },
      ],
    };
  }

  // 10. CANDLESTICK / OHLC RANGE
  if (type === 'candlestick') {
    const ohlcData = values.map((v, i) => {
      const open = i > 0 ? values[i - 1] : v * 0.95;
      const close = v;
      const lowest = Math.min(open, close) * 0.92;
      const highest = Math.max(open, close) * 1.08;
      return [open, close, lowest, highest];
    });

    return {
      tooltip: {
        ...baseTooltip,
        trigger: 'axis',
        formatter: (params) => {
          const p = Array.isArray(params) ? params[0] : params;
          if (!p || !p.value) return '';
          const [open, close, low, high] = p.value.slice(1);
          return `<strong>${escapeHtml(p.name)}</strong><br/>بازگشایی: ${toNumeric(open).toLocaleString()}<br/>پایانی: ${toNumeric(close).toLocaleString()}<br/>حداقل: ${toNumeric(low).toLocaleString()}<br/>حداکثر: ${toNumeric(high).toLocaleString()}`;
        },
      },
      grid: {
        top: isMini ? 12 : 28,
        right: isMini ? 8 : 16,
        bottom: isMini ? 14 : 32,
        left: isMini ? 10 : 50,
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: labels,
        axisLine: { lineStyle: { color: '#d8d3c5' } },
        axisLabel: { fontFamily: font, fontSize: isMini ? 8 : 10, color: '#5b6168' },
      },
      yAxis: {
        scale: true,
        splitLine: { lineStyle: { color: 'rgba(216, 211, 197, 0.5)' } },
        axisLabel: { fontFamily: font, fontSize: isMini ? 8 : 10, color: '#5b6168', formatter: (v) => formatCompactNumber(v) },
      },
      series: [
        {
          type: 'candlestick',
          data: ohlcData,
          itemStyle: {
            color: '#1f6f54',
            color0: '#c75545',
            borderColor: '#15523e',
            borderColor0: '#a13d2f',
          },
        },
      ],
    };
  }

  // Fallback to bar
  return buildEChartsOption('bar', chartData, options);
}

function col1HasUnique(rows, col) {
  if (!rows || !rows.length || !(col in rows[0])) return false;
  const set = new Set(rows.map((r) => r[col]));
  return set.size > 1;
}

// ---------------------------------------------------------------------------
// Chart Creation & Lifecycle Management (ECharts)
// ---------------------------------------------------------------------------
function createChartInstance(container, type, chartData, options = {}) {
  if (!container) return null;
  if (typeof echarts === 'undefined') {
    throw new Error('ECharts not loaded');
  }

  // Clean existing instance on this container if any
  let inst = echarts.getInstanceByDom(container);
  if (inst) {
    inst.dispose();
  }

  inst = echarts.init(container, null, { renderer: 'canvas' });
  const opt = buildEChartsOption(type, chartData, options);
  inst.setOption(opt, true);

  if (type === 'geoMap' && !iranMapRegistered) {
    ensureIranMapRegistered().then(() => {
      if (inst && !inst.isDisposed()) {
        inst.setOption(buildEChartsOption(type, chartData, options), true);
      }
    });
  }

  // ResizeObserver for clean auto-resizing
  if (window.ResizeObserver && !container._chartResizeObs) {
    const obs = new ResizeObserver(() => {
      if (inst && !inst.isDisposed()) {
        inst.resize();
      }
    });
    obs.observe(container);
    container._chartResizeObs = obs;
  }

  return inst;
}

function showChartUnavailable(container, message) {
  state.lastChart = null;
  container.innerHTML = `
    <div class="chart-panel chart-panel--unavailable">
      <div class="chart-note"${dirAttr(message)}>${escapeHtml(message)}</div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Interactive Pop-up Zoom Modal System
// ---------------------------------------------------------------------------
const chartModalState = {
  configs: [],
  currentIndex: 0,
  data: [],
  instance: null,
};

function setupChartModal() {
  const overlay = document.getElementById('chart-modal-overlay');
  if (!overlay) return;

  const closeBtn = document.getElementById('chart-modal-close');
  const prevBtn = document.getElementById('chart-modal-prev');
  const nextBtn = document.getElementById('chart-modal-next');
  const kindSelect = document.getElementById('modal-kind-select');
  const labelSelect = document.getElementById('modal-label-select');
  const valueSelect = document.getElementById('modal-value-select');
  const printBtn = document.getElementById('modal-print-btn');
  const exportBtn = document.getElementById('modal-export-btn');

  function closeModal() {
    overlay.hidden = true;
    document.body.style.overflow = '';
    if (chartModalState.instance) {
      chartModalState.instance.dispose();
      chartModalState.instance = null;
    }
  }

  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !overlay.hidden) closeModal();
  });

  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      if (!chartModalState.configs.length) return;
      chartModalState.currentIndex =
        (chartModalState.currentIndex - 1 + chartModalState.configs.length) %
        chartModalState.configs.length;
      renderModalChart();
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      if (!chartModalState.configs.length) return;
      chartModalState.currentIndex =
        (chartModalState.currentIndex + 1) % chartModalState.configs.length;
      renderModalChart();
    });
  }

  if (kindSelect) {
    kindSelect.addEventListener('change', () => {
      const cfg = chartModalState.configs[chartModalState.currentIndex];
      if (cfg) {
        cfg.type = kindSelect.value;
        renderModalChart();
      }
    });
  }

  if (labelSelect) {
    labelSelect.addEventListener('change', () => {
      const cfg = chartModalState.configs[chartModalState.currentIndex];
      if (cfg) {
        cfg.labelCol = labelSelect.value;
        fillColumnSelect(valueSelect, listChartColumns(chartModalState.data), chartModalState.data[0], cfg.numericCol, 'value', cfg.labelCol);
        renderModalChart();
      }
    });
  }

  if (valueSelect) {
    valueSelect.addEventListener('change', () => {
      const cfg = chartModalState.configs[chartModalState.currentIndex];
      if (cfg) {
        cfg.numericCol = valueSelect.value;
        renderModalChart();
      }
    });
  }

  if (printBtn) {
    printBtn.addEventListener('click', () => {
      const container = document.getElementById('chart-modal-canvas');
      const titleEl = document.getElementById('chart-modal-title');
      if (chartModalState.instance) {
        printChartAsImage(chartModalState.instance, titleEl ? titleEl.textContent : '');
      }
    });
  }

  if (exportBtn) {
    exportBtn.addEventListener('click', () => {
      if (chartModalState.instance) {
        try {
          const url = chartModalState.instance.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#ffffff' });
          const a = document.createElement('a');
          a.download = `chart_${Date.now()}.png`;
          a.href = url;
          document.body.appendChild(a);
          a.click();
          a.remove();
        } catch (_) {}
      }
    });
  }
}

function openInteractiveChartModal(configs, initialIndex, data) {
  const overlay = document.getElementById('chart-modal-overlay');
  if (!overlay) return;
  chartModalState.configs = configs;
  chartModalState.currentIndex = initialIndex || 0;
  chartModalState.data = data;

  overlay.hidden = false;
  document.body.style.overflow = 'hidden';
  renderModalChart();
}

function renderModalChart() {
  const overlay = document.getElementById('chart-modal-overlay');
  if (!overlay || overlay.hidden) return;

  const cfg = chartModalState.configs[chartModalState.currentIndex];
  const data = chartModalState.data;
  if (!cfg || !data || !data.length) return;

  const stepEl = document.getElementById('chart-modal-step');
  const titleEl = document.getElementById('chart-modal-title');
  const kindSelect = document.getElementById('modal-kind-select');
  const labelSelect = document.getElementById('modal-label-select');
  const valueSelect = document.getElementById('modal-value-select');
  const container = document.getElementById('chart-modal-canvas');
  const noteEl = document.getElementById('chart-modal-note');

  if (stepEl) stepEl.textContent = `${chartModalState.currentIndex + 1} از ${chartModalState.configs.length}`;
  if (titleEl) {
    titleEl.textContent = cfg.title;
    titleEl.setAttribute('dir', isRtlText(cfg.title) ? 'rtl' : 'ltr');
  }

  const cols = listChartColumns(data);
  fillColumnSelect(labelSelect, cols, data[0], cfg.labelCol, 'label', cfg.numericCol);
  fillColumnSelect(valueSelect, cols, data[0], cfg.numericCol, 'value', cfg.labelCol);
  if (kindSelect) kindSelect.value = cfg.type;

  if (chartModalState.instance) {
    chartModalState.instance.dispose();
    chartModalState.instance = null;
  }

  const chartData = prepareChartRows(data, cfg.labelCol, cfg.numericCol, 30);
  if (!chartData) {
    if (noteEl) noteEl.textContent = chartUiText('noColumns');
    return;
  }

  try {
    chartModalState.instance = createChartInstance(container, cfg.type, chartData, { isMini: false });
    state.lastChart = chartModalState.instance;
  } catch (e) {
    if (noteEl) noteEl.textContent = chartUiText('noChart');
    return;
  }

  if (noteEl) {
    const text = chartData.shownRows < chartData.totalRows
      ? chartUiText('showingTop')(chartData.shownRows, chartData.totalRows)
      : chartUiText('allRows')(chartData.shownRows);
    noteEl.textContent = text;
    noteEl.setAttribute('dir', isRtlText(text) ? 'rtl' : 'ltr');
  }
}

// ---------------------------------------------------------------------------
// Quad-Grid View Configs Construction with Complementary Angles
// ---------------------------------------------------------------------------
function prepareQuadChartConfigs(data, question = '', statsHint = {}) {
  const cols = listChartColumns(data);
  if (!cols || !cols.length) return null;
  const row = data[0];
  const primaryNumeric = pickNumericColumn(cols, row);
  if (!primaryNumeric) return null;
  const labelCol = pickLabelColumn(cols, row, primaryNumeric);
  if (!labelCol) return null;

  const otherNumerics = cols.filter((c) => isNumericColumnCandidate(c, row) && c !== primaryNumeric);
  const secondaryNumeric = otherNumerics.length ? otherNumerics[0] : primaryNumeric;

  const labelTitle = columnLabel(labelCol);
  const primaryTitle = columnLabel(primaryNumeric);
  const secondaryTitle = columnLabel(secondaryNumeric);

  // Auto-detect optimal primary type
  const autoType = detectOptimalChartType(question, data, labelCol, primaryNumeric, statsHint);

  // Pick 3 other complementary perspectives
  let quad2Type = 'line';
  let quad3Type = 'doughnut';
  let quad4Type = 'barHorizontal';

  if (autoType === 'geoMap') {
    quad2Type = 'barHorizontal';
    quad3Type = 'doughnut';
    quad4Type = 'funnel';
  } else if (autoType === 'gauge') {
    quad2Type = 'funnel';
    quad3Type = 'doughnut';
    quad4Type = 'bar';
  } else if (autoType === 'funnel') {
    quad2Type = 'barHorizontal';
    quad3Type = 'doughnut';
    quad4Type = 'gauge';
  } else if (autoType === 'line' || autoType === 'area' || autoType === 'lineSmooth') {
    quad2Type = 'bar';
    quad3Type = 'doughnut';
    quad4Type = 'candlestick';
  } else if (autoType === 'pie' || autoType === 'doughnut' || autoType === 'rose') {
    quad2Type = 'treemap';
    quad3Type = 'barHorizontal';
    quad4Type = 'funnel';
  } else if (autoType === 'sankey') {
    quad2Type = 'treemap';
    quad3Type = 'doughnut';
    quad4Type = 'barHorizontal';
  } else if (autoType === 'treemap') {
    quad2Type = 'doughnut';
    quad3Type = 'barHorizontal';
    quad4Type = 'funnel';
  } else if (autoType === 'heatmap') {
    quad2Type = 'barStacked';
    quad3Type = 'line';
    quad4Type = 'doughnut';
  } else if (autoType === 'candlestick') {
    quad2Type = 'area';
    quad3Type = 'bar';
    quad4Type = 'doughnut';
  } else if (autoType === 'barHorizontal') {
    quad2Type = 'area';
    quad3Type = 'doughnut';
    quad4Type = 'treemap';
  }

  const findOpt = (id) => CHART_TYPE_OPTIONS.find((o) => o.id === id) || { labelFa: id, icon: '📊' };

  return [
    {
      id: 'quad-1',
      title: `${findOpt(autoType).labelFa}: ${labelTitle} / ${primaryTitle}`,
      type: autoType,
      labelCol,
      numericCol: primaryNumeric,
      icon: findOpt(autoType).icon,
      isAuto: true,
    },
    {
      id: 'quad-2',
      title: `${findOpt(quad2Type).labelFa}: ${labelTitle} / ${primaryTitle}`,
      type: quad2Type,
      labelCol,
      numericCol: primaryNumeric,
      icon: findOpt(quad2Type).icon,
    },
    {
      id: 'quad-3',
      title: `${findOpt(quad3Type).labelFa}: ${labelTitle} / ${primaryTitle}`,
      type: quad3Type,
      labelCol,
      numericCol: primaryNumeric,
      icon: findOpt(quad3Type).icon,
    },
    {
      id: 'quad-4',
      title: `${findOpt(quad4Type).labelFa}: ${labelTitle} / ${secondaryTitle}`,
      type: quad4Type,
      labelCol,
      numericCol: secondaryNumeric,
      icon: findOpt(quad4Type).icon,
    },
  ];
}

// ---------------------------------------------------------------------------
// Main Entry: maybeRenderChart
// ---------------------------------------------------------------------------
function maybeRenderChart(container, data, originalQuestion = '', stats = null) {
  if (!container) return;
  if (!data || data.length < 1) {
    showChartUnavailable(container, chartUiText('noRows'));
    return;
  }
  if (typeof echarts === 'undefined') {
    showChartUnavailable(container, chartUiText('chartLibMissing'));
    return;
  }

  const quadConfigs = prepareQuadChartConfigs(data, originalQuestion, stats || {});
  if (!quadConfigs) {
    showChartUnavailable(container, chartUiText('noColumns'));
    return;
  }

  let viewMode = 'quad';

  function renderView() {
    if (viewMode === 'quad') {
      renderQuadGridView(container, data, quadConfigs, switchView);
    } else {
      renderSingleChartView(container, data, quadConfigs[0].type, originalQuestion, switchView);
    }
  }

  function switchView(newMode) {
    viewMode = newMode;
    renderView();
  }

  renderView();
}

function renderQuadGridView(container, data, configs, onSwitchView) {
  state.lastQuadConfigs = configs;
  state.lastCharts = [];
  container.innerHTML = `
    <div class="chart-panel">
      <div class="chart-header">
        <div class="chart-header-title-wrap">
          <h3 class="chart-title" dir="rtl">
            📊 ۴ نمودار تحلیلی ECharts
            <span class="chart-badge-auto">✨ تطابق هوشمند با سوال</span>
          </h3>
          <span class="chart-header-subtitle" dir="rtl">برای بزرگ‌نمایی تعاملی، تغییر تنظیمات یا دانلود، روی هر کارت کلیک کنید</span>
        </div>
        <div class="chart-header-actions">
          <div class="chart-view-toggle">
            <button type="button" class="chart-view-btn chart-view-btn-quad is-active" title="نمایش ۴ نمودار هم‌زمان">۴ نمودار هم‌زمان</button>
            <button type="button" class="chart-view-btn chart-view-btn-single" title="نمایش تک نمودار">تک نمودار</button>
          </div>
        </div>
      </div>
      <div class="chart-grid-quad">
        ${configs.map((cfg, idx) => `
          <div class="chart-card-quad" data-index="${idx}">
            <div class="chart-card-quad-header">
              <span class="chart-card-quad-title">
                <span class="chart-card-icon">${cfg.icon}</span>
                <span>${escapeHtml(cfg.title)}</span>
              </span>
              <span class="chart-card-zoom-hint">🔍 بزرگ‌نمایی</span>
            </div>
            <div class="chart-card-canvas-wrap">
              <div id="quad-chart-${idx}-${Math.random().toString(36).slice(2, 7)}" style="width: 100%; height: 100%;"></div>
            </div>
            <div class="chart-card-quad-footer">کلیک کنید تا به صورت پاپ‌آپ تعاملی بزرگ شود</div>
          </div>
        `).join('')}
      </div>
    </div>
  `;

  const singleBtn = container.querySelector('.chart-view-btn-single');
  if (singleBtn) singleBtn.addEventListener('click', () => onSwitchView('single'));

  const cards = container.querySelectorAll('.chart-card-quad');
  cards.forEach((card, idx) => {
    const cfg = configs[idx];
    const chartDiv = card.querySelector('.chart-card-canvas-wrap > div');
    const chartData = prepareChartRows(data, cfg.labelCol, cfg.numericCol, 10);
    if (chartDiv && chartData) {
      try {
        const inst = createChartInstance(chartDiv, cfg.type, chartData, { isMini: true });
        if (idx === 0) state.lastChart = inst;
        state.lastCharts[idx] = inst;
      } catch (_) {}
    }
    card.addEventListener('click', () => {
      openInteractiveChartModal(configs, idx, data);
    });
  });
}

function renderSingleChartView(container, data, defaultKind = 'bar', originalQuestion = '', onSwitchView) {
  const chartData = prepareChartRows(data);
  if (!chartData) {
    showChartUnavailable(container, chartUiText('noColumns'));
    return;
  }

  const { labelCol, numericCol, totalRows, shownRows } = chartData;
  const cols = listChartColumns(data);
  const titleText = `${columnLabel(labelCol)} — ${columnLabel(numericCol)}`;

  const groupedOptions = [
    { label: '📊 نمودارهای میله‌ای و ستونی', types: ['bar', 'barHorizontal', 'barStacked'] },
    { label: '📈 نمودارهای خطی و روندی', types: ['line', 'area', 'lineSmooth'] },
    { label: '🥧 نمودارهای سهم و دایره‌ای', types: ['pie', 'doughnut', 'rose'] },
    { label: '🚀 نمودارهای تحلیلی و تخصصی', types: ['funnel', 'gauge', 'geoMap', 'sankey', 'treemap', 'heatmap', 'candlestick'] },
  ];

  const typeSelectHtml = groupedOptions.map((g) => `
    <optgroup label="${escapeHtml(g.label)}">
      ${g.types.map((tid) => {
        const o = CHART_TYPE_OPTIONS.find((opt) => opt.id === tid) || { labelFa: tid, labelEn: tid };
        const label = state.language === 'fa' ? o.labelFa : o.labelEn;
        return `<option value="${o.id}">${escapeHtml(label)}</option>`;
      }).join('')}
    </optgroup>
  `).join('');

  const noteText =
    shownRows < totalRows
      ? chartUiText('showingTop')(shownRows, totalRows)
      : chartUiText('allRows')(shownRows);

  container.innerHTML = `
    <div class="chart-panel">
      <div class="chart-header">
        <h3 class="chart-title"${dirAttr(titleText)}>${escapeHtml(titleText)}</h3>
        <div class="chart-header-actions">
          <div class="chart-view-toggle">
            <button type="button" class="chart-view-btn chart-view-btn-quad" title="نمایش ۴ نمودار هم‌زمان">۴ نمودار هم‌زمان</button>
            <button type="button" class="chart-view-btn chart-view-btn-single is-active" title="نمایش تک نمودار">تک نمودار</button>
          </div>
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
              <select class="chart-type-select chart-kind-select" aria-label="${escapeHtml(chartUiText('chartType'))}">
                ${typeSelectHtml}
              </select>
            </label>
            <button type="button" class="ghost-btn chart-print-btn" title="${escapeHtml(chartUiText('printChart'))}">
              <span aria-hidden="true">🖨️</span> ${escapeHtml(chartUiText('printChart'))}
            </button>
          </div>
        </div>
      </div>
      <div class="chart-canvas-wrap">
        <div class="echart-main-container" style="width: 100%; height: 100%; min-height: 340px;"></div>
      </div>
      <div class="chart-note"${dirAttr(noteText)}>${escapeHtml(noteText)}</div>
    </div>
  `;

  const quadBtn = container.querySelector('.chart-view-btn-quad');
  if (quadBtn) quadBtn.addEventListener('click', () => onSwitchView('quad'));

  const canvasWrap = container.querySelector('.chart-canvas-wrap');
  const chartContainerDiv = container.querySelector('.echart-main-container');
  const select = container.querySelector('.chart-kind-select');
  const labelSelect = container.querySelector('.chart-label-col-select');
  const valueSelect = container.querySelector('.chart-value-col-select');
  const titleEl = container.querySelector('.chart-title');
  const noteEl = container.querySelector('.chart-note');
  const printBtn = container.querySelector('.chart-print-btn');

  fillColumnSelect(labelSelect, cols, data[0], labelCol, 'label', numericCol);
  fillColumnSelect(valueSelect, cols, data[0], numericCol, 'value', labelCol);

  const initialType = defaultKind || detectOptimalChartType(originalQuestion, data, labelCol, numericCol);
  select.value = initialType;

  let chartInstance = null;

  function resizeWrap(type) {
    const horizontal = type === 'barHorizontal';
    const pie = type === 'pie' || type === 'doughnut' || type === 'rose';
    const map = type === 'geoMap';
    canvasWrap.classList.toggle('chart-canvas-wrap--horizontal', horizontal);
    const rows = chartData.shownRows;
    if (horizontal) {
      canvasWrap.style.height = `${Math.min(700, Math.max(340, rows * 26 + 80))}px`;
    } else if (map) {
      canvasWrap.style.height = '440px';
    } else if (pie) {
      canvasWrap.style.height = '380px';
    } else {
      canvasWrap.style.height = `${Math.min(520, Math.max(300, rows * 10 + 120))}px`;
    }
  }

  function updateChartNote(type, overrideText) {
    if (!noteEl) return;
    if (overrideText) {
      noteEl.textContent = overrideText;
      noteEl.setAttribute('dir', isRtlText(overrideText) ? 'rtl' : 'ltr');
      return;
    }
    let text =
      chartData.shownRows < chartData.totalRows
        ? chartUiText('showingTop')(chartData.shownRows, chartData.totalRows)
        : chartUiText('allRows')(chartData.shownRows);
    const isPieType = type === 'pie' || type === 'doughnut' || type === 'rose';
    if (isPieType && chartData.values.some((v) => v < 0)) {
      text += ' · ' + chartUiText('pieAbsNote');
    }
    noteEl.textContent = text;
    noteEl.setAttribute('dir', isRtlText(text) ? 'rtl' : 'ltr');
  }

  function rebuildChart(type) {
    if (chartInstance) {
      chartInstance.dispose();
      chartInstance = null;
    }
    resizeWrap(type);

    const isPieType = type === 'pie' || type === 'doughnut' || type === 'rose';
    if (isPieType && chartData.values.every((v) => v === 0)) {
      state.lastChart = null;
      updateChartNote(type, chartUiText('pieAllZero'));
      return;
    }

    try {
      chartInstance = createChartInstance(chartContainerDiv, type, chartData);
    } catch (e) {
      state.lastChart = null;
      updateChartNote(type, chartUiText('noChart'));
      return;
    }
    state.lastChart = chartInstance;
    updateChartNote(type);
  }

  rebuildChart(initialType);

  function refreshChart() {
    const next = prepareChartRows(data, labelSelect.value, valueSelect.value);
    if (!next) return;
    Object.assign(chartData, next);
    titleEl.textContent = `${columnLabel(next.labelCol)} — ${columnLabel(next.numericCol)}`;
    titleEl.setAttribute('dir', isRtlText(titleEl.textContent) ? 'rtl' : 'ltr');
    rebuildChart(select.value);
  }

  labelSelect.addEventListener('change', () => {
    fillColumnSelect(valueSelect, cols, data[0], valueSelect.value, 'value', labelSelect.value);
    refreshChart();
  });
  valueSelect.addEventListener('change', refreshChart);

  select.addEventListener('change', () => {
    rebuildChart(select.value);
  });

  if (printBtn) {
    printBtn.addEventListener('click', () => {
      if (chartInstance) {
        printChartAsImage(chartInstance, titleEl.textContent || titleText);
      }
    });
  }
}

function printChartAsImage(chartOrCanvas, titleText) {
  let dataUrl = null;
  if (chartOrCanvas && typeof chartOrCanvas.getDataURL === 'function') {
    try {
      dataUrl = chartOrCanvas.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#ffffff' });
    } catch (_) {}
  }
  if (!dataUrl && chartOrCanvas && typeof chartOrCanvas.toDataURL === 'function') {
    try {
      dataUrl = chartOrCanvas.toDataURL('image/png', 1.0);
    } catch (_) {}
  }
  if (!dataUrl) return;

  const safeTitle = escapeHtml(titleText || '');
  const rtl = isRtlText(titleText || '');
  const iframe = document.createElement('iframe');
  iframe.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden;';
  document.body.appendChild(iframe);

  const doc = iframe.contentWindow.document;
  doc.open();
  doc.write(`<!DOCTYPE html>
<html dir="${rtl ? 'rtl' : 'ltr'}">
<head>
<meta charset="utf-8">
<title>${safeTitle}</title>
<style>
  html, body { margin: 0; padding: 24px; font-family: ${chartFontFamily()}; text-align: center; }
  h1 { font-size: 16px; color: #15523e; margin: 0 0 16px; }
  img { max-width: 100%; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.1); }
</style>
</head>
<body>
  <h1>${safeTitle}</h1>
  <img src="${dataUrl}" />
  <script>
    window.onload = function () {
      setTimeout(function () { window.focus(); window.print(); }, 60);
    };
  <\/script>
</body>
</html>`);
  doc.close();

  setTimeout(() => { iframe.remove(); }, 60000);
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

// ---------------------------------------------------------------------------
// Voice: speech-to-text (microphone input only) — FA + EN
// ---------------------------------------------------------------------------
function speechLocale(langHint) {
  const lang = langHint || state.language;
  return lang === 'fa' ? 'fa-IR' : 'en-US';
}

const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
let voiceRecognition = null;
let voiceListening = false;

function updateVoiceInputUi(listening) {
  const btn = document.getElementById('voice-input-btn');
  if (!btn) return;
  voiceListening = listening;
  btn.classList.toggle('is-listening', listening);
  btn.setAttribute('aria-pressed', listening ? 'true' : 'false');
  btn.title = listening
    ? chatUiText('voiceListening')
    : state.language === 'fa'
      ? 'ورودی صوتی (فارسی/انگلیسی)'
      : 'Voice input (FA/EN)';
  btn.setAttribute('aria-label', btn.title);
  btn.textContent = listening ? '⏹' : '🎤';
}

function stopVoiceInput() {
  if (voiceRecognition && voiceListening) {
    try {
      voiceRecognition.stop();
    } catch (_) { /* ignore */ }
  }
  updateVoiceInputUi(false);
}

function startVoiceInput() {
  if (!SpeechRecognitionAPI) {
    alert(chatUiText('voiceUnsupported'));
    return;
  }
  if (voiceListening) {
    stopVoiceInput();
    return;
  }

  voiceRecognition = new SpeechRecognitionAPI();
  voiceRecognition.lang = speechLocale(state.language);
  voiceRecognition.interimResults = true;
  voiceRecognition.continuous = false;
  voiceRecognition.maxAlternatives = 1;

  let finalTranscript = '';

  voiceRecognition.onstart = () => updateVoiceInputUi(true);
  voiceRecognition.onend = () => {
    updateVoiceInputUi(false);
    delete messageInput.dataset.voiceBase;
    messageInput.dir = isRtlText(messageInput.value) ? 'rtl' : 'ltr';
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
    messageInput.focus();
  };
  voiceRecognition.onerror = (ev) => {
    updateVoiceInputUi(false);
    delete messageInput.dataset.voiceBase;
    if (ev.error === 'not-allowed' || ev.error === 'service-not-allowed') {
      alert(chatUiText('voiceMicDenied'));
    }
  };
  voiceRecognition.onresult = (event) => {
    let interim = '';
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const chunk = event.results[i][0].transcript;
      if (event.results[i].isFinal) finalTranscript += `${chunk} `;
      else interim += chunk;
    }
    const base = messageInput.dataset.voiceBase || '';
    const preview = `${base}${finalTranscript}${interim}`.replace(/\s+/g, ' ').trim();
    messageInput.value = preview;
    messageInput.dir = isRtlText(preview) ? 'rtl' : 'ltr';
  };

  messageInput.dataset.voiceBase = messageInput.value ? `${messageInput.value.trim()} ` : '';
  try {
    voiceRecognition.start();
  } catch (_) {
    updateVoiceInputUi(false);
  }
}

const voiceInputBtn = document.getElementById('voice-input-btn');
if (voiceInputBtn) {
  if (!SpeechRecognitionAPI) {
    voiceInputBtn.disabled = true;
    voiceInputBtn.title = 'Voice input unsupported';
  } else {
    voiceInputBtn.addEventListener('click', startVoiceInput);
  }
}

// ---------------------------------------------------------------------------
// Feature poll (نظرسنجی قابلیت‌های آینده)
// ---------------------------------------------------------------------------
const pollCard = document.getElementById('feature-poll-card');
const pollOptionsEl = document.getElementById('poll-options');
const pollSubmitBtn = document.getElementById('poll-submit-btn');
const pollMsgEl = document.getElementById('poll-msg');
const pollResultsEl = document.getElementById('poll-results');

const pollState = {
  maxChoices: 3,
  options: [],
  customOptions: [],
  counts: {},
  totalVoters: 0,
  myVotes: [],
};

const CUSTOM_PREFIX = '_custom_';

function pollToFaDigits(n) {
  return String(n).replace(/\d/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[d]);
}

function showPollMsg(text, ok) {
  if (!pollMsgEl) return;
  pollMsgEl.textContent = text;
  pollMsgEl.classList.toggle('is-ok', !!ok);
  pollMsgEl.hidden = false;
}

function selectedPollFeatureIds() {
  return Array.from(
    pollOptionsEl.querySelectorAll('input[type="checkbox"]:checked'),
  ).map((el) => el.value);
}

function enforceMaxChoices() {
  const selected = selectedPollFeatureIds();
  if (selected.length > pollState.maxChoices) {
    const boxes = pollOptionsEl.querySelectorAll('input[type="checkbox"]:checked');
    const lastCb = boxes[boxes.length - 1];
    if (lastCb) {
      lastCb.checked = false;
      showPollMsg(`حداکثر ${pollToFaDigits(pollState.maxChoices)} گزینه قابل انتخاب است.`, false);
    }
  } else {
    if (pollMsgEl) pollMsgEl.hidden = true;
  }
}

function renderPollOptions() {
  pollOptionsEl.innerHTML = '';
  const allOpts = pollState.options.concat(pollState.customOptions || []);
  allOpts.forEach((opt) => {
    const label = document.createElement('label');
    label.className = 'poll-option';
    if (opt.id.startsWith(CUSTOM_PREFIX)) label.classList.add('poll-option-custom');
    const checked = pollState.myVotes.includes(opt.id) ? ' checked' : '';
    label.innerHTML = `
      <input type="checkbox" value="${escapeHtml(opt.id)}"${checked} />
      <span>${escapeHtml(opt.label)}</span>
    `;
    pollOptionsEl.appendChild(label);
  });

  pollOptionsEl.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
    cb.addEventListener('change', enforceMaxChoices);
  });
}

function renderPollResults() {
  if (!pollResultsEl) return;
  if (!pollState.totalVoters) {
    pollResultsEl.hidden = true;
    return;
  }
  const allOpts = pollState.options.concat(pollState.customOptions || []);
  const maxCount = Math.max(1, ...Object.values(pollState.counts));
  const rows = allOpts
    .slice()
    .sort((a, b) => (pollState.counts[b.id] || 0) - (pollState.counts[a.id] || 0))
    .map((opt) => {
      const count = pollState.counts[opt.id] || 0;
      const pct = Math.round((count / maxCount) * 100);
      const mine = pollState.myVotes.includes(opt.id) ? ' is-mine' : '';
      return `
        <div class="poll-result-row${mine}">
          <div class="poll-result-label">
            <span>${escapeHtml(opt.label)}</span>
            <b>${pollToFaDigits(count)}</b>
          </div>
          <div class="poll-result-bar"><i style="width:${pct}%"></i></div>
        </div>
      `;
    });
  pollResultsEl.innerHTML = `
    <div class="poll-results-title">نتایج تاکنون (${pollToFaDigits(pollState.totalVoters)} رأی‌دهنده)</div>
    ${rows.join('')}
  `;
  pollResultsEl.hidden = false;
}

function applyPollState(json) {
  pollState.options = json.options || [];
  pollState.customOptions = json.custom_options || [];
  pollState.counts = json.counts || {};
  pollState.totalVoters = json.total_voters || 0;
  pollState.myVotes = json.my_votes || [];
  pollState.maxChoices = json.max_choices || 3;
  renderPollOptions();
  renderPollResults();
  if (pollSubmitBtn) {
    pollSubmitBtn.textContent = pollState.myVotes.length ? 'به‌روزرسانی رأی' : 'ثبت رأی';
  }
}

async function loadFeaturePoll() {
  if (!pollCard) return;
  if (pollOptionsEl) {
    pollOptionsEl.innerHTML = '';
    for (let i = 0; i < 4; i += 1) {
      const row = document.createElement('div');
      row.className = 'skeleton-row';
      row.style.height = '32px';
      pollOptionsEl.appendChild(row);
    }
  }
  try {
    const res = await apiFetch('/api/feature-poll');
    if (!res.ok) throw new Error('poll load failed');
    applyPollState(await res.json());
  } catch (_) {
    pollCard.hidden = true;
  }
}

const pollCustomInput = document.getElementById('poll-custom-input');
const pollCustomAddBtn = document.getElementById('poll-custom-add-btn');

if (pollCustomAddBtn && pollCustomInput) {
  pollCustomAddBtn.addEventListener('click', () => {
    const text = pollCustomInput.value.trim();
    if (!text) { showPollMsg('متنی وارد کنید.', false); return; }
    if (text.length > 100) { showPollMsg('حداکثر ۱۰۰ کاراکتر مجاز است.', false); return; }
    const existing = pollOptionsEl.querySelectorAll('input[type="checkbox"]');
    const ids = Array.from(existing).map((cb) => cb.value);
    const prefix = CUSTOM_PREFIX + text;
    if (ids.includes(prefix)) { showPollMsg('این گزینه قبلاً اضافه شده.', false); return; }
    if (selectedPollFeatureIds().length >= pollState.maxChoices) {
      showPollMsg(`پیش از افزودن، یکی از انتخاب‌های فعلی را لغو کنید. حداکثر ${pollToFaDigits(pollState.maxChoices)}.`, false);
      return;
    }
    const label = document.createElement('label');
    label.className = 'poll-option poll-option-custom';
    label.innerHTML = `
      <input type="checkbox" value="${escapeHtml(prefix)}" checked />
      <span>${escapeHtml(text)}</span>
    `;
    pollOptionsEl.appendChild(label);
    label.querySelector('input').addEventListener('change', enforceMaxChoices);
    pollCustomInput.value = '';
    if (pollMsgEl) pollMsgEl.hidden = true;
  });

  pollCustomInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); pollCustomAddBtn.click(); }
  });
}

if (pollSubmitBtn) {
  pollSubmitBtn.addEventListener('click', async () => {
    const features = selectedPollFeatureIds();
    if (!features.length) {
      showPollMsg('حداقل یک گزینه را انتخاب کنید یا با نوشتن در کادر بالا گزینه جدید اضافه کنید.', false);
      return;
    }
    pollSubmitBtn.disabled = true;
    try {
      const res = await apiFetch('/api/feature-poll', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ features }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        showPollMsg(json.error || 'ثبت رأی ناموفق بود.', false);
        return;
      }
      applyPollState(json);
      showPollMsg('رأی شما با موفقیت ثبت شد. متشکریم! 🌱', true);
    } catch (_) {
      showPollMsg('خطا در ارتباط با سرور.', false);
    } finally {
      pollSubmitBtn.disabled = false;
    }
  });
}

function initDashboardAccordions() {
  const sidebar = document.getElementById('dash-sidebar');
  if (!sidebar) return;

  const cards = sidebar.querySelectorAll('.dash-card');
  cards.forEach((card) => {
    const titleEl = card.querySelector('.dash-card-title');
    if (!titleEl || titleEl.dataset.accordionWired === '1') return;
    titleEl.dataset.accordionWired = '1';

    // Start all cards collapsed for a clean sidebar
    card.classList.add('is-collapsed');
    titleEl.setAttribute('aria-expanded', 'false');

    const toggle = () => {
      const isCollapsed = card.classList.toggle('is-collapsed');
      titleEl.setAttribute('aria-expanded', String(!isCollapsed));
    };

    titleEl.addEventListener('click', toggle);
    titleEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggle();
      }
    });
  });
}

/* ================================================================
   What's New Modal
   ================================================================ */
function initWhatsNewModal() {
  const overlay = document.getElementById('whatsnew-overlay');
  const closeBtn = document.getElementById('whatsnew-close');
  const gotItBtn = document.getElementById('whatsnew-gotit');

  if (!overlay) return;

  const STORAGE_KEY = 'bichart_whatsnew_seen';
  const CURRENT_VERSION = 'v1';

  function hideModal() {
    overlay.setAttribute('hidden', '');
    try {
      localStorage.setItem(STORAGE_KEY, CURRENT_VERSION);
    } catch (e) {
      // localStorage unavailable — silently ignore
    }
  }

  function showModal() {
    overlay.removeAttribute('hidden');
  }

  // Check if user has already seen this version
  let hasSeen = false;
  try {
    hasSeen = localStorage.getItem(STORAGE_KEY) === CURRENT_VERSION;
  } catch (e) {
    // localStorage unavailable — show modal anyway
  }

  if (!hasSeen) {
    showModal();
  }

  // Close handlers
  if (closeBtn) {
    closeBtn.addEventListener('click', hideModal);
  }
  if (gotItBtn) {
    gotItBtn.addEventListener('click', hideModal);
  }

  // Close on overlay click (clicking outside the modal)
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) {
      hideModal();
    }
  });

  // Close on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !overlay.hasAttribute('hidden')) {
      hideModal();
    }
  });
}

if (document.readyState === 'loading') {
  window.addEventListener('DOMContentLoaded', () => {
    loadFeaturePoll();
    initDashboardAccordions();
    initWhatsNewModal();
  });
} else {
  loadFeaturePoll();
  initDashboardAccordions();
  initWhatsNewModal();
}

// ---------------------------------------------------------------------------
// Bilingual System Help Panel Modal
// ---------------------------------------------------------------------------
const HELP_FEATURES = {
  fa: {
    title: 'راهنمای جامع دستیار هوش تجاری',
    subtitle: 'آشنایی کامل با تمامی قابلیت‌ها و امکانات پیشرفته سیستم',
    footerNote: '💡 نکته: برای شروع سریع، می‌توانید بر روی یکی از پیشنهادهای آزمایشی کلیک کنید.',
    gotitBtn: 'متوجه شدم',
    sampleTitle: 'پیشنهاد آزمایشی سریع:',
    features: [
      {
        icon: '🤖',
        title: '۱. پرسش و پاسخ هوشمند و SQL خودکار',
        badge: 'هوش مصنوعی تعاملی',
        desc: 'پرسش درباره داده‌ها به زبان فارسی یا انگلیسی. تولید خودکار و هوشمند queries SQL توسط مدل‌های هوش مصنوعی (API / Ollama) با قابلیت اصلاح خودکار خطاها (Auto-Fix) و ویرایش دستی کد.',
        prompt: '۱۰ فروشنده برتر از نظر حجم تراکنش را نشان بده',
      },
      {
        icon: '📊',
        title: '۲. ۴ نمودار هم‌زمان و پاپ‌آپ بزرگ‌نمایی',
        badge: 'تجسم پیشرفته داده‌ها',
        desc: 'رسم خودکار ۴ نمودار متناسب با داده‌ها در ۴ مربع خلوت (میله‌ای، خطی، دایره‌ای، افقی). کلیک روی هر مربع، پنجره پاپ‌آپ بزرگ‌نمایی تعاملی با امکان تغییر نوع نمودار و ستون‌ها را باز می‌کند.',
        prompt: 'نمودار حجم تراکنش ماهانه',
      },
      {
        icon: '🖼️',
        title: '۳. پوستر تصویری اینفوگرافیک',
        badge: 'گزارش‌دهی تصویری',
        desc: 'تولید خودکار پوستر داده‌محور شیک شامل شاخص‌های کلیدی عملکرد (KPIs) و برترین دسته‌ها پس از تحلیل، همراه با قابلیت دانلود تصویر کیفیت بالای PNG.',
        prompt: 'خلاصه تراکنش‌های امروز را بده',
      },
      {
        icon: '💬',
        title: '۴. بحث و بررسی هوشمند نتایج',
        badge: 'تحلیل تعاملی و اصلاحیه',
        desc: 'امکان انتخاب یا هایلایت کردن هر بخش از متن تحلیل AI، ارسال سؤال، اعتراض یا چالش برای هوش مصنوعی و جایگزینی مستقیم پاسخ در گزارش اصلی.',
        prompt: 'تراکنش‌های ناموفق دیروز را نشان بده',
      },
      {
        icon: '🔊',
        title: '۵. ورودی صوتی دو زبانه (FA/EN)',
        badge: 'پردازش گفتار صوتی',
        desc: 'پرسش سوالات تراکنشی به صورت صوتی با استفاده از دکمه میکروفون به هر دو زبان فارسی و انگلیسی بدون نیاز به تایپ کردن.',
      },
      {
        icon: '📤',
        title: '۶. خروجی PDF و Excel با یک کلیک',
        badge: 'گزارش‌گیری استاندارد',
        desc: 'دریافت خروجی کامل گزارش شامل متن تحلیل هوش مصنوعی، تصویر نمودار گرافیکی و جدول داده‌ها در قالب فایل‌های رسمی PDF و Excel.',
      },
      {
        icon: '⏱️',
        title: '۷. پایش زمان‌بندی سرویس‌ها (Timings)',
        badge: 'شفافیت فرایند processing',
        desc: 'مشاهده دقیق مدت زمان تفکیکی هر مرحله از فرایند پردازش (تولید SQL، بررسی امنیت، اجرای دیتابیس، تحلیل و بحث) به صورت نمودار میله‌ای.',
      },
      {
        icon: '🕘',
        title: '۸. تاریخچه، سؤالات پرتکرار و نظرسنجی',
        badge: 'مدیریت و شخصی‌سازی',
        desc: 'دسترسی سریع به ۱۰ سؤال پرتکرار، بازپخش کامل گفتگوی قدیمی، کارت‌های جمع‌شونده نوار کناری و مشارکت در نظرسنجی قابلیت‌های آتی.',
      },
    ],
  },
  en: {
    title: 'Complete BI Assistant Guide',
    subtitle: 'Explore all key features and advanced analytical capabilities of the platform',
    footerNote: '💡 Tip: Click on any sample prompt to test it immediately.',
    gotitBtn: 'Got it',
    sampleTitle: 'Quick sample prompt:',
    features: [
      {
        icon: '🤖',
        title: '1. Conversational AI & Automatic SQL',
        badge: 'Interactive AI Query',
        desc: 'Ask transaction questions in natural Persian or English. AI automatically constructs SQL queries using API/Ollama with manual editing and automatic error self-healing (Auto-Fix).',
        prompt: 'Show top 10 merchants by volume',
      },
      {
        icon: '📊',
        title: '2. Interactive 4-Chart Quad Grid & Modal Zoom',
        badge: 'Data Visualization',
        desc: 'Renders 4 clean analytical charts (Vertical Bar, Line, Pie, Horizontal Bar) in 4 square cards. Click any card to open an interactive pop-up zoom with chart type & column selectors.',
        prompt: 'Show monthly transaction volume chart',
      },
      {
        icon: '🖼️',
        title: '3. Infographic Visual Poster',
        badge: 'Visual Reporting',
        desc: 'Automatic generation of data-driven infographic posters featuring Key Performance Indicators (KPIs) and top category shares, downloadable as high-resolution PNG images.',
        prompt: 'Show today transaction summary',
      },
      {
        icon: '💬',
        title: '4. Discussion & Challenge Panel',
        badge: 'Interactive Analysis Refinement',
        desc: 'Highlight any sentence or text snippet in the AI analysis to challenge or clarify. Smart AI replies can be applied directly to update the original report text.',
        prompt: 'Show yesterday failed transactions',
      },
      {
        icon: '🔊',
        title: '5. Bilingual Voice Input (FA/EN)',
        badge: 'Speech Recognition',
        desc: 'Ask transaction questions directly via speech recognition in Persian or English by clicking the microphone icon without typing.',
      },
      {
        icon: '📤',
        title: '6. One-Click PDF & Excel Exports',
        badge: 'Standard Exporting',
        desc: 'Export full reports containing AI analysis text, high-res chart visuals, and formatted data tables into standard PDF and Excel files.',
      },
      {
        icon: '⏱️',
        title: '7. Service Pipeline Timings',
        badge: 'Processing Transparency',
        desc: 'Inspect step-by-step performance timelines for SQL generation, safety checks, database queries, analysis, and discussion.',
      },
      {
        icon: '🕘',
        title: '8. History, Top Questions & Feature Poll',
        badge: 'Management & Personalization',
        desc: 'Quick access to top 10 frequent questions, historical conversation replay, collapsible sidebar panels, and community feature voting.',
      },
    ],
  },
};

const helpModalState = {
  lang: 'fa',
};

function openHelpModal() {
  const overlay = document.getElementById('help-modal-overlay');
  if (!overlay) return;
  overlay.removeAttribute('hidden');
  overlay.style.display = 'flex';
  document.body.style.overflow = 'hidden';
  renderHelpContent();
}

function closeHelpModal() {
  const overlay = document.getElementById('help-modal-overlay');
  if (!overlay) return;
  overlay.setAttribute('hidden', '');
  overlay.style.display = 'none';
  document.body.style.overflow = '';
}

function setupHelpModal() {
  const helpBtn = document.getElementById('help-btn');
  const overlay = document.getElementById('help-modal-overlay');
  if (!overlay) return;

  const closeBtn = document.getElementById('help-modal-close');
  const gotitBtn = document.getElementById('help-gotit-btn');
  const faBtn = document.getElementById('help-lang-fa');
  const enBtn = document.getElementById('help-lang-en');

  if (helpBtn) helpBtn.addEventListener('click', openHelpModal);
  if (closeBtn) closeBtn.addEventListener('click', closeHelpModal);
  if (gotitBtn) gotitBtn.addEventListener('click', closeHelpModal);

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeHelpModal();
  });

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !overlay.hasAttribute('hidden')) {
      closeHelpModal();
    }
  });

  if (faBtn) {
    faBtn.addEventListener('click', () => {
      helpModalState.lang = 'fa';
      faBtn.classList.add('is-active');
      if (enBtn) enBtn.classList.remove('is-active');
      renderHelpContent();
    });
  }

  if (enBtn) {
    enBtn.addEventListener('click', () => {
      helpModalState.lang = 'en';
      enBtn.classList.add('is-active');
      if (faBtn) faBtn.classList.remove('is-active');
      renderHelpContent();
    });
  }
}

// Allow native navigation to /help page via <a href="/help">

function renderHelpContent() {
  const bodyEl = document.getElementById('help-modal-body');
  const titleEl = document.getElementById('help-modal-title');
  const subtitleEl = document.getElementById('help-modal-subtitle');
  const noteEl = document.getElementById('help-footer-note');
  const gotitBtn = document.getElementById('help-gotit-btn');
  if (!bodyEl) return;

  const lang = helpModalState.lang || 'fa';
  const content = HELP_FEATURES[lang];

  if (titleEl) {
    titleEl.textContent = content.title;
    titleEl.setAttribute('dir', lang === 'fa' ? 'rtl' : 'ltr');
  }
  if (subtitleEl) {
    subtitleEl.textContent = content.subtitle;
    subtitleEl.setAttribute('dir', lang === 'fa' ? 'rtl' : 'ltr');
  }
  if (noteEl) {
    noteEl.textContent = content.footerNote;
    noteEl.setAttribute('dir', lang === 'fa' ? 'rtl' : 'ltr');
  }
  if (gotitBtn) {
    gotitBtn.textContent = content.gotitBtn;
  }

  const cardsHtml = content.features.map((item) => `
    <div class="help-card" dir="${lang === 'fa' ? 'rtl' : 'ltr'}">
      <div class="help-card-header">
        <span class="help-card-icon">${item.icon}</span>
        <div class="help-card-title-wrap">
          <h3 class="help-card-title">${escapeHtml(item.title)}</h3>
          <span class="help-card-badge">${escapeHtml(item.badge)}</span>
        </div>
      </div>
      <p class="help-card-desc">${escapeHtml(item.desc)}</p>
      ${item.prompt ? `
        <div class="help-prompts-wrap">
          <span class="help-prompts-title">${escapeHtml(content.sampleTitle)}</span>
          <button type="button" class="help-prompt-tag" data-prompt="${escapeHtml(item.prompt)}">${escapeHtml(item.prompt)}</button>
        </div>
      ` : ''}
    </div>
  `).join('');

  bodyEl.innerHTML = `<div class="help-grid">${cardsHtml}</div>`;

  bodyEl.querySelectorAll('.help-prompt-tag').forEach((btn) => {
    btn.addEventListener('click', () => {
      const q = btn.getAttribute('data-prompt');
      if (!q) return;
      closeHelpModal();
      messageInput.value = q;
      messageInput.dir = isRtlText(q) ? 'rtl' : 'ltr';
      sendMessage();
    });
  });
}
