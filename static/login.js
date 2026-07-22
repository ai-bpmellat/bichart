const loginForm = document.getElementById('login-form');
const usernameInput = document.getElementById('username-input');
const passwordInput = document.getElementById('password-input');
const captchaInput = document.getElementById('captcha-input');
const loginBtn = document.getElementById('login-btn');
const loginError = document.getElementById('login-error');
const togglePass = document.getElementById('toggle-pass');
const rememberMe = document.getElementById('remember-me');
const forgotLink = document.getElementById('forgot-link');
const companyLoginBtn = document.getElementById('company-login-btn');

const REMEMBER_KEY = 'rayamate_remember_user';

if (usernameInput) {
  const saved = localStorage.getItem(REMEMBER_KEY);
  if (saved) {
    usernameInput.value = saved;
    if (rememberMe) rememberMe.checked = true;
  }
}

if (togglePass && passwordInput) {
  togglePass.addEventListener('click', () => {
    const show = passwordInput.type === 'password';
    passwordInput.type = show ? 'text' : 'password';
    togglePass.textContent = show ? 'پنهان' : 'نمایش';
  });
}

if (forgotLink) {
  forgotLink.addEventListener('click', (e) => {
    e.preventDefault();
    showError('بازیابی رمز عبور به‌زودی فعال می‌شود.');
  });
}

if (companyLoginBtn) {
  companyLoginBtn.addEventListener('click', () => {
    showError('ورود سازمانی به‌زودی فعال می‌شود.');
  });
}

if (loginForm) {
  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (loginError) loginError.hidden = true;

    const username = usernameInput.value.trim();
    const password = passwordInput.value;
    if (!username || !password) {
      showError('نام کاربری و رمز عبور را وارد کنید.');
      return;
    }

    if (!captchaInput || !captchaInput.checked) {
      showError('لطفاً گزینه «من ربات نیستم» را تیک بزنید.');
      return;
    }

    loginBtn.disabled = true;
    loginBtn.textContent = 'در حال ورود…';

    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({
          username,
          password,
          captcha: true,
        }),
      });
      const json = await res.json().catch(() => ({}));

      if (!res.ok) {
        showError(json.error || 'ورود ناموفق بود.');
        return;
      }

      if (rememberMe && rememberMe.checked) {
        localStorage.setItem(REMEMBER_KEY, username);
      } else {
        localStorage.removeItem(REMEMBER_KEY);
      }

      window.location.href = '/app';
    } catch (_) {
      showError('خطا در ارتباط با سرور.');
    } finally {
      loginBtn.disabled = false;
      loginBtn.textContent = 'ورود';
    }
  });
}

function showError(message) {
  if (!loginError) return;
  loginError.textContent = message;
  loginError.hidden = false;
}
