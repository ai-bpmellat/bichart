"""LLM provider factory (port/adapter style)."""

from __future__ import annotations

from types import ModuleType

from modules.llm import avalai, ollama

VALID_PROVIDERS = frozenset({"ollama", "avalai"})


def get_llm_client(provider: str) -> ModuleType:
    if provider == "avalai":
        return avalai
    return ollama
