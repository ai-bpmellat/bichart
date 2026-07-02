"""
memory_manager.py
------------------
Keeps the running conversation in memory for the current process AND
persists it to history.json on disk, so history survives a server restart.

Each message dict has the shape:
{
    "timestamp": "...",
    "customer_id": ...,
    "user_question": "...",
    "sql": "...",
    "explanation": "...",
    "row_count": 12,
    "analysis": "...",
}
"""

import json
import os
import threading
import datetime

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.json")


class MemoryManager:
    def __init__(self, history_path: str = HISTORY_FILE):
        self.history_path = history_path
        self._lock = threading.Lock()
        self.messages = []  # in-memory list for the current session
        self.load_from_disk()

    def add_message(self, **kwargs) -> dict:
        """Add a message to in-memory history and persist immediately."""
        entry = {"timestamp": datetime.datetime.now().isoformat(), **kwargs}
        with self._lock:
            self.messages.append(entry)
            self.save_to_disk()
        return entry

    def get_context(self, n: int = 5) -> list:
        """Return the last n messages, useful as conversational context for the model."""
        with self._lock:
            return self.messages[-n:]

    def update_last_analysis(self, analysis: str, user_question: str | None = None) -> None:
        """Attach analysis to the most recent turn (optionally matching question)."""
        with self._lock:
            if not self.messages:
                return
            target = self.messages[-1]
            if user_question is not None:
                for entry in reversed(self.messages):
                    if entry.get("user_question") == user_question:
                        target = entry
                        break
            target["analysis"] = analysis
            self.save_to_disk()

    def save_to_disk(self):
        """Write the full in-memory history out to history.json (overwrite)."""
        try:
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(self.messages, f, ensure_ascii=False, indent=2, default=str)
        except OSError as e:
            print(f"[memory_manager] Warning: could not write history.json: {e}")

    def load_from_disk(self):
        """Load prior history from history.json if it exists, into memory."""
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    self.messages = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"[memory_manager] Warning: could not read history.json ({e}); starting fresh.")
                self.messages = []
        else:
            self.messages = []


# Single shared instance used across the app's lifetime
memory = MemoryManager()
