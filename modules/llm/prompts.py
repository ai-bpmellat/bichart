"""Shared analysis prompt rules for AvalAI and Ollama BI analysts."""

ANALYSIS_SYSTEM_RULES = """
You are a senior BI data analyst for a Payment Service Provider.

Accuracy and Quality rules (mandatory):
1. Focus on real business insights: concentration of volume, percentage shares, rank disparities, risks, and actionable recommendations.
2. Do NOT simply restate or list the rows of data with words.
3. Use the provided pre-calculated metrics (totals, percentage shares, ratios) directly instead of guessing or recalculating them.
4. Only describe patterns literally supported by the data. Never invent a trend.
5. Be concise, professional, and specific. Plain text only (no JSON, no markdown headers).
""".strip()

DISCUSSION_SYSTEM_RULES = """
You are a BI discussion partner for a Payment Service Provider report.

The user may challenge data, analysis wording, trends, or conclusions that look wrong or debatable.

Rules:
1. Re-check claims against the provided data numbers. Admit mistakes when the prior analysis was wrong.
2. If the user points at a specific snippet (focus), address that snippet first.
3. When correcting a trend, describe consecutive period changes accurately (up/down/flat). Never invent continuous decline.
4. Be concise, concrete, and open to debate. Plain text only (no JSON, no markdown headers).
5. If evidence is insufficient, say what is missing instead of guessing.
6. When correcting a specific focus snippet, end your reply with a marked replacement block — only the corrected text for that snippet, not the full analysis:
CORRECTED_SNIPPET:
<replacement text for the focus snippet only>
""".strip()


def build_analysis_prompt(
    data_json: str,
    user_question: str,
    precomputed_stats: dict | None = None,
) -> str:
    stats = precomputed_stats or {}
    intent = stats.get("intent_type", "comparison")
    col = stats.get("column", "مقدار")

    if intent == "forecast":
        lines = []
        if "estimated_growth_prob_pct" in stats:
            lines.append(f"• احتمال برآوردشده برای رشد در دوره/ماه آینده: {stats.get('estimated_growth_prob_pct')}٪")
        if "projected_next_value" in stats:
            lines.append(f"• مقدار پیش‌بینی‌شده برای دوره آینده: {stats.get('projected_next_value')} (بازه برآوردی: {stats.get('projected_range_low')} تا {stats.get('projected_range_high')})")
        if "avg_growth_pct" in stats:
            lines.append(f"• میانگین نرخ رشد دوره‌ای (MoM Growth): {stats.get('avg_growth_pct')}٪")
        if "momentum_label" in stats:
            lines.append(f"• شتاب و شیوه‌وضعیت روند: {stats.get('momentum_label')}")
        if "latest_vs_avg_pct" in stats:
            lines.append(f"• مقایسه دوره اخیر با میانگین تاریخی: {stats.get('latest_vs_avg_pct')}٪ انحراف از میانگین")
        if "latest_val" in stats:
            lines.append(f"• آخرین مقدار ثبت‌شده {col}: {stats.get('latest_val')}")

        stats_block = (
            "\nشاخص‌ها، آمار مقایسه‌ای و محاسبات پیش‌بینی (این اعداد را مستقیماً در پاسخ استفاده کن):\n"
            + "\n".join(lines)
            + "\n"
        )
        instructions = (
            "پاسخ خود را دقیقاً بر اساس ۵ بخش زیر و تماماً در قالب **بولت پوینت (Bullet Points)** تنظیم کن:\n\n"
            "📌 **خلاصه اجرایی و پاسخ مستقیم:**\n"
            "• پاسخ شفاف به سوال کاربر درباره احتمال رشد/پیش‌بینی و اعلام درصد برآوردی احتمال رشد.\n\n"
            "🔮 **پیش‌بینی و برآوردهای کمّی آینده:**\n"
            "• عدد پیش‌بینی‌شده دوره بعد و بازه حداقل-حداکثر برآوردی.\n"
            "• شتاب تغییرات و مومنتوم رشد.\n\n"
            "📊 **تحلیل آماری و مقایسه‌ای تاریخی:**\n"
            "• میانگین رشد دوره‌ای و مقایسه آخرین دوره ثبت‌شده با میانگین کل دوره.\n"
            "• ثبات روند و نوسانات شاخص.\n\n"
            "⚠️ **ارزیابی ریسک و نقاط انحراف:**\n"
            "• ریسک‌های محقق نشدن پیش‌بینی و متغیرهای کلیدی بازار.\n\n"
            "🎯 **پیشنهادهای عملیاتی بازاریابی:**\n"
            "• ۲ پیشنهاد کاربردی برای تیم بازاریابی و فروش جهت تحقق رشد."
        )

    elif intent == "churn":
        lines = []
        if "drop_from_peak_pct" in stats:
            lines.append(f"• درصد افت از اوج (Peak Drop): {stats.get('drop_from_peak_pct')}٪")
        if "latest_vs_avg_pct" in stats:
            lines.append(f"• مقایسه وضعیت فعلی با میانگین تاریخی: {stats.get('latest_vs_avg_pct')}٪ انحراف")
        if "latest_val" in stats and "max_val" in stats:
            lines.append(f"• مقدار اوج: {stats.get('max_val')} | مقدار اخیر: {stats.get('latest_val')}")
        if "avg_growth_pct" in stats:
            lines.append(f"• میانگین نرخ تغییرات: {stats.get('avg_growth_pct')}٪")

        stats_block = (
            "\nشاخص‌ها و محاسبات آماری مقایسه‌ای ریزش (این اعداد را مستقیماً استفاده کن):\n"
            + "\n".join(lines)
            + "\n"
        )
        instructions = (
            "پاسخ خود را دقیقاً بر اساس ۵ بخش زیر و تماماً در قالب **بولت پوینت (Bullet Points)** تنظیم کن:\n\n"
            "📌 **خلاصه اجرایی و وضعیت افت:**\n"
            "• درصد دقیق افت/ریزش و شدت تغییرات.\n\n"
            "📊 **تحلیل آماری و مقایسه‌ای:**\n"
            "• مقایسه نقطه اوج با وضعیت فعلی و انحراف از میانگین تاریخی.\n\n"
            "🔮 **پیش‌بینی ادامه روند ریزش:**\n"
            "• برآورد ادامه افت یا احتمال بازگشت در دوره بعدی.\n\n"
            "⚠️ **ارزیابی ریسک و اثرات کسب‌وکار:**\n"
            "• خطرات مالی و اثر بر درآمد شرکت.\n\n"
            "🎯 **راهکارهای عملیاتی بازاریابی و نگه‌داشت:**\n"
            "• پیشنهادهای سریع بازاریابی برای مهار ریزش و حفظ مشتریان."
        )

    elif intent == "ranking":
        lines = []
        if "total_sum" in stats:
            lines.append(f"• مجموع کل {col}: {stats.get('total_sum'):,}" if isinstance(stats.get('total_sum'), (int, float)) else f"• مجموع کل {col}: {stats.get('total_sum')}")
        if "top_share_pct" in stats:
            lines.append(f"• سهم بالاترین مورد از کل (پارتو): {stats.get('top_share_pct')}٪")
        if "top_vs_avg_ratio" in stats:
            lines.append(f"• نسبت عملکرد رتبه اول به میانگین کل: {stats.get('top_vs_avg_ratio')} برابر میانگین")
        if "top_3_share_pct" in stats and stats.get("top_3_share_pct") is not None:
            lines.append(f"• سهم ۳ مورد اول از کل: {stats.get('top_3_share_pct')}٪")
        if "top_to_bottom_ratio" in stats and stats.get("top_to_bottom_ratio") is not None:
            lines.append(f"• نسبت رتبه اول به پایین‌ترین مورد: {stats.get('top_to_bottom_ratio')} برابر")

        stats_block = (
            "\nمحاسبات آماده آماری، مقایسه‌ای و سهم بازار (این اعداد را مستقیماً استفاده کن):\n"
            + "\n".join(lines)
            + "\n"
        )
        instructions = (
            "پاسخ خود را دقیقاً بر اساس ۵ بخش زیر و تماماً در قالب **بولت پوینت (Bullet Points)** تنظیم کن:\n\n"
            "📌 **خلاصه وضعیت سهم و رتبه‌بندی:**\n"
            "• میزان تمرکز بازار و سهم رتبه‌های برتر.\n\n"
            "📊 **تحلیل آماری و مقایسه‌ای:**\n"
            "• مقایسه عملکرد رتبه ۱ با میانگین کل (چند برابر میانگین).\n"
            "• سهم تراکمی ۳ مورد اول از کل volume.\n\n"
            "🔮 **پیش‌بینی تغییر سهم بازار:**\n"
            "• برآورد روند جابجایی رتبه‌ها یا تثبیت جایگاه موارد برتر.\n\n"
            "⚠️ **ارزیابی ریسک‌های بازار:**\n"
            "• ریسک‌های وابستگی شدید به رتبه‌های اول.\n\n"
            "🎯 **پیشنهادهای توسعه سهم بازار:**\n"
            "• راهکارهای بازاریابی برای رشد ردیف‌های پایین‌تر و متوازن‌سازی سهم."
        )

    else:  # comparison / summary
        lines = []
        if "total_sum" in stats:
            lines.append(f"• مجموع کل {col}: {stats.get('total_sum'):,}" if isinstance(stats.get('total_sum'), (int, float)) else f"• مجموع کل {col}: {stats.get('total_sum')}")
        if "avg_val" in stats:
            lines.append(f"• میانگین {col}: {stats.get('avg_val')}")
        if "max_val" in stats and "min_val" in stats:
            lines.append(f"• دامنه تغییرات: از {stats.get('min_val')} تا {stats.get('max_val')}")

        stats_block = (
            "\nخلاصه محاسبات آمار کلیدی:\n"
            + "\n".join(lines)
            + "\n"
        ) if lines else ""
        instructions = (
            "راهنمای ساخت پاسخ تحلیل عمومی:\n"
            "۱. به پرسش کاربر درباره داده‌ها پاسخ بده و الگوی اصلی را توضیح بده.\n"
            "۲. مقایسه یا تفاوت‌های کلیدی را روشن کن.\n"
            "۳. نتیجه‌گیری کوتاه و کاربردی ارائه بده."
        )

    return (
        f"داده‌های زیر نتیجه یک پرس‌وجو برای پاسخ به این سوال کاربر است:\n"
        f"سوال کاربر: {user_question}\n\n"
        f"نمونه داده (JSON):\n{data_json}\n"
        f"{stats_block}\n"
        f"{instructions}\n\n"
        f"مهم: به هیچ وجه پاسخ عمومی و تکراری نده. پاسخ دقیقاً باید در راستای سوال کاربر باشد."
    )


def build_discussion_prompt(
    data_json: str,
    user_question: str,
    analysis: str,
    focus: str,
    history: list,
    user_message: str,
) -> str:
    history_lines = []
    for turn in history or []:
        role = (turn.get("role") or "").strip().lower()
        content = (turn.get("content") or "").strip()
        if not content:
            continue
        label = "User" if role == "user" else "Assistant"
        history_lines.append(f"{label}: {content}")
    history_block = "\n".join(history_lines) if history_lines else "(none yet)"

    return (
        f"Original user question:\n{user_question or '(n/a)'}\n\n"
        f"Current analysis text (may be empty or flawed):\n{analysis or '(none)'}\n\n"
        f"Focus snippet the user wants to discuss (optional):\n{focus or '(entire report)'}\n\n"
        f"Data sample (JSON):\n{data_json}\n\n"
        f"Prior discussion turns:\n{history_block}\n\n"
        f"User's new discussion message:\n{user_message}\n\n"
        "Respond to the discussion. Correct errors when the data disagrees with the analysis."
    )
