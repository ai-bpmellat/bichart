"""Generate a complete Persian technical-documentation PDF for the current project
working tree (not a specific git commit — this reflects files exactly as they are
on disk right now, including uncommitted work).

Usage:
    python scripts/generate_project_docs_fa.py

Produces:
    docs/bichart_project_documentation_fa.html
    docs/bichart_project_documentation_fa.pdf   (rendered via headless Chrome/Edge)
"""

from __future__ import annotations

import html
import os
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True)
HTML_OUT = DOCS / "bichart_project_documentation_fa.html"
PDF_OUT = DOCS / "bichart_project_documentation_fa.pdf"


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


def read_file(path: str) -> bytes | None:
    p = ROOT / path
    if not p.exists():
        return None
    return p.read_bytes()


def file_size_metric(path: str) -> str:
    raw = read_file(path)
    if raw is None:
        return "یافت نشد"
    try:
        lines = len(raw.decode("utf-8").splitlines())
        return f"{lines:,} خط"
    except UnicodeDecodeError:
        return f"{len(raw):,} بایت (دودویی)"


def file_block(path: str, role: str, details: list[str], symbols: list[tuple[str, str]] | None = None) -> str:
    metric = file_size_metric(path)
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


generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

try:
    git_branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True
    ).strip()
except Exception:
    git_branch = "نامشخص"

try:
    git_status_lines = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True
    ).splitlines()
    uncommitted_count = len(git_status_lines)
except Exception:
    uncommitted_count = None


# ---------------------------------------------------------------------------
# Data: routes, schema
# ---------------------------------------------------------------------------
route_rows = [
    ["GET /", "عمومی", "صفحه معرفی محصول <code>static/first.html</code>."],
    ["GET /login", "عمومی", "فرم ورود؛ کاربر واردشده مستقیم به <code>/app</code> هدایت می‌شود."],
    ["POST /api/login", "عمومی", "بررسی کپچا، احراز هویت با users.py و ساخت نشست."],
    ["POST /api/logout", "واردشده", "پاک‌کردن کامل نشست."],
    ["GET /api/me", "واردشده", "اطلاعات کاربر جاری + ترجیحات (provider/language)."],
    ["GET /favicon.ico", "عمومی", "آیکون سایت."],
    ["GET /app", "واردشده", "پوسته داشبورد گفتگو (<code>static/index.html</code>)."],
    ["GET /users", "مدیر", "صفحه مدیریت کاربران؛ غیرمدیر به /app هدایت می‌شود."],
    ["GET /api/users", "مدیر", "فهرست کامل حساب‌های برنامه."],
    ["POST /api/users", "مدیر", "ساخت حساب جدید و هش‌کردن گذرواژه."],
    ["PUT /api/users/{id}", "مدیر", "ویرایش نام کاربری، رمز، نقش، وضعیت فعال."],
    ["DELETE /api/users/{id}", "مدیر", "حذف حساب؛ حذف خود و آخرین مدیر مسدود است."],
    ["GET /api/health", "واردشده", "بررسی سلامت DB، Ollama و AvalAI."],
    ["GET /api/avalai/credit", "واردشده", "پروکسی سرور برای مانده اعتبار AvalAI (کلید هرگز به مرورگر نمی‌رود)."],
    ["POST /api/chat", "واردشده", "گام ۱: تولید SQL از سؤال کاربر (بدون اجرا)."],
    ["POST /api/run_sql", "واردشده", "گام ۲: اعتبارسنجی ایمنی، اجرا؛ در صورت خطا یک تلاش خودکار اصلاح SQL توسط مدل."],
    ["POST /api/analyze", "واردشده", "تحلیل اختیاری حداکثر ۸۰ ردیف اول نتیجه."],
    ["POST /api/discuss", "واردشده", "بحث/چالش چندنوبتی درباره داده یا تحلیل."],
    ["POST /api/feedback", "واردشده", "ثبت 👍/👎 روی یک پیام برای یادگیری از بازخورد."],
    ["GET /api/history", "واردشده", "۵۰ پیام اخیر همان کاربر، شامل داده ذخیره‌شده برای بازپخش."],
    ["GET /api/frequent-questions", "واردشده", "۱۰ سؤال پرتکرار از میان همهٔ کاربران (جدید)."],
    ["GET /api/preferences", "واردشده", "خواندن provider/language ذخیره‌شده کاربر."],
    ["PUT /api/preferences", "واردشده", "ذخیره provider/language معتبر."],
    ["POST /api/export_pdf", "واردشده", "ساخت و بازگرداندن PDF فارسی نتیجه (fpdf2 + HarfBuzz)."],
    ["POST /api/export_excel", "واردشده", "ساخت و بازگرداندن اکسل سه‌شیتی (Data/Explanation/Analysis)."],
    ["GET /api/feature-poll", "واردشده", "وضعیت نظرسنجی قابلیت‌های آینده."],
    ["POST /api/feature-poll", "واردشده", "ثبت رأی کاربر (حداکثر ۳ گزینه + پیشنهاد سفارشی)."],
]

schema_rows = [
    ["app_users", "حساب‌های ورود", "id، username، password_hash (PBKDF2)، mobile، display_name، role، is_active"],
    ["dim_date", "بعد تاریخ", "date_key به‌شکل عدد YYYYMMDD، full_date، روز/ماه/سال، آخرهفته و تعطیلی"],
    ["dim_category", "بعد صنف", "شناسه و عنوان فارسی ۱۵ صنف استاندارد پذیرندگان"],
    ["dim_customer", "مشتری قراردادی PSP", "نام، access_key نمایشی و نقش customer/admin؛ مستقل از app_users است"],
    ["dim_merchant", "پذیرنده", "نام/کد، MCC، صنف، شهر، مالک (owner_customer_id) و وضعیت فعال"],
    ["dim_terminal", "پایانه", "سریال، پذیرنده، نوع POS/mPOS/Online، تاریخ نصب و وضعیت active/inactive"],
    ["fact_transactions", "فکت تراکنش", "تاریخ، پایانه، پذیرنده، مبلغ، وضعیت approved/declined/reversed، PAN ماسک‌شده، کانال"],
]

architecture = """
<div class="flow" dir="ltr">
  <div>Browser<br><small>Landing / Login / Dashboard</small></div><b>→</b>
  <div>FastAPI<br><small>Session + Routes</small></div><b>→</b>
  <div>LLM Provider<br><small>AvalAI or Ollama</small></div><b>→</b>
  <div>SQL Safety + Auto-fix<br><small>Regex repair + retry</small></div><b>→</b>
  <div>SQLAlchemy<br><small>SQLite / external DB</small></div>
</div>
<div class="callout">
  <strong>مسیر اصلی سؤال:</strong>
  مرورگر سؤال و تنظیمات زبان/مدل را به <code>/api/chat</code> می‌فرستد؛ مدل یک JSON شامل SQL و توضیح می‌سازد.
  کاربر SQL را (در صورت نیاز) ویرایش و اجرا می‌کند: <code>/api/run_sql</code> ابتدا SQL را نرمال‌سازی و ایمن‌سازی
  می‌کند، سپس اجرا می‌کند؛ اگر اجرا با خطا مواجه شود، خطای دیتابیس یک‌بار به‌صورت خودکار به مدل بازخورد داده می‌شود
  تا SQL را اصلاح کند (<code>fix_sql</code>) و دوباره اجرا شود. نتیجه، زمان هر مرحله و (در صورت اصلاح خودکار) پرچم
  <code>auto_fixed</code> به رابط برمی‌گردد. تحلیل هوشمند عمداً در درخواست جداگانه <code>/api/analyze</code> و با
  اقدام کاربر اجرا می‌شود تا مصرف مدل کنترل‌شده بماند.
</div>
"""


# ---------------------------------------------------------------------------
# Backend files
# ---------------------------------------------------------------------------
backend_files = [
    file_block(
        "app.py",
        "مرکز اتصال تمام اجزای برنامه: تعریف FastAPI، middlewareها، مدل‌های Pydantic و تمام endpointها.",
        [
            "دو provider با مجموعه <code>VALID_PROVIDERS</code> کنترل می‌شوند و <code>get_llm_client</code> ماژول AvalAI یا Ollama را برمی‌گرداند.",
            "ترتیب middleware مهم است: <code>SessionMiddleware</code> بعد از تعریف middleware ورود اضافه می‌شود تا در پشته بیرونی‌تر باشد و <code>request.session</code> از قبل در دسترس middleware ورود باشد.",
            "رشته <code>SCHEMA_DESCRIPTION</code> ساختار دقیق جداول و قواعد حیاتی تاریخ/وضعیت را به مدل می‌دهد تا SQL سازگار با SQLite تولید شود.",
            "<code>/api/chat</code> فقط SQL تولید می‌کند (بدون اجرا)؛ <code>/api/run_sql</code> جداگانه اعتبارسنجی و اجرا می‌کند تا کاربر بتواند پیش از اجرا SQL را ببیند/ویرایش کند.",
            "در <code>/api/run_sql</code> اگر اجرای SQL خطا بدهد، یک تلاش خودکار اصلاح انجام می‌شود: خطای واقعی دیتابیس به <code>llm.fix_sql(...)</code> داده می‌شود، خروجی دوباره از فیلتر normalize/strip_limit/validate عبور می‌کند و اجرا می‌شود؛ در صورت شکست اصلاح، خطای اصلی (نه خطای تلاش دوم) به کاربر برمی‌گردد.",
            "هر پیام موفق با <code>memory.add_message(..., data=records[:HISTORY_DATA_CAP])</code> ذخیره می‌شود؛ ذخیرهٔ خودِ داده (حداکثر ۵۰۰ ردیف) امکان «بازپخش کامل» یک گفتگوی قدیمی از تاریخچه را فراهم می‌کند.",
            "<code>/api/frequent-questions</code> سؤالات پرتکرار میان همهٔ کاربران را از <code>memory.get_frequent_questions</code> می‌گیرد.",
            "خروجی PDF/Excel با <code>pdf_generator.generate_llm_pdf</code> و <code>excel_generator.generate_llm_excel</code> ساخته و به‌عنوان فایل دانلودی بازگردانده می‌شود.",
            "نظرسنجی قابلیت‌های آینده (feature poll) در همین فایل با قفل نخی و ذخیره در <code>feature_poll.json</code> پیاده شده است؛ گزینه‌های سفارشی کاربر تا ۱۰۰ کاراکتر مجاز است.",
            "مدیریت کاربران فقط با نقش admin در دسترس است؛ حذف خودِ کاربر جاری در همین route نیز مسدود می‌شود.",
        ],
        [
            ("get_llm_client(provider)", "انتخاب پیاده‌سازی مشترک generate_sql/generate_analysis/fix_sql."),
            ("require_login_middleware", "تفکیک مسیرهای عمومی، API بدون نشست و صفحات نیازمند ورود."),
            ("_startup_init_users", "ساخت جدول app_users و مدیر آغازین هنگام startup."),
            ("require_admin", "تولید پاسخ 401 یا 403 برای عملیات مدیریتی."),
            ("chat", "گام تولید SQL؛ بدون اجرا."),
            ("run_sql", "اعتبارسنجی، اجرا، تلاش خودکار اصلاح در صورت خطا، ذخیره تاریخچه."),
            ("analyze / discuss", "تحلیل ثانویه و بحث چندنوبتی روی نتیجه."),
            ("get_history / get_frequent_questions", "تاریخچهٔ شخصی و سؤالات پرتکرار سراسری."),
            ("export_pdf / export_excel", "تولید فایل‌های خروجی از آخرین نتیجه."),
            ("get_feature_poll / post_feature_poll", "نظرسنجی قابلیت‌های آینده."),
        ],
    ),
    file_block(
        "database.py",
        "تنظیم مرکزی SQLAlchemy؛ تنها نقطه انتخاب SQLite یا پایگاه داده خارجی.",
        [
            "<code>DATABASE_URL</code> از environment خوانده می‌شود و در حالت پیش‌فرض به <code>psp_bi_mock.db</code> اشاره دارد.",
            "برای SQLite گزینه <code>check_same_thread=False</code> فعال است؛ برای DB2/SQL Server/PostgreSQL فقط رشتهٔ اتصال عوض می‌شود.",
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
            "شش کلاس ORM (ابعاد + فکت)، ۱۵ صنف استاندارد و MCCهای متناظر، ~۵۵ پذیرنده فارسی، ۱۰ شهر و ۶ مشتری نمونه تعریف می‌کند.",
            "بازهٔ تاریخ به‌صورت متحرک است: از ۶ ماه قبل تا امروز (<code>MOCK_DATE_START</code>/<code>MOCK_DATE_END</code>) — یعنی هر بار اجرا داده تازه‌ای متناسب با تاریخ جاری می‌سازد.",
            "seed ثابت ۴۲ باعث بازتولیدپذیری بخش تصادفی داده می‌شود.",
            "مبلغ تراکنش‌ها با <code>lognormvariate</code> تولید می‌شود تا توزیع واقعی‌تر (چوله به راست) داشته باشد.",
            "اجرای دوباره این فایل مخرب است: فایل دیتابیس را حذف یا (در صورت قفل بودن) جداول را drop/create مجدد می‌کند.",
        ],
        [
            ("DimDate / DimCategory", "ابعاد تقویم و صنف."),
            ("DimCustomer / DimMerchant / DimTerminal", "مالکیت تجاری، پذیرنده و پایانه."),
            ("FactTransaction", "جدول رخدادهای مالی."),
            ("weighted_choice", "انتخاب احتمالی وزن‌دار برای داده طبیعی‌تر."),
            ("mask_pan", "تولید شماره کارت ماسک‌شده نمایشی."),
            ("months_ago", "محاسبهٔ تاریخ N ماه قبل با کلمپ روز پایان ماه."),
            ("build_database(n_transactions=1000)", "ساخت کامل schema و داده نمونه."),
        ],
    ),
    file_block(
        "auth.py",
        "توابع کوچک و متمرکز برای احراز هویت مبتنی بر session امضاشده (Starlette SessionMiddleware).",
        [
            "کلیدهای username، user_id، role و display_name را در کوکی نشست امضاشده نگه می‌دارد؛ خودِ کوکی رمزنگاری محتوا نمی‌کند، فقط امضا می‌شود.",
            "اعتبارسنجی واقعی گذرواژه به <code>users.py</code> واگذار می‌شود؛ این فایل فقط لایهٔ نشست است.",
            "<code>SESSION_SECRET</code> قابل تنظیم با environment است؛ در نبود آن یک مقدار پیش‌فرض توسعه استفاده می‌شود که برای production باید حتماً عوض شود.",
        ],
        [
            ("verify_credentials", "wrapper روی users.authenticate_user."),
            ("set_session_user", "نوشتن داده عمومی کاربر در نشست."),
            ("is_authenticated / is_admin", "کنترل سریع وضعیت و نقش."),
            ("current_user", "ساخت dict عمومی کاربر از session."),
        ],
    ),
    file_block(
        "users.py",
        "مدل ORM و عملیات CRUD حساب‌های ورود برنامه (app_users)؛ کاملاً مستقل از dim_customer تحلیلی در db_mock.py.",
        [
            "گذرواژه با PBKDF2-HMAC-SHA256، salt تصادفی ۱۶ بایتی و ۱۲۰هزار iteration به‌صورت <code>pbkdf2_sha256$120000$salt$hash</code> ذخیره می‌شود.",
            "مقایسه digest با <code>hmac.compare_digest</code> (مقاوم در برابر timing attack) انجام می‌شود.",
            "مدیر bootstrap از environment یا مقادیر پیش‌فرض ساخته می‌شود و در هر startup فعال/admin نگه داشته می‌شود.",
            "کد صریحاً از حذف، غیرفعال‌سازی یا تنزل آخرین مدیر فعال جلوگیری می‌کند (بررسی <code>admin_count &lt;= 1</code> در سه تابع).",
        ],
        [
            ("AppUser", "کلاس ORM جدول app_users (id، username، password_hash، mobile، display_name، role، is_active، created_at، updated_at)."),
            ("hash_password / verify_password", "هش و بررسی گذرواژه."),
            ("init_users_table / seed_bootstrap_admin", "راه‌اندازی اولیه جدول و حساب مدیر."),
            ("authenticate_user", "بررسی وجود، فعال بودن و صحت رمز."),
            ("list_users / create_user / update_user / delete_user", "عملیات مدیریت با کنترل‌های کسب‌وکار."),
        ],
    ),
    file_block(
        "memory_manager.py",
        "حافظهٔ گفتگو و ترجیحات جداگانه برای هر username، با persistence در history.json و کلاس <code>MemoryManager</code>.",
        [
            "ساختار دیسک: <code>{\"users\": {username: {\"preferences\": {...}, \"messages\": [...]}}}</code>.",
            "یک <code>threading.Lock</code> از تداخل نوشتن/خواندن هم‌زمان چند درخواست جلوگیری می‌کند.",
            "هر پیام موفق اکنون شامل کلید <code>data</code> (نمونهٔ ردیف‌های واقعی نتیجه، حداکثر ۵۰۰ تا) است — این افزودهٔ تازه است که «بازپخش» کامل یک گفتگوی قدیمی (جدول + نمودار + تحلیل) را از سمت فرانت‌اند ممکن می‌کند.",
            "<code>get_frequent_questions</code> (تازه) روی همهٔ کاربران سؤالات را نرمال (lower-case) و شمارش می‌کند، «SQL run» پیش‌فرض را نادیده می‌گیرد و بر اساس (تعداد، جدیدترین) مرتب می‌کند.",
            "فرمت قدیمی که یک list ساده بوده به bucket کاربر anonymous مهاجرت داده می‌شود؛ history.json در Git نیست.",
        ],
        [
            ("MemoryManager", "کلاس اصلی با قفل نخی، بارگذاری/ذخیرهٔ دیسک و همهٔ متدهای زیر."),
            ("_ensure_user", "ساخت bucket و تکمیل preferenceهای پیش‌فرض."),
            ("add_message / get_context", "ثبت پیام (به‌همراه data) و دریافت n پیام پایانی."),
            ("get_frequent_questions(n=10)", "شمارش سؤالات میان همهٔ کاربران، مرتب‌شده بر اساس تکرار و تازگی."),
            ("update_last_analysis", "افزودن تحلیل به آخرین سؤال مطابق."),
            ("set_feedback / _append_feedback_log", "ثبت 👍/👎 روی پیام و لاگ جداگانه در feedback.json برای ارزیابی."),
            ("get_preferences / set_preferences", "مدیریت provider و language هر کاربر."),
        ],
    ),
    file_block(
        "sql_safety.py",
        "لایهٔ اصلاح خطاهای رایج مدل (regex-based، نه parser کامل SQL) و رد SQLهای غیرخواندنی پیش از اجرا.",
        [
            "<code>fix_date_key_sql</code> عبارت‌های اشتباه روی <code>fact_transactions.date_key</code> (عدد YYYYMMDD) را تشخیص و در صورت نیاز خودکار <code>JOIN dim_date</code> اضافه و ارجاع را به <code>full_date</code> بازنویسی می‌کند.",
            "<code>fix_sqlite_date_modifiers</code> عبارت نامعتبر SQLite «first/last day of month» را به «start of month» معتبر تبدیل می‌کند.",
            "<code>fix_status_literals</code> بزرگی/کوچکی حروف رایج غلط (Active/Inactive) را نرمال می‌کند.",
            "<code>strip_unrequested_limit</code> فقط وقتی کاربر عدد مشخصی نخواسته (فارسی یا انگلیسی)، LIMIT اضافه‌شدهٔ مدل را حذف می‌کند.",
            "<code>validate_select_only</code> دروازهٔ نهایی است: فقط یک SELECT/WITH بدون semicolon میانی، بدون کلیدواژهٔ مخرب (DROP/DELETE/UPDATE/...) و LIMIT حداکثر ۱۰۰هزار.",
        ],
        [
            ("fix_date_key_sql", "بازنویسی تاریخ عددی به join با dim_date."),
            ("fix_sqlite_date_modifiers / fix_status_literals", "دو اصلاح متنی هدفمند دیگر."),
            ("normalize_generated_sql", "اجرای زنجیرهٔ هر سه اصلاح روی یک SQL."),
            ("user_requested_row_limit / strip_unrequested_limit", "تشخیص درخواست تعداد مشخص و حذف LIMIT ناخواسته."),
            ("validate_select_only", "دروازهٔ نهایی SQL خواندنی؛ در صورت رد شدن UnsafeSQLError می‌دهد."),
        ],
    ),
    file_block(
        "ollama_client.py",
        "کلاینت HTTP مدل محلی Ollama با قرارداد عمومی مشترک با avalai_client.py.",
        [
            "به <code>127.0.0.1:11434</code> متصل می‌شود و <code>trust_env=False</code> باعث می‌شود proxy سیستم در Windows در اتصال loopback دخالت نکند.",
            "خروجی SQL باید JSON با کلیدهای <code>sql</code> و <code>explanation</code> باشد؛ زنجیرهٔ <code>_extract_json</code> خروجی خام مدل (fence مارک‌داون، quote تکی، comma پایانی، newline خام داخل رشته) را تحمل می‌کند.",
            "<code>fix_sql</code> (تازه) تابع سوم قرارداد است: SQL شکست‌خورده + متن دقیق خطای دیتابیس را می‌گیرد و همان قرارداد JSON اصلاح‌شده را برمی‌گرداند — برای حلقهٔ خوداصلاحی در app.py.",
            "تولید تحلیل متن آزاد با temperature بالاتر (۰.۲) و زبان فارسی/انگلیسی قابل انتخاب انجام می‌شود.",
        ],
        [
            ("_post", "فراخوانی /api/generate و تبدیل خطاهای شبکه به OllamaError."),
            ("_escape_literal_control_chars_in_strings", "تعمیر newline/tab غیرمجاز داخل رشتهٔ JSON مدل."),
            ("_try_parse / _extract_json", "زنجیرهٔ استخراج مقاوم JSON از خروجی خام."),
            ("generate_sql", "ساخت prompt دقیق SQLite (قواعد تاریخ/وضعیت) و بازگرداندن dict."),
            ("_fix_sql_prompt / fix_sql", "ساخت prompt اصلاح خطا و فراخوانی مدل برای SQL تصحیح‌شده (تازه)."),
            ("generate_analysis / generate_discussion", "تحلیل نمونهٔ داده و بحث چندنوبتی."),
        ],
    ),
    file_block(
        "avalai_client.py",
        "کلاینت API سازگار با OpenAI برای AvalAI، با همان interface سه‌تابعی ماژول Ollama.",
        [
            "مدل از <code>AVALAI_MODEL</code> (پیش‌فرض gpt-4o-mini) و کلید از <code>AVALAI_API_KEY</code> خوانده می‌شود.",
            "<strong>نکتهٔ امنیتی:</strong> مقدار پیش‌فرض <code>AVALAI_API_KEY</code> یک کلید واقعی‌نما مستقیم در سورس است (در این سند بازنشر نشده). باید فوراً revoke/rotate و default خالی شود.",
            "<code>fix_sql</code> (تازه) از همان <code>_fix_sql_prompt</code> مشترک با ollama_client.py استفاده می‌کند تا رفتار دو provider در حلقهٔ خوداصلاحی یکسان بماند.",
            "<code>check_credit</code> به endpoint حساب AvalAI متصل می‌شود؛ کلید هرگز مستقیماً به مرورگر ارسال نمی‌شود (پروکسی از طریق app.py).",
        ],
        [
            ("_chat", "فراخوانی chat/completions و مدیریت خطاهای Connection/Timeout/HTTP/Format."),
            ("check_credit", "دریافت اعتبار حساب از سمت سرور."),
            ("generate_sql / generate_analysis / generate_discussion", "سه تابع اصلی، هم‌قرارداد با Ollama."),
            ("fix_sql", "اصلاح SQL شکست‌خورده با AvalAI (تازه)."),
        ],
    ),
    file_block(
        "analysis_prompt.py",
        "قواعد سیستمی و سازندهٔ prompt مشترک بین دو provider برای تحلیل و بحث — تنها یک‌بار نوشته و در هر دو کلاینت import می‌شود.",
        [
            "قواعد صحت (accuracy rules) صریحاً از «روند نزولی مداوم» ادعاکردن جلوگیری می‌کند مگر واقعاً هر دورهٔ پیاپی کمتر از قبلی باشد.",
            "برای بحث/چالش، در صورت اصلاح یک بخش مشخص، مدل باید پاسخ را با بلوک <code>CORRECTED_SNIPPET:</code> ببندد تا فرانت‌اند بتواند جایگزینی خودکار انجام دهد.",
        ],
        [
            ("ANALYSIS_SYSTEM_RULES / DISCUSSION_SYSTEM_RULES", "دو رشتهٔ ثابت قوانین سیستمی."),
            ("build_analysis_prompt", "ترکیب داده و سؤال برای تحلیل."),
            ("build_discussion_prompt", "ترکیب تحلیل فعلی، تمرکز کاربر و تاریخچهٔ بحث."),
        ],
    ),
    file_block(
        "column_labels.py",
        "نگاشت نام ستون‌های انگلیسی دیتابیس/SQL به عنوان فارسی خوانا؛ فقط برای نمایش UI و هدر خروجی‌ها — خود دیتابیس انگلیسی می‌ماند.",
        [
            "یک دیکشنری دقیق (<code>COLUMN_LABELS</code>) برای نام‌های شناخته‌شده و یک نگاشت کلمه‌به‌کلمه (<code>_WORD_FA</code>) برای snake_case/camelCase ناشناخته دارد.",
            "اگر ستون از قبل فارسی باشد (یا شامل نیم‌فاصله باشد) بدون تغییر برگردانده می‌شود.",
            "هم در جدول/نمودار static/script.js (از طریق منطق مشابه سمت کلاینت) و هم در pdf_generator.py و excel_generator.py استفاده می‌شود.",
        ],
        [
            ("column_label(key)", "تابع اصلی نگاشت؛ دقیق → کلمه‌به‌کلمه → بازگشت به متن اصلی."),
            ("is_rtl_text", "تشخیص متن فارسی/عربی برای تصمیم جهت."),
        ],
    ),
    file_block(
        "pdf_generator.py",
        "خروجی PDF فارسی/راست‌به‌چپ برای نتیجهٔ گفتگو، با کلاس <code>PDFGenerator</code> مبتنی بر fpdf2 و شکل‌دهی متن HarfBuzz.",
        [
            "<code>_resolve_unicode_font</code> اولین فونت یونیکد موجود را از میان Vazirmatn، Tahoma، Segoe UI، Arial یا Noto Sans Arabic انتخاب می‌کند؛ در نبود هیچ‌کدام خطا می‌دهد.",
            "<code>normalize_persian_pdf_text</code> نیم‌فاصله (ZWNJ) را با یک فاصلهٔ نازک جایگزین می‌کند چون fpdf2+HarfBuzz آن را حذف و حروف را می‌چسباند.",
            "<code>set_text_shaping(True)</code> فعال است تا حروف فارسی به‌درستی به هم متصل شوند (چیزی که بدون HarfBuzz در PDF کار نمی‌کند).",
            "جهت هر سلول به‌صورت پویا بر اساس RTL بودن متن آن سلول تعیین می‌شود، نه یک تنظیم سراسری ثابت.",
            "صفحه شامل نوار عنوان، توضیح، تصویر نمودار (در صورت وجود)، جدول داده (حداکثر ۸۰ ردیف با یادداشت برش) و تحلیل است؛ هدر/فوتر تکرارشونده از طریق override متدهای <code>header/footer</code> پیاده شده.",
        ],
        [
            ("PDFGenerator", "زیرکلاس FPDF با هدر/فوتر برندشده و متد section_title."),
            ("_resolve_unicode_font", "انتخاب فونت یونیکد در دسترس سیستم."),
            ("normalize_persian_pdf_text", "رفع مشکل حذف نیم‌فاصله در رندر."),
            ("format_number", "قالب‌بندی عدد با جداکنندهٔ هزارگان قابل تنظیم."),
            ("generate_llm_pdf", "تابع ورودی اصلی: عنوان، توضیح، داده، تحلیل، تصویر نمودار → فایل PDF."),
        ],
    ),
    file_block(
        "excel_generator.py",
        "خروجی اکسل سه‌شیتی (Data / Explanation / Analysis) با استایل‌دهی openpyxl.",
        [
            "شیت Data شامل هدر رنگی، فریز ردیف اول، فیلتر خودکار، رنگ‌آمیزی ردیف زوج و راست‌چین‌کردن خودکار متن فارسی است.",
            "اعداد رشته‌ای (با کاما/سمی‌کالن) قبل از نوشتن به نوع عددی واقعی اکسل تبدیل می‌شوند تا SUM/فیلتر عددی در اکسل درست کار کند.",
            "پهنای ستون‌ها با <code>_autosize</code> بر اساس طولانی‌ترین مقدار هر ستون تنظیم می‌شود.",
        ],
        [
            ("generate_llm_excel", "ورودی اصلی: سه شیت را می‌سازد و فایل را ذخیره می‌کند."),
            ("_is_number / _to_number", "تشخیص و تبدیل مقدار متنی به عدد واقعی."),
            ("_autosize", "تنظیم خودکار عرض ستون."),
        ],
    ),
    file_block(
        "passenger_wsgi.py",
        "نقطهٔ ورود میزبانی cPanel/Phusion Passenger؛ مسیر استقرار جایگزین Dockerfile.",
        [
            "دایرکتوری برنامه را به <code>sys.path</code> اضافه می‌کند تا import های نسبی کار کنند.",
            "چون FastAPI اپلیکیشن ASGI است ولی Passenger انتظار WSGI دارد، <code>a2wsgi.ASGIMiddleware</code> پل بین این دو را می‌زند.",
        ],
        [("application", "شیء entry point مورد انتظار Passenger.")],
    ),
]


# ---------------------------------------------------------------------------
# Frontend files
# ---------------------------------------------------------------------------
frontend_files = [
    file_block(
        "static/first.html",
        "صفحهٔ عمومی معرفی Rayamate که مسیر ریشهٔ سایت (<code>GET /</code>) آن را نمایش می‌دهد.",
        [
            "Tailwind از CDN، آیکون Iconify و فونت Vazirmatn از گوگل بارگذاری می‌شود؛ CSS تکمیلی inline است.",
            "بخش‌های hero، آمار متحرک، نمایش محصول، قابلیت‌ها، CTA و فوتر شامل لینک شبکه‌های اجتماعی دارد؛ لینک لینکدین به آدرس رسمی صفحهٔ شرکت (linkedin.com/company/rayamate) تنظیم شده است.",
            "Canvas ذرات متحرک و خطوط ارتباطی پس‌زمینه، شمارندهٔ آماری با IntersectionObserver و افکت tilt کارت‌ها با جاوااسکریپت inline پیاده‌سازی شده‌اند.",
        ],
    ),
    file_block(
        "static/login.html",
        "صفحهٔ ورود راست‌به‌چپ با تم سبز Rayamate، CSS کامل inline و اتصال به login.js.",
        [
            "طرح دو ستونه (معرفی محصول + فرم ورود)؛ در موبایل تک‌ستونه می‌شود.",
            "ورودی نام کاربری، رمز، «مرا به خاطر بسپار»، چک‌باکس «من ربات نیستم» (کپچای نمایشی، نه واقعی)، دکمهٔ نمایش/پنهان رمز و ناحیهٔ پیام خطا دارد.",
        ],
    ),
    file_block(
        "static/login.js",
        "کنترل رفتار فرم ورود در مرورگر.",
        [
            "فقط username را (در صورت فعال بودن «مرا به خاطر بسپار») در localStorage نگه می‌دارد و هرگز password را ذخیره نمی‌کند.",
            "قبل از ارسال، خالی نبودن فیلدها و تیک‌خوردن چک‌باکس کپچا را بررسی می‌کند.",
            "درخواست JSON به <code>/api/login</code> می‌فرستد و پس از موفقیت به <code>/app</code> هدایت می‌شود؛ دکمه‌های «بازیابی رمز» و «ورود سازمانی» فعلاً فقط پیام «به‌زودی» نشان می‌دهند.",
        ],
        [
            ("submit handler", "اعتبارسنجی فرم، غیرفعال‌سازی موقت دکمه، مدیریت پاسخ/خطا."),
            ("toggle password handler", "تغییر type بین password و text."),
            ("showError", "نمایش پیام خطای فارسی."),
        ],
    ),
    file_block(
        "static/index.html",
        "پوستهٔ داشبورد احراز‌شده؛ فایل واقعی سرو‌شده روی مسیر <code>/app</code>.",
        [
            "هدر شامل عنوان، دکمهٔ تعویض زبان، لینک مدیریت کاربران (فقط برای admin) و دکمهٔ خروج است.",
            "ستون گفتگو شامل پیام خوش‌آمد، ناحیهٔ چت، ورودی متن و دکمه‌های صدا/PDF/Excel/ارسال است.",
            "نوار کناری (sidebar) اکنون پنج کارت دارد: «تاریخچهٔ گفتگو» (قابل کلیک برای بازپخش کامل)، «۱۰ سؤال پرتکرار» (تازه — سراسر کاربران)، «اقدامات سریع»، «تنظیمات» و «نظرسنجی قابلیت‌های آینده»؛ عرض نوار کناری با drag قابل تغییر و قابل جمع‌شدن است.",
            "Chart.js محلی (vendored) و static/script.js در پایان صفحه بارگذاری می‌شوند.",
        ],
    ),
    file_block(
        "static/script.js",
        "منطق کامل کلاینت داشبورد؛ بدون هیچ فریم‌ورک، مبتنی بر DOM API خام (بزرگ‌ترین فایل پروژه).",
        [
            "در startup از <code>/api/preferences</code> و <code>/api/me</code> ترجیحات و نقش کاربر را می‌خواند، تاریخچه و سؤالات پرتکرار را بارگذاری می‌کند.",
            "هر «نوبت» گفتگو (turn) از یک SQL قابل‌ویرایش، سپس نتایج (اکنون در کارت‌های رنگی مجزا) تشکیل می‌شود: کارت SQL (آبی)، کارت جدول (سبز)، کارت نمودار (بنفش)، کارت تحلیل (گرادیان سبز/نارنجی موجود قبلی)، کارت بحث (کهربایی، اکنون به‌صورت آکاردئون جمع‌شونده) و کارت بازخورد (خاکستری).",
            "کلیک روی یک آیتم تاریخچه اکنون کل نوبت قدیمی را «بازپخش» می‌کند (سؤال، SQL، جدول، نمودار، تحلیل، وضعیت بازخورد قبلی) به‌جای فقط پرکردن کادر ورودی؛ برای پیام‌های قدیمی‌تر که داده ذخیره‌شده ندارند، پیام راهنما نشان داده می‌شود.",
            "برای نمودار، ستون عددی/برچسب هوشمند انتخاب می‌شود و انواع bar/barHorizontal/line/pie/doughnut پشتیبانی می‌شوند؛ تعویض نوع نمودار اکنون از یک تابع واحد <code>rebuildChart</code> عبور می‌کند (پیش‌تر سه بلوک کد تکراری بود که باعث باگ سوییچ‌نکردن نمودار می‌شد).",
            "یک دکمهٔ «چاپ نمودار» (تازه) نمودار جاری را به PNG تبدیل و در یک iframe مخفی برای چاپ/ذخیرهٔ PDF باز می‌کند.",
            "تحلیل مدل escape و سپس heading/list/عددها به HTML کنترل‌شده تبدیل می‌شود تا XSS ممکن نباشد.",
        ],
        [
            ("state", "شیء وضعیت سراسری: زبان، provider، آخرین پاسخ، آخرین نمودار."),
            ("apiFetch / logout / savePreferences", "ارتباط session-aware با backend."),
            ("loadHistorySidebar / replayHistoryEntry", "نمایش تاریخچه و بازپخش کامل یک نوبت قدیمی (تازه)."),
            ("loadFrequentQuestions", "بارگذاری و نمایش ۱۰ سؤال پرتکرار سراسری (تازه)."),
            ("sendMessage / renderSqlDraft / renderRunResults", "چرخهٔ کامل هر نوبت گفتگو، اکنون در کارت‌های مجزا."),
            ("wireSqlRunner", "اجرای SQL، نمایش نتیجه یا خطا، و یادداشت «اصلاح خودکار» در صورت auto_fixed (تازه)."),
            ("prepareChartRows / createChartInstance / rebuildChart", "ساخت و تعویض ایمن نمودار Chart.js (بازنگری‌شده)."),
            ("printChartAsImage", "خروجی چاپی نمودار به‌صورت تصویر (تازه)."),
            ("wireDiscussPanel", "منطق بحث چندنوبتی + تاگل باز/بسته‌شدن آکاردئون (تازه)."),
            ("mountPaginatedTable / buildTableHtml", "ساخت امن و صفحه‌بندی جدول نتایج."),
            ("escapeHtml / formatAnalysisHtml / isRtlText", "ایمنی خروجی و پشتیبانی دوجهته."),
        ],
    ),
    file_block(
        "static/style.css",
        "سامانهٔ طراحی مشترک داشبورد و صفحهٔ کاربران؛ الهام از فیش تسویهٔ POS (ledger/receipt).",
        [
            "متغیرهای رنگ، کاغذ، accent، danger، فونت sans/mono/RTL را در <code>:root</code> تعریف می‌کند.",
            "هر «نوبت» گفتگو اکنون از چند کارت رنگی مجزا (به‌جای یک نوار پیوسته با خط‌چین) تشکیل شده: هر بخش (<code>.sql-draft-section</code>، <code>.table-section</code>، <code>.chart-section</code>، <code>.discuss-section</code>، <code>.feedback-section</code>) یک نوار رنگی بالای خودش دارد که با متغیر <code>--section-accent</code> تعیین می‌شود.",
            "بخش «بحث و بررسی» اکنون آکاردئون است: <code>.discuss-body</code> با کلاس <code>is-open</code> روی <code>.discuss-section</code> کنترل می‌شود.",
            "استایل جدول pagination، نمودار، تحلیل، نوار زمان‌بندی، حالت loading و breakpointهای واکنش‌گرا را نیز دارد.",
        ],
    ),
    file_block(
        "static/users.html",
        "صفحهٔ CRUD کاربران، فقط برای نقش مدیر.",
        [
            "استایل اختصاصی صفحه inline است و style.css مشترک جداگانه بارگذاری می‌شود.",
            "جدول کاربران، حالت خالی، پیام عملیات و modal افزودن/ویرایش دارد؛ فرم شامل نام نمایشی، username، موبایل، password، role و وضعیت فعال است.",
        ],
    ),
    file_block(
        "static/users.js",
        "اتصال UI مدیریت کاربران به APIهای admin در app.py.",
        [
            "wrapper مشترک <code>api()</code> پاسخ 401 را به /login و پاسخ 403 را به /app هدایت می‌کند.",
            "در ساخت کاربر جدید رمز الزامی است؛ در ویرایش اختیاری (خالی = بدون تغییر رمز).",
            "پیش از بارگذاری فهرست کاربران، ابتدا <code>/api/me</code> نقش را کنترل می‌کند تا غیرمدیر به /app هدایت شود.",
        ],
        [
            ("api", "fetch با تبدیل پاسخ خطا/401/403 به رفتار مناسب."),
            ("openModal / closeModal", "حالت create/edit فرم."),
            ("renderUsers / loadUsers", "رندر جدول و دریافت فهرست."),
            ("removeUser", "تأیید و درخواست DELETE."),
        ],
    ),
    file_block(
        "static/vendor/chart.umd.min.js",
        "نسخهٔ minified و vendored کتابخانهٔ Chart.js v4 برای رسم نمودار بدون وابستگی runtime به CDN.",
        [
            "کد third-party تولیدشده است؛ نگهداری دستی آن توصیه نمی‌شود.",
            "از طریق global به نام <code>Chart</code> در static/script.js مصرف می‌شود.",
        ],
    ),
]


# ---------------------------------------------------------------------------
# Support / config / tooling / legacy files
# ---------------------------------------------------------------------------
support_files = [
    file_block(
        "Dockerfile",
        "ساخت image سبک Python 3.11 برای اجرا در container یا Hugging Face Spaces.",
        [
            "dependencyها پیش از COPY کل پروژه نصب می‌شوند تا cache لایه‌ها بهتر استفاده شود.",
            "پورت ۷۸۶۰ expose می‌شود؛ در startup اگر فایل DB وجود نداشته باشد db_mock.py اجرا و سپس Uvicorn بالا می‌آید.",
        ],
    ),
    file_block(
        "requirements.txt",
        "فهرست dependency‌های runtime پایتون.",
        [
            "FastAPI/Uvicorn برای وب، SQLAlchemy/Pandas برای داده، Requests برای دو کلاینت مدل، python-multipart/itsdangerous برای session، a2wsgi برای Passenger، fpdf2/uharfbuzz برای PDF فارسی و openpyxl برای اکسل.",
            "برخی packageها pin نشده‌اند (مثل pandas و requests)؛ برای build تکرارپذیر بهتر است نسخه ثابت شود.",
        ],
    ),
    file_block(
        "README.md",
        "راهنمای اولیهٔ پروژه؛ اکنون با کد فعلی به‌روز نیست.",
        [
            "همچنان معماری access_key/dim_customer و endpointهایی مثل <code>/api/customers</code> را توصیف می‌کند، در حالی که برنامهٔ فعلی احراز هویت session-based با جدول app_users و مجموعهٔ endpoint متفاوتی دارد.",
            "بخش‌های نصب Ollama، ساخت DB و اجرای Uvicorn همچنان درست و مفیدند.",
        ],
    ),
    file_block(
        ".gitignore",
        "حذف فایل‌های پایتون، محیط مجازی، DB/history/env، آرشیو و تنظیمات IDE از Git.",
        [
            "به‌درستی <code>.env</code>، <code>*.db</code>، <code>history.json</code> و <code>feedback.json</code> را نادیده می‌گیرد.",
            "الگوی <code>* copy.py</code> باعث نادیده‌گرفتن فایل‌های پشتیبان دستی مثل <code>ollama_client copy.py</code> می‌شود؛ کلید/رمز نوشته‌شده مستقیم در سورس (مثل avalai_client.py) با gitignore محافظت نمی‌شود.",
        ],
    ),
    file_block(
        "feature_poll.json",
        "فایل دادهٔ ساده (نه کد) که آرای نظرسنجی قابلیت‌های آینده را نگه می‌دارد؛ توسط app.py خوانده/نوشته می‌شود.",
        ["ساختار: <code>{\"votes\": {username: [option_id, ...]}}</code>؛ گزینه‌های سفارشی با پیشوند <code>_custom_</code> ذخیره می‌شوند."],
    ),
    file_block(
        "create_presentation.py",
        "اسکریپت مستقل ساخت ارائهٔ فارسی PowerPoint دربارهٔ پروژه (ابزار مستندسازی، نه بخشی از اپلیکیشن).",
        [
            "با python-pptx شکل‌ها، متن‌باکس‌ها، بولت‌ها و اسلایدهای فارسی راست‌به‌چپ می‌سازد.",
            "dependency python-pptx در requirements.txt نیست؛ برای بازتولید ارائه باید جداگانه نصب شود.",
        ],
    ),
    file_block(
        "generate_newDashboard2_slides.py",
        "نسخهٔ قبلی اسکریپت ساخت ارائه، مخصوص یک برنچ قدیمی‌تر (newDashboard2)؛ ابزار مستندسازی است، بخشی از اپلیکیشن نیست.",
        ["امروز جایگزین بهتری برای این اسکریپت لازم نیست؛ فقط برای بازتولید تاریخی نگه داشته شده."],
    ),
    file_block(
        "generate_newDashboard2_docs.py",
        "مولد HTML/PDF مستندات فنی فارسی برای برنچ قدیمی newDashboard2 (با <code>git show</code> از یک commit خاص)؛ الگوی طراحی همین سند از آن اقتباس شده است.",
        [
            "خروجی‌های آن (<code>newDashboard2_code_documentation_fa.html/.pdf</code>) در Git باقی مانده‌اند؛ محتوایشان مربوط به وضعیت قدیمی‌تر کد است، نه نسخهٔ فعلی.",
            "این سند («bichart_project_documentation_fa.pdf») بر خلاف آن، مستقیماً از working tree فعلی (شامل تغییرات ثبت‌نشده) ساخته می‌شود، نه از یک commit گیت.",
        ],
    ),
    file_block(
        "index.html",
        "نسخهٔ قدیمی/مرجع پوستهٔ گفتگو در ریشهٔ repository — FastAPI این فایل را سرو نمی‌کند.",
        ["مسیر فعال به <code>static/index.html</code> اشاره دارد؛ این فایل احتمالاً باقی‌ماندهٔ طراحی قبلی است."],
    ),
    file_block(
        "script.js",
        "جاوااسکریپت قدیمی رابط access_key در ریشه؛ در صفحات فعال بارگذاری نمی‌شود.",
        ["DOMهایی مثل login-gate و APIهایی مثل /api/customers را انتظار دارد که با app.py فعلی هماهنگ نیستند."],
    ),
    file_block(
        "style.css",
        "CSS قدیمی رابط تک‌ستونه در ریشه؛ توسط FastAPI mount نشده و صفحات فعال آن را نمی‌خوانند.",
        ["توکن‌های هویت بصری اولیه و login-gate قدیمی را نگه می‌دارد."],
    ),
]


legacy_note = """
<div class="callout">
<strong>فایل‌های اضافی/موقتی که در working tree هستند ولی توسط اپلیکیشن استفاده نمی‌شوند:</strong>
<ul>
<li><code>ollama_client copy.py</code> — نسخهٔ پشتیبان دستی، توسط .gitignore نادیده گرفته می‌شود و هیچ‌جا import نشده است.</li>
<li><code>change_logo_color.py</code> و <code>test_pdf.py</code> — اسکریپت‌های یک‌بارمصرف توسعه (تغییر رنگ لوگو با Pillow، تست دستی pdf_generator.py)؛ بخشی از مسیر اجرای برنامه نیستند.</li>
<li>~۹۰ فایل <code>report*.pdf/.xlsx</code>، <code>test_font_*.pdf</code> و مشابه در ریشهٔ پروژه — خروجی‌های تولیدشده هنگام آزمایش export_pdf/export_excel و انتخاب فونت؛ می‌توانند با خیال راحت حذف شوند.</li>
<li><code>Rayamate_Presentation.pptx</code> و <code>newDashboard2_code_documentation_fa.html/.pdf</code> — خروجی‌های ابزارهای بالا، نه سورس کد.</li>
</ul>
</div>
"""


# ---------------------------------------------------------------------------
# What changed in this working session
# ---------------------------------------------------------------------------
recent_changes = """
<div class="change-grid">
  <div class="change">
    <h3>۱ · پنل سؤالات پرتکرار سراسری</h3>
    <p><code>MemoryManager.get_frequent_questions</code> + مسیر <code>GET /api/frequent-questions</code> + کارت جدید در sidebar.
    سؤالات میان همهٔ کاربران شمارش و ۱۰ مورد برتر (بر اساس تکرار، سپس تازگی) نمایش داده می‌شود؛ کلیک روی هرکدام همان لحظه پرسیده می‌شود.</p>
  </div>
  <div class="change">
    <h3>۲ · بازپخش کامل تاریخچه</h3>
    <p><code>run_sql</code> اکنون نمونهٔ واقعی ردیف‌های نتیجه را نیز در history.json ذخیره می‌کند (<code>HISTORY_DATA_CAP=500</code>).
    کلیک روی یک آیتم تاریخچه، سؤال/SQL/جدول/نمودار/تحلیل/وضعیت بازخورد همان نوبت قدیمی را دوباره می‌سازد.</p>
  </div>
  <div class="change">
    <h3>۳ · بازنگری نمودارها + چاپ</h3>
    <p>باگ اصلی: سه select در چارت همگی کلاس <code>chart-type-select</code> داشتند و <code>querySelector</code> عنصر اشتباه (ستون برچسب) را
    به‌جای منوی نوع نمودار انتخاب می‌کرد — با کلاس یکتای <code>chart-kind-select</code> رفع شد. علاوه‌بر آن: مقدار نادرست tooltip در حالت افقی،
    نمایش نادرست نمودار دایره‌ای با مقادیر منفی، و نبود به‌روزرسانی یادداشت «نمایش N از M» پس از تعویض ستون اصلاح شدند؛ نوع پیش‌فرض همیشه ستونی
    (عمودی) شد و دکمهٔ «چاپ نمودار» (خروجی PNG در پنجرهٔ چاپ) اضافه شد.</p>
  </div>
  <div class="change">
    <h3>۴ · بازطراحی کارت‌های نتیجه + آکاردئون بحث</h3>
    <p>هر بخش (SQL، جدول، نمودار، تحلیل، بحث، بازخورد) اکنون یک کارت رنگی مجزا با نوار رنگی بالا (<code>--section-accent</code>) است، نه یک
    نوار خط‌چین پیوسته. بخش «بحث و بررسی» به یک آکاردئون جمع‌شونده تبدیل شد.</p>
  </div>
  <div class="change">
    <h3>۵ · حلقهٔ خوداصلاحی اجرای SQL</h3>
    <p>تابع تازهٔ <code>fix_sql</code> در هر دو کلاینت مدل (با prompt مشترک <code>_fix_sql_prompt</code>) و منطق تازه در <code>run_sql</code>:
    اگر اجرای SQL خطا بدهد، خطای واقعی دیتابیس یک‌بار به مدل بازخورد داده می‌شود تا SQL را اصلاح کند و دوباره اجرا شود؛ در صورت موفقیت پرچم
    <code>auto_fixed</code> برگردانده و یک یادداشت سبز به کاربر نشان داده می‌شود.</p>
  </div>
  <div class="change">
    <h3>۶ · اصلاح لینک لینکدین</h3>
    <p>لینک نمادِ لینکدین در فوتر <code>static/first.html</code> که placeholder بود، به آدرس واقعی صفحهٔ شرکت اصلاح شد.</p>
  </div>
</div>
"""


security_body = """
<div class="risk-grid">
  <div class="risk high"><h3>بحرانی — کلید API در سورس</h3><p>در avalai_client.py برای AvalAI یک مقدار پیش‌فرض واقعی‌نما مستقیم در کد وجود دارد (در این سند بازنشر نشده). باید فوراً revoke/rotate شود و فقط از environment/secret manager خوانده شود؛ مقدار پیش‌فرض باید خالی باشد.</p></div>
  <div class="risk high"><h3>بالا — credentialهای پیش‌فرض</h3><p>نام کاربری/گذرواژهٔ مدیر bootstrap (users.py) و SESSION_SECRET (auth.py) مقدار پیش‌فرض ثابت دارند. در production باید بدون environment امن، startup fail شود.</p></div>
  <div class="risk med"><h3>متوسط — کپچای نمایشی</h3><p>کپچا فقط یک boolean ارسالی از مرورگر است، نه اثبات ضدربات واقعی. برای دسترسی عمومی باید سرویس captcha واقعی و rate limiting اضافه شود.</p></div>
  <div class="risk med"><h3>متوسط — CSRF و rate limit</h3><p>عملیات POST/PUT/DELETE توکن ضد-CSRF ندارند و هیچ محدودیت نرخ درخواستی روی /api/chat یا /api/run_sql وجود ندارد، در حالی که این مسیرها به مصرف پولی AvalAI منجر می‌شوند.</p></div>
  <div class="risk med"><h3>متوسط — اعتبارسنجی SQL بر پایهٔ regex</h3><p>sql_safety.py برای نمونهٔ اولیه مناسب است ولی parser کامل SQL نیست؛ اجازهٔ WITH/SELECT، نبود timeout یا محدودیت هزینهٔ query، و امکان کوئری سنگین باقی می‌ماند. کاربر DB باید read-only باشد.</p></div>
  <div class="risk med"><h3>متوسط — نبود row-level scope واقعی</h3><p>SCHEMA_DESCRIPTION مدل را راهنمایی می‌کند اما هیچ محدودیت اجباری در لایهٔ SQL برای محدودکردن نتیجه به مشتری/پذیرندهٔ مشخص کاربر وجود ندارد؛ app_users هم به dim_customer متصل نیست.</p></div>
  <div class="risk low"><h3>پایین — persistence تک‌پردازه‌ای</h3><p>قفل MemoryManager فقط داخل یک process معتبر است؛ چند worker می‌توانند history.json را هم‌زمان بازنویسی کنند.</p></div>
  <div class="risk low"><h3>پایین — dependency بدون pin و CDN</h3><p>برخی packageها نسخهٔ ثابت ندارند و first.html/login.html به Tailwind/فونت CDN وابسته‌اند؛ برای شبکهٔ بسته باید asset محلی شود.</p></div>
</div>
"""

run_body = """
<ol class="steps">
  <li><strong>محیط:</strong> Python 3.11 و virtualenv بسازید؛ سپس <code>pip install -r requirements.txt</code>.</li>
  <li><strong>تنظیم secrets:</strong> حداقل <code>SESSION_SECRET</code>، <code>AUTH_USERNAME</code>، <code>AUTH_PASSWORD</code> و در صورت استفاده از AvalAI مقدار <code>AVALAI_API_KEY</code> را در محیط امن قرار دهید (نه در سورس).</li>
  <li><strong>مدل محلی (اختیاری):</strong> برای Ollama مدل تنظیم‌شده در <code>MODEL_NAME</code> (ollama_client.py) را pull و <code>ollama serve</code> را اجرا کنید.</li>
  <li><strong>داده mock:</strong> یک‌بار <code>python db_mock.py</code> — توجه: اجرای مجدد دیتابیس را بازسازی می‌کند.</li>
  <li><strong>اجرا:</strong> <code>uvicorn app:app --host 0.0.0.0 --port 8000</code> سپس بازکردن مسیر ریشه در مرورگر.</li>
  <li><strong>استقرار:</strong> Dockerfile برای container/Hugging Face Spaces و passenger_wsgi.py برای cPanel دو مسیر مستقل استقرارند.</li>
</ol>
"""


# ---------------------------------------------------------------------------
# Full inventory (all files currently on disk, honoring a light exclude list)
# ---------------------------------------------------------------------------
EXCLUDE_DIR_NAMES = {".git", "__pycache__", "node_modules", "venv", ".venv"}
EXCLUDE_EXTS = {".pyc"}

inventory_rows = []
all_paths = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR_NAMES]
    for fn in filenames:
        full = Path(dirpath) / fn
        rel = full.relative_to(ROOT).as_posix()
        if full.suffix in EXCLUDE_EXTS:
            continue
        if rel in (HTML_OUT.name, PDF_OUT.name):
            continue
        all_paths.append(rel)
all_paths.sort()

for index, relpath in enumerate(all_paths, start=1):
    raw = read_file(relpath)
    if raw is None:
        continue
    try:
        count = f"{len(raw.decode('utf-8').splitlines()):,} خط"
    except UnicodeDecodeError:
        count = f"{len(raw):,} بایت"
    inventory_rows.append([str(index), f"<code>{esc(relpath)}</code>", count])


# ---------------------------------------------------------------------------
# Assemble document
# ---------------------------------------------------------------------------
body = f"""
<section class="cover page">
  <div class="cover-mark">RAYAMATE · BICHART · CODE DOCUMENTATION</div>
  <h1>مستند فنی کامل پروژه<br><span dir="ltr">bichart</span></h1>
  <p class="lead">معماری، جریان اجرا، APIها، مدل داده، تمام فایل‌های موجود در پروژه و منطق کدهای اصلی — به فارسی</p>
  <div class="meta">
    <div><span>برنچ فعلی</span><code dir="ltr">{esc(git_branch)}</code></div>
    <div><span>تعداد فایل‌های بررسی‌شده</span><b>{len(inventory_rows)} فایل</b></div>
    <div><span>تولید سند</span><b dir="ltr">{esc(generated_at)}</b></div>
    <div><span>تغییرات ثبت‌نشدهٔ Git</span><b>{esc(uncommitted_count) if uncommitted_count is not None else 'نامشخص'} مورد</b></div>
  </div>
  <p class="scope">این سند مستقیماً از فایل‌های working tree خوانده شده است (نه از یک commit گیت خاص)، پس شامل تمام تغییرات همین نشست کاری هم می‌شود.
  مقادیر secret عمداً در سند بازنشر نشده‌اند.</p>
</section>

{page("خلاصهٔ سامانه", architecture + bullets([
    "<strong>هدف:</strong> پرسش فارسی/انگلیسی دربارهٔ تراکنش‌های پرداخت، تبدیل به SQL و نمایش جدول/نمودار/تحلیل.",
    "<strong>Backend:</strong> FastAPI، Pydantic، SQLAlchemy و Pandas.",
    "<strong>مدل زبانی:</strong> AvalAI (ابری، پیش‌فرض) یا Ollama (محلی) با interface یکسان generate_sql/generate_analysis/generate_discussion/fix_sql.",
    "<strong>Frontend:</strong> HTML/CSS/JavaScript خالص (بدون framework) و Chart.js.",
    "<strong>هویت:</strong> session امضاشده، حساب app_users و نقش admin/user.",
    "<strong>داده:</strong> star schema آزمایشی PSP روی SQLite با قابلیت تغییر DATABASE_URL به DB2/SQL Server/PostgreSQL.",
]), "۱ · نمای کلان")}

{page("قابلیت‌های تازهٔ این نشست کاری", recent_changes, "۲ · تازه‌ترین تغییرات")}

{page("مسیرهای HTTP و سطح دسترسی", table(["مسیر", "دسترسی", "وظیفه"], route_rows, ltr_first=True), "۳ · API")}

{page("مدل داده", table(["جدول", "نقش", "ستون‌ها/رابطه‌های مهم"], schema_rows, ltr_first=True) + """
<div class="callout">
<strong>قاعدهٔ حیاتی تاریخ:</strong> <code>fact_transactions.date_key</code> یک عدد YYYYMMDD است؛ برای هر فیلتر تقویمی باید
<code>dim_date</code> جوین شود و از <code>full_date</code> استفاده گردد. هم prompt مدل (SCHEMA_DESCRIPTION در app.py) و هم
sql_safety.py این قاعده را تقویت/تعمیر می‌کنند.
</div>
""", "۴ · پایگاه داده")}

{page("فایل‌های Backend (پایتون)", "".join(backend_files), "۵ · Python")}
{page("فایل‌های Frontend (HTML/CSS/JavaScript)", "".join(frontend_files), "۶ · رابط کاربری")}
{page("فایل‌های پیکربندی، مستندسازی و legacy", "".join(support_files) + legacy_note, "۷ · سایر فایل‌ها")}

{page("جریان‌های اجرایی مهم", """
<div class="sequence">
  <h3>ورود</h3><p>login.js → POST /api/login → users.authenticate_user → verify_password → set_session_user → cookie session → redirect /app</p>
  <h3>گفتگو + اجرا + خوداصلاحی</h3><p>sendMessage → POST /api/chat → provider.generate_sql → wireSqlRunner → POST /api/run_sql → normalize/validate → execute
  → (در صورت خطا) provider.fix_sql → validate → execute مجدد → memory.add_message(data=...) → renderRunResults</p>
  <h3>تحلیل</h3><p>دکمهٔ تحلیل → POST /api/analyze → provider.generate_analysis(نمونهٔ ۸۰ ردیف) → memory.update_last_analysis → formatAnalysisHtml</p>
  <h3>بحث</h3><p>discuss-composer (داخل آکاردئون) → POST /api/discuss → provider.generate_discussion(تاریخچهٔ محدود) → appendBubble</p>
  <h3>تاریخچه و بازپخش</h3><p>کلیک آیتم تاریخچه → replayHistoryEntry(entry با data ذخیره‌شده) → بازسازی کامل جدول/نمودار/تحلیل بدون فراخوانی مجدد مدل</p>
  <h3>سؤالات پرتکرار</h3><p>loadFrequentQuestions → GET /api/frequent-questions → memory.get_frequent_questions (شمارش سراسری) → کلیک = ارسال فوری سؤال</p>
  <h3>خروجی PDF/Excel</h3><p>دکمهٔ PDF/Excel → POST /api/export_pdf یا /api/export_excel → pdf_generator/excel_generator → دانلود فایل</p>
  <h3>مدیریت کاربر</h3><p>/users → require_admin → users.js CRUD → /api/users → users.py → SQLAlchemy app_users</p>
</div>
""", "۸ · End-to-End")}

{page("ریسک‌ها و پیشنهادهای فنی", security_body, "۹ · بازبینی امنیتی")}
{page("راه‌اندازی و استقرار", run_body, "۱۰ · عملیات")}
{page("فهرست کامل فایل‌های پروژه", table(["ردیف", "مسیر", "اندازه"], inventory_rows), "۱۱ · پوشش")}

{page("جمع‌بندی", """
<div class="summary">
  <p>bichart یک ابزار BI مکالمه‌ای نسبتاً کامل است: صفحهٔ معرفی، ورود، داشبورد گفتگو با تاریخچهٔ قابل‌بازپخش و سؤالات پرتکرار سراسری،
  مدیریت کاربران، انتخاب دو مدل زبانی، تولید/اصلاح/اجرای SQL با حلقهٔ خوداصلاحی، جدول و نمودار (اکنون در کارت‌های مجزا با قابلیت چاپ)،
  تحلیل و بحث ثانویه، و خروجی PDF/Excel فارسی را یک‌جا دارد.</p>
  <p>مهم‌ترین کارهای پیش از production عبارت‌اند از: حذف/چرخش کلید API نوشته‌شده در سورس، اجباری‌کردن secretهای امن، افزودن
  row-level authorization واقعی، CSRF و rate-limit، استفاده از یک دیتابیس واقعی به‌جای history.json برای تاریخچه، parser/timeout قوی‌تر SQL،
  به‌روزرسانی README و حذف فایل‌های legacy ریشه.</p>
  <div class="stamp">پایان سند · تولیدشده در {esc(generated_at)}</div>
</div>
""", "۱۲ · نتیجه")}
"""


document = f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>مستند فنی پروژه bichart</title>
<style>
  @page {{ size: A4; margin: 16mm 14mm 17mm; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; color: #17231f; background: #fff; font-family: Tahoma, Arial, sans-serif; font-size: 10.3pt; line-height: 1.85; }}
  .page {{ break-before: page; }}
  .cover {{ break-before: auto; min-height: 255mm; display: flex; flex-direction: column; justify-content: center; padding: 12mm; border: 2px solid #0b7654; }}
  .cover-mark, .kicker {{ color: #0b7654; letter-spacing: .08em; font-size: 8.5pt; font-weight: bold; }}
  h1 {{ font-size: 27pt; line-height: 1.45; margin: 18mm 0 7mm; color: #103b2e; }}
  h1 span {{ color: #0b7654; }}
  .lead {{ font-size: 13.5pt; color: #48635a; max-width: 145mm; }}
  .meta {{ margin-top: 16mm; display: grid; grid-template-columns: 1fr 1fr; gap: 3mm; }}
  .meta div {{ background: #eef7f3; padding: 3mm 4mm; border-right: 3px solid #0b7654; }}
  .meta span {{ display: block; color: #688078; font-size: 8pt; }}
  .scope {{ margin-top: 16mm; font-size: 8.5pt; color: #5a6d66; border-top: 1px solid #cbdad4; padding-top: 4mm; }}
  .section-head {{ margin: 0 0 8mm; border-bottom: 2px solid #0b7654; padding-bottom: 3mm; }}
  h2 {{ margin: 1mm 0 0; font-size: 19pt; color: #103b2e; }}
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
  .callout ul {{ margin-bottom: 0; }}
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
  .code-list > div {{ display: grid; grid-template-columns: 52mm 1fr; gap: 3mm; align-items: start; background: #f7faf9; padding: 2mm; }}
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
  .change-grid {{ display: grid; grid-template-columns: 1fr; gap: 4mm; }}
  .change {{ break-inside: avoid; border: 1px solid #c9d9d3; border-right: 4px solid #0b7654; padding: 3.5mm 5mm; background: #fbfdfc; }}
  .change h3 {{ margin-bottom: 1.5mm; }}
  .summary {{ font-size: 12.5pt; line-height: 2.05; padding: 12mm 8mm; border: 1px solid #9cbeb2; }}
  .stamp {{ margin-top: 16mm; color: #0b7654; font-weight: bold; text-align: center; }}
  @media print {{
    a {{ color: inherit; text-decoration: none; }}
    .file-block, .callout, .change, tr {{ break-inside: avoid; }}
  }}
</style>
</head>
<body>{body}</body>
</html>
"""


HTML_OUT.write_text(document, encoding="utf-8")

chrome_candidates = [
    Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
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
print(f"Generated at:   {generated_at}")
