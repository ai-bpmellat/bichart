"""
memory_manager.py
------------------
Per-user conversation history + preferences, persisted to history.json.

Disk shape:
{
  "users": {
    "<username>": {
      "preferences": {"provider": "avalai", "language": "fa"},
      "messages": [ {timestamp, user_question, sql, ...}, ... ]
    }
  }
}
"""

from __future__ import annotations

import datetime
import json
import os
import threading
import uuid
from typing import Optional

_BASE = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BASE, "data")
os.makedirs(_DATA_DIR, exist_ok=True)
HISTORY_FILE = os.path.join(_DATA_DIR, "history.json")
FEEDBACK_FILE = os.path.join(_DATA_DIR, "feedback.json")

DEFAULT_PREFERENCES = {
    "provider": "avalai",
    "language": "fa",
}


class MemoryManager:
    def __init__(self, history_path: str = HISTORY_FILE):
        self.history_path = history_path
        self._lock = threading.Lock()
        self.users: dict = {}
        self.load_from_disk()

    def _ensure_user(self, username: str) -> dict:
        key = (username or "anonymous").strip() or "anonymous"
        if key not in self.users:
            self.users[key] = {
                "preferences": dict(DEFAULT_PREFERENCES),
                "messages": [],
            }
        bucket = self.users[key]
        bucket.setdefault("preferences", dict(DEFAULT_PREFERENCES))
        bucket.setdefault("messages", [])
        # Fill missing preference keys with defaults
        for k, v in DEFAULT_PREFERENCES.items():
            bucket["preferences"].setdefault(k, v)
        return bucket

    def add_message(self, username: Optional[str] = None, **kwargs) -> dict:
        """Add a message to the user's in-memory history and persist immediately."""
        entry = {
            "id": kwargs.pop("id", None) or str(uuid.uuid4()),
            "timestamp": datetime.datetime.now().isoformat(),
            **kwargs,
        }
        with self._lock:
            bucket = self._ensure_user(username or kwargs.get("username") or "anonymous")
            if username:
                entry.setdefault("username", username)
            bucket["messages"].append(entry)
            self.save_to_disk()
        return entry

    def get_context(self, username: Optional[str] = None, n: int = 5) -> list:
        """Return the last n messages for a user."""
        with self._lock:
            bucket = self._ensure_user(username or "anonymous")
            return list(bucket["messages"][-n:])

    def update_last_analysis(
        self,
        analysis: str,
        user_question: str | None = None,
        username: Optional[str] = None,
    ) -> None:
        """Attach analysis to the most recent turn (optionally matching question)."""
        with self._lock:
            bucket = self._ensure_user(username or "anonymous")
            messages = bucket["messages"]
            if not messages:
                return
            target = messages[-1]
            if user_question is not None:
                for entry in reversed(messages):
                    if entry.get("user_question") == user_question:
                        target = entry
                        break
            target["analysis"] = analysis
            self.save_to_disk()

    def set_feedback(
        self,
        username: Optional[str],
        message_id: str,
        rating: str,
    ) -> tuple[bool, Optional[str]]:
        """Attach thumbs up/down feedback to a stored message. Returns (ok, error)."""
        if rating not in ("up", "down"):
            return False, "Invalid rating."
        if not message_id:
            return False, "Message id is required."

        with self._lock:
            bucket = self._ensure_user(username or "anonymous")
            target = None
            for entry in bucket["messages"]:
                if entry.get("id") == message_id:
                    target = entry
                    break
            if not target:
                return False, "Message not found."

            feedback = {
                "rating": rating,
                "at": datetime.datetime.now().isoformat(),
            }
            target["feedback"] = feedback
            self.save_to_disk()
            self._append_feedback_log(username or "anonymous", message_id, target, feedback)
        return True, None

    def _append_feedback_log(
        self,
        username: str,
        message_id: str,
        message: dict,
        feedback: dict,
    ) -> None:
        """Persist feedback entries for offline evaluation / prompt tuning."""
        record = {
            "message_id": message_id,
            "username": username,
            "rating": feedback["rating"],
            "at": feedback["at"],
            "user_question": message.get("user_question"),
            "sql": message.get("sql"),
            "explanation": message.get("explanation"),
            "row_count": message.get("row_count"),
            "provider": message.get("provider"),
            "language": message.get("language"),
            "analysis": message.get("analysis"),
        }
        try:
            entries: list = []
            if os.path.exists(FEEDBACK_FILE):
                with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and isinstance(data.get("entries"), list):
                        entries = data["entries"]
            entries.append(record)
            with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
                json.dump({"entries": entries}, f, ensure_ascii=False, indent=2, default=str)
        except OSError as e:
            print(f"[memory_manager] Warning: could not write feedback.json: {e}")

    def get_frequent_questions(self, n: int = 10) -> list:
        """Return the top-n most-asked questions across all users, most frequent first."""
        with self._lock:
            counts: dict[str, dict] = {}
            for bucket in self.users.values():
                for entry in bucket.get("messages", []):
                    q = (entry.get("user_question") or "").strip()
                    if not q or q == "SQL run":
                        continue
                    key = q.lower()
                    info = counts.setdefault(key, {"question": q, "count": 0, "last_asked": ""})
                    info["count"] += 1
                    ts = entry.get("timestamp") or ""
                    if ts > info["last_asked"]:
                        info["last_asked"] = ts
            ranked = sorted(counts.values(), key=lambda x: (x["count"], x["last_asked"]), reverse=True)
            return ranked[:n]

    def get_preferences(self, username: Optional[str] = None) -> dict:
        with self._lock:
            bucket = self._ensure_user(username or "anonymous")
            return dict(bucket["preferences"])

    def set_preferences(self, username: Optional[str], **kwargs) -> dict:
        with self._lock:
            bucket = self._ensure_user(username or "anonymous")
            prefs = bucket["preferences"]
            if "provider" in kwargs and kwargs["provider"] is not None:
                prefs["provider"] = kwargs["provider"]
            if "language" in kwargs and kwargs["language"] is not None:
                prefs["language"] = kwargs["language"]
            self.save_to_disk()
            return dict(prefs)

    def save_to_disk(self):
        try:
            payload = {"users": self.users}
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
        except OSError as e:
            print(f"[memory_manager] Warning: could not write history.json: {e}")

    def load_from_disk(self):
        if not os.path.exists(self.history_path):
            self.users = {}
            return
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[memory_manager] Warning: could not read history.json ({e}); starting fresh.")
            self.users = {}
            return

        # Migrate legacy list format
        if isinstance(data, list):
            self.users = {
                "anonymous": {
                    "preferences": dict(DEFAULT_PREFERENCES),
                    "messages": data,
                }
            }
            self.save_to_disk()
            return

        if isinstance(data, dict) and "users" in data:
            self.users = data.get("users") or {}
            return

        # Unknown shape
        self.users = {}


# Single shared instance used across the app's lifetime
memory = MemoryManager()
