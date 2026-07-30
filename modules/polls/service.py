"""Feature poll persistence + vote aggregation."""

from __future__ import annotations

import json
import os
import threading

from shared.paths import DATA_DIR

FEATURE_POLL_FILE = os.path.join(DATA_DIR, "feature_poll.json")
_feature_poll_lock = threading.Lock()

FEATURE_POLL_OPTIONS = [
    {"id": "anomaly_alerts", "label": "هشدار هوشمند ناهنجاری تراکنش‌ها"},
    {"id": "jalali_calendar", "label": "تقویم شمسی در نمودارها و فیلترها"},
    {"id": "geo_map", "label": "نقشه جغرافیایی تراکنش‌ها"},
    {"id": "scheduled_reports", "label": "گزارش زمان‌بندی‌شده و ارسال خودکار"},
    {"id": "excel_export", "label": "خروجی اکسل و PDF از نتایج"},
    {"id": "telegram_bot", "label": "ربات تلگرام / پیامک هشدار"},
    {"id": "forecast", "label": "پیش‌بینی روند تراکنش‌ها"},
]
FEATURE_POLL_IDS = frozenset(o["id"] for o in FEATURE_POLL_OPTIONS)
FEATURE_POLL_MAX_CHOICES = 3
FEATURE_CUSTOM_MAX_LEN = 100
FEATURE_CUSTOM_PREFIX = "_custom_"


def load_feature_poll() -> dict:
    try:
        with open(FEATURE_POLL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("votes"), dict):
            return data
    except (OSError, ValueError):
        pass
    return {"votes": {}}


def save_feature_poll(data: dict) -> None:
    with open(FEATURE_POLL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def feature_poll_state(username: str) -> dict:
    data = load_feature_poll()
    votes = data["votes"]

    counts: dict[str, int] = {o["id"]: 0 for o in FEATURE_POLL_OPTIONS}
    custom_pool: dict[str, str] = {}
    for selection in votes.values():
        for oid in selection:
            if oid in counts:
                counts[oid] += 1
            elif oid.startswith(FEATURE_CUSTOM_PREFIX):
                label = oid[len(FEATURE_CUSTOM_PREFIX):]
                custom_pool[oid] = label
                counts.setdefault(oid, 0)
                counts[oid] += 1

    return {
        "options": FEATURE_POLL_OPTIONS,
        "custom_options": [{"id": k, "label": v} for k, v in custom_pool.items()],
        "counts": counts,
        "total_voters": len(votes),
        "my_votes": votes.get(username, []),
    }


def cast_votes(username: str, features: list[str]) -> tuple[dict | None, str | None]:
    selection = []
    for f in dict.fromkeys(features):
        if f in FEATURE_POLL_IDS:
            selection.append(f)
        elif f.startswith(FEATURE_CUSTOM_PREFIX):
            label = f[len(FEATURE_CUSTOM_PREFIX):]
            if label and len(label) <= FEATURE_CUSTOM_MAX_LEN:
                selection.append(f)
            elif label:
                return None, "متن گزینه سفارشی حداکثر ۱۰۰ کاراکتر می‌تواند باشد."

    if not selection:
        return None, "حداقل یک قابلیت را انتخاب یا پیشنهاد کنید."
    if len(selection) > FEATURE_POLL_MAX_CHOICES:
        return None, f"حداکثر {FEATURE_POLL_MAX_CHOICES} گزینه قابل انتخاب است."

    with _feature_poll_lock:
        data = load_feature_poll()
        data["votes"][username] = selection
        save_feature_poll(data)
        return {"ok": True, **feature_poll_state(username)}, None


def get_state(username: str) -> dict:
    with _feature_poll_lock:
        return feature_poll_state(username)
