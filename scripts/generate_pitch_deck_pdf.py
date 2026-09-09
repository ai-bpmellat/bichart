"""
Generate a professional 16:9 PDF Pitch Deck for BiChart / Rayamate using Headless Chrome/Edge.
Output: docs/presentations/BiChart_Rayamate_Pitch_Deck.pdf
"""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_PRESENTATIONS = ROOT / "docs" / "presentations"
DOCS_PRESENTATIONS.mkdir(parents=True, exist_ok=True)

HTML_OUT = DOCS_PRESENTATIONS / "pitch_deck_printable.html"
PDF_OUT = DOCS_PRESENTATIONS / "BiChart_Rayamate_Pitch_Deck.pdf"

html_content = """<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>رایامیت | از داده تا تصمیم هوشمند</title>
<meta name="title" content="رایامیت | از داده تا تصمیم هوشمند">
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
  @page {
    size: 338mm 190mm; /* 16:9 widescreen presentation */
    margin: 0;
  }

  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  body {
    margin: 0;
    background: #ffffff;
    color: #0f2a1f;
    font-family: 'Vazirmatn', Tahoma, -apple-system, sans-serif;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }

  .slide {
    width: 338mm;
    height: 190mm;
    padding: 0;
    position: relative;
    page-break-after: always;
    break-after: page;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    background: #ffffff;
  }

  /* Header */
  .header {
    background: linear-gradient(135deg, #059669 0%, #047857 100%);
    padding: 12mm 24mm 10mm;
    color: #ffffff;
    position: relative;
    flex-shrink: 0;
  }

  .header::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: #34d399;
  }

  .kicker {
    font-size: 11pt;
    font-weight: 700;
    color: #a7f3d0;
    letter-spacing: 0.05em;
    margin-bottom: 2mm;
  }

  .title {
    font-size: 22pt;
    font-weight: 800;
    color: #ffffff;
    line-height: 1.25;
  }

  /* Body */
  .body {
    flex: 1;
    padding: 12mm 24mm 10mm;
    background: #f8fafc;
    display: flex;
    flex-direction: column;
    gap: 8mm;
    overflow: hidden;
  }

  /* Footer */
  .footer {
    padding: 6mm 24mm;
    background: #ffffff;
    border-top: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 10pt;
    color: #64748b;
    flex-shrink: 0;
  }

  .footer-brand {
    color: #047857;
    font-weight: 700;
  }

  /* Dark Slide for Cover & Closing */
  .slide-dark {
    background: radial-gradient(circle at 80% 20%, #113829 0%, #061711 75%);
    color: #ffffff;
    padding: 20mm 24mm 12mm;
    justify-content: space-between;
  }

  .slide-dark .footer {
    background: transparent;
    border-top: 1px solid rgba(255, 255, 255, 0.12);
    color: #94a3b8;
  }

  .slide-dark .footer-brand {
    color: #34d399;
  }

  /* Grids */
  .grid-2x2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8mm;
    flex: 1;
  }

  .grid-3-col {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 8mm;
    flex: 1;
  }

  .grid-4-col {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 6mm;
    flex: 1;
  }

  /* Cards */
  .card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 8mm 10mm;
    display: flex;
    flex-direction: column;
    gap: 3mm;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
  }

  .card-header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2mm;
  }

  .badge {
    padding: 2mm 5mm;
    border-radius: 999px;
    font-size: 9.5pt;
    font-weight: 700;
    display: inline-block;
  }

  .badge-amber {
    background: #fef3c7;
    color: #b45309;
    border: 1px solid #fde68a;
  }

  .badge-emerald {
    background: #ecfdf5;
    color: #047857;
    border: 1px solid #a7f3d0;
  }

  .card-title {
    font-size: 15pt;
    font-weight: 800;
    color: #0f2a1f;
  }

  .card-desc {
    font-size: 11.5pt;
    line-height: 1.7;
    color: #334155;
  }

  /* Rows */
  .row-item {
    background: #ffffff;
    border: 1px solid #a7f3d0;
    border-right: 6px solid #059669;
    border-radius: 10px;
    padding: 6mm 8mm;
    display: flex;
    flex-direction: column;
    gap: 2mm;
  }

  .row-title {
    font-size: 14pt;
    font-weight: 800;
    color: #047857;
  }

  .row-desc {
    font-size: 11.5pt;
    color: #334155;
    line-height: 1.65;
  }

  /* KPI Box */
  .kpi-box {
    background: #ecfdf5;
    border: 1.5px solid #a7f3d0;
    border-radius: 12px;
    padding: 7mm 6mm;
    text-align: center;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    gap: 2mm;
  }

  .kpi-num {
    font-size: 26pt;
    font-weight: 900;
    color: #047857;
    line-height: 1.1;
  }

  .kpi-lbl {
    font-size: 12pt;
    font-weight: 700;
    color: #0f2a1f;
  }

  .kpi-sub {
    font-size: 9.5pt;
    color: #64748b;
  }

  /* Cover elements */
  .cover-center {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    gap: 6mm;
  }

  .cover-badge {
    background: rgba(5, 150, 105, 0.25);
    border: 1px solid rgba(52, 211, 153, 0.4);
    color: #6ee7b7;
    padding: 3mm 10mm;
    border-radius: 999px;
    font-size: 12pt;
    font-weight: 700;
    letter-spacing: 0.05em;
  }

  .cover-title {
    font-size: 46pt;
    font-weight: 900;
    color: #ffffff;
    line-height: 1.15;
  }

  .cover-title span {
    color: #34d399;
  }

  .cover-sub {
    font-size: 20pt;
    font-weight: 600;
    color: #e2e8f0;
    max-width: 250mm;
    line-height: 1.5;
  }

  .cover-desc {
    font-size: 13.5pt;
    color: #94a3b8;
    max-width: 220mm;
    line-height: 1.6;
  }

  .pills {
    display: flex;
    gap: 4mm;
    margin-top: 4mm;
  }

  .pill {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    padding: 3mm 7mm;
    border-radius: 999px;
    font-size: 11pt;
    color: #e2e8f0;
  }
</style>
</head>
<body>

  <!-- ================= SLIDE 1: COVER ================= -->
  <section class="slide slide-dark">
    <div class="cover-center">
      <div class="cover-badge">● PITCH DECK & EXECUTIVE BRIEF</div>
      <h1 class="cover-title">رایامیت <span>| از داده تا تصمیم هوشمند</span></h1>
      <p class="cover-sub">نسل نوین هوش تجاری مکالمه‌محور برای صنعت پرداخت الکترونیک و بانکی</p>
      <p class="cover-desc">تبدیل پرسش‌های فارسی مدیران به گزارش‌های تحلیلی، نمودارهای آنی و بینش‌های استراتژیک در چند ثانیه</p>
      <div class="pills">
        <div class="pill">🔒 معماری امن On-Premise</div>
        <div class="pill">⚡ پاسخ‌دهی زیر ۲ ثانیه</div>
        <div class="pill">🧠 بدون خروج ۱ بایت داده بانکی</div>
        <div class="pill">📊 خروجی آنی اکسل و PDF</div>
      </div>
    </div>
    <div class="footer">
      <span class="footer-brand">بهپرداخت ملت • زیست‌بوم نوآوری و هوش مصنوعی</span>
      <span>ارائه به مدیران ارشد و سرمایه‌گذاران | اسلاید ۱ از ۱۲</span>
    </div>
  </section>

  <!-- ================= SLIDE 2: THE PROBLEM ================= -->
  <section class="slide">
    <div class="header">
      <div class="kicker">THE PROBLEM | چالش‌های بنیادی بازار</div>
      <div class="title">چرا ابزارهای متداول BI در صنعت پرداخت پاسخگوی نیاز امروز نیستند؟</div>
    </div>
    <div class="body">
      <div class="grid-2x2">
        <div class="card">
          <div class="card-header-row">
            <span class="card-title">۱. صف‌های طولانی درخواست گزارش</span>
            <span class="badge badge-amber">تاخیر ۳ تا ۷ روزه</span>
          </div>
          <p class="card-desc">مدیران ارشد و بازاریابی برای هر گزارش مقایسه‌ای یا تصمیم فوری، وابسته به کارشناسان دیتابیس و BI هستند. تا زمان آماده‌سازی گزارش، فرصت‌های تجاری و مداخله در بازار از دست می‌رود.</p>
        </div>
        <div class="card">
          <div class="card-header-row">
            <span class="card-title">۲. پیچیدگی ابزارهای سنتی (PowerBI / Tableau)</span>
            <span class="badge badge-amber">افت ۴۰٪ نرخ پذیرش</span>
          </div>
          <p class="card-desc">این ابزارها برای مدیران غیرفنی طراحی نشده‌اند؛ ساخت کوئری‌های پیچیده DAX/SQL هزینه‌بر است و هیچ‌کدام توانایی فهم زبان طبیعی فارسی یا ادبیات اختصاصی شبکه شاپرک را ندارند.</p>
        </div>
        <div class="card">
          <div class="card-header-row">
            <span class="card-title">۳. خط قرمز امنیت داده‌های مالی</span>
            <span class="badge badge-amber">عدم انطباق با شاپرک</span>
          </div>
          <p class="card-desc">استفاده از سرویس‌های عمومی هوش مصنوعی (مانند ChatGPT) به دلیل ارسال داده‌های مالی به سرورهای خارجی، نقض آشکار مقررات بانک مرکزی و پدافند سایبری بوده و ریسک امنیتی بالایی دارد.</p>
        </div>
        <div class="card">
          <div class="card-header-row">
            <span class="card-title">۴. فقدان تحلیل روایی و توصیه‌ای</span>
            <span class="badge badge-amber">اعداد خام بدون بینش</span>
          </div>
          <p class="card-desc">داشبوردهای متداول تنها ارقام را به شکل جدول و گراف ارائه می‌دهند و چرایی افت تراکنش‌ها، کشف رفتار غیرعادی پذیرندگان یا پیش‌بینی دوره‌های بعدی را توضیح نمی‌دهند.</p>
        </div>
      </div>
    </div>
    <div class="footer">
      <span class="footer-brand">BiChart / Rayamate</span>
      <span>اسلاید ۲ از ۱۲</span>
    </div>
  </section>

  <!-- ================= SLIDE 3: THE SOLUTION ================= -->
  <section class="slide">
    <div class="header">
      <div class="kicker">THE SOLUTION | ارزش پیشنهادی منحصر‌به‌فرد</div>
      <div class="title">رایامیت: ترکیب گفتگوی شهودی، امنیت بانکی و تحلیل هوشمند داده‌ها</div>
    </div>
    <div class="body">
      <div class="row-item">
        <div class="row-title">۱. مکالمه کاملاً روان به زبان فارسی و فهم ادبیات پرداخت</div>
        <div class="row-desc">درک دقیق اصطلاحات شاپرک، پایانه POS، درگاه IPG، پذیرنده، مغایرت، افت فصلی و محاسبه نرخ رشد بدون نیاز به یادگیری کوچک‌ترین دانش فنی یا کدنویسی.</div>
      </div>
      <div class="row-item">
        <div class="row-title">۲. معماری On-Premise و تضمین حاکمیت داده (Data Sovereignty)</div>
        <div class="row-desc">پشتیبانی از مدل‌های هوش مصنوعی محلی بانکی (مانند Gemma و Llama) روی سرورهای اختصاصی درون سازمان بدون نیاز به اتصال به اینترنت بین‌الملل.</div>
      </div>
      <div class="row-item">
        <div class="row-title">۳. خط لوله اعتبارسنجی امنیتی و کنترل دسترسی در سطح ردیف (RLS)</div>
        <div class="row-desc">تضمین ۱۰۰٪ جلوگیری از SQL Injection، بازنویسی خودکار کوئری با محدودیت دامنه‌ای مشتری (Scoping) و اجرای صرفاً دستورات مجاز خواندنی (SELECT).</div>
      </div>
      <div class="row-item">
        <div class="row-title">۴. تولید سه‌گانه هم‌زمان: جدول داده، نمودار بصری و روایت تحلیلی</div>
        <div class="row-desc">هر پاسخ شامل داده‌های خام جدول، نمودار تعاملی متناسب و یک پاراگراف تحلیل روایی هوشمند با ارائه پیش‌بینی روندها و توصیه‌های تجاری است.</div>
      </div>
    </div>
    <div class="footer">
      <span class="footer-brand">BiChart / Rayamate</span>
      <span>اسلاید ۳ از ۱۲</span>
    </div>
  </section>

  <!-- ================= SLIDE 4: PRODUCT EXPERIENCE ================= -->
  <section class="slide">
    <div class="header">
      <div class="kicker">PRODUCT EXPERIENCE | تجربه محصول</div>
      <div class="title">داشبورد متمرکز، سریع و آماده استفاده بدون نیاز به آموزش</div>
    </div>
    <div class="body">
      <div class="grid-2x2">
        <div class="card" style="justify-content: center;">
          <div class="card-title" style="margin-bottom: 3mm; color: #047857;">قابلیت‌های برجسته رابط کاربری</div>
          <ul style="padding-right: 6mm; font-size: 11.5pt; line-height: 1.85; color: #334155;">
            <li><strong>پیشنهادهای سریع (Quick Prompts):</strong> اجرای پرسش‌های متداول با ۱ کلیک</li>
            <li><strong>نمایش شفاف SQL:</strong> امکان مشاهده و بازرسی کوئری تولیدشده و زمان اجرا</li>
            <li><strong>نمودارسازی هوشمند خودکار:</strong> رسم بی‌درنگ نمودارهای میله‌ای و خطی</li>
            <li><strong>خروجی رسمی سازمانی:</strong> دریافت گزارش شکیل در قالب Excel و PDF</li>
            <li><strong>تنظیمات پیشرفته هوش مصنوعی:</strong> جابجایی بلادرنگ میان مدل محلی و ابری</li>
          </ul>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 5mm;">
          <div class="kpi-box">
            <div class="kpi-num">&lt; ۲ ثانیه</div>
            <div class="kpi-lbl">زمان پاسخ</div>
            <div class="kpi-sub">تولید کوئری تا نمایش نمودار</div>
          </div>
          <div class="kpi-box">
            <div class="kpi-num">۱۰۰٪</div>
            <div class="kpi-lbl">امنیت تفکیک داده</div>
            <div class="kpi-sub">Row-Level Scoping بدون نشت</div>
          </div>
          <div class="kpi-box">
            <div class="kpi-num">صفر</div>
            <div class="kpi-lbl">نیاز به آموزش</div>
            <div class="kpi-sub">رویکرد گفتگوی طبیعی فارسی</div>
          </div>
          <div class="kpi-box">
            <div class="kpi-num">۳ کلیک</div>
            <div class="kpi-lbl">تا خروجی اکسل/PDF</div>
            <div class="kpi-sub">گزارش‌گیری رسمی سازمانی</div>
          </div>
        </div>
      </div>
    </div>
    <div class="footer">
      <span class="footer-brand">BiChart / Rayamate</span>
      <span>اسلاید ۴ از ۱۲</span>
    </div>
  </section>

  <!-- ================= SLIDE 5: ARCHITECTURE ================= -->
  <section class="slide">
    <div class="header">
      <div class="kicker">ARCHITECTURE & SECURITY | معماری فنی</div>
      <div class="title">معماری ماژولار با خط لوله پردازش امن ۷ مرحله‌ای</div>
    </div>
    <div class="body">
      <div class="grid-4-col">
        <div class="card" style="border-top: 4px solid #059669;">
          <div class="card-title">۱. هویت و نشست</div>
          <div class="card-desc">احراز هویت چندعامله، کپچای ضد ربات، نشست‌های رمزنگاری شده و مدیریت سطح دسترسی سازمانی (RBAC).</div>
        </div>
        <div class="card" style="border-top: 4px solid #059669;">
          <div class="card-title">۲. تبدیل متن به SQL</div>
          <div class="card-desc">پرامپت‌های مهندسی‌شده با اعتبارسنجی خروجی ساختاریافته JSON و تزریق متادیتای دقیق جداول پرداخت.</div>
        </div>
        <div class="card" style="border-top: 4px solid #059669;">
          <div class="card-title">۳. گارد امنیتی کوئری</div>
          <div class="card-desc">تحلیل گرامری AST، فیلتر اجباری شناسه مشتری، سقف ۱۰۰ ردیف و مسدودسازی هرگونه دستور مخرب.</div>
        </div>
        <div class="card" style="border-top: 4px solid #059669;">
          <div class="card-title">۴. تحلیل تفسیری روایی</div>
          <div class="card-desc">محاسبه معیارهای آماری (روند، رشد، انحراف معیار) و فراخوانی تحلیل هوشمند روایی و پیش‌بینی.</div>
        </div>
      </div>
      <div class="row-item" style="background: #ecfdf5;">
        <div class="row-title">سازگاری زیرساختی: Docker، وب‌سرور FastAPI و اتصال به دیتابیس‌های بانکی (Oracle, Postgres, SQL Server)</div>
        <div class="row-desc">طراحی شده بر مبنای الگوی Modular Monolith با قابلیت تفکیک آسان به میکروسرویس‌های مستقل در صورت افزایش بار پردازشی.</div>
      </div>
    </div>
    <div class="footer">
      <span class="footer-brand">BiChart / Rayamate</span>
      <span>اسلاید ۵ از ۱۲</span>
    </div>
  </section>

  <!-- ================= SLIDE 6: MARKET SIZE ================= -->
  <section class="slide">
    <div class="header">
      <div class="kicker">MARKET OPPORTUNITY | اندازه و فرصت بازار</div>
      <div class="title">بیش از ۴ میلیارد تراکنش ماهانه شاپرک در جستجوی بینش بلادرنگ</div>
    </div>
    <div class="body">
      <div class="grid-3-col">
        <div class="card" style="text-align: center; border-color: #a7f3d0;">
          <span class="badge badge-emerald" style="margin-bottom: 2mm;">TAM | بازار کل در دسترس</span>
          <div class="kpi-num">+۳۵۰ میلیون $</div>
          <div class="card-desc">بازار نرم‌افزارهای BI، انبار داده و هوش مصنوعی مولد سازمانی در خاورمیانه و صنایع مالی ایران</div>
        </div>
        <div class="card" style="text-align: center; border-color: #059669;">
          <span class="badge badge-emerald" style="margin-bottom: 2mm;">SAM | بازار صنعت پرداخت</span>
          <div class="kpi-num">+۵۰ میلیون $</div>
          <div class="card-desc">۱۲ شرکت بزرگ PSP، بیش از ۳۰ بانک و موسسه اعتباری و ۱۵۰ پرداخت‌یار فعال متصل به شاپرک</div>
        </div>
        <div class="card" style="text-align: center; border-color: #047857;">
          <span class="badge badge-emerald" style="margin-bottom: 2mm;">SOM | سهم هدف ۲ سال</span>
          <div class="kpi-num">۵ میلیون $</div>
          <div class="card-desc">تجهیز ۴ شرکت PSP برتر، ۱۰ بانک بزرگ و ۳۰ هلدینگ بزرگ زنجیره‌ای به دستیار هوشمند رایامیت</div>
        </div>
      </div>
      <div class="card" style="background: #0f172a; color: #ffffff; border: none;">
        <div class="card-title" style="color: #6ee7b7; margin-bottom: 2mm;">بهره‌برداران مستقیم سامانه در اکوسیستم بهپرداخت و شبکه بانکی:</div>
        <div class="card-desc" style="color: #cbd5e1; line-height: 1.7;">
          • <strong>مدیران ارشد و هیئت مدیره:</strong> رصد لحظه‌ای درآمد کارمزدی و نوسانات سهم بازار بدون نیاز به گزارش‌های کند سنتی<br>
          • <strong>معاونت بازاریابی و امور پذیرندگان:</strong> کشف پایگاه‌های پرریسک و پایانه‌های با کاهش تراکنش ناگهانی<br>
          • <strong>تیم‌های مدیریت ریسک و تطبیق:</strong> پایش پیوسته ناهنجاری‌ها و انحرافات تراکنشی مشکوک
        </div>
      </div>
    </div>
    <div class="footer">
      <span class="footer-brand">BiChart / Rayamate</span>
      <span>اسلاید ۶ از ۱۲</span>
    </div>
  </section>

  <!-- ================= SLIDE 7: BUSINESS MODEL ================= -->
  <section class="slide">
    <div class="header">
      <div class="kicker">BUSINESS MODEL | مدل کسب‌وکار و درآمد</div>
      <div class="title">جریان‌های درآمدی چندلایه B2B مبتنی بر لایسنس، اشتراک و یکپارچه‌سازی</div>
    </div>
    <div class="body">
      <div class="grid-3-col">
        <div class="card">
          <span class="badge badge-emerald" style="align-self: flex-start;">مدل ۱: اشتراک پایه (SaaS)</span>
          <div class="card-title" style="margin: 2mm 0;">پرداخت‌یارها و فین‌تک‌ها</div>
          <div class="card-desc">
            • استقرار بر روی کلود خصوصی اختصاصی<br>
            • سقف تا ۵۰ کاربر و ۱۰ میلیون تراکنش در ماه<br>
            • به‌روزرسانی فصلی مدل‌های تحلیل داده<br>
            • درآمد تکرارشونده ماهانه و سالانه (ARR)
          </div>
        </div>
        <div class="card" style="border: 2px solid #059669; background: #ecfdf5;">
          <span class="badge" style="background: #059669; color: white; align-self: flex-start;">مدل ۲: لایسنس سازمانی (Enterprise)</span>
          <div class="card-title" style="margin: 2mm 0; color: #047857;">شرکت‌های PSP و بانک‌ها</div>
          <div class="card-desc" style="color: #0f2a1f;">
            • استقرار کامل On-Premise داخل دیتاسنتر بانک<br>
            • کاربران نامحدود و مقیاس‌پذیری چند دیتابیسی<br>
            • تیونینگ اختصاصی مدل‌های زبانی با متادیتای شرکت<br>
            • قرارداد پشتیبانی ۲۴/۷ و SLA تضمین‌شده
          </div>
        </div>
        <div class="card">
          <span class="badge badge-emerald" style="align-self: flex-start;">مدل ۳: خدمات سفارشی‌سازی</span>
          <div class="card-title" style="margin: 2mm 0;">ادغام با سامانه‌های Core</div>
          <div class="card-desc">
            • اتصال به انباره داده‌های کلان (ClickHouse / Oracle)<br>
            • طراحی داشبوردهای اختصاصی هیئت‌مدیره<br>
            • آموزش پرسنل و مشاوره استراتژی داده‌محور<br>
            • کارمزد پیاده‌سازی و توسعه سفارشی
          </div>
        </div>
      </div>
    </div>
    <div class="footer">
      <span class="footer-brand">BiChart / Rayamate</span>
      <span>اسلاید ۷ از ۱۲</span>
    </div>
  </section>

  <!-- ================= SLIDE 8: COMPETITIVE ADVANTAGE ================= -->
  <section class="slide">
    <div class="header">
      <div class="kicker">COMPETITIVE ADVANTAGE | مزیت‌های رقابتی</div>
      <div class="title">چرا رایامیت گزینه برتر در برابر رقبای داخلی و خارجی است؟</div>
    </div>
    <div class="body">
      <div class="grid-2x2">
        <div class="card">
          <div class="card-title" style="color: #047857;">★ بومی‌سازی عمیق برای زبان و مفاهیم مالی ایران</div>
          <div class="card-desc">درک دقیق مفاهیم شاپرکی، تاریخ شمسی، نوع پایانه و خطاهای سوییچ پرداخت که برای مدل‌های عمومی خارجی ناشناخته و گمراه‌کننده‌اند.</div>
        </div>
        <div class="card">
          <div class="card-title" style="color: #047857;">★ استقرار صددرصد امن و آفلاین (Zero Leakage)</div>
          <div class="card-desc">قابلیت کارکرد کامل در شبکه ملی اطلاعات و بدون نیاز به اینترنت جهانی، متناسب با الزامات حراست فناوری و پدافند غیرعامل بانکی.</div>
        </div>
        <div class="card">
          <div class="card-title" style="color: #047857;">★ سرعت راه‌اندازی و بازگشت سرمایه (زیر ۲ هفته)</div>
          <div class="card-desc">برخلاف پروژه‌های طاقت‌فرسای استقرار انبار داده که ماه‌ها زمان می‌برند، رایامیت در کمتر از ۲ هفته مستقیماً به دیتابیس متصل و فعال می‌شود.</div>
        </div>
        <div class="card">
          <div class="card-title" style="color: #047857;">★ ساختار ماژولار و هزینه نگهداری بسیار پایین</div>
          <div class="card-desc">عدم وابستگی به لایسنس‌های دلاری ابزارهای خارجی؛ امکان بهره‌گیری هوشمندانه از سخت‌افزارهای موجود سازمان.</div>
        </div>
      </div>
    </div>
    <div class="footer">
      <span class="footer-brand">BiChart / Rayamate</span>
      <span>اسلاید ۸ از ۱۲</span>
    </div>
  </section>

  <!-- ================= SLIDE 9: USE CASES ================= -->
  <section class="slide">
    <div class="header">
      <div class="kicker">OPERATIONAL USE CASES | سناریوهای کاربردی</div>
      <div class="title">پاسخ به سوالات حیاتی کسب‌وکار در جلسات مدیران ارشد</div>
    </div>
    <div class="body">
      <div class="row-item">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span class="row-title">پایش ریزش پذیرندگان کلیدی (Churn Detection)</span>
          <span class="badge badge-amber">اقدام پیشگیرانه بازاریابی</span>
        </div>
        <div class="row-desc">
          <strong>پرسش مدیر:</strong> «کدام پذیرندگان با گردش بیش از ۱۰۰ میلیون تومان در ۲ هفته اخیر دچار افت تراکنش بیش از ۲۵٪ شده‌اند؟»<br>
          <strong>ارزش کسب‌وکاری:</strong> شناسایی فوری اختلال دستگاه یا اقدام رقبا قبل از مهاجرت قطعی پذیرنده به شرکت رقیب.
        </div>
      </div>
      <div class="row-item">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span class="row-title">تحلیل و مقایسه سهم بازار اصناف</span>
          <span class="badge badge-emerald">بهینه‌سازی توزیع دستگاه POS</span>
        </div>
        <div class="row-desc">
          <strong>پرسش مدیر:</strong> «سهم مبلغی و تعدادی صنف داروخانه‌ها در شهر اصفهان نسبت به ماه گذشته چه تغییری کرده است؟»<br>
          <strong>ارزش کسب‌وکاری:</strong> بازتوزیع هوشمند پایانه‌ها به اصناف پربازده و جمع‌آوری دستگاه‌های کم‌تراکنش و زیان‌ده.
        </div>
      </div>
      <div class="row-item">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span class="row-title">گزارش‌گیری آنی در صحن هیئت مدیره</span>
          <span class="badge badge-emerald">پاسخگویی بی‌درنگ</span>
        </div>
        <div class="row-desc">
          <strong>پرسش مدیر:</strong> «خلاصه عملکرد کارمزدی شعب استان خراسان در مقایسه با هدف تعیین‌شده سه‌ماهه»<br>
          <strong>ارزش کسب‌وکاری:</strong> دریافت آنی گزارش در میانه جلسه بدون ارجاع به کارشناس یا تعویق تصمیم‌گیری.
        </div>
      </div>
    </div>
    <div class="footer">
      <span class="footer-brand">BiChart / Rayamate</span>
      <span>اسلاید ۹ از ۱۲</span>
    </div>
  </section>

  <!-- ================= SLIDE 10: ROADMAP ================= -->
  <section class="slide">
    <div class="header">
      <div class="kicker">PRODUCT ROADMAP | نقشه راه محصول</div>
      <div class="title">برنامه توسعه گام‌به‌گام به سوی مغز متفکر هوش تجاری پرداخت</div>
    </div>
    <div class="body">
      <div class="grid-4-col">
        <div class="card" style="border-color: #059669; background: #ecfdf5;">
          <span class="badge badge-emerald" style="align-self: flex-start;">فاز ۱: وضعیت فعلی</span>
          <div class="card-title" style="color: #047857; margin: 2mm 0;">MVP عملیاتی و امن</div>
          <div class="card-desc">
            • تبدیل دقیق متن به SQL<br>
            • گارد امنیتی و Row-Level Scoping<br>
            • نمودارسازی و تحلیل روایی<br>
            • اکسپورت PDF و Excel<br>
            • مدیریت کاربران و مدل هیبریدی
          </div>
        </div>
        <div class="card">
          <span class="badge badge-amber" style="align-self: flex-start;">فاز ۲: ۳ ماه آینده</span>
          <div class="card-title" style="margin: 2mm 0;">کشف هوشمند ناهنجاری</div>
          <div class="card-desc">
            • ماژول Anomaly Detection<br>
            • سیستم هشدار زودهنگام افت تراکنش<br>
            • پیش‌بینی سری‌های زمانی فروش<br>
            • ادغام با پایگاه‌های کلان ClickHouse
          </div>
        </div>
        <div class="card">
          <span class="badge badge-emerald" style="align-self: flex-start;">فاز ۳: ۶ ماه آینده</span>
          <div class="card-title" style="margin: 2mm 0;">دستیار صوتی و پیام‌رسان</div>
          <div class="card-desc">
            • گزارش‌گیری صوتی به زبان فارسی<br>
            • بات اختصاصی پیام‌رسان‌های بله/تلگرام<br>
            • ارسال خودکار خلاصه‌های روزانه<br>
            • ارزیابی پیشرفته رفتار پذیرندگان
          </div>
        </div>
        <div class="card">
          <span class="badge badge-emerald" style="align-self: flex-start;">فاز ۴: افق یک‌ساله</span>
          <div class="card-title" style="margin: 2mm 0;">هوش تجاری تجویزی</div>
          <div class="card-desc">
            • پیشنهاد خودکار اقدامات بازاریابی<br>
            • اتصال یکپارچه با سامانه سوییچ Core<br>
            • عرضه لایسنس به سایر بازیگران فین‌تک<br>
            • پشتیبانی از زبان‌های عربی و انگلیسی
          </div>
        </div>
      </div>
    </div>
    <div class="footer">
      <span class="footer-brand">BiChart / Rayamate</span>
      <span>اسلاید ۱۰ از ۱۲</span>
    </div>
  </section>

  <!-- ================= SLIDE 11: PROPOSAL & ROI ================= -->
  <section class="slide">
    <div class="header">
      <div class="kicker">THE PROPOSAL & ROI | پیشنهاد همکاری و توجیه اقتصادی</div>
      <div class="title">افزایش چشمگیر بهره‌وری سازمانی با بازگشت سرمایه زیر ۶ ماه</div>
    </div>
    <div class="body">
      <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 6mm;">
        <div class="kpi-box">
          <div class="kpi-num">۷۰٪</div>
          <div class="kpi-lbl">کاهش زمان گزارش‌گیری</div>
          <div class="kpi-sub">از چند روز به چند ثانیه</div>
        </div>
        <div class="kpi-box">
          <div class="kpi-num">۱۵٪</div>
          <div class="kpi-lbl">کاهش ریزش پذیرندگان</div>
          <div class="kpi-sub">با هشدارهای پیشگیرانه</div>
        </div>
        <div class="kpi-box">
          <div class="kpi-num">۸۰٪</div>
          <div class="kpi-lbl">آزادسازی زمان تیم IT</div>
          <div class="kpi-sub">حذف صف استخراج کوئری</div>
        </div>
        <div class="kpi-box">
          <div class="kpi-num">&lt; ۲ هفته</div>
          <div class="kpi-lbl">سرعت راه‌اندازی فاز پایلوت</div>
          <div class="kpi-sub">بدون اختلال در کارکرد سیستم</div>
        </div>
      </div>
      <div class="card" style="background: linear-gradient(135deg, #064e3b 0%, #047857 100%); color: white; border: none; padding: 6mm 8mm;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2mm;">
          <span class="card-title" style="color: #6ee7b7; font-size: 15pt;">پیشنهاد اجرای پایلوت عملیاتی (Pilot Implementation)</span>
          <span class="badge" style="background: rgba(255,255,255,0.2); color: white;">۳۰ روز بدون ریسک مالی</span>
        </div>
        <div class="card-desc" style="color: #ecfdf5; line-height: 1.7; font-size: 11.5pt;">
          پیشنهاد می‌شود این سامانه به مدت یک ماه در یکی از معاونت‌های عملیاتی یا امور پذیرندگان بهپرداخت ملت به صورت پایلوت راه‌اندازی گردد. پس از ارزیابی اثربخشی، سنجش رضایت مدیران و استخراج شاخص‌های واقعی بهره‌وری، تصمیم‌گیری جهت استقرار در سطح کل سازمان انجام خواهد شد.
        </div>
      </div>
    </div>
    <div class="footer">
      <span class="footer-brand">BiChart / Rayamate</span>
      <span>اسلاید ۱۱ از ۱۲</span>
    </div>
  </section>

  <!-- ================= SLIDE 12: CLOSING ================= -->
  <section class="slide slide-dark">
    <div class="cover-center">
      <div class="cover-badge">● JOIN THE FUTURE OF FINTECH BI</div>
      <h1 class="cover-title" style="font-size: 38pt;">آینده تصمیم‌گیری هوشمند، <span>یک مکالمه ساده است</span></h1>
      <p class="cover-sub" style="font-size: 17pt; max-width: 220mm;">سامانه رایامیت آماده است تا جریان بینش داده‌ها را در سازمان شما دگرگون سازد.</p>
      <div class="card" style="background: rgba(19, 45, 35, 0.8); border: 1px solid rgba(52, 211, 153, 0.4); max-width: 180mm; width: 100%; text-align: center; padding: 6mm 10mm;">
        <div style="font-size: 14pt; font-weight: 700; color: #34d399; margin-bottom: 2mm;">درگاه‌های ارتباطی و مشاهده دمو:</div>
        <div style="font-size: 12pt; color: #e2e8f0; line-height: 1.8;">
          🌐 نشانی سامانه: <strong>http://localhost:8000</strong><br>
          📁 کاتالوگ و مستندات فنی: پوشه <strong>docs/</strong> در مخزن پروژه<br>
          ✉️ ایمیل تیم محصول: <strong>product@bichart.ir</strong>
        </div>
      </div>
      <div style="font-size: 18pt; font-weight: 800; color: #34d399; margin-top: 4mm;">از توجه و همراهی شما صمیمانه سپاسگزاریم • پرسش و پاسخ (Q&A)</div>
    </div>
    <div class="footer">
      <span class="footer-brand">BiChart / Rayamate</span>
      <span>پایان ارائه | اسلاید ۱۲ از ۱۲</span>
    </div>
  </section>

</body>
</html>
"""

HTML_OUT.write_text(html_content, encoding="utf-8")
print(f"[OK] Wrote printable HTML: {HTML_OUT}")

chrome_candidates = [
    Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
]

browser = next((p for p in chrome_candidates if p.exists()), None)
if browser is None:
    raise SystemExit("Neither Chrome nor Edge was found.")

print(f"[INFO] Using browser: {browser}")

cmd = [
    str(browser),
    "--headless",
    "--disable-gpu",
    "--no-pdf-header-footer",
    "--run-all-compositor-stages-before-draw",
    f"--print-to-pdf={PDF_OUT}",
    HTML_OUT.as_uri(),
]

subprocess.run(cmd, check=True)

if PDF_OUT.exists():
    size_kb = PDF_OUT.stat().st_size / 1024
    print(f"[SUCCESS] Generated PDF Pitch Deck: {PDF_OUT} ({size_kb:.1f} KB)")
else:
    print(f"[ERROR] PDF was not generated at {PDF_OUT}")
