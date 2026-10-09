"""Shared state + helpers for the guardrail middleware.

Every guardrail appends events to `guard_events` in the agent state; the UI turns
them into the guardrail timeline chips (⚡ Keyword ✓ · 🧠 Jev ✓ · 🔏 PII 3 redacted …).
"""
import operator
import time
from typing import Annotated, Any, Literal, NotRequired

from langchain.agents import AgentState
from langchain_core.messages import AIMessage, HumanMessage

from agents.schemas import AnswerCard

Layer = Literal["keyword", "jev_input", "pii", "hitl", "grounding"]
Status = Literal["pass", "blocked", "redacted", "flagged", "pending", "info", "error"]


class GuardState(AgentState):
    guard_events: NotRequired[Annotated[list[dict[str, Any]], operator.add]]


def event(layer: Layer, status: Status, label: str, detail: str = "", scores: dict | None = None,
          started: float | None = None) -> dict[str, Any]:
    return {
        "layer": layer,
        "status": status,
        "label": label,
        "detail": detail,
        "scores": scores or {},
        "ms": round((time.perf_counter() - started) * 1000) if started else None,
    }


def last_user_text(state: dict) -> str:
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            content = msg.content
            if isinstance(content, list):
                content = " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
            return content
    return ""


def block(card_title: str, emoji: str, summary: str, insights: list[str], events: list[dict]) -> dict[str, Any]:
    """State update that ends the run with a 'blocked' card — the LLM is never called."""
    card = AnswerCard(title=card_title, emoji=emoji, status="danger", summary=summary, insights=insights)
    return {
        "messages": [AIMessage(content=summary)],
        "structured_response": card,
        "guard_events": events,
        "blocked": True,
    }
