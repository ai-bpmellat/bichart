"""
Generate a professional 12-slide Persian Pitch Deck (PPTX) for BiChart / Rayamate.
Target Audience: C-level Executives, Bank/PSP Directors, Investors, and Innovation Committees.
Run: venv\\Scripts\\python.exe scripts/create_pitch_deck.py
"""

from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from lxml import etree

# Brand Colors (Beh Pardakht / Rayamate FinTech Palette)
EMERALD = RGBColor(0x05, 0x96, 0x69)
EMERALD_DARK = RGBColor(0x04, 0x78, 0x57)
EMERALD_DEEP = RGBColor(0x06, 0x4E, 0x3B)
EMERALD_LIGHT = RGBColor(0xEC, 0xFD, 0xF5)
EMERALD_BORDER = RGBColor(0xA7, 0xF3, 0xD0)

BG_DARK = RGBColor(0x0A, 0x1F, 0x17)
BG_CARD_DARK = RGBColor(0x13, 0x2D, 0x23)
SLATE_900 = RGBColor(0x0F, 0x17, 0x2A)
SLATE_800 = RGBColor(0x1E, 0x29, 0x3B)
SLATE_700 = RGBColor(0x33, 0x41, 0x55)
SLATE_100 = RGBColor(0xF1, 0xF5, 0xF9)

WHITE = RGBColor(0xFF, 0xFF, 0xFF)
CREAM = RGBColor(0xF8, 0xFA, 0xFC)
INK = RGBColor(0x0F, 0x2A, 0x1F)
MUTED = RGBColor(0x64, 0x74, 0x8B)
AMBER = RGBColor(0xD9, 0x77, 0x06)
AMBER_LIGHT = RGBColor(0xFE, 0xF3, 0xC7)
BLUE = RGBColor(0x02, 0x84, 0xC7)
RED_ACCENT = RGBColor(0xDC, 0x26, 0x26)

FONT = "Tahoma"  # Standard Persian font supported universally in Office/Windows


def set_run_font(run, size=16, bold=False, color=INK, font_name=FONT):
    run.font.name = font_name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    rPr = run._r.get_or_add_rPr()
    try:
        from pptx.oxml.ns import qn
        for local in ("latin", "ea", "cs"):
            node = rPr.find(qn(f"a:{local}"))
            if node is None:
                node = etree.SubElement(rPr, qn(f"a:{local}"))
            node.set("typeface", font_name)
    except Exception:
        pass


def add_shape(slide, shape_type, left, top, width, height, fill_color, border_color=None, border_width=1):
    shape = slide.shapes.add_shape(shape_type, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if border_color:
        shape.line.color.rgb = border_color
        shape.line.width = Pt(border_width)
    else:
        shape.line.fill.background()
    return shape


def add_textbox(
    slide,
    left,
    top,
    width,
    height,
    text,
    size=16,
    bold=False,
    color=INK,
    align=PP_ALIGN.RIGHT,
    font_name=FONT,
):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.08)
    tf.margin_right = Inches(0.08)
    tf.margin_top = Inches(0.06)
    tf.margin_bottom = Inches(0.06)
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    set_run_font(run, size=size, bold=bold, color=color, font_name=font_name)
    return box


def add_bullets(
    slide,
    left,
    top,
    width,
    height,
    items,
    size=15,
    color=INK,
    space_after=8,
    bullet_char="•  ",
):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.08)
    tf.margin_right = Inches(0.08)
    tf.margin_top = Inches(0.06)
    tf.margin_bottom = Inches(0.06)
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.RIGHT
        p.space_after = Pt(space_after)
        run = p.add_run()
        run.text = f"{bullet_char}{item}"
        set_run_font(run, size=size, color=color)
    return box


def header(slide, kicker, title, dark_mode=False):
    bg_bar = EMERALD if dark_mode else EMERALD
    add_shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(1.15), bg_bar)
    
    # Kicker (sub-label)
    k_color = EMERALD_LIGHT if dark_mode else EMERALD_LIGHT
    add_textbox(slide, Inches(0.8), Inches(0.12), Inches(11.7), Inches(0.35), kicker, size=12, bold=True, color=k_color, align=PP_ALIGN.RIGHT)
    
    # Title
    t_color = WHITE
    add_textbox(slide, Inches(0.8), Inches(0.42), Inches(11.7), Inches(0.65), title, size=24, bold=True, color=t_color, align=PP_ALIGN.RIGHT)


def footer(slide, current_page, total_pages=12, dark_mode=False):
    line_color = EMERALD_DARK if dark_mode else RGBColor(0xDC, 0xEC, 0xE4)
    txt_color = EMERALD_BORDER if dark_mode else MUTED
    
    # Thin divider line
    add_shape(slide, MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(7.0), Inches(11.733), Inches(0.02), line_color)
    
    # Brand tag & page number
    add_textbox(
        slide,
        Inches(0.8),
        Inches(7.05),
        Inches(5.0),
        Inches(0.35),
        "BiChart / Rayamate  |  سامانه هوش تجاری مکالمه‌محور صنعت پرداخت",
        size=10,
        color=txt_color,
        align=PP_ALIGN.LEFT,
    )
    add_textbox(
        slide,
        Inches(8.5),
        Inches(7.05),
        Inches(4.0),
        Inches(0.35),
        f"صفحه {current_page} از {total_pages}",
        size=10,
        color=txt_color,
        align=PP_ALIGN.RIGHT,
    )


def add_kpi_card(slide, left, top, width, height, number_str, label_str, subtext="", bg_color=EMERALD_LIGHT, border_color=EMERALD_BORDER):
    add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height, bg_color, border_color, border_width=1.5)
    add_textbox(slide, left + Inches(0.15), top + Inches(0.2), width - Inches(0.3), Inches(0.7), number_str, size=28, bold=True, color=EMERALD_DARK, align=PP_ALIGN.CENTER)
    add_textbox(slide, left + Inches(0.15), top + Inches(0.95), width - Inches(0.3), Inches(0.45), label_str, size=14, bold=True, color=INK, align=PP_ALIGN.CENTER)
    if subtext:
        add_textbox(slide, left + Inches(0.15), top + Inches(1.4), width - Inches(0.3), Inches(0.5), subtext, size=11, color=MUTED, align=PP_ALIGN.CENTER)


def build_pitch_deck():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]
    total = 12

    base_dir = Path(__file__).resolve().parent.parent
    logo_path = base_dir / "static" / "logo.png"
    img_screen_landing = base_dir / "docs" / "images" / "screen_landing.png"
    img_screen_dash = base_dir / "docs" / "images" / "screen_dashboard.png"

    # =========================================================================
    # SLIDE 1: COVER / TITLE (Investor Pitch Deck)
    # =========================================================================
    s = prs.slides.add_slide(blank)
    # Background
    add_shape(s, MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height, BG_DARK)
    # Visual accent geometry
    add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, Inches(9.2), Inches(-1.5), Inches(5.5), Inches(4.5), BG_CARD_DARK)
    add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, Inches(-1.0), Inches(5.0), Inches(4.5), Inches(3.5), BG_CARD_DARK)
    add_shape(s, MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.4), prs.slide_height, EMERALD)

    # Logo if exists
    if logo_path.exists():
        try:
            s.shapes.add_picture(str(logo_path), Inches(6.15), Inches(0.8), Inches(1.2), Inches(1.2))
        except Exception:
            pass

    add_textbox(s, Inches(1.0), Inches(2.1), Inches(11.333), Inches(0.5), "PITCH DECK  |  ارائه معرفی محصول به مدیران و سرمایه‌گذاران", size=14, bold=True, color=EMERALD_BORDER, align=PP_ALIGN.CENTER)
    add_textbox(s, Inches(1.0), Inches(2.65), Inches(11.333), Inches(1.1), "BiChart  /  رایامیت", size=48, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_textbox(s, Inches(1.0), Inches(3.85), Inches(11.333), Inches(0.8), "نسل نوین هوش تجاری مکالمه‌محور برای صنعت پرداخت الکترونیک و بانکی", size=22, bold=True, color=EMERALD_LIGHT, align=PP_ALIGN.CENTER)
    add_textbox(s, Inches(1.5), Inches(4.7), Inches(10.333), Inches(0.6), "تبدیل داده‌های چندمیلیونی تراکنش‌ها به بینش‌های استراتژیک تنها با یک مکالمه طبیعی فارسی", size=16, color=WHITE, align=PP_ALIGN.CENTER)

    # Key highlights pill
    add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, Inches(2.5), Inches(5.4), Inches(8.333), Inches(0.7), BG_CARD_DARK, EMERALD_DARK, border_width=1)
    add_textbox(s, Inches(2.6), Inches(5.52), Inches(8.133), Inches(0.45), "امنیت چندلایه Zero-Trust  •  پشتیبانی از مدل‌های محلی On-Premise  •  تولید خودکار SQL و تحلیل آماری", size=13, color=EMERALD_BORDER, align=PP_ALIGN.CENTER)

    add_textbox(s, Inches(1.0), Inches(6.4), Inches(11.333), Inches(0.4), "توسعه‌یافته برای اکوسیستم بهپرداخت ملت و فعالان نظام پرداخت کشور", size=13, color=MUTED, align=PP_ALIGN.CENTER)
    footer(s, 1, total, dark_mode=True)

    # =========================================================================
    # SLIDE 2: THE PROBLEM (چالش‌های صنعت پرداخت و ابزارهای سنتی BI)
    # =========================================================================
    s = prs.slides.add_slide(blank)
    add_shape(s, MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height, CREAM)
    header(s, "THE PROBLEM  |  شناسایی گلوگاه‌های کلیدی", "چرا ابزارهای سنتی BI و هوش مصنوعی عمومی در صنعت پرداخت ناکارآمدند؟")

    problems = [
        ("گلوگاه صف گزارش‌گیری (Bottleneck)", "مدیران کسب‌وکار برای هر سوال تحلیلی باید در صف انتظار تیم دیتابیس/BI بمانند. زمان پاسخ از چند ساعت تا چند روز به درازا می‌کشد و فرصت تصمیم‌گیری از دست می‌رود.", "تاخیر ۳ تا ۷ روزه"),
        ("پیچیدگی ابزارهای سنتی (High Complexity)", "داشبوردهایی مانند PowerBI و Tableau نیازمند آموزش تخصصی و تسلط به DAX/SQL هستند و هیچ درک معنایی از زبان فارسی یا ادبیات بانکی شاپرک ندارند.", "افت ۴۰٪ مشارکت مدیران"),
        ("ممنوعیت امنیتی ابزارهای خارجی (Security Risk)", "ارسال داده‌های مالی و تراکنشی پذیرندگان به مدل‌های ابری عمومی (مانند ChatGPT) طبق الزامات بانک مرکزی و پدافند سایبری اکیداً ممنوع و پرریسک است.", "ریسک نشت داده"),
        ("تحلیل خام بدون روایت‌گری (Lack of Context)", "ابزارهای متداول فقط ارقام و نمودارهای خام نشان می‌دهند؛ درحالی‌که مدیران به تفسیر روایی، تشخیص ناهنجاری، مقایسه دوره‌ای و پیش‌بینی روندهای آینده نیاز دارند.", "عدم درک چرایی داده"),
    ]

    for i, (title, desc, badge) in enumerate(problems):
        col = i % 2
        row = i // 2
        left = Inches(0.8 + col * 5.95)
        top = Inches(1.5 + row * 2.6)
        
        # Card container
        add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, left, top, Inches(5.75), Inches(2.4), WHITE, border_color=RGBColor(0xE2, 0xE8, 0xF0))
        # Badge
        add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, left + Inches(0.3), top + Inches(0.25), Inches(2.2), Inches(0.4), AMBER_LIGHT, border_color=AMBER)
        add_textbox(s, left + Inches(0.3), top + Inches(0.28), Inches(2.2), Inches(0.35), badge, size=11, bold=True, color=AMBER, align=PP_ALIGN.CENTER)
        # Title
        add_textbox(s, left + Inches(2.6), top + Inches(0.25), Inches(2.9), Inches(0.45), title, size=15, bold=True, color=INK, align=PP_ALIGN.RIGHT)
        # Desc
        add_textbox(s, left + Inches(0.3), top + Inches(0.8), Inches(5.15), Inches(1.45), desc, size=13, color=SLATE_700, align=PP_ALIGN.RIGHT)

    footer(s, 2, total)

    # =========================================================================
    # SLIDE 3: THE SOLUTION (راه‌حل رایامیت / بی‌چارت)
    # =========================================================================
    s = prs.slides.add_slide(blank)
    add_shape(s, MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height, CREAM)
    header(s, "THE SOLUTION  |  ارزش پیشنهادی محوری", "رایامیت: تبدیل مکالمه طبیعی به هوش تجاری عملیاتی در چند ثانیه")

    sol_cards = [
        ("۱. گفتگوی کاملاً بومی به زبان فارسی", "درک اصطلاحات تخصصی شبکه پرداخت (پذیرنده، سوییچ، پایانه، شاپرک، افت تراکنش، وفاداری) بدون نیاز به کدنویسی یا یادگیری نرم‌افزار جدید."),
        ("۲. معماری امنیت داده درون‌سازمانی (On-Premise)", "پشتیبانی کامل از مدل‌های زبانی محلی بانکی (Gemma/Llama عبر Ollama) بدون خروج حتی یک بایت داده مالی از شبکه خصوصی شرکت."),
        ("۳. گاردریل امنیتی پیشرفته SQL (Zero-Trust)", "بازنویسی خودکار کوئری در سطح ردیف (Row-Level Security) متناسب با مشتری مجاز، مسدودسازی ۱۰۰٪ کدهای مخرب و محدودیت خواندنی SELECT."),
        ("۴. مصورسازی خودکار و تحلیل هوشمند روایی", "تولید هم‌زمان جدول اطلاعاتی، نمودار آماری تعاملی و یک پاراگراف تحلیل هوشمند به همراه پیش‌بینی روندهای آتی و توصیه‌های تجاری."),
    ]

    for i, (title, body) in enumerate(sol_cards):
        top = Inches(1.5 + i * 1.3)
        add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), top, Inches(11.733), Inches(1.15), WHITE, border_color=EMERALD_BORDER)
        # Green edge highlight
        add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, Inches(12.3), top + Inches(0.15), Inches(0.15), Inches(0.85), EMERALD)
        add_textbox(s, Inches(1.0), top + Inches(0.15), Inches(11.1), Inches(0.4), title, size=17, bold=True, color=EMERALD_DARK, align=PP_ALIGN.RIGHT)
        add_textbox(s, Inches(1.0), top + Inches(0.55), Inches(11.1), Inches(0.5), body, size=13, color=SLATE_700, align=PP_ALIGN.RIGHT)

    footer(s, 3, total)

    # =========================================================================
    # SLIDE 4: PRODUCT CAPABILITIES & DEMO
    # =========================================================================
    s = prs.slides.add_slide(blank)
    add_shape(s, MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height, WHITE)
    header(s, "PRODUCT EXPERIENCE  |  دمو و قابلیت‌های کاربری", "تجربه کاربری یکپارچه، سبک، با سرعت پاسخگویی زیر ۲ ثانیه")

    # Left: Feature list
    add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.5), Inches(5.8), Inches(5.2), CREAM, border_color=RGBColor(0xCB, 0xD5, 0xE1))
    add_textbox(s, Inches(1.1), Inches(1.7), Inches(5.2), Inches(0.45), "ویژگی‌های ارگونومیک داشبورد", size=18, bold=True, color=EMERALD_DARK, align=PP_ALIGN.RIGHT)
    add_bullets(
        s,
        Inches(1.1),
        Inches(2.25),
        Inches(5.2),
        Inches(4.2),
        [
            "اقدامات سریع (Quick Prompts) با یک کلیک برای سوالات پرکاربرد مدیران",
            "نمایش شفاف کوئری SQL تولیدشده همراه با زمان‌سنجی دقیق اجرای دیتابیس",
            "رسم خودکار نمودارهای میله‌ای، افقی و هیستوگرام متناسب با ابعاد داده",
            "قابلیت تغییر آسان موتور هوش مصنوعی میان AvalAI (ابری) و Ollama (محلی)",
            "خروجی رسمی فوری به فرمت اکسل (Excel) و گزارش سازمانی PDF",
            "پنل مدیریت کاربران، نقش‌های دسترسی و نظرسنجی رضایت کاربران",
        ],
        size=13,
        color=SLATE_800,
        space_after=9,
    )

    # Right: KPI Cards / Product Metrics
    kpi_cards = [
        ("زیر ۲ ثانیه", "سرعت تولید و اجرای کوئری", "بهینه‌سازی شده در خط پردازش SQL"),
        ("۱۰۰٪ ایمن", "جداسازی داده در سطح مشتری", "Row-Level Scoping بدون نشت"),
        ("دو زبانه", "پشتیبانی فارسی و انگلیسی", "تطبیق خودکار با عبارات محاوره‌ای"),
        ("۳ کلیک", "از ورود تا خروجی اکسل/PDF", "بدون نیاز به نصب نرم‌افزار اضافی"),
    ]
    for i, (kpi, label, sub) in enumerate(kpi_cards):
        col = i % 2
        row = i // 2
        left = Inches(7.0 + col * 2.8)
        top = Inches(1.5 + row * 2.6)
        add_kpi_card(s, left, top, Inches(2.6), Inches(2.4), kpi, label, sub)

    footer(s, 4, total)

    # =========================================================================
    # SLIDE 5: TECHNICAL ARCHITECTURE & SECURITY
    # =========================================================================
    s = prs.slides.add_slide(blank)
    add_shape(s, MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height, CREAM)
    header(s, "TECHNICAL ARCHITECTURE  |  معماری فنی و امنیت بانکی", "معماری ماژولار با خط لوله ۷ مرحله‌ای امن‌سازی و پردازش کوئری")

    # 4 Architecture layers cards
    arch_layers = [
        ("لایه ۱: دسترسی و احراز هویت (Identity)", "سیستم ورود امن با کپچای ضدبات، مدیریت نشست‌های رمزنگاری‌شده، نقش‌های RBAC (کاربر، کارشناس BI، مدیر ارشد) و تفکیک مشتریان."),
        ("لایه ۲: خط تبدیل متن به زبان داده (Text-to-SQL)", "پرامپت‌های مهندسی‌شده با قوانین سختگیرانه JSON، تزریق متادیتای پایگاه‌داده و مدل‌های زبانی فارسی برای استخراج دقیق ساختار SQL."),
        ("لایه ۳: گاردریل امنیتی و اسکوپینگ (SQL Guard)", "بررسی AST دستورات، مسدودسازی قطعی توابع مخرب (DROP/UPDATE/INSERT)، بازنویسی خودکار کوئری با Customer Scope و محدودسازی رکوردها."),
        ("لایه ۴: موتور تحلیل روایی و پیش‌بینی (Narrative AI)", "محاسبه شاخص‌های توصیفی (رشد، سهم بازار، میانه، انحراف معیار) و فراخوانی مجدد LLM جهت تدوین تحلیل تحلیلی و هشدار روندهای منفی."),
    ]

    for i, (title, desc) in enumerate(arch_layers):
        top = Inches(1.5 + i * 1.3)
        add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), top, Inches(11.733), Inches(1.15), WHITE, border_color=EMERALD_BORDER)
        add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.0), top + Inches(0.2), Inches(0.9), Inches(0.75), EMERALD_LIGHT)
        add_textbox(s, Inches(1.0), top + Inches(0.3), Inches(0.9), Inches(0.5), f"#{i+1}", size=18, bold=True, color=EMERALD_DARK, align=PP_ALIGN.CENTER)
        add_textbox(s, Inches(2.1), top + Inches(0.15), Inches(10.2), Inches(0.4), title, size=16, bold=True, color=EMERALD_DARK, align=PP_ALIGN.RIGHT)
        add_textbox(s, Inches(2.1), top + Inches(0.55), Inches(10.2), Inches(0.5), desc, size=13, color=SLATE_700, align=PP_ALIGN.RIGHT)

    footer(s, 5, total)

    # =========================================================================
    # SLIDE 6: MARKET SIZE & TARGET AUDIENCE
    # =========================================================================
    s = prs.slides.add_slide(blank)
    add_shape(s, MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height, CREAM)
    header(s, "MARKET OPPORTUNITY  |  فرصت و اندازه بازار", "بازار بزرگ بیش از ۴ میلیارد تراکنش ماهانه در نظام بانکی و پرداخت ایران")

    # TAM / SAM / SOM Boxes
    tam_boxes = [
        ("TAM: بازار کل هوش تجاری و هوش مصنوعی", "بیش از ۳۵۰ میلیون دلار", "کل بازار نرم‌افزارهای BI، انبار داده و دستیاران هوش مصنوعی سازمانی در خاورمیانه و صنایع مالی ایران"),
        ("SAM: بازار پرداخت و بانکداری الکترونیک", "بیش از ۵۰ میلیون دلار", "۱۲ شرکت PSP، بیش از ۳۰ بانک و موسسه مالی، و بیش از ۱۵۰ پرداخت‌یار فعال متصل به شاپرک"),
        ("SOM: سهم بازار هدف در ۲ سال نخست", "۵ میلیون دلار (۵۰+ سازمان)", "دستیابی به ۴ شرکت PSP برتر، ۱۰ بانک بزرگ و ۳۰ هلدینگ زنجیره‌ای بزرگ خرده‌فروشی"),
    ]

    for i, (title, figure, desc) in enumerate(tam_boxes):
        left = Inches(0.8 + i * 3.98)
        add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, left, Inches(1.5), Inches(3.78), Inches(3.2), WHITE, border_color=EMERALD_BORDER)
        add_textbox(s, left + Inches(0.2), Inches(1.7), Inches(3.38), Inches(0.5), title, size=13, bold=True, color=SLATE_700, align=PP_ALIGN.CENTER)
        add_textbox(s, left + Inches(0.2), Inches(2.3), Inches(3.38), Inches(0.8), figure, size=24, bold=True, color=EMERALD_DARK, align=PP_ALIGN.CENTER)
        add_textbox(s, left + Inches(0.2), Inches(3.2), Inches(3.38), Inches(1.3), desc, size=12, color=MUTED, align=PP_ALIGN.CENTER)

    # Target Customers bottom banner
    add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(4.9), Inches(11.733), Inches(1.8), BG_DARK, EMERALD_DARK)
    add_textbox(s, Inches(1.1), Inches(5.05), Inches(11.1), Inches(0.4), "مشتریان هدف و بهره‌برداران کلیدی سامانه:", size=16, bold=True, color=EMERALD_LIGHT, align=PP_ALIGN.RIGHT)
    add_textbox(
        s,
        Inches(1.1),
        Inches(5.5),
        Inches(11.1),
        Inches(1.0),
        "۱. مدیران ارشد و هیئت‌مدیره PSPها (پایش آنی سهم بازار و سودآوری)   •   ۲. مدیران بازاریابی و امور پذیرندگان (شناسایی پایانه‌های کم‌کارکرد و وفادار)\n۳. مدیران ریسک و امنیت (کشف رفتار مشکوک و مغایرت‌های تسویه)   •   ۴. شرکت‌های پرداخت‌یار و فروشگاه‌های زنجیره‌ای بزرگ",
        size=13,
        color=WHITE,
        align=PP_ALIGN.RIGHT,
    )

    footer(s, 6, total)

    # =========================================================================
    # SLIDE 7: BUSINESS & MONETIZATION MODEL
    # =========================================================================
    s = prs.slides.add_slide(blank)
    add_shape(s, MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height, CREAM)
    header(s, "BUSINESS MODEL  |  مدل درآمدی و تجاری‌سازی", "جریان‌های متنوع درآمدی B2B با تکیه بر استقرار On-Premise و لایسنس سالانه")

    plans = [
        ("لایسنس پایه (Starter)", "مناسب پرداخت‌یارها و فین‌تک‌ها", "استقرار متمرکز ابری خصوصی\nتا ۵۰ کاربر فعال\nپشتیبانی از دیتابیس‌های رابطه‌ای\nبه‌روزرسانی فصلی مدل‌ها", "اشتراک ماهانه / سالانه"),
        ("سازمانی (Enterprise)", "مناسب شرکت‌های PSP و بانک‌ها", "استقرار کامل On-Premise\nکاربران نامحدود و دسترسی سازمانی\nتیونینگ مدل زبانی با دیتای بانکی\nپشتیبانی ۲۴/۷ و SLA اختصاصی", "لایسنس سالانه + پشتیبانی"),
        ("خدمات شخصی‌سازی (Customization)", "اتصال به Core Banking و انبار داده", "یکپارچه‌سازی با Oracle/ClickHouse\nطراحی داشبوردهای اختصاصی هیئت‌مدیره\nآموزش پرسنل و مشاوره استقرار BI", "قرارداد پروژه‌ای"),
    ]

    for i, (title, sub, features, tag) in enumerate(plans):
        left = Inches(0.8 + i * 3.98)
        bg = WHITE if i != 1 else EMERALD_LIGHT
        border = EMERALD_BORDER if i != 1 else EMERALD
        add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, left, Inches(1.5), Inches(3.78), Inches(5.2), bg, border, border_width=2 if i == 1 else 1)
        
        # Tag
        add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, left + Inches(0.4), Inches(1.75), Inches(2.98), Inches(0.4), EMERALD_DARK if i == 1 else SLATE_100)
        add_textbox(s, left + Inches(0.4), Inches(1.8), Inches(2.98), Inches(0.35), tag, size=11, bold=True, color=WHITE if i == 1 else SLATE_700, align=PP_ALIGN.CENTER)

        add_textbox(s, left + Inches(0.2), Inches(2.35), Inches(3.38), Inches(0.5), title, size=18, bold=True, color=EMERALD_DARK if i == 1 else INK, align=PP_ALIGN.CENTER)
        add_textbox(s, left + Inches(0.2), Inches(2.85), Inches(3.38), Inches(0.4), sub, size=12, color=MUTED, align=PP_ALIGN.CENTER)

        # Bullets
        bullet_items = features.split("\n")
        add_bullets(s, left + Inches(0.3), Inches(3.4), Inches(3.18), Inches(3.0), bullet_items, size=13, color=SLATE_800, space_after=10)

    footer(s, 7, total)

    # =========================================================================
    # SLIDE 8: COMPETITIVE ADVANTAGE
    # =========================================================================
    s = prs.slides.add_slide(blank)
    add_shape(s, MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height, CREAM)
    header(s, "COMPETITIVE ADVANTAGE  |  مزیت‌های رقابتی", "چرا رایامیت در مقایسه با رقبا انتخاب قطعی نظام پرداخت است؟")

    advantages = [
        ("سازگاری عمیق با ادبیات بانکی فارسی", "مدل‌های عمومی خارجی مفاهیمی نظیر «پذیرنده»، «پایانه بی‌سیم»، «تسویه شاپرکی» و «کارمزد سپام» را اشتباه تفسیر می‌کنند، درحالی‌که رایامیت دقیقاً برای اصطلاحات پرداخت ایران کالیبره شده است."),
        ("امنیت کامل داده و استقرار On-Premise", "امکان اجرای ۱۰۰٪ بدون نیاز به اینترنت بین‌الملل و بدون ارتباط با سرورهای خارجی؛ داده‌های حساس بانکی درون دیوار آتشین (Firewall) سازمان باقی می‌مانند."),
        ("رویکرد Zero-Training برای کاربران", "نیازی به ساعت‌ها آموزش کار با ابزارهای پیچیده گزارش‌گیری نیست. هر مدیر یا کارشناس با زبان محاوره‌ای روزمره، همانند چت کردن با دستیار متخصص گزارش می‌گیرد."),
        ("سرعت راه‌اندازی شگفت‌انگیز (زیر ۲ هفته)", "اتصال سریع به پایگاه‌داده‌های موجود بانک یا PSP بدون نیاز به ماه‌ها پروژه سنگین انبار داده؛ ایجاد بازگشت سریع سرمایه (Rapid ROI)."),
    ]

    for i, (adv_title, adv_desc) in enumerate(advantages):
        col = i % 2
        row = i // 2
        left = Inches(0.8 + col * 5.95)
        top = Inches(1.5 + row * 2.6)
        add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, left, top, Inches(5.75), Inches(2.4), WHITE, border_color=EMERALD_BORDER)
        add_textbox(s, left + Inches(0.3), top + Inches(0.25), Inches(5.15), Inches(0.45), f"★  {adv_title}", size=16, bold=True, color=EMERALD_DARK, align=PP_ALIGN.RIGHT)
        add_textbox(s, left + Inches(0.3), top + Inches(0.75), Inches(5.15), Inches(1.5), adv_desc, size=13, color=SLATE_700, align=PP_ALIGN.RIGHT)

    footer(s, 8, total)

    # =========================================================================
    # SLIDE 9: OPERATIONAL USE CASES (سناریوهای واقعی در بهپرداخت ملت)
    # =========================================================================
    s = prs.slides.add_slide(blank)
    add_shape(s, MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height, CREAM)
    header(s, "USE CASES  |  سناریوهای عملیاتی در صنعت پرداخت", "نمونه سوالات واقعی مدیران و نحوه پاسخگویی هوشمند سامانه")

    cases = [
        ("پایش ریزش پذیرندگان (Churn Detection)", "«کدام فروشگاه‌های با تراکنش بالای ۵۰ میلیون تومان، در ۲ هفته گذشته افت بیش از ۳۰ درصدی داشتند؟»", "شناسایی سریع خرابی پایانه یا ورود رقبا قبل از مهاجرت قطعی پذیرنده"),
        ("تحلیل سهم بازار اصناف و شهرها", "«سهم مبلغی تراکنش‌های صنف سوپرمارکت در شهر مشهد در ماه گذشته نسبت به ماه قبل چگونه بوده است؟»", "تصمیم‌گیری استراتژیک برای تخصیص و جمع‌آوری پایانه‌های کارتخوان (POS)"),
        ("ارزیابی کارمزد و سودآوری پذیرنده", "«۱۰ پذیرنده با بالاترین سودآوری کارمزدی برای شرکت در ۳ ماه اخیر را با نمودار نشان بده.»", "تمرکز خدمات VIP و پشتیبانی ویژه روی پذیرندگان طلایی شرکت"),
        ("گزارش‌گیری فوری برای جلسات هیئت‌مدیره", "«خلاصه مقایسه‌ای حجم تراکنش‌های موفق و ناموفق امروز نسبت به میانگین هفته گذشته»", "پاسخگویی لحظه‌ای در صحن جلسه بدون معطلی و بدون درگیری تیم IT"),
    ]

    for i, (title, question, outcome) in enumerate(cases):
        top = Inches(1.5 + i * 1.3)
        add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), top, Inches(11.733), Inches(1.15), WHITE, border_color=EMERALD_BORDER)
        add_textbox(s, Inches(1.0), top + Inches(0.12), Inches(11.1), Inches(0.35), title, size=15, bold=True, color=EMERALD_DARK, align=PP_ALIGN.RIGHT)
        add_textbox(s, Inches(1.0), top + Inches(0.45), Inches(6.0), Inches(0.55), f"پرسش مدیر: {question}", size=12, color=SLATE_900, align=PP_ALIGN.RIGHT)
        # Outcome badge
        add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, Inches(7.2), top + Inches(0.45), Inches(5.1), Inches(0.55), EMERALD_LIGHT)
        add_textbox(s, Inches(7.3), top + Inches(0.5), Inches(4.9), Inches(0.45), f"دست‌آورد تجاری: {outcome}", size=11, bold=True, color=EMERALD_DARK, align=PP_ALIGN.RIGHT)

    footer(s, 9, total)

    # =========================================================================
    # SLIDE 10: PRODUCT ROADMAP
    # =========================================================================
    s = prs.slides.add_slide(blank)
    add_shape(s, MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height, CREAM)
    header(s, "PRODUCT ROADMAP  |  نقشه راه توسعه محصول", "برنامه توسعه ۴ فازی برای تبدیل شدن به مغز متفکر هوش تجاری پرداخت")

    roadmap_steps = [
        ("فاز ۱: نسخه فعلی (تکمیل شده)", "• خط Text-to-SQL بهینه و ایمن\n• اتصال به دیتابیس تراکنش‌ها\n• مصورسازی و تحلیل روایی هوش مصنوعی\n• خروجی اکسل، PDF و مدیریت کاربران"),
        ("فاز ۲: ۳ ماهه آینده", "• تشخیص خودکار ناهنجاری (Anomaly Detection)\n• پیش‌بینی سری‌های زمانی با الگوریتم‌های مالی\n• سیستم آلرتینگ روی افت ناگهانی تراکنش\n• ادغام با انبار داده ClickHouse / Oracle"),
        ("فاز ۳: ۶ ماهه آینده", "• دستیار صوتی فارسی (Voice-to-BI)\n• اتصال به پیام‌رسان‌های سازمانی (بله/تلگرام)\n• گزارش‌گیری زمان‌بندی‌شده خودکار روزانه\n• ماژول بهینه‌سازی پورسانت بازاریاب‌ها"),
        ("فاز ۴: افق یک‌ساله", "• سیستم تصمیم‌یار خودکار (Prescriptive AI)\n• تحلیل رفتار و دسته‌بندی هوشمند مشتریان\n• اتصال یکپارچه با سوییچ بانکی Core\n• لایسنسینگ برای سایر PSPهای منطقه"),
    ]

    for i, (phase, details) in enumerate(roadmap_steps):
        left = Inches(0.8 + i * 2.98)
        add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, left, Inches(1.5), Inches(2.78), Inches(5.2), WHITE, border_color=EMERALD_BORDER)
        # Phase header
        add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, left + Inches(0.2), Inches(1.7), Inches(2.38), Inches(0.6), EMERALD_DARK if i == 0 else BG_CARD_DARK)
        add_textbox(s, left + Inches(0.2), Inches(1.8), Inches(2.38), Inches(0.4), phase.split(":")[0], size=13, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        add_textbox(s, left + Inches(0.15), Inches(2.4), Inches(2.48), Inches(0.4), phase.split(":")[1], size=12, bold=True, color=EMERALD_DARK, align=PP_ALIGN.CENTER)
        
        # Details
        items = [line.replace("• ", "") for line in details.split("\n")]
        add_bullets(s, left + Inches(0.2), Inches(2.9), Inches(2.38), Inches(3.5), items, size=12, color=SLATE_700, space_after=8)

    footer(s, 10, total)

    # =========================================================================
    # SLIDE 11: THE PROPOSAL & ROI (پیشنهاد همکاری و بازگشت سرمایه)
    # =========================================================================
    s = prs.slides.add_slide(blank)
    add_shape(s, MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height, CREAM)
    header(s, "THE PROPOSAL  |  پیشنهاد همکاری و توجیه اقتصادی", "بازگشت سرمایه در کمتر از ۶ ماه با افزایش بهره‌وری و نجات پذیرندگان پرگردش")

    roi_metrics = [
        ("۷۰٪ کاهش", "زمان تهیه گزارش‌های تحلیلی مدیریتی", "از میانگین ۳ روز به کمتر از چند ثانیه"),
        ("۱۵٪ کاهش", "ریزش پذیرندگان کلیدی با پایش زودهنگام", "حفظ حداقل ۲۰ میلیارد ریال گردش در ماه"),
        ("۸۰٪ کاهش", "بار کاری تکراری تیم‌های پایگاه داده و BI", "آزادسازی زمان تیم فنی برای پروژه‌های زیرساختی"),
        ("زیر ۳۰ روز", "مدت زمان پیاده‌سازی و استقرار اولیه", "بدون وقفه در فرآیندهای روزمره سازمان"),
    ]

    for i, (num, title, sub) in enumerate(roi_metrics):
        col = i % 2
        row = i // 2
        left = Inches(0.8 + col * 5.95)
        top = Inches(1.5 + row * 1.9)
        add_kpi_card(s, left, top, Inches(5.75), Inches(1.75), num, title, sub)

    # Offer banner
    add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(5.45), Inches(11.733), Inches(1.4), EMERALD_DARK)
    add_textbox(s, Inches(1.1), Inches(5.55), Inches(11.1), Inches(0.4), "پیشنهاد فاز پایلوت (Pilot Program):", size=16, bold=True, color=WHITE, align=PP_ALIGN.RIGHT)
    add_textbox(
        s,
        Inches(1.1),
        Inches(5.95),
        Inches(11.1),
        Inches(0.75),
        "اجرای آزمایشی ۳۰ روزه در یکی از معاونت‌های بهپرداخت ملت با اتصال به داده‌های منتخب • ارائه گزارش عملکرد تحلیلی و مقایسه‌ای • سنجش رضایت مدیران و اثبات کارایی بدون هزینه اولیه زیرساخت",
        size=13,
        color=EMERALD_LIGHT,
        align=PP_ALIGN.RIGHT,
    )

    footer(s, 11, total)

    # =========================================================================
    # SLIDE 12: CLOSING & Q&A
    # =========================================================================
    s = prs.slides.add_slide(blank)
    add_shape(s, MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height, BG_DARK)
    add_shape(s, MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.4), prs.slide_height, EMERALD)
    add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, Inches(9.2), Inches(-1.5), Inches(5.5), Inches(4.5), BG_CARD_DARK)
    add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, Inches(-1.0), Inches(5.0), Inches(4.5), Inches(3.5), BG_CARD_DARK)

    add_textbox(s, Inches(1.0), Inches(1.8), Inches(11.333), Inches(0.7), "آینده هوش تجاری در صنعت پرداخت با مکالمه آغاز می‌شود", size=32, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_textbox(s, Inches(1.5), Inches(2.6), Inches(10.333), Inches(0.8), "سامانه رایامیت (BiChart) آماده ایجاد تحول در تصمیم‌گیری‌های داده‌محور شماست.", size=18, color=EMERALD_LIGHT, align=PP_ALIGN.CENTER)

    # Contact & Links Card
    add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, Inches(3.0), Inches(3.6), Inches(7.333), Inches(2.2), BG_CARD_DARK, EMERALD_DARK, border_width=1.5)
    add_textbox(s, Inches(3.2), Inches(3.85), Inches(6.933), Inches(0.4), "راه‌های ارتباطی و مشاهده دمو زنده:", size=16, bold=True, color=EMERALD_BORDER, align=PP_ALIGN.CENTER)
    add_textbox(
        s,
        Inches(3.2),
        Inches(4.35),
        Inches(6.933),
        Inches(1.2),
        "نشانی وب‌سایت دمو: bichart.local  /  درگاه سازمانی بهپرداخت ملت\nایمیل تیم محصول: product@bichart.ir\nمستندات معماری و کاتالوگ قابلیت‌ها در پوشه docs/",
        size=14,
        color=WHITE,
        align=PP_ALIGN.CENTER,
    )

    add_textbox(s, Inches(1.0), Inches(6.1), Inches(11.333), Inches(0.6), "از توجه و همراهی شما سپاسگزاریم  •  پرسش و پاسخ (Q&A)", size=22, bold=True, color=EMERALD, align=PP_ALIGN.CENTER)
    footer(s, 12, total, dark_mode=True)

    # Save presentation
    out_dir = base_dir / "docs" / "presentations"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "BiChart_Rayamate_Pitch_Deck.pptx"
    prs.save(str(out_file))
    print(f"[SUCCESS] Saved Pitch Deck PPTX to: {out_file}")
    return out_file


if __name__ == "__main__":
    build_pitch_deck()
