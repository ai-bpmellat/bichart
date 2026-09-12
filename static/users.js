const tbody = document.getElementById('users-tbody');
const table = document.getElementById('users-table');
const empty = document.getElementById('users-empty');
const msg = document.getElementById('users-msg');
const modal = document.getElementById('user-modal');
const form = document.getElementById('user-form');
const modalTitle = document.getElementById('modal-title');
const pwdHint = document.getElementById('pwd-hint');
const activeWrap = document.getElementById('active-wrap');
const btnLang = document.getElementById('btn-lang');

let cachedUsers = [];
let currentEditingUser = null;
let currentLang = localStorage.getItem('rayamate_lang') || 'fa';

const I18N_USERS = {
  fa: {
    pageTitle: 'مدیریت کاربران و سطوح دسترسی — Rayamate',
    h1: 'مدیریت کاربران و سطح‌بندی',
    subtitle: 'تعیین سطوح دسترسی (سطح ۳: ۵ پیام کل، سطح ۲: ۱۰ پیام روزانه، سطح ۱: نامحدود، مدیر) و نظارت بر مصرف',
    backBtn: 'بازگشت به برنامه',
    langBtn: 'EN',
    langBtnTitle: 'Switch to English',
    addBtn: 'افزودن کاربر',
    logoutBtn: 'خروج',
    emptyMsg: 'هنوز کاربری ثبت نشده است.',
    thDisplay: 'نام نمایشی',
    thUsername: 'نام کاربری',
    thEmail: 'ایمیل',
    thMobile: 'موبایل',
    thRole: 'نقش سیستم',
    thTier: 'سطح کاربری',
    thUsage: 'میزان مصرف',
    thStatus: 'وضعیت',
    thActions: 'عملیات',
    modalTitleAdd: 'افزودن کاربر جدید',
    modalTitleEdit: 'ویرایش اطلاعات و سطح کاربر',
    lblDisplay: 'نام و نام خانوادگی',
    fDisplayPlh: 'مثلاً علی رضایی',
    lblUsername: 'نام کاربری',
    lblEmail: 'آدرس ایمیل',
    lblMobile: 'شماره موبایل',
    lblPwd: 'رمز عبور',
    pwdReq: '(الزامی)',
    pwdOpt: '(اختیاری — فقط در صورت تغییر رمز)',
    lblTier: 'سطح کاربری',
    optTier3: 'کاربر سطح ۳ (محدود به ۵ پیام در کل — پیش‌فرض ثبت‌نام)',
    optTier2: 'کاربر سطح ۲ (محدود به ۱۰ پیام در روز)',
    optTier1: 'کاربر سطح ۱ (نامحدود)',
    lblRole: 'نقش سیستمی',
    optRoleUser: 'کاربر عادی',
    optRoleAdmin: 'مدیر سیستم (دسترسی کامل و مدیریت کاربران)',
    lblActive: 'وضعیت حساب',
    optActiveTrue: 'فعال',
    optActiveFalse: 'غیرفعال',
    btnSave: 'ذخیره اطلاعات',
    btnCancel: 'انصراف',
    roleAdmin: '👑 مدیر سیستم',
    roleUser: 'کاربر عادی',
    tier1: '🌟 سطح ۱ (نامحدود)',
    tier2: 'سطح ۲ (۱۰ روزانه)',
    tier3: 'سطح ۳ (۵ پیام کل)',
    statusActive: 'فعال',
    statusInactive: 'غیرفعال',
    btnEdit: 'ویرایش / ارتقا',
    btnDel: 'حذف',
    delConfirm: 'کاربر «{username}» حذف شود؟',
    delSuccess: 'کاربر با موفقیت حذف شد.',
    saveSuccessUpdate: 'اطلاعات و سطح کاربر با موفقیت به‌روزرسانی شد.',
    saveSuccessCreate: 'کاربر جدید با موفقیت ایجاد شد.',
    pwdRequiredAlert: 'رمز عبور برای کاربر جدید الزامی است.',
    titleUnlimited: 'بدون محدودیت پیام',
    titleTier2: 'سقف ۱۰ پیام در روز',
    titleTier3: 'سقف ۵ پیام در کل',
  },
  en: {
    pageTitle: 'User & Tier Management — Rayamate',
    h1: 'User & Tier Management',
    subtitle: 'Configure user tiers (Tier 3: 5 total queries, Tier 2: 10 daily queries, Tier 1: unlimited, Admin) and track usage',
    backBtn: 'Back to App',
    langBtn: 'FA',
    langBtnTitle: 'تغییر به زبان فارسی',
    addBtn: 'Add User',
    logoutBtn: 'Logout',
    emptyMsg: 'No users registered yet.',
    thDisplay: 'Display Name',
    thUsername: 'Username',
    thEmail: 'Email',
    thMobile: 'Mobile',
    thRole: 'Role',
    thTier: 'User Tier',
    thUsage: 'Usage',
    thStatus: 'Status',
    thActions: 'Actions',
    modalTitleAdd: 'Add New User',
    modalTitleEdit: 'Edit User & Tier',
    lblDisplay: 'Full Name',
    fDisplayPlh: 'e.g. John Doe',
    lblUsername: 'Username',
    lblEmail: 'Email Address',
    lblMobile: 'Mobile Number',
    lblPwd: 'Password',
    pwdReq: '(Required)',
    pwdOpt: '(Optional — only if changing password)',
    lblTier: 'User Tier',
    optTier3: 'Tier 3 User (Limit 5 lifetime queries — default)',
    optTier2: 'Tier 2 User (Limit 10 queries/day)',
    optTier1: 'Tier 1 User (Unlimited queries)',
    lblRole: 'System Role',
    optRoleUser: 'Standard User',
    optRoleAdmin: 'System Admin (Full access & user management)',
    lblActive: 'Account Status',
    optActiveTrue: 'Active',
    optActiveFalse: 'Inactive',
    btnSave: 'Save User',
    btnCancel: 'Cancel',
    roleAdmin: '👑 System Admin',
    roleUser: 'Standard User',
    tier1: '🌟 Tier 1 (Unlimited)',
    tier2: 'Tier 2 (10 Daily)',
    tier3: 'Tier 3 (5 Total)',
    statusActive: 'Active',
    statusInactive: 'Inactive',
    btnEdit: 'Edit / Upgrade',
    btnDel: 'Delete',
    delConfirm: 'Delete user "{username}"?',
    delSuccess: 'User deleted successfully.',
    saveSuccessUpdate: 'User information and tier updated successfully.',
    saveSuccessCreate: 'New user created successfully.',
    pwdRequiredAlert: 'Password is required for a new user.',
    titleUnlimited: 'Unlimited queries',
    titleTier2: 'Limit 10 queries per day',
    titleTier3: 'Limit 5 lifetime queries',
  }
};

function applyUsersLanguage(lang) {
  currentLang = lang;
  localStorage.setItem('rayamate_lang', lang);
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === 'en' ? 'ltr' : 'rtl';

  const dict = I18N_USERS[lang] || I18N_USERS.fa;

  document.title = dict.pageTitle;
  const pTitle = document.getElementById('page-title');
  if (pTitle) pTitle.textContent = dict.h1;
  const pSub = document.getElementById('page-subtitle');
  if (pSub) pSub.textContent = dict.subtitle;
  const bBack = document.getElementById('btn-back');
  if (bBack) bBack.textContent = dict.backBtn;
  if (btnLang) {
    btnLang.textContent = dict.langBtn;
    btnLang.title = dict.langBtnTitle;
  }
  const bAdd = document.getElementById('btn-add');
  if (bAdd) bAdd.textContent = dict.addBtn;
  const bLogout = document.getElementById('btn-logout');
  if (bLogout) bLogout.textContent = dict.logoutBtn;
  if (empty) empty.textContent = dict.emptyMsg;

  // Table headers
  const thMap = {
    'th-display': dict.thDisplay,
    'th-username': dict.thUsername,
    'th-email': dict.thEmail,
    'th-mobile': dict.thMobile,
    'th-role': dict.thRole,
    'th-tier': dict.thTier,
    'th-usage': dict.thUsage,
    'th-status': dict.thStatus,
    'th-actions': dict.thActions,
  };
  Object.keys(thMap).forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.textContent = thMap[id];
  });

  // Modal labels & options
  const lblDisplay = document.getElementById('lbl-display');
  if (lblDisplay) lblDisplay.textContent = dict.lblDisplay;
  const fDisplay = document.getElementById('f-display');
  if (fDisplay) fDisplay.placeholder = dict.fDisplayPlh;
  const lblUsername = document.getElementById('lbl-username');
  if (lblUsername) lblUsername.textContent = dict.lblUsername;
  const lblEmail = document.getElementById('lbl-email');
  if (lblEmail) lblEmail.textContent = dict.lblEmail;
  const lblMobile = document.getElementById('lbl-mobile');
  if (lblMobile) lblMobile.textContent = dict.lblMobile;
  const lblPwdText = document.getElementById('lbl-pwd-text');
  if (lblPwdText) lblPwdText.textContent = dict.lblPwd;
  if (pwdHint) {
    pwdHint.textContent = currentEditingUser ? dict.pwdOpt : dict.pwdReq;
  }
  const lblTier = document.getElementById('lbl-tier');
  if (lblTier) lblTier.textContent = dict.lblTier;
  const optTier3 = document.getElementById('opt-tier3');
  if (optTier3) optTier3.textContent = dict.optTier3;
  const optTier2 = document.getElementById('opt-tier2');
  if (optTier2) optTier2.textContent = dict.optTier2;
  const optTier1 = document.getElementById('opt-tier1');
  if (optTier1) optTier1.textContent = dict.optTier1;
  const lblRole = document.getElementById('lbl-role');
  if (lblRole) lblRole.textContent = dict.lblRole;
  const optRoleUser = document.getElementById('opt-role-user');
  if (optRoleUser) optRoleUser.textContent = dict.optRoleUser;
  const optRoleAdmin = document.getElementById('opt-role-admin');
  if (optRoleAdmin) optRoleAdmin.textContent = dict.optRoleAdmin;
  const lblActive = document.getElementById('lbl-active');
  if (lblActive) lblActive.textContent = dict.lblActive;
  const optActiveTrue = document.getElementById('opt-active-true');
  if (optActiveTrue) optActiveTrue.textContent = dict.optActiveTrue;
  const optActiveFalse = document.getElementById('opt-active-false');
  if (optActiveFalse) optActiveFalse.textContent = dict.optActiveFalse;
  const bSave = document.getElementById('btn-save');
  if (bSave) bSave.textContent = dict.btnSave;
  const bCancel = document.getElementById('btn-cancel');
  if (bCancel) bCancel.textContent = dict.btnCancel;

  if (modalTitle) {
    modalTitle.textContent = currentEditingUser ? dict.modalTitleEdit : dict.modalTitleAdd;
  }
}

async function api(url, options) {
  const res = await fetch(url, options);
  if (res.status === 401) {
    window.location.href = '/login';
    throw new Error('unauthorized');
  }
  if (res.status === 403) {
    window.location.href = '/app';
    throw new Error('forbidden');
  }
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.error || 'Request failed');
  return json;
}

function showMsg(text, ok) {
  msg.textContent = text;
  msg.className = `msg show ${ok ? 'ok' : 'err'}`;
}

function clearMsg() {
  msg.className = 'msg';
  msg.textContent = '';
}

function openModal(editUser) {
  clearMsg();
  form.reset();
  currentEditingUser = editUser;
  const dict = I18N_USERS[currentLang] || I18N_USERS.fa;

  if (editUser) {
    modalTitle.textContent = dict.modalTitleEdit;
    document.getElementById('user-id').value = editUser.id;
    document.getElementById('f-display').value = editUser.display_name || '';
    document.getElementById('f-username').value = editUser.username || '';
    document.getElementById('f-email').value = editUser.email || '';
    document.getElementById('f-mobile').value = editUser.mobile || '';
    document.getElementById('f-password').value = '';
    document.getElementById('f-tier').value = editUser.tier || 'tier3';
    document.getElementById('f-role').value = editUser.role || 'user';
    document.getElementById('f-active').value = editUser.is_active ? 'true' : 'false';
    pwdHint.textContent = dict.pwdOpt;
    activeWrap.hidden = false;
  } else {
    modalTitle.textContent = dict.modalTitleAdd;
    document.getElementById('user-id').value = '';
    document.getElementById('f-tier').value = 'tier3';
    document.getElementById('f-role').value = 'user';
    pwdHint.textContent = dict.pwdReq;
    activeWrap.hidden = true;
  }
  modal.classList.add('open');
}

function closeModal() {
  modal.classList.remove('open');
  currentEditingUser = null;
}

function renderUsers(users) {
  cachedUsers = users || [];
  tbody.innerHTML = '';
  const dict = I18N_USERS[currentLang] || I18N_USERS.fa;
  const isEn = currentLang === 'en';

  if (!cachedUsers.length) {
    table.hidden = true;
    empty.hidden = false;
    return;
  }
  empty.hidden = true;
  table.hidden = false;

  cachedUsers.forEach((u) => {
    const tr = document.createElement('tr');

    const roleBadge = u.role === 'admin'
      ? `<span class="badge badge-admin">${dict.roleAdmin}</span>`
      : `<span class="badge badge-user">${dict.roleUser}</span>`;

    let tierBadge = '';
    if (u.role === 'admin' || u.tier === 'tier1' || u.tier === 'premium') {
      tierBadge = `<span class="badge badge-tier1">${dict.tier1}</span>`;
    } else if (u.tier === 'tier2') {
      tierBadge = `<span class="badge badge-tier2">${dict.tier2}</span>`;
    } else {
      tierBadge = `<span class="badge badge-tier3">${dict.tier3}</span>`;
    }

    let usageText = '';
    if (u.role === 'admin' || u.tier === 'tier1' || u.tier === 'premium') {
      const total = u.total_queries ?? 0;
      const today = u.queries_today ?? 0;
      const text = isEn ? `${total} total (${today} today) — Unlimited` : `${total} کل (${today} امروز) — نامحدود`;
      usageText = `<span class="usage-pill" title="${dict.titleUnlimited}">${text}</span>`;
    } else if (u.tier === 'tier2') {
      const today = u.queries_today ?? 0;
      const total = u.total_queries ?? 0;
      const text = isEn ? `${today} of 10 today (${total} total)` : `${today} از ۱۰ امروز (${total} کل)`;
      usageText = `<span class="usage-pill" title="${dict.titleTier2}">${text}</span>`;
    } else {
      const total = u.total_queries ?? 0;
      const text = isEn ? `${total} of 5 lifetime` : `${total} از ۵ پیام کل`;
      usageText = `<span class="usage-pill" title="${dict.titleTier3}">${text}</span>`;
    }

    const statusBadge = `<span class="badge ${u.is_active ? 'badge-on' : 'badge-off'}">${u.is_active ? dict.statusActive : dict.statusInactive}</span>`;

    tr.innerHTML = `
      <td><strong>${escapeHtml(u.display_name || '')}</strong></td>
      <td><code>${escapeHtml(u.username || '')}</code></td>
      <td>${escapeHtml(u.email || '-')}</td>
      <td>${escapeHtml(u.mobile || '-')}</td>
      <td>${roleBadge}</td>
      <td>${tierBadge}</td>
      <td>${usageText}</td>
      <td>${statusBadge}</td>
      <td>
        <div class="row-btns">
          <button type="button" class="ghost-btn tiny btn-edit">${dict.btnEdit}</button>
          <button type="button" class="ghost-btn tiny danger btn-del">${dict.btnDel}</button>
        </div>
      </td>
    `;
    tr.querySelector('.btn-edit').addEventListener('click', () => openModal(u));
    tr.querySelector('.btn-del').addEventListener('click', () => removeUser(u));
    tbody.appendChild(tr);
  });
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function loadUsers() {
  const data = await api('/api/users');
  renderUsers(data.users || []);
}

async function removeUser(u) {
  const dict = I18N_USERS[currentLang] || I18N_USERS.fa;
  const confirmMsg = dict.delConfirm.replace('{username}', u.username);
  if (!confirm(confirmMsg)) return;
  try {
    await api(`/api/users/${u.id}`, { method: 'DELETE' });
    showMsg(dict.delSuccess, true);
    await loadUsers();
  } catch (e) {
    showMsg(e.message, false);
  }
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const dict = I18N_USERS[currentLang] || I18N_USERS.fa;
  const id = document.getElementById('user-id').value;
  const payload = {
    display_name: document.getElementById('f-display').value.trim(),
    username: document.getElementById('f-username').value.trim(),
    email: document.getElementById('f-email').value.trim(),
    mobile: document.getElementById('f-mobile').value.trim(),
    tier: document.getElementById('f-tier').value,
    role: document.getElementById('f-role').value,
  };
  const password = document.getElementById('f-password').value;
  if (!id && !password) {
    showMsg(dict.pwdRequiredAlert, false);
    return;
  }
  if (password) payload.password = password;

  try {
    if (id) {
      payload.is_active = document.getElementById('f-active').value === 'true';
      await api(`/api/users/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      showMsg(dict.saveSuccessUpdate, true);
    } else {
      await api('/api/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      showMsg(dict.saveSuccessCreate, true);
    }
    closeModal();
    await loadUsers();
  } catch (err) {
    showMsg(err.message, false);
  }
});

if (btnLang) {
  btnLang.addEventListener('click', () => {
    const nextLang = currentLang === 'fa' ? 'en' : 'fa';
    applyUsersLanguage(nextLang);
    renderUsers(cachedUsers);
  });
}

document.getElementById('btn-add').addEventListener('click', () => openModal(null));
document.getElementById('btn-cancel').addEventListener('click', closeModal);
document.getElementById('btn-logout').addEventListener('click', async () => {
  await fetch('/api/logout', { method: 'POST' });
  window.location.href = '/login';
});
modal.addEventListener('click', (e) => {
  if (e.target === modal) closeModal();
});

(async function init() {
  try {
    applyUsersLanguage(currentLang);
    const me = await api('/api/me');
    if (me.role !== 'admin') {
      window.location.href = '/app';
      return;
    }
    await loadUsers();
  } catch (_) {
    /* redirects handled in api() */
  }
})();
