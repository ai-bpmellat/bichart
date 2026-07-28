"""Persian display labels for English DB / SQL column names.

Database columns stay English; this map is only for UI and export headers.
"""

from __future__ import annotations

import re
from typing import Any

# Exact column / common alias -> Persian header
COLUMN_LABELS: dict[str, str] = {
    # dim_date
    "date_key": "کلید تاریخ",
    "full_date": "تاریخ",
    "day_name": "نام روز",
    "month_name": "نام ماه",
    "year": "سال",
    "month": "ماه",
    "day": "روز",
    "is_weekend": "آخر هفته",
    "is_holiday": "تعطیل",
    # dim_customer
    "customer_id": "شناسه مشتری",
    "customer_name": "نام مشتری",
    "access_key": "کلید دسترسی",
    "role": "نقش",
    # dim_category
    "category_id": "شناسه دسته‌بندی",
    "category_name": "نام دسته‌بندی",
    "category": "دسته‌بندی",
    # dim_merchant
    "merchant_id": "شناسه پذیرنده",
    "merchant_name": "نام پذیرنده",
    "merchant_code": "کد پذیرنده",
    "mcc": "کد صنف (MCC)",
    "city": "شهر",
    "owner_customer_id": "شناسه مشتری مالک",
    "is_active": "فعال",
    # dim_terminal
    "terminal_id": "شناسه ترمینال",
    "terminal_serial": "سریال ترمینال",
    "terminal_type": "نوع ترمینال",
    "install_date": "تاریخ نصب",
    "status": "وضعیت",
    # fact_transactions
    "transaction_id": "شناسه تراکنش",
    "transaction_time": "زمان تراکنش",
    "amount": "مبلغ",
    "currency": "واحد پول",
    "card_pan_masked": "شماره کارت",
    "response_code": "کد پاسخ",
    "settlement_date": "تاریخ تسویه",
    "channel": "کانال",
    # common query aliases / aggregates
    "transaction_count": "تعداد تراکنش",
    "txn_count": "تعداد تراکنش",
    "tx_count": "تعداد تراکنش",
    "cnt": "تعداد",
    "count": "تعداد",
    "row_count": "تعداد ردیف",
    "total_amount": "مجموع مبلغ",
    "sum_amount": "مجموع مبلغ",
    "amount_sum": "مجموع مبلغ",
    "total_sales": "مجموع فروش",
    "total_volume": "مجموع حجم تراکنش",
    "avg_amount": "میانگین مبلغ",
    "average_amount": "میانگین مبلغ",
    "min_amount": "حداقل مبلغ",
    "max_amount": "حداکثر مبلغ",
    "transaction_month": "ماه تراکنش",
    "txn_month": "ماه تراکنش",
    "year_month": "سال-ماه",
    "ym": "سال-ماه",
    "avg_growth": "میانگین نرخ رشد",
    "growth_rate": "نرخ رشد",
    "growth": "رشد",
    "sales": "فروش",
    "volume": "حجم",
    "name": "نام",
    "id": "شناسه",
    "rank": "رتبه",
    "pct": "درصد",
    "percent": "درصد",
    "percentage": "درصد",
    "share": "سهم",
    "ratio": "نسبت",
}

# Word tokens used when falling back for unknown snake_case keys
_WORD_FA: dict[str, str] = {
    "date": "تاریخ",
    "key": "کلید",
    "full": "کامل",
    "day": "روز",
    "name": "نام",
    "month": "ماه",
    "year": "سال",
    "is": "",
    "weekend": "آخر هفته",
    "holiday": "تعطیل",
    "customer": "مشتری",
    "id": "شناسه",
    "access": "دسترسی",
    "role": "نقش",
    "category": "دسته‌بندی",
    "merchant": "پذیرنده",
    "code": "کد",
    "mcc": "MCC",
    "city": "شهر",
    "owner": "مالک",
    "active": "فعال",
    "terminal": "ترمینال",
    "serial": "سریال",
    "type": "نوع",
    "install": "نصب",
    "status": "وضعیت",
    "transaction": "تراکنش",
    "txn": "تراکنش",
    "tx": "تراکنش",
    "time": "زمان",
    "amount": "مبلغ",
    "currency": "واحد پول",
    "card": "کارت",
    "pan": "PAN",
    "masked": "ماسک‌شده",
    "response": "پاسخ",
    "settlement": "تسویه",
    "channel": "کانال",
    "count": "تعداد",
    "cnt": "تعداد",
    "total": "مجموع",
    "sum": "جمع",
    "avg": "میانگین",
    "average": "میانگین",
    "min": "حداقل",
    "max": "حداکثر",
    "growth": "رشد",
    "rate": "نرخ",
    "sales": "فروش",
    "volume": "حجم",
    "row": "ردیف",
    "rank": "رتبه",
    "pct": "درصد",
    "percent": "درصد",
    "percentage": "درصد",
    "share": "سهم",
    "ratio": "نسبت",
    "num": "تعداد",
    "number": "تعداد",
    "qty": "تعداد",
    "quantity": "تعداد",
    "value": "مقدار",
    "price": "قیمت",
    "fee": "کارمزد",
    "approved": "موفق",
    "declined": "ناموفق",
    "reversed": "برگشتی",
}

_RTL_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)


def is_rtl_text(text: str) -> bool:
    return bool(text and _RTL_RE.search(text))


def column_label(key: Any) -> str:
    """Return a Persian header for a column key; keep already-Persian aliases."""
    if key is None:
        return ""
    raw = str(key).strip()
    if not raw:
        return ""
    if raw in COLUMN_LABELS:
        return COLUMN_LABELS[raw]
    lower = raw.lower()
    if lower in COLUMN_LABELS:
        return COLUMN_LABELS[lower]
    if is_rtl_text(raw) or "\u200c" in raw:
        return raw

    # snake_case / camelCase -> tokens
    spaced = re.sub(r"([a-z])([A-Z])", r"\1_\2", raw)
    parts = [p for p in re.split(r"[_\s]+", spaced.lower()) if p]
    if not parts:
        return raw

    translated: list[str] = []
    for part in parts:
        fa = _WORD_FA.get(part)
        if fa is None:
            # unknown token: keep readable Latin rather than inventing Persian
            translated.append(part)
        elif fa:
            translated.append(fa)

    if translated and any(is_rtl_text(t) for t in translated):
        # Persian reads right-to-left; keep token order as written (natural for labels)
        return " ".join(translated)
    return raw.replace("_", " ")
