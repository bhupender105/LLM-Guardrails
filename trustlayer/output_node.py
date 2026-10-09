"""trustlayer_output — the last node of every guarded turn (everything that runs AFTER the agent).

🔍 Grounding: deterministic number tracing (every figure must appear in a SQL result) + ONE Jev call
(`grounded`, `answer_toxicity`). A failing card is downgraded to a visible warning, or withheld if toxic.
A turn blocked by trustlayer_input passes through untouched.
"""
from agents.chat_ui import push_guard_strip
from agents.graph_common import AgentGraphState
from guardrails.hallucination import HallucinationGuard
from trustlayer.trace import stamp

_GROUNDING = HallucinationGuard()


def trustlayer_output_node(state: AgentGraphState) -> dict:
    if state.get("blocked"):
        return {}
    out = _GROUNDING.after_agent(state, None) or {}
    events = stamp(out.get("guard_events", []), "output")
    push_guard_strip(state, events, "done")
    return {**out, "guard_events": events} if out else {}
