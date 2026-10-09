"""Glue for the ChatGPT-style chat UI (chat-ui/, served by `langgraph dev`).

The graphs push LangGraph generative-UI messages that chat-ui renders with its own React components:
  guard_strip  — the 🛡️ Trust Layer chips of one turn (keyed by the turn's human message id)
  answer_card  — KPIs / chart / table / insights, attached to the final AI reply

Outside the LangGraph server (Streamlit, smoke test) push_ui_message only writes to the `ui` state key.
"""
import uuid

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph.ui import push_ui_message

from agents.graph_common import ANSWER, RESET, AgentGraphState


def turn_id(state: AgentGraphState) -> str:
    return next((m.id for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), "") or ""


def push_guard_strip(state: AgentGraphState, new_events: list[dict], stage: str, *, fresh: bool = False) -> None:
    """Re-push the turn's full event list so the strip updates in place as each guard node finishes."""
    prior = [] if fresh else [e for e in state.get("guard_events", []) if not e.get("__reset__")]
    turn = turn_id(state)
    push_ui_message("guard_strip", {"events": prior + new_events, "stage": stage},
                    id=f"guard-{turn}", metadata={"turn": turn})


def new_turn(events: list[dict]) -> list[dict]:
    """guard_events update that starts a fresh turn (see graph_common.merge_events)."""
    return [RESET, *events]


def respond(state: AgentGraphState) -> dict:
    """Last node: close the AnswerCard tool call and post the card as a normal chat reply."""
    card = state.get("structured_response")
    last = state["messages"][-1]
    out = []
    if isinstance(last, AIMessage) and (call := next((tc for tc in last.tool_calls if tc["name"] == ANSWER), None)):
        out.append(ToolMessage("Answer card shown to the user.", name=ANSWER, tool_call_id=call["id"]))
    if card is None:
        return {"messages": out} if out else {}
    if isinstance(last, AIMessage) and not last.tool_calls and last.content:  # blocked turn: reuse the refusal
        reply = last
    else:
        reply = AIMessage(id=str(uuid.uuid4()), content=card.summary)
        out.append(reply)
    push_ui_message("answer_card", card.model_dump(mode="json"), id=f"card-{reply.id}", message=reply,
                    metadata={"turn": turn_id(state)})
    return {"messages": out} if out else {}
