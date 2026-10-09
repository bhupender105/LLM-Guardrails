"""trustlayer_input — the first node of every guarded turn (everything that runs BEFORE the agent).

Cheapest check first, so a block never pays for the later ones:
  1. ⚡ keyword    — regex rules, ~0 ms, no network
  2. 🧠 jev_input  — ONE Jev call: toxicity · prompt injection · intent · bulk-PII request (~350 ms)
  3. 🔏 pii        — block secrets / national IDs, redact emails + phones in the user message

A block returns the refusal card + `blocked=True`; the graph then skips the LLM and goes straight
to trustlayer_output. Jev is fail-open (an outage is logged as an `error` event, the turn continues).
"""
from agents.chat_ui import new_turn, push_guard_strip
from agents.graph_common import AgentGraphState
from guardrails.jev_input import JevInputGuardrail
from guardrails.keyword import KeywordGuardrail
from guardrails.pii import scrub_messages
from trustlayer.trace import stamp

_CHECKS = (KeywordGuardrail().before_agent, JevInputGuardrail().before_agent)


def trustlayer_input_node(state: AgentGraphState) -> dict:
    events: list[dict] = []
    for check in _CHECKS:
        out = check(state, None) or {}
        events += out.get("guard_events", [])
        if out.get("blocked"):
            events = stamp(events, "input")
            push_guard_strip(state, events, "blocked", fresh=True)
            return {**out, "guard_events": new_turn(events)}

    out = scrub_messages(state["messages"])
    events = stamp(events + out.get("guard_events", []), "input")
    push_guard_strip(state, events, "input", fresh=True)
    return {**out, "guard_events": new_turn(events), "blocked": False, "structured_response": None}
