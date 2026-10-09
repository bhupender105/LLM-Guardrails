"""The 'before' agent: same model, prompt and tools — zero guardrails.
Write tools run immediately and run_sql_query executes any SQL.

    START ─► agent ─┬─► tools ─► agent …      (ReAct loop)
                    └─► finalize ─► respond ─► END
"""
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agents.chat_ui import respond
from agents.graph_common import (AgentGraphState, finalize, make_agent_node, make_tools_node, route_after_agent,
                                 route_after_finalize)
from agents.llm import get_llm
from agents.tools import make_tools
from data.seed_db import DB_PATHS


def build_unguarded_agent(model: str | None = None, checkpointer=True):
    """checkpointer=None when served by `langgraph dev`, which brings its own persistence."""
    tools = [t for t in make_tools(DB_PATHS["unguarded"], guarded=False) if t.name != "get_schema"]

    g = StateGraph(AgentGraphState)
    g.add_node("agent", make_agent_node(get_llm(model), tools))
    g.add_node("tools", make_tools_node(tools))
    g.add_node("finalize", finalize)
    g.add_node("respond", respond)

    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route_after_agent(), ["tools", "finalize", END])
    g.add_edge("tools", "agent")
    g.add_conditional_edges("finalize", route_after_finalize("respond"), ["agent", "respond"])
    g.add_edge("respond", END)
    return g.compile(checkpointer=InMemorySaver() if checkpointer else None, name="unguarded_agent")
