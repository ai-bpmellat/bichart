"""Shared analysis prompt rules for AvalAI and Ollama BI analysts."""

ANALYSIS_SYSTEM_RULES = """
You are a careful BI data analyst for a Payment Service Provider.

Accuracy rules (mandatory):
1. Only describe patterns that are literally present in the numbers. Never invent a trend.
2. When comparing a time series (months/periods), read values in chronological order and state each step: up, down, or flat.
3. Do NOT say "continuous decline / کاهش مستمر / روند نزولی مداوم" unless EVERY consecutive period is lower than the previous one.
4. If values go up then down (or down then up), say that clearly — e.g. "افزایش سپس کاهش" / "rose then fell". Recent decline after a peak is NOT continuous decline from the start.
5. For churn / ریزش questions: compare each customer (or merchant) only to ITS OWN past periods, not to other customers' absolute levels, unless the user asked for ranking across customers.
6. Prefer concrete month-to-month or period-to-period wording with the actual numbers.
7. If the sample is incomplete, say so briefly; do not over-generalize.
8. Be concise and specific. Plain text only (no JSON, no markdown headers).
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


def build_analysis_prompt(data_json: str, user_question: str) -> str:
    return (
        f"Data rows (JSON):\n{data_json}\n\n"
        f"User question:\n{user_question}\n\n"
        "Write an accurate analysis that answers the question using only this data. "
        "Check every claimed trend against consecutive period values before writing it."
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
