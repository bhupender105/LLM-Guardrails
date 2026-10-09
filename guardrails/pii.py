"""Layer 3 — LangChain's built-in PIIMiddleware.

Thin subclass only to (a) report what was redacted to the guardrail timeline and
(b) turn the `block` strategy's exception into a friendly blocked card.

Key point for the demo: `apply_to_tool_results=True` scrubs the SQL rows BEFORE the
LLM sees them, so the model can't leak what it never received.
"""
import time
from typing import Any

from langchain.agents.middleware import PIIMiddleware, hook_config
from langchain.agents.middleware._redaction import PIIDetectionError
from langgraph.graph.message import add_messages
from langgraph.runtime import Runtime

from guardrails.state import GuardState, block, event

PHONE = r"\+91[\s-]?[6-9]\d{9}"
AADHAAR = r"\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b"
API_KEY = r"\b(sk|AIza)[-_A-Za-z0-9]{20,}\b"

LABELS = {"email": "emails", "phone": "phone numbers", "aadhaar": "Aadhaar numbers",
          "aadhaar_no": "Aadhaar numbers", "credit_card": "card numbers", "api_key": "API keys"}


class TracedPIIMiddleware(PIIMiddleware):
    state_schema = GuardState

    def _count(self, old_messages, new_messages) -> int:
        n = 0
        for old, new in zip(old_messages, new_messages):
            if old is not new and isinstance(old.content, str):
                n += len(self.detector(old.content))
        return n

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: GuardState, runtime: Runtime) -> dict[str, Any] | None:
        started = time.perf_counter()
        try:
            result = super().before_model(state, runtime)
        except PIIDetectionError as e:
            label = LABELS.get(self.pii_type, self.pii_type)
            ev = event("pii", "blocked", "PII guard", f"{label} in input → blocked", started=started)
            return block("Sensitive data detected", "🪪",
                         f"Your message contains **{label}**. For your safety it was blocked and never sent to the LLM "
                         "or written to logs.",
                         ["🔏 Detected by a deterministic PII rule", "🧾 Nothing was stored",
                          "💡 Ask using your student ID instead"], [ev])
        if not result:
            return None
        count = self._count(state["messages"], result["messages"])
        verb = {"redact": "redacted", "mask": "masked", "hash": "hashed"}.get(self.strategy, self.strategy)
        result["guard_events"] = [event("pii", "redacted", "PII guard",
                                        f"{count} {LABELS.get(self.pii_type, self.pii_type)} {verb}", started=started)]
        return result


def pii_middleware() -> list[PIIMiddleware]:
    return [
        # Input: block secrets and national IDs outright
        TracedPIIMiddleware("aadhaar", detector=AADHAAR, strategy="block", apply_to_input=True),
        TracedPIIMiddleware("credit_card", strategy="block", apply_to_input=True),
        TracedPIIMiddleware("api_key", detector=API_KEY, strategy="block", apply_to_input=True),
        # Input + tool results: scrub contact details before the LLM sees them
        TracedPIIMiddleware("email", strategy="redact", apply_to_input=True, apply_to_tool_results=True),
        TracedPIIMiddleware("phone", detector=PHONE, strategy="mask", apply_to_input=True, apply_to_tool_results=True),
        TracedPIIMiddleware("aadhaar_no", detector=AADHAAR, strategy="redact", apply_to_input=False,
                            apply_to_tool_results=True),
    ]


_RULES = pii_middleware()


def scrub_messages(messages: list) -> dict[str, Any]:
    """Run every PII rule in order over the user message + latest tool results; each sees the previous
    one's output. Returns a state update, or a blocked card (`blocked=True`) if a block rule matched."""
    events: list[dict] = []
    for mw in _RULES:
        out = mw.before_model({"messages": messages}, None)
        if not out:
            continue
        if out.get("blocked"):
            return {**out, "guard_events": events + out["guard_events"]}
        messages = add_messages(messages, out["messages"])  # same ids → replaces the redacted messages
        events += out.get("guard_events", [])
    return {"messages": messages, "guard_events": events} if events else {}
