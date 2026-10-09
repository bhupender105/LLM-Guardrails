"""The 'after' agent: same model, prompt and tools — wrapped in the Trust Layer.

    START → trustlayer_input ─┬─► agent ─┬─► tools ─► trustlayer_tools ─► agent …   (ReAct loop)
                              │          ├─► hitl ─┬─► tools                         (update/delete only)
                              │          │         └─► agent                         (everything rejected)
                              │          └─► finalize ─► trustlayer_output ─► respond ─► END
                              └─ blocked ──────────────────► trustlayer_output ─► respond ─► END   (LLM never called)

  trustlayer_input   ⚡ keyword → 🧠 Jev → 🔏 PII          (see trustlayer/input_node.py)
  trustlayer_tools   🔏 scrub SQL results before the LLM    (see trustlayer/tools_node.py)
  trustlayer_output  🔍 grounding + number tracing          (see trustlayer/output_node.py)
  hitl               🧑‍⚖️ interrupt() for human approval
  respond            💬 posts the card as a chat reply (see agents/chat_ui.py)
"""
import time

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from agents.chat_ui import push_guard_strip, respond
from agents.graph_common import (AgentGraphState, finalize, make_agent_node, make_tools_node, pending_calls,
                                 route_after_agent, route_after_finalize)
from agents.llm import get_llm
from agents.tools import count_matching, make_tools
from data.seed_db import DB_PATHS, row_count
from guardrails.state import event
from trustlayer import trustlayer_input_node, trustlayer_output_node, trustlayer_tools_node

# tool name → decisions the human may take
APPROVAL = {
    "delete_student_records": ["approve", "reject"],
    "update_student_records": ["approve", "edit", "reject"],
}


def hitl(state: AgentGraphState) -> dict:
    ai: AIMessage = state["messages"][-1]
    idx = [i for i, tc in enumerate(ai.tool_calls) if tc["name"] in APPROVAL]
    started = time.perf_counter()
    push_guard_strip(state, [event("hitl", "pending", "Human approval", "waiting for a human")], "hitl")
    reviewed = interrupt({
        "action_requests": [{"name": ai.tool_calls[i]["name"], "args": ai.tool_calls[i]["args"],
                             "impact": _impact(ai.tool_calls[i]["args"]),
                             "description": f"Sensitive database write — human approval required\n\n"
                                            f"Tool: {ai.tool_calls[i]['name']}\nArgs: {ai.tool_calls[i]['args']}"}
                            for i in idx],
        "review_configs": [{"action_name": ai.tool_calls[i]["name"],
                            "allowed_decisions": APPROVAL[ai.tool_calls[i]["name"]]} for i in idx],
    })
    calls, rejections = list(ai.tool_calls), []
    for i, d in zip(idx, reviewed["decisions"]):
        tc = calls[i]
        if d["type"] not in APPROVAL[tc["name"]]:
            raise ValueError(f"Decision '{d['type']}' not allowed for {tc['name']}")
        if d["type"] == "edit":
            calls[i] = {**tc, **d["edited_action"]}
        elif d["type"] == "reject":
            rejections.append(ToolMessage(
                f"User rejected the tool call for `{tc['name']}` with reason: {d.get('message')}",
                name=tc["name"], tool_call_id=tc["id"], status="error"))
    kinds = [d["type"] for d in reviewed["decisions"]]
    ev = event("hitl", "blocked" if all(k == "reject" for k in kinds) else "pass", "Human approval",
               "human " + ", ".join({"approve": "approved", "edit": "edited", "reject": "rejected"}[k] for k in kinds),
               {"decisions": kinds}, started)
    push_guard_strip(state, [ev], "hitl-done")
    return {"messages": [ai.model_copy(update={"tool_calls": calls}), *rejections],  # same id → replaces the AI msg
            "guard_events": [{**ev, "phase": "hitl"}]}


def _impact(args: dict) -> dict:
    """Rows the write would touch — shown on the approval card."""
    try:
        return {"affected": count_matching(DB_PATHS["guarded"], args.get("where_clause", "1=0")),
                "total": row_count(DB_PATHS["guarded"])}
    except Exception:
        return {}


def after_input(state: AgentGraphState) -> str:
    return "trustlayer_output" if state.get("blocked") else "agent"


def after_hitl(state: AgentGraphState) -> str:
    return "tools" if pending_calls(state) else "agent"


def build_guarded_agent(model: str | None = None, checkpointer=True):
    """checkpointer=None when served by `langgraph dev`, which brings its own persistence."""
    tools = [t for t in make_tools(DB_PATHS["guarded"], guarded=True) if t.name != "get_schema"]

    g = StateGraph(AgentGraphState)
    g.add_node("trustlayer_input", trustlayer_input_node)
    g.add_node("agent", make_agent_node(get_llm(model), tools))
    g.add_node("hitl", hitl)
    g.add_node("tools", make_tools_node(tools))
    g.add_node("trustlayer_tools", trustlayer_tools_node)
    g.add_node("finalize", finalize)
    g.add_node("trustlayer_output", trustlayer_output_node)
    g.add_node("respond", respond)

    g.add_edge(START, "trustlayer_input")
    g.add_conditional_edges("trustlayer_input", after_input, ["agent", "trustlayer_output"])
    g.add_conditional_edges("agent", route_after_agent(frozenset(APPROVAL)), ["hitl", "tools", "finalize", END])
    g.add_conditional_edges("hitl", after_hitl, ["tools", "agent"])
    g.add_edge("tools", "trustlayer_tools")
    g.add_edge("trustlayer_tools", "agent")
    g.add_conditional_edges("finalize", route_after_finalize("trustlayer_output"), ["agent", "trustlayer_output"])
    g.add_edge("trustlayer_output", "respond")
    g.add_edge("respond", END)
    return g.compile(checkpointer=InMemorySaver() if checkpointer else None, name="guarded_agent")
