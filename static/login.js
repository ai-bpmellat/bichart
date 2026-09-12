/**
 * login.js
 * --------
 * Handles authentication, registration modal, Cloudflare Turnstile CAPTCHA,
 * and Google Identity Services sign-in / sign-up.
 */

// DOM Elements - Login
const loginForm = document.getElementById('login-form');
const usernameInput = document.getElementById('username-input');
const passwordInput = document.getElementById('password-input');
const loginBtn = document.getElementById('login-btn');
const loginError = document.getElementById('login-error');
const loginSuccess = document.getElementById('login-success');
const togglePass = document.getElementById('toggle-pass');
const rememberMe = document.getElementById('remember-me');
const forgotLink = document.getElementById('forgot-link');
const btnGoogleLogin = document.getElementById('btn-google-login');
const googleHolder = document.getElementById('g_id_signin_holder');
const loginFallbackCheckbox = document.getElementById('login-fallback-checkbox');
const loginTurnstileFallback = document.getElementById('login-turnstile-fallback');

// DOM Elements - Registration Modal
const openRegBtn = document.getElementById('open-register-modal-btn');
const regBackdrop = document.getElementById('reg-modal-backdrop');
const regCloseBtn = document.getElementById('reg-close-btn');
const regForm = document.getElementById('reg-form');
const regNameInput = document.getElementById('reg-name');
const regMobileInput = document.getElementById('reg-mobile');
const regEmailInput = document.getElementById('reg-email');
const regUsernameInput = document.getElementById('reg-username');
const regPasswordInput = document.getElementById('reg-password');
const regPasswordConfirmInput = document.getElementById('reg-password-confirm');
const regSubmitBtn = document.getElementById('reg-submit-btn');
const regError = document.getElementById('reg-error');
const regSuccess = document.getElementById('reg-success');
const regFallbackCheckbox = document.getElementById('reg-fallback-checkbox');
const regTurnstileFallback = document.getElementById('reg-turnstile-fallback');

const REMEMBER_KEY = 'rayamate_remember_user';

// State
let authConfig = {
  turnstile_site_key: '1x00000000000000000000AA',
  google_client_id: '',
};
let loginTurnstileToken = '';
let regTurnstileToken = '';
let loginWidgetId = null;
let regWidgetId = null;

// Populate remembered username
if (usernameInput) {
  const saved = localStorage.getItem(REMEMBER_KEY);
  if (saved) {
    usernameInput.value = saved;
    if (rememberMe) rememberMe.checked = true;
  }
}

// Password toggle
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
    showLoginError('برای بازیابی رمز عبور، لطفاً با مدیر سیستم تماس حاصل فرمایید.');
  });
}

// ============================================================================
// Registration Modal Logic
// ============================================================================
function openRegistrationModal() {
  clearRegMessages();
  regForm.reset();
  regBackdrop.classList.add('open');
  regNameInput.focus();

  // Render Turnstile widget for registration if not yet rendered
  if (window.turnstile && document.getElementById('reg-turnstile')) {
    try {
      if (regWidgetId !== null) {
        window.turnstile.reset(regWidgetId);
      } else {
        regWidgetId = window.turnstile.render('#reg-turnstile', {
          sitekey: authConfig.turnstile_site_key,
          callback: (token) => {
            regTurnstileToken = token;
          },
          'expired-callback': () => {
            regTurnstileToken = '';
          },
          'error-callback': () => {
            regTurnstileFallback.style.display = 'flex';
          },
        });
      }
    } catch (_) {
      regTurnstileFallback.style.display = 'flex';
    }
  } else {
    regTurnstileFallback.style.display = 'flex';
  }
}

function closeRegistrationModal() {
  regBackdrop.classList.remove('open');
  clearRegMessages();
}

if (openRegBtn) openRegBtn.addEventListener('click', openRegistrationModal);
if (regCloseBtn) regCloseBtn.addEventListener('click', closeRegistrationModal);
if (regBackdrop) {
  regBackdrop.addEventListener('click', (e) => {
    if (e.target === regBackdrop) closeRegistrationModal();
  });
}
window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && regBackdrop.classList.contains('open')) {
    closeRegistrationModal();
  }
});

// Auto-suggest username from email
if (regEmailInput && regUsernameInput) {
  regEmailInput.addEventListener('blur', () => {
    if (!regUsernameInput.value.trim() && regEmailInput.value.includes('@')) {
      const suggested = regEmailInput.value.split('@')[0].replace(/[^a-zA-Z0-9_]/g, '_');
      regUsernameInput.value = suggested.toLowerCase();
    }
  });
}

// Registration Submit Handler
if (regForm) {
  regForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearRegMessages();

    const name = regNameInput.value.trim();
    const mobile = regMobileInput.value.trim();
    const email = regEmailInput.value.trim().toLowerCase();
    const username = regUsernameInput.value.trim();
    const password = regPasswordInput.value;
    const confirm = regPasswordConfirmInput.value;

    if (!name || !mobile || !email || !username || !password) {
      showRegError('لطفاً تمامی فیلدهای الزامی را تکمیل کنید.');
      return;
    }

    if (!/^09\d{9}$/.test(mobile)) {
      showRegError('شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود (مانند ۰۹۱۲۳۴۵۶۷۸۹).');
      return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      showRegError('فرمت آدرس ایمیل صحیح نیست.');
      return;
    }

    if (password.length < 6) {
      showRegError('رمز عبور باید حداقل ۶ کاراکتر باشد.');
      return;
    }

    if (password !== confirm) {
      showRegError('رمز عبور با تکرار آن یکسان نیست.');
      return;
    }

    let token = regTurnstileToken;
    if (!token && regFallbackCheckbox && regFallbackCheckbox.checked) {
      token = 'bypass_dev_captcha';
    }

    if (!token) {
      showRegError('لطفاً تایید کنید که ربات نیستید (کپچا).');
      return;
    }

    regSubmitBtn.disabled = true;
    regSubmitBtn.textContent = 'در حال ثبت‌نام و فعال‌سازی طرح رایگان…';

    try {
      const res = await fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({
          name,
          mobile,
          email,
          username,
          password,
          captcha_token: token,
        }),
      });

      const json = await res.json().catch(() => ({}));

      if (!res.ok) {
        showRegError(json.error || 'خطا در ثبت‌نام.');
        return;
      }

      showRegSuccess('ثبت‌نام با موفقیت انجام شد! در حال انتقال به سامانه…');
      setTimeout(() => {
        window.location.href = '/app';
      }, 1000);
    } catch (_) {
      showRegError('خطا در برقراری ارتباط با سرور.');
    } finally {
      regSubmitBtn.disabled = false;
      regSubmitBtn.textContent = 'تکمیل ثبت‌نام و ورود به برنامه';
    }
  });
}

// ============================================================================
// Login Submit Handler
// ============================================================================
if (loginForm) {
  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearLoginMessages();

    const username = usernameInput.value.trim();
    const password = passwordInput.value;

    if (!username || !password) {
      showLoginError('نام کاربری و رمز عبور را وارد کنید.');
      return;
    }

    let token = loginTurnstileToken;
    if (!token && loginFallbackCheckbox && loginFallbackCheckbox.checked) {
      token = 'bypass_dev_captcha';
    }

    if (!token) {
      showLoginError('لطفاً تایید کنید که ربات نیستید (کپچا).');
      return;
    }

    loginBtn.disabled = true;
    loginBtn.textContent = 'در حال بررسی اطلاعات…';

    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({
          username,
          password,
          captcha_token: token,
        }),
      });

      const json = await res.json().catch(() => ({}));

      if (!res.ok) {
        showLoginError(json.error || 'ورود ناموفق بود.');
        if (window.turnstile && loginWidgetId !== null) {
          try { window.turnstile.reset(loginWidgetId); } catch (_) {}
        }
        return;
      }

      if (rememberMe && rememberMe.checked) {
        localStorage.setItem(REMEMBER_KEY, username);
      } else {
        localStorage.removeItem(REMEMBER_KEY);
      }

      showLoginSuccess('ورود موفقیت‌آمیز بود. در حال انتقال…');
      window.location.href = '/app';
    } catch (_) {
      showLoginError('خطا در ارتباط با سرور.');
    } finally {
      loginBtn.disabled = false;
      loginBtn.textContent = 'ورود به سامانه';
    }
  });
}

// ============================================================================
// Google OAuth Authentication
// ============================================================================
async function handleGoogleCredentialResponse(response) {
  if (!response || !response.credential) {
    showLoginError('توکن ورود با گوگل دریافت نشد.');
    return;
  }

  showLoginSuccess('در حال اعتبارسنجی حساب گوگل…');

  try {
    const res = await fetch('/api/auth/google', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ credential: response.credential }),
    });

    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      showLoginError(json.error || 'ورود با حساب گوگل ناموفق بود.');
      return;
    }

    showLoginSuccess('خوش آمدید! در حال انتقال به داشبورد…');
    window.location.href = '/app';
  } catch (_) {
    showLoginError('خطا در برقراری ارتباط با سرور جهت ورود با گوگل.');
  }
}

function setupGoogle() {
  if (authConfig.google_client_id && window.google && window.google.accounts) {
    try {
      window.google.accounts.id.initialize({
        client_id: authConfig.google_client_id,
        callback: handleGoogleCredentialResponse,
        auto_select: false,
        cancel_on_tap_outside: true,
      });

      if (googleHolder) {
        window.google.accounts.id.renderButton(googleHolder, {
          theme: 'outline',
          size: 'large',
          width: 320,
          text: 'signin_with',
          locale: 'fa',
        });
      }
      return true;
    } catch (e) {
      console.warn('[google gsi error]', e);
    }
  }
  return false;
}

if (btnGoogleLogin) {
  btnGoogleLogin.addEventListener('click', async () => {
    if (!authConfig.google_client_id) {
      try {
        const res = await fetch('/api/auth/config');
        if (res.ok) {
          authConfig = await res.json();
          if (authConfig.google_client_id) {
            setupGoogle();
          }
        }
      } catch (_) {}
    }

    if (!authConfig.google_client_id) {
      alert(
        'تنظیمات ورود با گوگل:\n' +
        'شناسه GOOGLE_CLIENT_ID هنوز در فایل .env خالی است یا فایل ذخیره (Ctrl+S) نشده است.\n\n' +
        'لطفاً پس از قرار دادن شناسه، فایل .env را ذخیره فرمایید.'
      );
      openRegistrationModal();
      return;
    }

    if (window.google && window.google.accounts && window.google.accounts.id) {
      setupGoogle();
      window.google.accounts.id.prompt((notification) => {
        if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
          const btnEl = googleHolder.querySelector('div[role="button"]');
          if (btnEl) btnEl.click();
        }
      });
    } else {
      showLoginError('کتابخانه گوگل در مرورگر شما در دسترس نیست. لطفاً اتصال اینترنت خود را بررسی نمایید.');
    }
  });
}

// ============================================================================
// Turnstile & Config Initialization
// ============================================================================
async function initAuth() {
  try {
    const res = await fetch('/api/auth/config');
    if (res.ok) {
      authConfig = await res.json();
    }
  } catch (err) {
    console.warn('[auth] Could not fetch auth config:', err);
  }

  // Setup Turnstile
  setupTurnstile();

  // Setup Google Identity Services if client_id is available
  setupGoogle();
}

function setupTurnstile() {
  const checkTurnstile = () => {
    if (window.turnstile && typeof window.turnstile.render === 'function') {
      try {
        loginWidgetId = window.turnstile.render('#login-turnstile', {
          sitekey: authConfig.turnstile_site_key,
          callback: (token) => {
            loginTurnstileToken = token;
          },
          'expired-callback': () => {
            loginTurnstileToken = '';
          },
          'error-callback': () => {
            if (loginTurnstileFallback) loginTurnstileFallback.style.display = 'flex';
          },
        });
      } catch (_) {
        if (loginTurnstileFallback) loginTurnstileFallback.style.display = 'flex';
      }
    } else {
      // If Turnstile script didn't load within 2.5s, display fallback
      setTimeout(() => {
        if (!loginTurnstileToken && loginTurnstileFallback) {
          loginTurnstileFallback.style.display = 'flex';
        }
      }, 2500);
    }
  };

  if (document.readyState === 'complete') {
    checkTurnstile();
  } else {
    window.addEventListener('load', checkTurnstile);
  }
}

// Helpers
function showLoginError(message) {
  if (!loginError) return;
  loginError.textContent = message;
  loginError.hidden = false;
  if (loginSuccess) loginSuccess.hidden = true;
}

function showLoginSuccess(message) {
  if (!loginSuccess) return;
  loginSuccess.textContent = message;
  loginSuccess.hidden = false;
  if (loginError) loginError.hidden = true;
}

function clearLoginMessages() {
  if (loginError) loginError.hidden = true;
  if (loginSuccess) loginSuccess.hidden = true;
}

function showRegError(message) {
  if (!regError) return;
  regError.textContent = message;
  regError.hidden = false;
  if (regSuccess) regSuccess.hidden = true;
}

function showRegSuccess(message) {
  if (!regSuccess) return;
  regSuccess.textContent = message;
  regSuccess.hidden = false;
  if (regError) regError.hidden = true;
}

function clearRegMessages() {
  if (regError) regError.hidden = true;
  if (regSuccess) regSuccess.hidden = true;
}

// Initialize on page ready
initAuth();
