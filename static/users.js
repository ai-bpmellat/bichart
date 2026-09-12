const tbody = document.getElementById('users-tbody');
const table = document.getElementById('users-table');
const empty = document.getElementById('users-empty');
const msg = document.getElementById('users-msg');
const modal = document.getElementById('user-modal');
const form = document.getElementById('user-form');
const modalTitle = document.getElementById('modal-title');
const pwdHint = document.getElementById('pwd-hint');
const activeWrap = document.getElementById('active-wrap');

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
  if (editUser) {
    modalTitle.textContent = 'ویرایش اطلاعات و سطح کاربر';
    document.getElementById('user-id').value = editUser.id;
    document.getElementById('f-display').value = editUser.display_name || '';
    document.getElementById('f-username').value = editUser.username || '';
    document.getElementById('f-email').value = editUser.email || '';
    document.getElementById('f-mobile').value = editUser.mobile || '';
    document.getElementById('f-password').value = '';
    document.getElementById('f-tier').value = editUser.tier || 'tier1';
    document.getElementById('f-role').value = editUser.role || 'user';
    document.getElementById('f-active').value = editUser.is_active ? 'true' : 'false';
    pwdHint.textContent = '(اختیاری — فقط در صورت تغییر رمز)';
    activeWrap.hidden = false;
  } else {
    modalTitle.textContent = 'افزودن کاربر جدید';
    document.getElementById('user-id').value = '';
    document.getElementById('f-tier').value = 'tier1';
    document.getElementById('f-role').value = 'user';
    pwdHint.textContent = '(الزامی)';
    activeWrap.hidden = true;
  }
  modal.classList.add('open');
}

function closeModal() {
  modal.classList.remove('open');
}

function renderUsers(users) {
  tbody.innerHTML = '';
  if (!users.length) {
    table.hidden = true;
    empty.hidden = false;
    return;
  }
  empty.hidden = true;
  table.hidden = false;
  users.forEach((u) => {
    const tr = document.createElement('tr');

    const roleBadge = u.role === 'admin'
      ? `<span class="badge badge-admin">👑 مدیر سیستم</span>`
      : `<span class="badge badge-user">کاربر عادی</span>`;

    const tierBadge = u.tier === 'premium'
      ? `<span class="badge badge-premium">🌟 کاربر برتر</span>`
      : `<span class="badge badge-tier1">کاربر سطح ۱</span>`;

    const usageText = u.role === 'admin' || u.tier === 'premium'
      ? `<span class="usage-pill" title="بدون سقف روزانه">${u.queries_today ?? 0} (نامحدود)</span>`
      : `<span class="usage-pill" title="سقف ۱۰ پرسش در روز">${u.queries_today ?? 0} از ${u.daily_limit ?? 10}</span>`;

    tr.innerHTML = `
      <td><strong>${escapeHtml(u.display_name || '')}</strong></td>
      <td><code>${escapeHtml(u.username || '')}</code></td>
      <td>${escapeHtml(u.email || '-')}</td>
      <td>${escapeHtml(u.mobile || '-')}</td>
      <td>${roleBadge}</td>
      <td>${tierBadge}</td>
      <td>${usageText}</td>
      <td><span class="badge ${u.is_active ? 'badge-on' : 'badge-off'}">${u.is_active ? 'فعال' : 'غیرفعال'}</span></td>
      <td>
        <div class="row-btns">
          <button type="button" class="ghost-btn tiny btn-edit">ویرایش / ارتقا</button>
          <button type="button" class="ghost-btn tiny danger btn-del">حذف</button>
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
  if (!confirm(`کاربر «${u.username}» حذف شود؟`)) return;
  try {
    await api(`/api/users/${u.id}`, { method: 'DELETE' });
    showMsg('کاربر با موفقیت حذف شد.', true);
    await loadUsers();
  } catch (e) {
    showMsg(e.message, false);
  }
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
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
    showMsg('رمز عبور برای کاربر جدید الزامی است.', false);
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
      showMsg('اطلاعات و سطح کاربر با موفقیت به‌روزرسانی شد.', true);
    } else {
      await api('/api/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      showMsg('کاربر جدید با موفقیت ایجاد شد.', true);
    }
    closeModal();
    await loadUsers();
  } catch (err) {
    showMsg(err.message, false);
  }
});

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
