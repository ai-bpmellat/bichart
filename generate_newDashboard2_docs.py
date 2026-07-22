"""Generate Persian HTML/PDF documentation for the newDashboard2 Git branch."""

from __future__ import annotations

import html
import os
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BRANCH = "newDashboard2"
HTML_OUT = ROOT / "newDashboard2_code_documentation_fa.html"
PDF_OUT = ROOT / "newDashboard2_code_documentation_fa.pdf"


def git(*args: str, text: bool = True):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=text)


def branch_file(path: str) -> bytes:
    return git("show", f"{BRANCH}:{path}", text=False)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def bullets(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"


def code_names(items: list[tuple[str, str]]) -> str:
    return '<div class="code-list">' + "".join(
        f'<div><code dir="ltr">{esc(name)}</code><span>{desc}</span></div>'
        for name, desc in items
    ) + "</div>"


def table(headers: list[str], rows: list[list[str]], ltr_first: bool = False) -> str:
    head = "".join(f"<th>{h}</th>" for h in headers)
    body_rows = []
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            cls = ' class="ltr"' if ltr_first and i == 0 else ""
            cells.append(f"<td{cls}>{cell}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>'


def file_block(path: str, role: str, details: list[str], symbols: list[tuple[str, str]] | None = None) -> str:
    raw = branch_file(path)
    try:
        lines = len(raw.decode("utf-8").splitlines())
        metric = f"{lines:,} خط"
    except UnicodeDecodeError:
        metric = f"{len(raw):,} بایت (دودویی)"
    symbol_html = code_names(symbols) if symbols else ""
    return f"""
    <article class="file-block">
      <div class="file-title">
        <h3><code dir="ltr">{esc(path)}</code></h3>
        <span>{metric}</span>
      </div>
      <p class="role">{role}</p>
      {bullets(details)}
      {symbol_html}
    </article>
    """


def page(title: str, body: str, kicker: str = "") -> str:
    return f"""
    <section class="page">
      <header class="section-head">
        {f'<div class="kicker">{kicker}</div>' if kicker else ''}
        <h2>{title}</h2>
      </header>
      {body}
    </section>
    """


commit_hash = git("rev-parse", BRANCH).strip()
commit_short = commit_hash[:10]
commit_date = git("show", "-s", "--format=%ad", "--date=iso-strict", BRANCH).strip()
commit_subject = git("show", "-s", "--format=%s", BRANCH).strip()
tracked_files = git("ls-tree", "-r", "--name-only", BRANCH).splitlines()


route_rows = [
    ["GET /", "عمومی", "نمایش صفحه معرفی <code>static/first.html</code>"],
    ["GET /login", "عمومی", "نمایش فرم ورود؛ کاربر واردشده به <code>/app</code> منتقل می‌شود."],
    ["POST /api/login", "عمومی", "بررسی چک‌باکس کپچا، نام کاربری و گذرواژه؛ ایجاد نشست."],
    ["POST /api/logout", "واردشده", "پاک‌کردن کامل داده‌های نشست."],
    ["GET /api/me", "واردشده", "اطلاعات کاربر جاری به‌همراه تنظیمات مدل و زبان."],
    ["GET /app", "واردشده", "نمایش داشبورد گفتگو از <code>static/index.html</code>."],
    ["GET /users", "مدیر", "صفحه مدیریت کاربران."],
    ["GET /api/users", "مدیر", "فهرست حساب‌های برنامه."],
    ["POST /api/users", "مدیر", "ساخت حساب و هش‌کردن گذرواژه."],
    ["PUT /api/users/{id}", "مدیر", "ویرایش حساب، نقش، وضعیت و گذرواژه."],
    ["DELETE /api/users/{id}", "مدیر", "حذف حساب با محافظت از آخرین مدیر و حذف خود."],
    ["GET /api/health", "واردشده", "بررسی پایگاه داده، Ollama و AvalAI."],
    ["GET /api/avalai/credit", "واردشده", "پروکسی سمت سرور برای مانده اعتبار AvalAI."],
    ["POST /api/chat", "واردشده", "تبدیل سؤال به SQL، نرمال‌سازی، کنترل ایمنی، اجرا و ثبت تاریخچه."],
    ["POST /api/analyze", "واردشده", "تحلیل اختیاری حداکثر ۲۰ ردیف اول نتیجه توسط مدل انتخاب‌شده."],
    ["GET /api/history", "واردشده", "۵۰ پیام اخیر همان نام کاربری."],
    ["GET /api/preferences", "واردشده", "خواندن مدل و زبان ذخیره‌شده کاربر."],
    ["PUT /api/preferences", "واردشده", "ذخیره provider و language معتبر."],
]


schema_rows = [
    ["app_users", "حساب‌های ورود", "id، username، password_hash، mobile، display_name، role، is_active، زمان‌ها"],
    ["dim_date", "بعد تاریخ", "date_key به‌شکل YYYYMMDD، full_date، روز/ماه/سال، تعطیلی و آخرهفته"],
    ["dim_category", "بعد صنف", "شناسه و عنوان فارسی ۱۵ صنف استاندارد"],
    ["dim_customer", "مشتری قراردادی PSP", "نام، access_key نمایشی و نقش customer/admin؛ با حساب app_users متفاوت است."],
    ["dim_merchant", "پذیرنده", "نام/کد، MCC، صنف، شهر، مالک مشتری و وضعیت فعال"],
    ["dim_terminal", "پایانه", "سریال، پذیرنده، نوع POS/mPOS/Online، تاریخ نصب و وضعیت"],
    ["fact_transactions", "فکت تراکنش", "تاریخ، پایانه، پذیرنده، مبلغ، وضعیت، PAN ماسک‌شده، پاسخ، تسویه و کانال"],
]


architecture = """
<div class="flow" dir="ltr">
  <div>Browser<br><small>Landing / Login / Dashboard</small></div><b>→</b>
  <div>FastAPI<br><small>Session + Routes</small></div><b>→</b>
  <div>LLM Provider<br><small>AvalAI or Ollama</small></div><b>→</b>
  <div>SQL Normalizer<br><small>Safety checks</small></div><b>→</b>
  <div>SQLAlchemy<br><small>SQLite / external DB</small></div>
</div>
<div class="callout">
  <strong>مسیر اصلی سؤال:</strong>
  مرورگر سؤال و تنظیمات زبان/مدل را به <code>/api/chat</code> می‌فرستد؛ مدل یک JSON شامل SQL و توضیح می‌سازد؛
  SQL اصلاح و ایمن‌سازی می‌شود؛ با Pandas/SQLAlchemy اجرا می‌گردد؛ نتیجه و زمان هر مرحله به رابط برمی‌گردد.
  تحلیل هوشمند عمداً در درخواست جداگانه <code>/api/analyze</code> و با اقدام کاربر اجرا می‌شود.
</div>
"""


backend_files = [
    file_block(
        "app.py",
        "مرکز اتصال تمام اجزای برنامه و تعریف FastAPI، middlewareها، مدل‌های ورودی و endpointها.",
        [
            "دو provider با مجموعه <code>VALID_PROVIDERS</code> کنترل می‌شوند و <code>get_llm_client</code> ماژول AvalAI یا Ollama را برمی‌گرداند.",
            "ترتیب middlewareها طوری است که SessionMiddleware بیرونی باشد و نشست قبل از RequireLoginMiddleware در دسترس قرار گیرد.",
            "رشته <code>SCHEMA_DESCRIPTION</code> ساختار دقیق جداول و قواعد تاریخ/وضعیت را به مدل می‌دهد تا SQL سازگار با SQLite تولید شود.",
            "در <code>/api/chat</code> زمان تولید SQL، نرمال‌سازی، کنترل ایمنی، اجرا و ذخیره حافظه جداگانه اندازه‌گیری می‌شود.",
            "اجرای SQL با <code>pandas.read_sql_query(text(...))</code> انجام و DataFrame به رکورد JSON تبدیل می‌شود.",
            "مدیریت کاربران فقط با نقش admin در دسترس است و حذف خودِ مدیر در route نیز مسدود می‌شود.",
        ],
        [
            ("get_llm_client(provider)", "انتخاب پیاده‌سازی مشترک generate_sql/generate_analysis."),
            ("RequireLoginMiddleware.dispatch", "تفکیک مسیرهای عمومی، API بدون نشست و صفحات نیازمند ورود."),
            ("_startup_init_users", "ساخت جدول app_users و مدیر آغازین هنگام startup."),
            ("require_admin", "تولید پاسخ 401 یا 403 برای عملیات مدیریتی."),
            ("chat", "خط لوله اصلی Text-to-SQL و اجرای گزارش."),
            ("analyze", "تحلیل ثانویه و ثبت تحلیل روی آخرین پیام متناظر."),
            ("get_history / get_preferences / put_preferences", "APIهای حافظه و تنظیمات شخصی."),
        ],
    ),
    file_block(
        "database.py",
        "تنظیم مرکزی SQLAlchemy؛ تنها نقطه انتخاب SQLite یا پایگاه داده خارجی.",
        [
            "<code>DATABASE_URL</code> از environment خوانده می‌شود و در حالت پیش‌فرض به <code>psp_bi_mock.db</code> اشاره دارد.",
            "برای SQLite گزینه <code>check_same_thread=False</code> فعال است؛ برای سایر DBها connect_args خالی است.",
            "<code>pool_pre_ping=True</code> اتصال مرده را پیش از استفاده تشخیص می‌دهد.",
        ],
        [
            ("engine", "موتور مشترک SQLAlchemy."),
            ("SessionLocal", "کارخانه نشست با autocommit/autoflush خاموش."),
            ("Base", "پایه declarative مدل‌های ORM."),
            ("get_db", "dependency مولد که نشست را در finally می‌بندد."),
        ],
    ),
    file_block(
        "db_mock.py",
        "تعریف star schema آزمایشی و ساخت داده واقع‌گرایانه تراکنش‌های پرداخت ایران.",
        [
            "شش مدل داده BI، رابطه‌های ORM، ۱۵ صنف، MCCهای متناظر، پذیرندگان فارسی، شهرها و مشتریان نمونه را تعریف می‌کند.",
            "seed ثابت ۴۲ باعث بازتولیدپذیری داده‌های تصادفی می‌شود.",
            "<code>build_database</code> فایل/جداول را بازسازی، ابعاد را درج و تراکنش‌ها را با توزیع مبلغ، وضعیت و کانال تولید می‌کند.",
            "اجرای دوباره این فایل مخرب است: دیتابیس mock را از نو می‌سازد.",
        ],
        [
            ("DimDate / DimCategory", "ابعاد تقویم و صنف."),
            ("DimCustomer / DimMerchant / DimTerminal", "مالکیت تجاری، پذیرنده و پایانه."),
            ("FactTransaction", "جدول رخدادهای مالی."),
            ("weighted_choice", "انتخاب احتمالی وزن‌دار برای داده طبیعی‌تر."),
            ("mask_pan", "تولید شماره کارت ماسک‌شده نمایشی."),
            ("build_database(n_transactions=1000)", "ساخت کامل schema و داده نمونه."),
        ],
    ),
    file_block(
        "auth.py",
        "توابع کوچک و متمرکز برای احراز هویت مبتنی بر session.",
        [
            "کلیدهای username، user_id، role و display_name را در کوکی نشست امضاشده نگه می‌دارد.",
            "اعتبارسنجی واقعی گذرواژه به users.py واگذار می‌شود.",
            "<code>SESSION_SECRET</code> قابل تنظیم با environment است.",
        ],
        [
            ("verify_credentials", "wrapper روی authenticate_user."),
            ("set_session_user", "نوشتن داده عمومی کاربر در نشست."),
            ("is_authenticated / is_admin", "کنترل سریع وضعیت و نقش."),
            ("current_user", "ساخت dict عمومی از session."),
        ],
    ),
    file_block(
        "users.py",
        "مدل و عملیات CRUD حساب‌های ورود برنامه؛ مستقل از dim_customer تحلیلی.",
        [
            "گذرواژه با PBKDF2-HMAC-SHA256، salt تصادفی و ۱۲۰هزار iteration ذخیره می‌شود.",
            "مقایسه digest با <code>hmac.compare_digest</code> انجام می‌شود.",
            "مدیر bootstrap از environment یا مقادیر پیش‌فرض ساخته و همیشه فعال/admin نگه داشته می‌شود.",
            "کد از حذف، غیرفعال‌سازی یا تنزل آخرین مدیر فعال جلوگیری می‌کند.",
        ],
        [
            ("AppUser", "مدل ORM حساب، نقش و وضعیت."),
            ("hash_password / verify_password", "هش و بررسی گذرواژه."),
            ("init_users_table / seed_bootstrap_admin", "راه‌اندازی اولیه حساب‌ها."),
            ("authenticate_user", "بررسی وجود، فعال بودن و رمز."),
            ("list_users / create_user / update_user / delete_user", "عملیات مدیریت کاربران با کنترل‌های کسب‌وکار."),
        ],
    ),
    file_block(
        "memory_manager.py",
        "حافظه گفتگو و ترجیحات جداگانه برای هر username با persistence در history.json.",
        [
            "ساختار دیسک شامل users، preferences و messages است.",
            "Lock درون‌پردازه‌ای از هم‌زمانی threadها هنگام خواندن/نوشتن جلوگیری می‌کند.",
            "فرمت قدیمی که یک list ساده بوده به bucket کاربر anonymous مهاجرت داده می‌شود.",
            "history.json در Git نیست و به‌وسیله .gitignore حذف شده است.",
        ],
        [
            ("_ensure_user", "ساخت bucket و تکمیل preferenceهای پیش‌فرض."),
            ("add_message / get_context", "ثبت پیام و دریافت n پیام پایانی."),
            ("update_last_analysis", "افزودن تحلیل به آخرین سؤال مطابق."),
            ("get_preferences / set_preferences", "مدیریت provider و language."),
            ("save_to_disk / load_from_disk", "serialization فارسی با JSON و بازیابی مقاوم به خطا."),
        ],
    ),
    file_block(
        "sql_safety.py",
        "لایه اصلاح خطاهای رایج مدل و رد SQLهای غیرخواندنی پیش از اجرا.",
        [
            "عبارت‌های date_key اشتباه را به join با dim_date و full_date تبدیل می‌کند.",
            "modifierهای نادرست ماه و حروف وضعیت Active/Inactive را برای SQLite اصلاح می‌کند.",
            "LIMIT ناخواسته مدل را فقط وقتی کاربر تعداد مشخص نخواسته حذف می‌کند.",
            "فقط یک SELECT یا WITH را می‌پذیرد، semicolon میانی و keywordهای مخرب را رد می‌کند و LIMIT بیش از ۱۰۰هزار را کاهش می‌دهد.",
        ],
        [
            ("fix_date_key_sql", "بازنویسی تاریخ integer به بعد تاریخ."),
            ("fix_sqlite_date_modifiers", "اصلاح first/last day of month."),
            ("fix_status_literals", "نرمال‌سازی active/inactive."),
            ("normalize_generated_sql", "اجرای زنجیره تمام fixها."),
            ("user_requested_row_limit / strip_unrequested_limit", "تشخیص درخواست تعداد به فارسی/انگلیسی."),
            ("validate_select_only", "دروازه نهایی SQL خواندنی."),
        ],
    ),
    file_block(
        "ollama_client.py",
        "کلاینت HTTP مدل محلی Ollama با قرارداد عمومی مشترک با AvalAI.",
        [
            "به 127.0.0.1:11434 متصل می‌شود و trust_env را خاموش می‌کند تا proxy سیستم در Windows دخالت نکند.",
            "خروجی SQL باید JSON با کلیدهای sql و explanation باشد.",
            "زنجیره parsing خروجی مستقیم، code fence، اولین بلوک آکولادی، quoteهای تکی، comma پایانی و newline داخل string را تحمل می‌کند.",
            "تولید تحلیل متن آزاد با temperature بالاتر و زبان فارسی/انگلیسی انجام می‌شود.",
        ],
        [
            ("_post", "فراخوانی /api/generate و تبدیل خطاهای شبکه به OllamaError."),
            ("_escape_literal_control_chars_in_strings", "تعمیر newline/tab غیرمجاز در JSON مدل."),
            ("_try_parse / _extract_json", "استخراج مقاوم JSON."),
            ("generate_sql", "ساخت prompt دقیق SQLite و بازگرداندن dict."),
            ("generate_analysis", "تحلیل ۲۰ ردیف نمونه به زبان انتخابی."),
        ],
    ),
    file_block(
        "avalai_client.py",
        "کلاینت API سازگار با OpenAI برای AvalAI با همان interface ماژول Ollama.",
        [
            "مدل از <code>AVALAI_MODEL</code> و کلید از <code>AVALAI_API_KEY</code> خوانده می‌شود.",
            "درخواست chat/completions با Bearer token و timeout شصت‌ثانیه‌ای ارسال می‌شود.",
            "prompt و parser از ollama_client بازاستفاده می‌شوند تا رفتار دو provider همسان بماند.",
            "تابع check_credit به endpoint حساب AvalAI متصل می‌شود؛ مقدار کلید در مرورگر ارسال نمی‌شود.",
        ],
        [
            ("_chat", "فراخوانی chat/completions و مدیریت Connection/Timeout/HTTP/Format."),
            ("check_credit", "دریافت اعتبار حساب از سمت سرور."),
            ("generate_sql", "تولید JSON SQL با قواعد schema."),
            ("generate_analysis", "تحلیل متنی داده نمونه."),
        ],
    ),
    file_block(
        "passenger_wsgi.py",
        "نقطه ورود میزبانی cPanel/Phusion Passenger.",
        [
            "دایرکتوری برنامه را به sys.path اضافه می‌کند.",
            "FastAPI که ASGI است با <code>a2wsgi.ASGIMiddleware</code> به application سازگار با WSGI تبدیل می‌شود.",
        ],
        [("application", "شیء entry point مورد انتظار Passenger.")],
    ),
]


frontend_files = [
    file_block(
        "static/first.html",
        "صفحه عمومی معرفی Rayamate که route ریشه آن را نمایش می‌دهد.",
        [
            "Tailwind CDN، Iconify و Google Fonts را از اینترنت می‌گیرد و CSS تکمیلی را inline نگه می‌دارد.",
            "بخش‌های hero، آمار، نمایش محصول، قابلیت‌ها، CTA و footer دارد.",
            "Canvas ذرات متحرک و خطوط ارتباطی، شمارنده آماری با IntersectionObserver، اسکرول نرم و tilt کارت‌ها با JavaScript inline پیاده شده‌اند.",
            "لینک‌های ورود هنگام اجرا با hostname جاری و پورت ۸۰۰۰ بازنویسی می‌شوند.",
        ],
        [
            ("Particle.reset/update/draw", "مدل هر ذره پس‌زمینه."),
            ("resizeCanvas / animateParticles", "انطباق canvas و حلقه انیمیشن."),
            ("animateStats", "افزایش نرم اعداد هنگام ورود به viewport."),
            ("setAppLinks IIFE", "ساخت URL صفحه login."),
        ],
    ),
    file_block(
        "static/login.html",
        "صفحه ورود راست‌به‌چپ با CSS کامل inline و اتصال به login.js.",
        [
            "طرح دو ستونه معرفی محصول و فرم ورود؛ در موبایل تک‌ستونه می‌شود.",
            "ورودی نام کاربری، رمز، remember me، چک‌باکس «من ربات نیستم»، نمایش رمز و پیام خطا دارد.",
            "بازیابی رمز و ورود سازمانی در UI حضور دارند ولی در این نسخه فقط پیام «به‌زودی» نشان می‌دهند.",
        ],
    ),
    file_block(
        "static/login.js",
        "کنترل رفتار فرم ورود در مرورگر.",
        [
            "فقط username را در localStorage نگه می‌دارد و هرگز password را ذخیره نمی‌کند.",
            "قبل از ارسال، خالی نبودن فیلدها و فعال بودن checkbox کپچا را بررسی می‌کند.",
            "درخواست JSON به <code>/api/login</code> می‌فرستد و پس از موفقیت به <code>/app</code> می‌رود.",
        ],
        [
            ("submit handler", "اعتبارسنجی، disable موقت دکمه و مدیریت پاسخ/خطا."),
            ("toggle password handler", "تغییر type بین password و text."),
            ("showError", "نمایش پیام خطای فارسی."),
        ],
    ),
    file_block(
        "static/index.html",
        "پوسته داشبورد احراز‌شده و فایل واقعی سرو‌شده در route /app.",
        [
            "header شامل عنوان، انتخاب AvalAI/Ollama، زبان، لینک مدیریت کاربران برای admin و خروج است.",
            "ستون گفتگو شامل welcome، chat-area، textarea و Send است.",
            "sidebar شامل تاریخچه، چهار اقدام سریع، تنظیمات مدل/زبان و درباره دستیار است.",
            "Chart.js محلی و static/script.js در پایان صفحه بارگذاری می‌شوند.",
        ],
    ),
    file_block(
        "static/script.js",
        "منطق اصلی کلاینت داشبورد؛ بدون framework و مبتنی بر DOM API.",
        [
            "در startup از /api/me هویت و preferenceها را می‌خواند؛ لینک کاربران را فقط برای admin آشکار می‌کند.",
            "ارسال سؤال، loading strip، خطا، SQL جمع‌شونده، توضیح، جدول صفحه‌بندی‌شده، نمودار و تحلیل را مدیریت می‌کند.",
            "جدول اندازه صفحه ۵۰ تا ۱۰۰۰ دارد و برچسب ستون‌های رایج را فارسی می‌کند.",
            "برای نمودار، ستون عددی و برچسب را هوشمند انتخاب و bar/line/pie/doughnut/horizontal را پشتیبانی می‌کند.",
            "متن تحلیل مدل escape می‌شود و سپس heading/list/عددها به HTML کنترل‌شده تبدیل می‌شوند.",
        ],
        [
            ("applyLanguageUI / applyProviderUI", "همگام‌سازی state و دکمه‌ها."),
            ("apiFetch / logout / savePreferences", "ارتباط session-aware با backend."),
            ("loadHistorySidebar", "نمایش معکوس تاریخچه و بازگرداندن سؤال به composer."),
            ("refreshAvalaiCredit", "نمایش اختیاری مانده اعتبار کنار provider."),
            ("sendMessage / renderError / renderResult", "چرخه کامل هر turn گفتگو."),
            ("renderTimingsSection", "نمایش سهم زمانی مراحل backend."),
            ("requestAnalysis", "فراخوانی جداگانه /api/analyze."),
            ("buildTableHtml / mountPaginatedTable", "ساخت امن و صفحه‌بندی جدول."),
            ("pickNumericColumn / pickLabelColumn / prepareChartRows", "استنباط ساختار نمودار."),
            ("createChartInstance / maybeRenderChart", "ساخت و تعویض نمودار Chart.js."),
            ("escapeHtml / formatAnalysisHtml / isRtlText", "ایمنی خروجی و پشتیبانی دو‌جهته."),
        ],
    ),
    file_block(
        "static/style.css",
        "سامانه طراحی مشترک داشبورد و صفحه کاربران.",
        [
            "متغیرهای رنگ، کاغذ، accent، danger، فونت sans/mono/RTL و قواعد پایه را تعریف می‌کند.",
            "layout داشبورد، sidebar قابل جمع‌شدن، کارت‌ها، تاریخچه، composer و message turnها را پوشش می‌دهد.",
            "استایل result strip، SQL، جدول pagination، نمودار، تحلیل، timing bar، loading و responsive breakpoints را دارد.",
            "قواعد <code>[dir=rtl]</code> برای جای‌گذاری دکمه‌ها و متن فارسی استفاده شده‌اند.",
        ],
    ),
    file_block(
        "static/users.html",
        "صفحه CRUD کاربران برای مدیر.",
        [
            "style اختصاصی صفحه را inline و style.css مشترک را جداگانه بارگذاری می‌کند.",
            "جدول کاربران، حالت خالی، پیام عملیات و modal افزودن/ویرایش دارد.",
            "فرم شامل نام نمایشی، username، موبایل، password، role و وضعیت فعال است.",
        ],
    ),
    file_block(
        "static/users.js",
        "اتصال UI مدیریت کاربران به APIهای admin.",
        [
            "wrapper مشترک api پاسخ‌های 401/403 را مدیریت و برای 401 به login هدایت می‌کند.",
            "ردیف‌های جدول با escapeHtml ساخته و دکمه ویرایش/حذف به هر کاربر متصل می‌شوند.",
            "در create رمز الزامی و در edit اختیاری است؛ modal بیرونی قابل بستن است.",
            "ابتدا /api/me نقش را کنترل و سپس کاربران را بارگذاری می‌کند.",
        ],
        [
            ("api", "fetch و تبدیل پاسخ خطا به exception."),
            ("openModal / closeModal", "حالت create/edit فرم."),
            ("renderUsers / loadUsers", "رندر و دریافت فهرست."),
            ("removeUser", "تأیید و DELETE."),
            ("form submit handler", "POST یا PUT بر اساس user-id."),
        ],
    ),
    file_block(
        "static/vendor/chart.umd.min.js",
        "نسخه minified و vendored کتابخانه Chart.js برای ترسیم نمودار بدون وابستگی runtime به CDN.",
        [
            "کد third-party تولیدشده است و نگهداری دستی آن توصیه نمی‌شود.",
            "از طریق global به نام <code>Chart</code> در static/script.js مصرف می‌شود.",
        ],
    ),
    file_block(
        "static/images/login-template.png",
        "دارایی تصویری دودویی مربوط به الگو/مرجع طراحی صفحه ورود.",
        [
            "فایل PNG کد اجرایی ندارد؛ در مستند فقط نقش و اندازه آن ثبت می‌شود.",
        ],
    ),
]


support_files = [
    file_block(
        "Dockerfile",
        "ساخت image سبک Python 3.11 برای اجرا در container/Hugging Face Spaces.",
        [
            "dependencyها را پیش از COPY کل پروژه نصب می‌کند تا cache لایه‌ها بهتر استفاده شود.",
            "پورت ۷۸۶۰ را expose می‌کند؛ در startup اگر DB وجود نداشته باشد db_mock.py را اجرا می‌کند و سپس Uvicorn را بالا می‌آورد.",
        ],
    ),
    file_block(
        "requirements.txt",
        "فهرست dependencyهای runtime پایتون.",
        [
            "FastAPI/Uvicorn برای وب، SQLAlchemy/Pandas برای داده، Requests برای مدل‌ها، python-multipart و itsdangerous برای وب و a2wsgi برای Passenger.",
            "بعضی packageها pin نشده‌اند؛ build آینده می‌تواند نسخه متفاوتی دریافت کند.",
        ],
    ),
    file_block(
        "README.md",
        "راهنمای پروژه، معماری اولیه، setup و توضیح تعویض پایگاه داده.",
        [
            "بخش‌هایی از README با کد جدید همگام نیست: هنوز auth مبتنی بر access_key و endpointهای قدیمی را توصیف می‌کند، در حالی که branch حساب app_users و session دارد.",
            "راهنمای Ollama، ساخت DB، اجرای Uvicorn و تنظیم DATABASE_URL همچنان مفید است.",
        ],
    ),
    file_block(
        ".gitignore",
        "حذف فایل‌های Python، محیط مجازی، DB/history/env، archive و تنظیمات IDE از Git.",
        [
            "به‌درستی <code>.env</code> و <code>*.db</code> را حذف می‌کند؛ اما secretی که مستقیماً در سورس نوشته شود با .gitignore محافظت نمی‌شود.",
        ],
    ),
    file_block(
        ".test_cookies.txt",
        "cookie jar با قالب Netscape که curl ساخته است.",
        [
            "در commit حاضر فقط header دارد و cookie فعال ذخیره نکرده است.",
            "اصولاً فایل‌های cookie واقعی نباید commit شوند، چون ممکن است session حساس داشته باشند.",
        ],
    ),
    file_block(
        "create_presentation.py",
        "اسکریپت ساخت خودکار ارائه فارسی PowerPoint درباره پروژه.",
        [
            "با python-pptx شکل‌ها، textboxها، bulletها، footer و ۱۱ اسلاید را تولید می‌کند.",
            "فونت فارسی، جهت و رنگ سازمانی را روی runهای PowerPoint اعمال می‌کند.",
            "dependency python-pptx در requirements.txt حاضر نیست و برای بازتولید ارائه باید جداگانه نصب شود.",
        ],
        [
            ("set_run_font / set_textbox", "تنظیم فونت و پاراگراف فارسی."),
            ("add_rect / add_round_rect", "ساخت عناصر هندسی."),
            ("add_bullets / footer", "لیست و شماره صفحه."),
            ("build", "تولید کل deck و ذخیره فایل."),
        ],
    ),
    file_block(
        "Rayamate_Presentation.pptx",
        "خروجی دودویی ارائه ساخته‌شده برای معرفی معماری و قابلیت‌ها.",
        [
            "کد نیست و محتوای داخلی OOXML در این مستند line-by-line بررسی نمی‌شود؛ منبع قابل نگهداری آن create_presentation.py است.",
        ],
    ),
    file_block(
        "index.html",
        "نسخه قدیمی/مرجع پوسته گفتگو در ریشه repository.",
        [
            "FastAPI این فایل را سرو نمی‌کند؛ route فعال به static/index.html اشاره دارد.",
            "نسخه ریشه sidebar، نشست و مدیریت کاربران جدید را ندارد و احتمالاً artifact باقی‌مانده از طراحی قبلی است.",
        ],
    ),
    file_block(
        "script.js",
        "JavaScript قدیمی رابط access_key در ریشه.",
        [
            "DOMهایی مانند login-gate و APIهایی مانند /api/customers را انتظار دارد که با app.py فعلی هماهنگ نیستند.",
            "در صفحات فعال load نمی‌شود و بهتر است در آینده حذف، archive یا صریحاً به‌عنوان legacy علامت‌گذاری شود.",
        ],
    ),
    file_block(
        "style.css",
        "CSS قدیمی رابط تک‌ستونه در ریشه.",
        [
            "صفحات فعال <code>/static/style.css</code> را می‌خوانند؛ این فایل توسط FastAPI mount نشده است.",
            "توکن‌های visual identity اولیه و login-gate قدیمی را نگه می‌دارد.",
        ],
    ),
]


security_body = """
<div class="risk-grid">
  <div class="risk high"><h3>بحرانی — کلید API در سورس</h3><p>در commit این branch برای AvalAI یک مقدار پیش‌فرض واقعی‌نما داخل کد وجود دارد. مقدار در این سند عمداً بازنشر نشده است. کلید باید فوراً revoke/rotate شود و فقط از secret manager یا environment دریافت گردد؛ default باید خالی باشد.</p></div>
  <div class="risk high"><h3>بالا — credentialهای پیش‌فرض</h3><p>نام کاربری/گذرواژه مدیر bootstrap و SESSION_SECRET دارای default ثابت هستند. در production باید startup بدون environment امن fail شود و secret قوی تزریق گردد.</p></div>
  <div class="risk med"><h3>متوسط — کپچای نمایشی</h3><p>captcha فقط یک boolean ارسالی از مرورگر است و اثبات ضدربات نیست. برای محیط عمومی باید سرویس captcha واقعی و rate limiting اضافه شود.</p></div>
  <div class="risk med"><h3>متوسط — CSRF و cookie</h3><p>عملیات POST/PUT/DELETE token ضد-CSRF ندارند. تنظیم secure/https-only کوکی نیز صریح نیست. SameSite=Lax کمک می‌کند اما جایگزین کامل CSRF protection نیست.</p></div>
  <div class="risk med"><h3>متوسط — اعتبارسنجی SQL regex</h3><p>لایه فعلی برای prototype مفید است ولی parser کامل SQL نیست. اجازه WITH/SELECT، نبود timeout/query-cost و حذف LIMIT می‌تواند query سنگین ایجاد کند. کاربر DB باید read-only و محدود باشد.</p></div>
  <div class="risk med"><h3>متوسط — نبود row-level scope</h3><p>README از محدودسازی داده مشتری صحبت می‌کند، اما app.py فعلی سؤال کاربر واردشده را بدون scope مبتنی بر مشتری روی DB اجرا می‌کند. app_users نیز به dim_customer متصل نیست.</p></div>
  <div class="risk low"><h3>پایین — persistence چندپردازه</h3><p>Lock حافظه فقط داخل یک process معتبر است. چند worker می‌توانند history.json را هم‌زمان بازنویسی کنند. برای production از DB یا storage تراکنشی استفاده شود.</p></div>
  <div class="risk low"><h3>پایین — dependency و CDN</h3><p>چند dependency بدون version pin و صفحه اول وابسته به CDN است. برای build تکرارپذیر و شبکه بسته، lockfile و asset محلی توصیه می‌شود.</p></div>
</div>
"""


run_body = """
<ol class="steps">
  <li><strong>محیط:</strong> Python 3.11 و virtualenv ایجاد کنید؛ سپس <code>pip install -r requirements.txt</code>.</li>
  <li><strong>تنظیم secrets:</strong> حداقل <code>SESSION_SECRET</code>، <code>AUTH_USERNAME</code>، <code>AUTH_PASSWORD</code> و در صورت استفاده <code>AVALAI_API_KEY</code> را در محیط امن قرار دهید.</li>
  <li><strong>مدل محلی:</strong> برای Ollama مدل تنظیم‌شده در <code>MODEL_NAME</code> را pull و <code>ollama serve</code> را اجرا کنید.</li>
  <li><strong>داده mock:</strong> یک بار <code>python db_mock.py</code>؛ توجه کنید اجرای مجدد DB را بازسازی می‌کند.</li>
  <li><strong>اجرا:</strong> <code>uvicorn app:app --host 0.0.0.0 --port 8000</code> و سپس بازکردن route ریشه.</li>
  <li><strong>استقرار:</strong> Dockerfile برای container و passenger_wsgi.py برای cPanel دو مسیر مستقل استقرار هستند.</li>
</ol>
"""


inventory_rows = []
for index, path in enumerate(tracked_files, start=1):
    raw = branch_file(path)
    try:
        count = f"{len(raw.decode('utf-8').splitlines()):,} خط"
        kind = "متنی/کد"
    except UnicodeDecodeError:
        count = f"{len(raw):,} بایت"
        kind = "دودویی"
    inventory_rows.append([str(index), f"<code>{esc(path)}</code>", kind, count])


body = f"""
<section class="cover page">
  <div class="cover-mark">RAYAMATE · CODE DOCUMENTATION</div>
  <h1>مستند فنی فارسی<br>برنچ <span dir="ltr">newDashboard2</span></h1>
  <p class="lead">شرح معماری، جریان اجرا، APIها، مدل داده، تمام فایل‌های tracked و منطق کدهای اصلی</p>
  <div class="meta">
    <div><span>Commit</span><code dir="ltr">{commit_short}</code></div>
    <div><span>تاریخ commit</span><b dir="ltr">{esc(commit_date)}</b></div>
    <div><span>عنوان</span><b>{esc(commit_subject)}</b></div>
    <div><span>تعداد فایل‌ها</span><b>{len(tracked_files)} فایل</b></div>
  </div>
  <p class="scope">منبع این سند مستقیماً از Git objectهای branch خوانده شده است، نه از تغییرات ثبت‌نشده working tree. مقادیر secret عمداً در سند بازنشر نشده‌اند.</p>
</section>

{page("خلاصه سامانه", architecture + bullets([
    "<strong>هدف:</strong> پرسش فارسی/انگلیسی درباره تراکنش‌ها، تبدیل به SQL و نمایش جدول/نمودار/تحلیل.",
    "<strong>Backend:</strong> FastAPI، Pydantic، SQLAlchemy و Pandas.",
    "<strong>مدل زبانی:</strong> AvalAI ابری یا Ollama محلی با interface یکسان.",
    "<strong>Frontend:</strong> HTML/CSS/JavaScript خالص و Chart.js.",
    "<strong>هویت:</strong> session امضاشده، حساب app_users و نقش admin/user.",
    "<strong>داده:</strong> star schema آزمایشی PSP روی SQLite با قابلیت تغییر DATABASE_URL.",
]), "۱ · نمای کلان")}

{page("مسیرهای HTTP و سطح دسترسی", table(["مسیر", "دسترسی", "وظیفه"], route_rows, ltr_first=True), "۲ · API")}

{page("مدل داده", table(["جدول", "نقش", "ستون‌ها/رابطه‌های مهم"], schema_rows, ltr_first=True) + """
<div class="callout">
<strong>قاعده حیاتی تاریخ:</strong> <code>fact_transactions.date_key</code> یک عدد YYYYMMDD است؛ برای فیلتر تقویمی باید
<code>dim_date</code> join شود و از <code>full_date</code> استفاده گردد. هم prompt مدل و هم sql_safety این قاعده را تقویت می‌کنند.
</div>
""", "۳ · پایگاه داده")}

{page("فایل‌های Backend", "".join(backend_files), "۴ · Python")}
{page("فایل‌های Frontend", "".join(frontend_files), "۵ · HTML / CSS / JavaScript")}
{page("فایل‌های پیکربندی، مستند و legacy", "".join(support_files), "۶ · سایر فایل‌ها")}
{page("جریان‌های اجرایی مهم", """
<div class="sequence">
  <h3>ورود</h3><p>login.js → POST /api/login → users.authenticate_user → verify_password → set_session_user → cookie session → redirect /app</p>
  <h3>گفتگو</h3><p>sendMessage → POST /api/chat → provider.generate_sql → strip/fix/validate SQL → read_sql_query → memory.add_message → renderResult</p>
  <h3>تحلیل</h3><p>Analyze button → POST /api/analyze → provider.generate_analysis(first 20 rows) → memory.update_last_analysis → formatAnalysisHtml</p>
  <h3>مدیریت کاربر</h3><p>/users → require_admin → users.js CRUD → /api/users → users.py → SQLAlchemy app_users</p>
  <h3>تغییر تنظیمات</h3><p>دکمه مدل/زبان → PUT /api/preferences → MemoryManager per-user → بارگذاری مجدد از /api/me</p>
</div>
""", "۷ · End-to-End")}
{page("ریسک‌ها و پیشنهادهای فنی", security_body, "۸ · بازبینی")}
{page("راه‌اندازی و استقرار", run_body, "۹ · عملیات")}
{page("فهرست کامل فایل‌های بررسی‌شده", table(["ردیف", "مسیر", "نوع", "اندازه"], inventory_rows), "۱۰ · پوشش")}
{page("جمع‌بندی", """
<div class="summary">
  <p>برنچ <code>newDashboard2</code> یک prototype نسبتاً کامل BI مکالمه‌ای است: صفحه معرفی، ورود، داشبورد، مدیریت کاربران،
  انتخاب دو مدل، تولید و اصلاح SQL، جدول و نمودار، تحلیل ثانویه و تاریخچه شخصی را یک‌جا دارد.</p>
  <p>مهم‌ترین کارهای پیش از production عبارت‌اند از حذف و rotate تمام secretهای commit‌شده، اجباری‌کردن تنظیمات امن،
  افزودن row-level authorization واقعی، CSRF/rate-limit، استفاده از DB برای history، parser/timeout قوی‌تر SQL،
  همگام‌سازی README و حذف نسخه‌های legacy ریشه.</p>
  <div class="stamp">پایان سند · commit <span dir="ltr">{commit_short}</span></div>
</div>
""", "۱۱ · نتیجه")}
"""


document = f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>مستند کد newDashboard2</title>
<style>
  @page {{ size: A4; margin: 16mm 14mm 17mm; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; color: #17231f; background: #fff; font-family: Tahoma, Arial, sans-serif; font-size: 10.3pt; line-height: 1.85; }}
  .page {{ break-before: page; }}
  .cover {{ break-before: auto; min-height: 255mm; display: flex; flex-direction: column; justify-content: center; padding: 12mm; border: 2px solid #0b7654; }}
  .cover-mark, .kicker {{ color: #0b7654; letter-spacing: .08em; font-size: 8.5pt; font-weight: bold; }}
  h1 {{ font-size: 29pt; line-height: 1.45; margin: 18mm 0 7mm; color: #103b2e; }}
  h1 span {{ color: #0b7654; }}
  .lead {{ font-size: 14pt; color: #48635a; max-width: 145mm; }}
  .meta {{ margin-top: 16mm; display: grid; grid-template-columns: 1fr 1fr; gap: 3mm; }}
  .meta div {{ background: #eef7f3; padding: 3mm 4mm; border-right: 3px solid #0b7654; }}
  .meta span {{ display: block; color: #688078; font-size: 8pt; }}
  .scope {{ margin-top: 16mm; font-size: 8.5pt; color: #5a6d66; border-top: 1px solid #cbdad4; padding-top: 4mm; }}
  .section-head {{ margin: 0 0 8mm; border-bottom: 2px solid #0b7654; padding-bottom: 3mm; }}
  h2 {{ margin: 1mm 0 0; font-size: 20pt; color: #103b2e; }}
  h3 {{ color: #145b45; margin: 0 0 2mm; font-size: 12.5pt; }}
  p {{ margin: 1.5mm 0 3mm; }}
  ul {{ margin: 2mm 0 3mm; padding-right: 6mm; }}
  li {{ margin-bottom: 1.2mm; }}
  code {{ font-family: Consolas, "Courier New", monospace; direction: ltr; unicode-bidi: embed; background: #edf3f0; color: #184f3e; border-radius: 3px; padding: .2mm 1mm; font-size: 8.6pt; overflow-wrap: anywhere; }}
  .flow {{ display: flex; align-items: stretch; justify-content: center; gap: 2mm; margin: 8mm 0; }}
  .flow div {{ border: 1px solid #8fb8aa; background: #f4faf7; padding: 4mm 3mm; text-align: center; flex: 1; border-radius: 5px; font-weight: bold; color: #15523e; }}
  .flow small {{ display: block; font-weight: normal; color: #60766f; }}
  .flow b {{ align-self: center; color: #0b7654; }}
  .callout {{ background: #eef7f3; border-right: 4px solid #0b7654; padding: 4mm 5mm; margin: 5mm 0; break-inside: avoid; }}
  .table-wrap {{ width: 100%; margin: 4mm 0 8mm; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 8.8pt; }}
  th {{ background: #145b45; color: white; text-align: right; padding: 2.4mm; }}
  td {{ border: 1px solid #cad9d3; padding: 2.2mm; vertical-align: top; }}
  tr:nth-child(even) td {{ background: #f6faf8; }}
  td.ltr {{ direction: ltr; text-align: left; font-family: Consolas, monospace; font-size: 8.2pt; }}
  .file-block {{ break-inside: avoid; margin: 0 0 6mm; border: 1px solid #c9d9d3; border-radius: 6px; padding: 4mm 5mm; }}
  .file-title {{ display: flex; justify-content: space-between; gap: 4mm; align-items: center; border-bottom: 1px solid #dbe6e2; padding-bottom: 2mm; }}
  .file-title h3 {{ margin: 0; direction: ltr; text-align: left; }}
  .file-title span {{ color: #667a73; font-size: 8pt; white-space: nowrap; }}
  .role {{ font-weight: bold; color: #314c43; }}
  .code-list {{ margin-top: 3mm; display: grid; gap: 1.5mm; }}
  .code-list > div {{ display: grid; grid-template-columns: 48mm 1fr; gap: 3mm; align-items: start; background: #f7faf9; padding: 2mm; }}
  .code-list code {{ text-align: left; }}
  .risk-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 4mm; }}
  .risk {{ break-inside: avoid; border: 1px solid #ccd8d4; border-top-width: 4px; padding: 4mm; }}
  .risk.high {{ border-top-color: #a43a32; }}
  .risk.med {{ border-top-color: #d08b24; }}
  .risk.low {{ border-top-color: #3b7d69; }}
  .risk p {{ font-size: 9pt; }}
  .steps li {{ margin-bottom: 4mm; }}
  .sequence h3 {{ margin-top: 5mm; padding-bottom: 1mm; border-bottom: 1px solid #c9d9d3; }}
  .sequence p {{ direction: ltr; text-align: left; font-family: Consolas, Tahoma, sans-serif; background: #f5f9f7; padding: 3mm; }}
  .summary {{ font-size: 13pt; line-height: 2.1; padding: 12mm 8mm; border: 1px solid #9cbeb2; }}
  .stamp {{ margin-top: 16mm; color: #0b7654; font-weight: bold; text-align: center; }}
  @media print {{
    a {{ color: inherit; text-decoration: none; }}
    .file-block, .callout, tr {{ break-inside: avoid; }}
  }}
</style>
</head>
<body>{body}</body>
</html>
"""


HTML_OUT.write_text(document, encoding="utf-8")

chrome_candidates = [
    Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
]
browser = next((path for path in chrome_candidates if path.exists()), None)
if browser is None:
    raise SystemExit(f"HTML created at {HTML_OUT}, but Chrome/Edge was not found.")

subprocess.run(
    [
        str(browser),
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--allow-file-access-from-files",
        f"--print-to-pdf={PDF_OUT}",
        HTML_OUT.as_uri(),
    ],
    check=True,
)

print(f"Generated HTML: {HTML_OUT}")
print(f"Generated PDF:  {PDF_OUT}")
print(f"Branch commit:  {commit_hash}")
print(f"Generated at:   {datetime.now().isoformat(timespec='seconds')}")
