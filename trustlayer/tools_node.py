"""trustlayer_tools — runs after every `tools` step, before the LLM reads the SQL results.

🔏 Scrubs emails / phones / Aadhaar from the tool output, so the model can't leak what it never received.
"""
from agents.chat_ui import push_guard_strip
from agents.graph_common import AgentGraphState
from guardrails.pii import scrub_messages
from trustlayer.trace import stamp


def trustlayer_tools_node(state: AgentGraphState) -> dict:
    out = scrub_messages(state["messages"])
    if not out:
        return {}
    events = stamp(out.get("guard_events", []), "tools")
    push_guard_strip(state, events, "tools")
    return {**out, "guard_events": events}
