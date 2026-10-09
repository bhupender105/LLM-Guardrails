"""Layer 1 — deterministic keyword / regex guardrail (before agent).

Zero LLM cost, ~0 ms, fully predictable. Catches the obvious attacks; it cannot
understand meaning, which is why Jev sits right behind it.
"""
import re
import time
from typing import Any

from langchain.agents.middleware import AgentMiddleware, hook_config
from langgraph.runtime import Runtime

from guardrails.state import GuardState, block, event, last_user_text

RULES: dict[str, list[str]] = {
    "Prompt injection": [
        r"ignore\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|earlier)\s+(instructions|rules|prompts?)",
        r"\bsystem\s+prompt\b",
        r"\byou\s+are\s+now\b",
        r"\bjailbreak\b",
        r"\bDAN\s+mode\b",
    ],
    "Destructive SQL": [
        r"\bdrop\s+table\b",
        r"\btruncate\s+table\b",
        r"\balter\s+table\b",
        r"\bdelete\s+from\s+\w+",
        r";\s*--",
    ],
    "Banned topic": [r"\bhack(ing)?\b", r"\bmalware\b", r"\bexploit\b", r"\bbomb\b"],
}
_COMPILED = {name: [re.compile(p, re.IGNORECASE) for p in pats] for name, pats in RULES.items()}


class KeywordGuardrail(AgentMiddleware):
    state_schema = GuardState
    name = "KeywordGuardrail"

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state: GuardState, runtime: Runtime) -> dict[str, Any] | None:
        started = time.perf_counter()
        text = last_user_text(state)
        for rule, patterns in _COMPILED.items():
            for pattern in patterns:
                if m := pattern.search(text):
                    ev = event("keyword", "blocked", "Keyword filter", f'{rule}: matched "{m.group(0)}"', started=started)
                    return block(
                        "Request blocked by keyword filter", "⛔",
                        f"This request matches a **{rule.lower()}** pattern (`{m.group(0)}`) and was stopped "
                        "before reaching the LLM.",
                        ["⚡ Deterministic rule — zero LLM cost, ~0 ms",
                         "🧾 Logged for the security team",
                         "💡 Rephrase as a normal placement question"],
                        [ev],
                    )
        return {"guard_events": [event("keyword", "pass", "Keyword filter", "no rule matched", started=started)]}
