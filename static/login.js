const loginForm = document.getElementById('login-form');
const usernameInput = document.getElementById('username-input');
const passwordInput = document.getElementById('password-input');
const loginBtn = document.getElementById('login-btn');
const loginError = document.getElementById('login-error');

loginForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  loginError.hidden = true;

  const username = usernameInput.value.trim();
  const password = passwordInput.value;
  if (!username || !password) {
    showError('نام کاربری و رمز عبور را وارد کنید.');
    return;
  }

  loginBtn.disabled = true;
  loginBtn.textContent = 'در حال ورود…';

  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const json = await res.json().catch(() => ({}));

    if (!res.ok) {
      showError(json.error || 'ورود ناموفق بود.');
      return;
    }

    window.location.href = '/app';
  } catch (_) {
    showError('خطا در ارتباط با سرور.');
  } finally {
    loginBtn.disabled = false;
    loginBtn.textContent = 'ورود';
  }
});

function showError(message) {
  loginError.textContent = message;
  loginError.hidden = false;
}
