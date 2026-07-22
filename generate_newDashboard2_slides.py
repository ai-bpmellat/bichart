"""Generate Persian slide-deck PDF explaining newDashboard2 code."""

from __future__ import annotations

import html
import os
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BRANCH = "newDashboard2"
HTML_OUT = ROOT / "newDashboard2_code_slides_fa.html"
PDF_OUT = ROOT / "newDashboard2_code_slides_fa.pdf"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


commit = git("rev-parse", "--short=10", BRANCH)
commit_date = git("show", "-s", "--format=%ad", "--date=short", BRANCH)
subject = git("show", "-s", "--format=%s", BRANCH)
file_count = len(git("ls-tree", "-r", "--name-only", BRANCH).splitlines())


def slide(kicker: str, title: str, body: str, page: int, total: int) -> str:
    return f"""
    <section class="slide">
      <div class="topbar"></div>
      <div class="kicker">{kicker}</div>
      <h2>{title}</h2>
      <div class="body">{body}</div>
      <div class="footer">
        <span>Rayamate · توضیح کد newDashboard2</span>
        <span>{page} / {total}</span>
      </div>
    </section>
    """


def cards(items: list[tuple[str, str]]) -> str:
    return '<div class="cards">' + "".join(
        f'<div class="card"><h3>{title}</h3><p>{text}</p></div>' for title, text in items
    ) + "</div>"


def bullets(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"


def two_col(left: str, right: str) -> str:
    return f'<div class="two"><div>{left}</div><div>{right}</div></div>'


def code_flow(steps: list[str]) -> str:
    parts = []
    for i, step in enumerate(steps):
        parts.append(f'<div class="step"><span>{i + 1}</span><p>{step}</p></div>')
        if i < len(steps) - 1:
            parts.append('<div class="arrow">←</div>')
    return f'<div class="flow">{"".join(parts)}</div>'


TOTAL = 14

slides = []

slides.append(f"""
<section class="slide cover">
  <div class="topbar"></div>
  <div class="kicker">RAYAMATE · CODE SLIDES</div>
  <h1>توضیح کدها و فایل‌ها<br><span dir="ltr">newDashboard2</span></h1>
  <p class="lead">ارائه اسلایدی فارسی از معماری، API، فرانت‌اند و فایل‌های مهم پروژه</p>
  <div class="meta">
    <div><span>Commit</span><b dir="ltr">{esc(commit)}</b></div>
    <div><span>تاریخ</span><b dir="ltr">{esc(commit_date)}</b></div>
    <div><span>فایل‌ها</span><b>{file_count} فایل</b></div>
    <div><span>موضوع</span><b>{esc(subject)}</b></div>
  </div>
  <div class="footer"><span>Rayamate</span><span>1 / {TOTAL}</span></div>
</section>
""")

slides.append(slide(
    "۱ · نمای کلان",
    "معماری سامانه",
    code_flow([
        "مرورگر<br>Landing / Login / Dashboard",
        "FastAPI<br>Session + Routes",
        "مدل زبانی<br>AvalAI یا Ollama",
        "SQL Safety<br>اصلاح و اعتبارسنجی",
        "SQLAlchemy<br>SQLite / DB",
    ]) + bullets([
        "هدف: سؤال فارسی/انگلیسی درباره تراکنش‌ها → تولید SQL → جدول/نمودار/تحلیل",
        "Backend: FastAPI + Pydantic + SQLAlchemy + Pandas",
        "Frontend فعال: پوشه <code>static/</code> (نسخه‌های ریشه legacy هستند)",
    ]),
    2, TOTAL,
))

slides.append(slide(
    "۲ · مسیر کاربر",
    "جریان End-to-End",
    cards([
        ("ورود", "login.js → POST /api/login → users.authenticate_user → session cookie → /app"),
        ("گفتگو", "sendMessage → POST /api/chat → generate_sql → normalize/validate → اجرا → جدول/نمودار"),
        ("تحلیل", "دکمه تحلیل → POST /api/analyze → generate_analysis روی ۲۰ ردیف اول"),
        ("کاربران", "فقط admin: /users → CRUD از طریق /api/users"),
    ]),
    3, TOTAL,
))

slides.append(slide(
    "۳ · Backend اصلی",
    "app.py — قلب برنامه",
    two_col(
        bullets([
            "تعریف FastAPI، middlewareها و مدل‌های Pydantic",
            "<code>RequireLoginMiddleware</code>: همه مسیرها به‌جز landing/login نیاز به ورود دارند",
            "<code>get_llm_client</code>: انتخاب AvalAI یا Ollama",
            "<code>SCHEMA_DESCRIPTION</code>: شرح جداول برای مدل",
        ]),
        bullets([
            "<code>/api/chat</code>: تولید SQL + اجرا + timings",
            "<code>/api/analyze</code>: تحلیل اختیاری",
            "مدیریت کاربران فقط برای نقش admin",
            "زمان هر مرحله (SQL، safety، اجرا، حافظه) اندازه‌گیری می‌شود",
        ]),
    ),
    4, TOTAL,
))

slides.append(slide(
    "۴ · داده و هویت",
    "database / users / auth / memory",
    cards([
        ("database.py", "تنظیم SQLAlchemy؛ DATABASE_URL برای تعویض DB؛ پیش‌فرض SQLite"),
        ("users.py", "جدول app_users؛ هش PBKDF2؛ CRUD؛ محافظت آخرین admin"),
        ("auth.py", "نشست امضاشده؛ is_authenticated / is_admin / current_user"),
        ("memory_manager.py", "تاریخچه و preference هر کاربر در history.json"),
    ]),
    5, TOTAL,
))

slides.append(slide(
    "۵ · مدل و ایمنی SQL",
    "تولید SQL و کنترل امنیتی",
    two_col(
        "<h3>کلاینت‌های مدل</h3>" + bullets([
            "<code>ollama_client.py</code>: مدل محلی gemma روی 127.0.0.1",
            "<code>avalai_client.py</code>: API ابری سازگار با OpenAI",
            "هر دو: <code>generate_sql</code> و <code>generate_analysis</code>",
            "استخراج مقاوم JSON از خروجی مدل",
        ]),
        "<h3>sql_safety.py</h3>" + bullets([
            "اصلاح date_key اشتباه → join با dim_date",
            "نرمال‌سازی modifier ماه و status",
            "حذف LIMIT ناخواسته",
            "فقط SELECT/WITH؛ رد DROP/DELETE/UPDATE/...",
        ]),
    ),
    6, TOTAL,
))

slides.append(slide(
    "۶ · داده آزمایشی",
    "db_mock.py — Star Schema",
    cards([
        ("dim_date", "تاریخ YYYYMMDD + full_date برای فیلتر تقویمی"),
        ("dim_category / merchant", "۱۵ صنف فارسی + پذیرندگان ایرانی"),
        ("dim_terminal", "پایانه POS / mPOS / Online"),
        ("fact_transactions", "~۱۰۰۰ تراکنش با مبلغ، وضعیت و کانال"),
        ("dim_customer", "مالک تجاری داده؛ جدا از حساب ورود app_users"),
        ("نکته", "اجرای مجدد db_mock.py دیتابیس را از نو می‌سازد"),
    ]),
    7, TOTAL,
))

slides.append(slide(
    "۷ · APIها",
    "مسیرهای مهم HTTP",
    """
    <div class="table">
      <div><code>GET /</code><span>صفحه معرفی first.html</span></div>
      <div><code>GET /login</code> · <code>POST /api/login</code><span>ورود و نشست</span></div>
      <div><code>GET /app</code><span>داشبورد گفتگو (نیاز به login)</span></div>
      <div><code>POST /api/chat</code><span>سؤال → SQL → نتیجه</span></div>
      <div><code>POST /api/analyze</code><span>تحلیل ثانویه</span></div>
      <div><code>/api/history</code> · <code>/api/preferences</code><span>حافظه و تنظیمات</span></div>
      <div><code>/users</code> · <code>/api/users</code><span>مدیریت کاربران (admin)</span></div>
      <div><code>/api/health</code><span>وضعیت DB و مدل‌ها</span></div>
    </div>
    """,
    8, TOTAL,
))

slides.append(slide(
    "۸ · Frontend فعال",
    "صفحات static/",
    cards([
        ("first.html", "لندینگ بازاریابی؛ Tailwind؛ لینک ورود پویا به :8000/login"),
        ("login.html + login.js", "فرم ورود، کپچای نمایشی، remember username، redirect به /app"),
        ("index.html", "داشبورد: provider، زبان، تاریخچه، quick actions، composer"),
        ("users.html + users.js", "CRUD کاربران برای admin"),
    ]),
    9, TOTAL,
))

slides.append(slide(
    "۹ · منطق کلاینت",
    "static/script.js",
    two_col(
        bullets([
            "خواندن هویت از <code>/api/me</code>",
            "انتخاب AvalAI / Ollama و زبان FA/EN",
            "ارسال سؤال به <code>/api/chat</code>",
            "نمایش SQL جمع‌شونده، توضیح و timings",
        ]),
        bullets([
            "جدول صفحه‌بندی‌شده تا ۱۰۰۰ ردیف در صفحه",
            "نمودار Chart.js: bar / line / pie / doughnut",
            "تحلیل اختیاری با دکمه جداگانه",
            "escapeHtml برای جلوگیری از XSS در خروجی",
        ]),
    ),
    10, TOTAL,
))

slides.append(slide(
    "۱۰ · استایل و دارایی‌ها",
    "CSS، Chart.js و فایل‌های کمکی",
    cards([
        ("static/style.css", "طراحی داشبورد RTL، sidebar، result strip، جدول و نمودار"),
        ("chart.umd.min.js", "کتابخانه Chart.js محلی (vendored)"),
        ("Dockerfile + passenger_wsgi", "استقرار container و cPanel"),
        ("requirements.txt", "FastAPI، Uvicorn، SQLAlchemy، Pandas، Requests، a2wsgi"),
    ]),
    11, TOTAL,
))

slides.append(slide(
    "۱۱ · Legacy",
    "فایل‌های ریشه که سرو نمی‌شوند",
    bullets([
        "<code>index.html</code> / <code>script.js</code> / <code>style.css</code> در ریشه: نسخه قدیمی",
        "FastAPI فقط <code>static/index.html</code> را برای <code>/app</code> سرو می‌کند",
        "script ریشه هنوز به access_key و /api/customers اشاره دارد (منسوخ)",
        "README در چند بخش با کد فعلی همگام نیست (auth، LIMIT، تعداد تراکنش‌ها)",
        "ارائه قدیمی: <code>create_presentation.py</code> → <code>Rayamate_Presentation.pptx</code>",
    ]),
    12, TOTAL,
))

slides.append(slide(
    "۱۲ · امنیت",
    "نقاط قوت و ریسک‌ها",
    two_col(
        "<h3>نقاط قوت</h3>" + bullets([
            "هش گذرواژه با PBKDF2",
            "SQL فقط خواندنی",
            "کلید AvalAI فقط سمت سرور",
            "CRUD کاربران محدود به admin",
        ]),
        "<h3>ریسک‌های مهم</h3>" + bullets([
            "secret و admin پیش‌فرض در کد/محیط",
            "کپچا فقط checkbox مرورگر",
            "نبود CSRF و row-level scope واقعی",
            "validator مبتنی بر regex نه parser کامل",
        ]),
    ),
    13, TOTAL,
))

slides.append(slide(
    "۱۳ · جمع‌بندی",
    "آماده استفاده به‌عنوان prototype",
    bullets([
        "newDashboard2 یک BI مکالمه‌ای کامل با ورود، داشبورد، دو مدل و مدیریت کاربر است",
        "مسیر فعال: <code>static/</code> + <code>app.py</code> + لایه SQL safety + memory",
        "پیش از production: rotate secrets، CSRF/rate-limit، auth سطح ردیف، همگام‌سازی README",
        "منبع این اسلایدها: commit <code dir='ltr'>" + esc(commit) + "</code> روی branch newDashboard2",
    ]) + f'<div class="stamp">پایان ارائه · {datetime.now().strftime("%Y-%m-%d")}</div>',
    14, TOTAL,
))

document = f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>اسلایدهای توضیح کد newDashboard2</title>
<style>
  @page {{ size: 338mm 190mm; margin: 0; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: #fff;
    color: #0f2a1f;
    font-family: Tahoma, Arial, sans-serif;
  }}
  .slide {{
    width: 338mm;
    height: 190mm;
    padding: 14mm 16mm 12mm;
    position: relative;
    break-after: page;
    overflow: hidden;
    background: #ffffff;
  }}
  .slide:last-child {{ break-after: auto; }}
  .topbar {{
    position: absolute; top: 0; left: 0; right: 0; height: 8px;
    background: linear-gradient(90deg, #059669, #047857);
  }}
  .kicker {{
    color: #059669; font-size: 12pt; font-weight: bold;
    letter-spacing: .04em; margin-top: 4mm;
  }}
  h1 {{
    font-size: 34pt; line-height: 1.45; margin: 8mm 0 4mm; color: #0f2a1f;
  }}
  h1 span {{ color: #059669; }}
  h2 {{
    font-size: 26pt; margin: 3mm 0 7mm; color: #0f2a1f;
  }}
  h3 {{ margin: 0 0 3mm; color: #047857; font-size: 14pt; }}
  .lead {{ font-size: 15pt; color: #5a7a6d; max-width: 240mm; }}
  .body {{ font-size: 13.5pt; line-height: 1.7; }}
  ul {{ margin: 0; padding-right: 7mm; }}
  li {{ margin: 2.2mm 0; }}
  code {{
    font-family: Consolas, "Courier New", monospace;
    direction: ltr; unicode-bidi: embed;
    background: #ecfdf5; color: #047857;
    padding: 0 2mm; border-radius: 3px; font-size: 11.5pt;
  }}
  .meta {{
    margin-top: 14mm; display: grid; grid-template-columns: 1fr 1fr; gap: 4mm; max-width: 220mm;
  }}
  .meta div {{
    background: #ecfdf5; border-right: 4px solid #059669; padding: 4mm 5mm;
  }}
  .meta span {{ display: block; color: #5a7a6d; font-size: 10pt; }}
  .footer {{
    position: absolute; left: 16mm; right: 16mm; bottom: 7mm;
    display: flex; justify-content: space-between;
    color: #5a7a6d; font-size: 10.5pt;
    border-top: 1px solid #d7e8e0; padding-top: 3mm;
  }}
  .cards {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 5mm;
  }}
  .card {{
    background: #f4f8f6; border: 1px solid #cfe3da; border-radius: 8px; padding: 5mm;
  }}
  .card p {{ margin: 0; font-size: 12.5pt; color: #314c43; }}
  .two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8mm; }}
  .flow {{
    display: flex; align-items: stretch; justify-content: space-between;
    gap: 2mm; margin-bottom: 7mm;
  }}
  .step {{
    flex: 1; background: #ecfdf5; border: 1px solid #a7d7c4; border-radius: 8px;
    padding: 4mm 3mm; text-align: center;
  }}
  .step span {{
    display: inline-flex; width: 8mm; height: 8mm; border-radius: 50%;
    background: #059669; color: white; align-items: center; justify-content: center;
    font-weight: bold; margin-bottom: 2mm;
  }}
  .step p {{ margin: 0; font-size: 11pt; line-height: 1.45; }}
  .arrow {{ align-self: center; color: #059669; font-size: 18pt; font-weight: bold; }}
  .table {{ display: grid; gap: 3mm; }}
  .table > div {{
    display: grid; grid-template-columns: 1.2fr 1fr; gap: 4mm;
    background: #f7faf9; border: 1px solid #d5e6df; border-radius: 6px; padding: 3.5mm 4mm;
    align-items: center;
  }}
  .table span {{ color: #48635a; }}
  .stamp {{
    margin-top: 10mm; text-align: center; color: #059669; font-weight: bold; font-size: 14pt;
  }}
  .cover .footer {{ border-top: none; }}
</style>
</head>
<body>
{''.join(slides)}
</body>
</html>
"""

HTML_OUT.write_text(document, encoding="utf-8")

chrome_candidates = [
    Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
]
browser = next((p for p in chrome_candidates if p.exists()), None)
if browser is None:
    raise SystemExit(f"HTML created at {HTML_OUT}, but Chrome/Edge not found.")

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
print(f"Slides: {TOTAL}")
print(f"Commit: {commit}")
