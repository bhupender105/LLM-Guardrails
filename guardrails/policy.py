"""Which Jev labels block a turn, and what the user sees when one does.

Thresholds live in `config.JevConfig` so they can be tuned per environment without a deploy. Refusals name
the reason and the way forward, but never echo thresholds or rule wording — nothing an attacker can iterate
against. (The score detail is still written to the trace for the team reviewing it.)
"""
from dataclasses import dataclass
from typing import Any

from config import jev_config


@dataclass(frozen=True, slots=True)
class Reason:
    label: str    # "Toxic content" · "Prompt injection" · "Harmful intent" · "Off-topic"
    detail: str   # scores — for the trace only


def scores_from_answers(answers: dict[str, Any]) -> dict[str, Any]:
    probs = answers["intent"].probabilities
    return {
        "toxicity": round(answers["toxicity"].score, 2),
        "injection": round(answers["prompt_injection"].noul, 2),
        "intent": answers["intent"].choice,
        "harmful": round(probs.get("harmful", 0.0), 2),
        "off_topic": round(probs.get("off_topic", 0.0), 2),
        "pii_request": round(answers["bulk_pii_request"].noul, 2),
    }


def blocking_reasons(s: dict[str, Any]) -> list[Reason]:
    """Every threshold the scores cross, in priority order (first one drives the refusal)."""
    checks = [
        (s["toxicity"] >= jev_config.TOXICITY_BLOCK, Reason("Toxic content", f"toxicity {s['toxicity']:.2f} / 2")),
        (s["injection"] >= jev_config.INJECTION_BLOCK, Reason("Prompt injection", f"injection p={s['injection']:.2f}")),
        (s["harmful"] >= jev_config.HARMFUL_INTENT_BLOCK, Reason("Harmful intent", f"harmful p={s['harmful']:.2f}")),
        (s["off_topic"] >= jev_config.OFF_TOPIC_BLOCK, Reason("Off-topic", f"off-topic p={s['off_topic']:.2f}")),
    ]
    return [r for hit, r in checks if hit]


_TRY = "💡 Try: *“Top 5 companies by average CTC”*"

REFUSALS: dict[str, tuple[str, str, str, list[str]]] = {
    # label → (card title, emoji, summary, insights)
    "Off-topic": ("Outside my scope", "🧭",
                  "I can only help with **student placement analytics** — this question is outside that scope.",
                  ["🎯 Topic guardrail keeps the assistant on-mission", _TRY]),
    "Toxic content": ("Blocked: toxic content", "🛡️",
                      "**I can't help with that request.** It contains language that is abusive or demeaning, "
                      "and it was stopped before reaching the LLM — no tokens spent, no data touched.",
                      ["🧠 Model-based check understands tone, not just keywords", "🧾 Event logged for review", _TRY]),
    "Prompt injection": ("Blocked: prompt injection", "🛡️",
                         "**I can't help with that request.** It looks like an attempt to change or reveal my "
                         "instructions, which stay fixed. It was stopped before reaching the LLM.",
                         ["🧠 Model-based check understands intent, not just keywords", "🧾 Event logged for review", _TRY]),
    "Harmful intent": ("Blocked: harmful intent", "🛡️",
                       "**I can't help with that request.** It asks for something abusive, discriminatory or "
                       "privacy-violating, and it was stopped before reaching the LLM.",
                       ["🧠 Model-based check understands intent, not just keywords", "🧾 Event logged for review", _TRY]),
}


def refusal(reason: Reason, ms: int) -> tuple[str, str, str, list[str]]:
    title, emoji, summary, insights = REFUSALS[reason.label]
    return title, emoji, summary, [*insights, f"⏱️ Decision in {ms} ms"]
