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
const LANG_STORAGE_KEY = 'rayamate_lang';

const I18N_LOGIN = {
  fa: {
    heroTitle: 'به سامانه هوشمند <em>رایامیت</em> خوش آمدید',
    heroSub: 'دسترسی سریع و امن به ابزارهای تحلیل داده، گزارش‌گیری و داشبوردهای هوشمند بانکی و پرداخت',
    artBadgeA: '▲ رشد دقیق داده',
    artMonthly: 'روند ماهانه',
    artTxns: 'تراکنش‌ها',
    artBadgeB: 'تحلیل آنی مکالمه‌محور',
    feat1Title: 'ایمن و مطمئن',
    feat1Desc: 'تضمین امنیت اطلاعات و اعتبارسنجی پیشرفته',
    feat2Title: 'سریع و هوشمند',
    feat2Desc: 'پرسش و پاسخ مکالمه‌محور بدون نیاز به کدنویسی',
    feat3Title: 'سهمیه پرسش آزمایشی',
    feat3Desc: '۵ پرسش تحلیلی اولیه پس از ثبت‌نام با قابلیت ارتقای سطح',
    loginTitle: 'ورود به دستیار هوش تجاری',
    loginDesc: 'نام کاربری یا ایمیل و رمز عبور خود را وارد کنید.',
    lblUser: 'نام کاربری یا ایمیل',
    placeholderUser: 'نام کاربری یا ایمیل',
    lblPass: 'رمز عبور',
    placeholderPass: 'رمز عبور',
    showPass: 'نمایش',
    hidePass: 'پنهان',
    lblRemember: 'مرا به خاطر بسپار',
    forgotLink: 'فراموشی رمز عبور؟',
    lblNotRobot: 'من ربات نیستم (تایید امنیتی)',
    btnLogin: 'ورود به سامانه',
    noAcc: 'حساب کاربری ندارید؟',
    registerCta: 'ثبت‌نام و دریافت ۵ سوال آزمایشی',
    divider: 'یا ورود با حساب کاربری دیگر',
    btnGoogle: 'ورود / ثبت‌نام سریع با گوگل',
    footerCopy: '© ۲۰۲۶ تمامی حقوق برای سامانه هوش تجاری Rayamate محفوظ است.',
    footHelp: 'راهنمای سیستم',
    footManual: 'مستندات',
    footSupport: 'پشتیبانی و ارتقای پلن',
    regTitle: 'ثبت‌نام در سامانه رایامیت',
    regSubtitle: 'لطفاً مشخصات خود را وارد کنید (کاربر سطح ۳)',
    regBadgeTxt: 'ثبت‌نام اولیه با <strong>سطح ۳ (شامل ۵ پرسش آزمایشی)</strong> فعال خواهد شد. امکان ارتقا به سطح ۲ و ۱ با هماهنگی مدیریت وجود دارد.',
    regName: 'نام و نام خانوادگی *',
    regNamePh: 'مثلاً: علی محمدی',
    regMobile: 'شماره موبایل *',
    regMobilePh: '09123456789',
    regEmail: 'آدرس ایمیل *',
    regEmailPh: 'example@domain.com',
    regUname: 'نام کاربری دلخواه *',
    regUnamePh: 'username (حروف انگلیسی یا اعداد)',
    regPass: 'رمز عبور *',
    regPassPh: 'حداقل ۶ کاراکتر',
    regPass2: 'تکرار رمز عبور *',
    regPass2Ph: 'تکرار رمز عبور',
    regSubmitBtn: 'تکمیل ثبت‌نام و ورود به برنامه',
    fillAll: 'لطفاً تمامی فیلدهای الزامی را تکمیل کنید.',
    invalidMobile: 'شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود (مانند ۰۹۱۲۳۴۵۶۷۸۹).',
    invalidEmail: 'فرمت آدرس ایمیل صحیح نیست.',
    shortPass: 'رمز عبور باید حداقل ۶ کاراکتر باشد.',
    mismatchPass: 'رمز عبور و تکرار آن یکسان نیستند.',
    enterUserPass: 'نام کاربری و رمز عبور را وارد کنید.',
    verifyCaptcha: 'لطفاً تایید کنید که ربات نیستید (کپچا).',
    checking: 'در حال بررسی اطلاعات…',
    loginSuccess: 'ورود موفقیت‌آمیز بود. در حال انتقال…',
    registering: 'در حال ثبت‌نام و فعال‌سازی طرح رایگان…',
    registeredSuccess: 'ثبت‌نام با موفقیت انجام شد! در حال انتقال به سامانه…',
    forgotMsg: 'برای بازیابی رمز عبور، لطفاً با پشتیبانی (support@rayamate.ir) تماس حاصل فرمایید.',
  },
  en: {
    heroTitle: 'Welcome to <em>Rayamate</em> Intelligence',
    heroSub: 'Fast and secure conversational analytics, automated charting, and smart banking BI dashboards',
    artBadgeA: '▲ Accurate Data Growth',
    artMonthly: 'Monthly Trends',
    artTxns: 'Transactions',
    artBadgeB: 'Real-time Conversational BI',
    feat1Title: 'Safe & Secure',
    feat1Desc: 'Enterprise-grade encryption and advanced authentication',
    feat2Title: 'Fast & Intelligent',
    feat2Desc: 'Conversational analytics without writing a single line of SQL',
    feat3Title: 'Trial Query Quota',
    feat3Desc: '5 initial trial analytical questions upon signup with upgrade paths',
    loginTitle: 'Sign In to BI Assistant',
    loginDesc: 'Enter your username or email and password.',
    lblUser: 'Username or Email',
    placeholderUser: 'Enter username or email',
    lblPass: 'Password',
    placeholderPass: 'Enter password',
    showPass: 'Show',
    hidePass: 'Hide',
    lblRemember: 'Remember me',
    forgotLink: 'Forgot password?',
    lblNotRobot: 'I am not a robot (Security check)',
    btnLogin: 'Sign In to Platform',
    noAcc: "Don't have an account?",
    registerCta: 'Sign up & get 5 trial queries',
    divider: 'Or continue with another account',
    btnGoogle: 'Fast Sign In / Sign Up with Google',
    footerCopy: '© 2026 Rayamate. All rights reserved.',
    footHelp: 'System Guide',
    footManual: 'Documentation',
    footSupport: 'Support & Plan Upgrade',
    regTitle: 'Create Rayamate Account',
    regSubtitle: 'Please enter your credentials (Tier 3 User)',
    regBadgeTxt: 'Initial registration starts at <strong>Tier 3 (5 trial queries)</strong>. Seamlessly upgrade to Tier 2 & Tier 1 via management.',
    regName: 'Full Name *',
    regNamePh: 'e.g. John Doe',
    regMobile: 'Mobile Number *',
    regMobilePh: '09123456789',
    regEmail: 'Email Address *',
    regEmailPh: 'user@example.com',
    regUname: 'Choose Username *',
    regUnamePh: 'username (alphanumeric)',
    regPass: 'Password *',
    regPassPh: 'At least 6 characters',
    regPass2: 'Confirm Password *',
    regPass2Ph: 'Re-enter password',
    regSubmitBtn: 'Complete Registration & Sign In',
    fillAll: 'Please fill in all required fields.',
    invalidMobile: 'Mobile number must be 11 digits starting with 09 (e.g. 09123456789).',
    invalidEmail: 'Invalid email address format.',
    shortPass: 'Password must be at least 6 characters.',
    mismatchPass: 'Passwords do not match.',
    enterUserPass: 'Please enter your username and password.',
    verifyCaptcha: 'Please verify you are not a robot (CAPTCHA).',
    checking: 'Checking credentials…',
    loginSuccess: 'Sign in successful! Redirecting…',
    registering: 'Registering and activating trial plan…',
    registeredSuccess: 'Account created successfully! Redirecting…',
    forgotMsg: 'To recover your password, please contact support at support@rayamate.ir.',
  }
};

let currentLang = localStorage.getItem(LANG_STORAGE_KEY) || 'fa';

function applyLoginLanguage(lang) {
  currentLang = lang === 'en' ? 'en' : 'fa';
  localStorage.setItem(LANG_STORAGE_KEY, currentLang);

  const t = I18N_LOGIN[currentLang];
  document.documentElement.lang = currentLang;
  document.documentElement.dir = currentLang === 'en' ? 'ltr' : 'rtl';

  const langLabel = document.getElementById('login-lang-label');
  if (langLabel) langLabel.textContent = currentLang === 'en' ? 'FA' : 'EN';

  // Hero Section
  const elHeroTitle = document.getElementById('t-hero-title');
  if (elHeroTitle) elHeroTitle.innerHTML = t.heroTitle;
  const elHeroSub = document.getElementById('t-hero-sub');
  if (elHeroSub) elHeroSub.textContent = t.heroSub;
  const elArtA = document.getElementById('t-art-badge-a');
  if (elArtA) elArtA.textContent = t.artBadgeA;
  const elArtMonthly = document.getElementById('t-art-monthly');
  if (elArtMonthly) elArtMonthly.textContent = t.artMonthly;
  const elArtTxns = document.getElementById('t-art-txns');
  if (elArtTxns) elArtTxns.textContent = t.artTxns;
  const elArtB = document.getElementById('t-art-badge-b');
  if (elArtB) elArtB.textContent = t.artBadgeB;

  const elF1T = document.getElementById('t-feat1-title');
  if (elF1T) elF1T.textContent = t.feat1Title;
  const elF1D = document.getElementById('t-feat1-desc');
  if (elF1D) elF1D.textContent = t.feat1Desc;
  const elF2T = document.getElementById('t-feat2-title');
  if (elF2T) elF2T.textContent = t.feat2Title;
  const elF2D = document.getElementById('t-feat2-desc');
  if (elF2D) elF2D.textContent = t.feat2Desc;
  const elF3T = document.getElementById('t-feat3-title');
  if (elF3T) elF3T.textContent = t.feat3Title;
  const elF3D = document.getElementById('t-feat3-desc');
  if (elF3D) elF3D.textContent = t.feat3Desc;

  // Login Card
  const elLogTitle = document.getElementById('t-login-title');
  if (elLogTitle) elLogTitle.textContent = t.loginTitle;
  const elLogDesc = document.getElementById('t-login-desc');
  if (elLogDesc) elLogDesc.textContent = t.loginDesc;
  const elLblUser = document.getElementById('t-lbl-user');
  if (elLblUser) elLblUser.textContent = t.lblUser;
  if (usernameInput) usernameInput.placeholder = t.placeholderUser;
  const elLblPass = document.getElementById('t-lbl-pass');
  if (elLblPass) elLblPass.textContent = t.lblPass;
  if (passwordInput) passwordInput.placeholder = t.placeholderPass;
  if (togglePass) togglePass.textContent = passwordInput && passwordInput.type === 'password' ? t.showPass : t.hidePass;
  const elRemember = document.getElementById('t-lbl-remember');
  if (elRemember) elRemember.textContent = t.lblRemember;
  if (forgotLink) forgotLink.textContent = t.forgotLink;
  const elNotRobot = document.getElementById('t-lbl-notrobot');
  if (elNotRobot) elNotRobot.textContent = t.lblNotRobot;
  if (loginBtn) loginBtn.textContent = t.btnLogin;
  const elNoAcc = document.getElementById('t-no-acc');
  if (elNoAcc) elNoAcc.textContent = t.noAcc;
  if (openRegBtn) openRegBtn.textContent = t.registerCta;
  const elDivider = document.getElementById('t-divider');
  if (elDivider) elDivider.textContent = t.divider;
  const elBtnGoogle = document.getElementById('t-btn-google');
  if (elBtnGoogle) elBtnGoogle.textContent = t.btnGoogle;

  // Footer
  const elFootCopy = document.getElementById('t-footer-copy');
  if (elFootCopy) elFootCopy.textContent = t.footerCopy;
  const elFootHelp = document.getElementById('t-foot-help');
  if (elFootHelp) elFootHelp.textContent = t.footHelp;
  const elFootManual = document.getElementById('t-foot-manual');
  if (elFootManual) elFootManual.textContent = t.footManual;
  const elFootSupport = document.getElementById('t-foot-support');
  if (elFootSupport) elFootSupport.textContent = t.footSupport;

  // Registration Modal
  const elRegTitle = document.getElementById('t-reg-title');
  if (elRegTitle) elRegTitle.textContent = t.regTitle;
  const elRegSub = document.getElementById('t-reg-subtitle');
  if (elRegSub) elRegSub.textContent = t.regSubtitle;
  const elRegBadgeTxt = document.getElementById('t-reg-badge-txt');
  if (elRegBadgeTxt) elRegBadgeTxt.innerHTML = t.regBadgeTxt;
  const elRegName = document.getElementById('t-reg-lbl-name');
  if (elRegName) elRegName.textContent = t.regName;
  if (regNameInput) regNameInput.placeholder = t.regNamePh;
  const elRegMob = document.getElementById('t-reg-lbl-mobile');
  if (elRegMob) elRegMob.textContent = t.regMobile;
  if (regMobileInput) regMobileInput.placeholder = t.regMobilePh;
  const elRegEmail = document.getElementById('t-reg-lbl-email');
  if (elRegEmail) elRegEmail.textContent = t.regEmail;
  if (regEmailInput) regEmailInput.placeholder = t.regEmailPh;
  const elRegUname = document.getElementById('t-reg-lbl-uname');
  if (elRegUname) elRegUname.textContent = t.regUname;
  if (regUsernameInput) regUsernameInput.placeholder = t.regUnamePh;
  const elRegPass = document.getElementById('t-reg-lbl-pass');
  if (elRegPass) elRegPass.textContent = t.regPass;
  if (regPasswordInput) regPasswordInput.placeholder = t.regPassPh;
  const elRegPass2 = document.getElementById('t-reg-lbl-pass2');
  if (elRegPass2) elRegPass2.textContent = t.regPass2;
  if (regPasswordConfirmInput) regPasswordConfirmInput.placeholder = t.regPass2Ph;
  const elRegNotRobot = document.getElementById('t-reg-lbl-notrobot');
  if (elRegNotRobot) elRegNotRobot.textContent = t.lblNotRobot;
  if (regSubmitBtn) regSubmitBtn.textContent = t.regSubmitBtn;
}

// State
let authConfig = {
  turnstile_site_key: '1x00000000000000000000AA',
  google_client_id: '',
};
let loginTurnstileToken = '';
let regTurnstileToken = '';
let loginWidgetId = null;
let regWidgetId = null;

// Attach language toggle listener
const loginLangBtn = document.getElementById('login-lang-btn');
if (loginLangBtn) {
  loginLangBtn.addEventListener('click', () => {
    applyLoginLanguage(currentLang === 'fa' ? 'en' : 'fa');
  });
}

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
    const t = I18N_LOGIN[currentLang] || I18N_LOGIN.fa;
    togglePass.textContent = show ? t.hidePass : t.showPass;
  });
}

if (forgotLink) {
  forgotLink.addEventListener('click', (e) => {
    e.preventDefault();
    const t = I18N_LOGIN[currentLang] || I18N_LOGIN.fa;
    showLoginError(t.forgotMsg);
  });
}

// Apply saved or default language on script start
applyLoginLanguage(currentLang);

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
          theme: 'light',
          language: currentLang || 'fa',
          size: 'normal',
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

    const t = I18N_LOGIN[currentLang] || I18N_LOGIN.fa;

    if (!name || !mobile || !email || !username || !password) {
      showRegError(t.fillAll);
      return;
    }

    if (!/^09\d{9}$/.test(mobile)) {
      showRegError(t.invalidMobile);
      return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      showRegError(t.invalidEmail);
      return;
    }

    if (password.length < 6) {
      showRegError(t.shortPass);
      return;
    }

    if (password !== confirm) {
      showRegError(t.mismatchPass);
      return;
    }

    let token = regTurnstileToken;
    if (!token && window.turnstile && regWidgetId !== null) {
      try { token = window.turnstile.getResponse(regWidgetId); } catch (_) {}
    }
    if (!token) {
      const hInput = document.querySelector('#reg-turnstile input[name="cf-turnstile-response"]');
      if (hInput && hInput.value) token = hInput.value;
    }
    if (!token && regFallbackCheckbox && regFallbackCheckbox.checked) {
      token = 'bypass_dev_captcha';
    }

    if (!token) {
      showRegError(t.verifyCaptcha);
      return;
    }

    regSubmitBtn.disabled = true;
    regSubmitBtn.textContent = t.registering;

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
        showRegError(json.error || (currentLang === 'en' ? 'Registration failed.' : 'خطا در ثبت‌نام.'));
        if (window.turnstile && regWidgetId !== null) {
          try {
            regTurnstileToken = '';
            window.turnstile.reset(regWidgetId);
          } catch (_) {}
        }
        return;
      }

      showRegSuccess(t.registeredSuccess);
      setTimeout(() => {
        window.location.href = '/app';
      }, 1000);
    } catch (_) {
      showRegError(currentLang === 'en' ? 'Server connection error.' : 'خطا در برقراری ارتباط با سرور.');
    } finally {
      regSubmitBtn.disabled = false;
      regSubmitBtn.textContent = t.regSubmitBtn;
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
    const t = I18N_LOGIN[currentLang] || I18N_LOGIN.fa;

    const username = usernameInput.value.trim();
    const password = passwordInput.value;

    if (!username || !password) {
      showLoginError(t.enterUserPass);
      return;
    }

    let token = loginTurnstileToken;
    if (!token && window.turnstile && loginWidgetId !== null) {
      try { token = window.turnstile.getResponse(loginWidgetId); } catch (_) {}
    }
    if (!token) {
      const hInput = document.querySelector('#login-turnstile input[name="cf-turnstile-response"]');
      if (hInput && hInput.value) token = hInput.value;
    }
    if (!token && loginFallbackCheckbox && loginFallbackCheckbox.checked) {
      token = 'bypass_dev_captcha';
    }

    if (!token) {
      showLoginError(t.verifyCaptcha);
      return;
    }

    loginBtn.disabled = true;
    loginBtn.textContent = t.checking;

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
          try {
            loginTurnstileToken = '';
            window.turnstile.reset(loginWidgetId);
          } catch (_) {}
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
          theme: 'light',
          language: currentLang || 'fa',
          size: 'normal',
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
