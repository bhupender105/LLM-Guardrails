"""Building blocks of the explicit LangGraph ReAct agents (shared by guarded + unguarded).

State  : AgentGraphState  (messages · guard_events · structured_response · blocked)
Nodes  : agent  — one Gemini call with the SQL tools AND `AnswerCard` bound, tool_choice="any"
         tools  — runs every pending tool call of the last AI message in parallel
         finalize — turns the model's `AnswerCard` call into `structured_response`
Edges  : agent ─► tools ─► agent …  (ReAct loop)   agent ─► finalize ─► END

Latency notes: the final answer is produced by the *same* model call that ends the loop (AnswerCard is
just another tool), so there is no separate structured-output call; `get_schema` is dropped because the
schema is already in the system prompt.
"""
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Any, Callable, NotRequired, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, SystemMessage, ToolMessage
from langgraph.graph import END
from langgraph.graph.message import add_messages
from langgraph.graph.ui import AnyUIMessage, ui_message_reducer
from pydantic import ValidationError

from agents.prompts import SYSTEM_PROMPT
from agents.schemas import AnswerCard

ANSWER = "AnswerCard"
_SYSTEM = SystemMessage(SYSTEM_PROMPT + "\n\nWhen you have the data, deliver the final answer by calling the "
                        "`AnswerCard` tool. Do not reply with plain text.")


RESET = {"__reset__": True}  # first item of a guard_events update → start a fresh turn


def merge_events(old: list[dict], new: list[dict]) -> list[dict]:
    """Append reducer for guard_events that a new chat turn can reset (multi-turn threads in the chat UI)."""
    if new and new[0].get("__reset__"):
        return list(new[1:])
    return (old or []) + new


class AgentGraphState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    guard_events: NotRequired[Annotated[list[dict[str, Any]], merge_events]]
    structured_response: NotRequired[AnswerCard | None]
    blocked: NotRequired[bool]
    ui: NotRequired[Annotated[list[AnyUIMessage], ui_message_reducer]]  # generative-UI cards for the chat UI


def pending_calls(state: AgentGraphState) -> list[dict]:
    """Tool calls of the last AI message that have no ToolMessage yet (AnswerCard excluded)."""
    msgs = state["messages"]
    idx = max(i for i, m in enumerate(msgs) if isinstance(m, AIMessage))
    done = {m.tool_call_id for m in msgs[idx + 1:] if isinstance(m, ToolMessage)}
    return [tc for tc in msgs[idx].tool_calls if tc["name"] != ANSWER and tc["id"] not in done]


def make_agent_node(llm, tools: list) -> Callable:
    bound = llm.bind_tools([*tools, AnswerCard], tool_choice="any")  # always a tool call → always structured

    def agent(state: AgentGraphState) -> dict:
        ai = bound.invoke([_SYSTEM, *state["messages"]])
        real = [tc for tc in ai.tool_calls if tc["name"] != ANSWER]
        if real and len(real) != len(ai.tool_calls):  # model mixed a premature AnswerCard with SQL calls
            ai = ai.model_copy(update={"tool_calls": real})
        return {"messages": [ai]}

    return agent


def make_tools_node(tools: list) -> Callable:
    by_name = {t.name: t for t in tools}

    def run(tc: dict) -> ToolMessage:
        try:
            return by_name[tc["name"]].invoke(tc)
        except Exception as e:  # bad args etc. go back to the model instead of crashing the graph
            return ToolMessage(f"Tool error: {e}", name=tc["name"], tool_call_id=tc["id"], status="error")

    def tools_node(state: AgentGraphState) -> dict:
        calls = pending_calls(state)
        if len(calls) == 1:
            return {"messages": [run(calls[0])]}
        with ThreadPoolExecutor(len(calls)) as pool:  # independent queries run concurrently
            return {"messages": list(pool.map(run, calls))}

    return tools_node


def finalize(state: AgentGraphState) -> dict:
    call = next(tc for tc in reversed(state["messages"][-1].tool_calls) if tc["name"] == ANSWER)
    try:
        return {"structured_response": AnswerCard.model_validate(call["args"])}
    except ValidationError as e:  # let the model fix its card
        return {"structured_response": None,
                "messages": [ToolMessage(f"Invalid AnswerCard: {e}", name=ANSWER, tool_call_id=call["id"], status="error")]}


def route_after_agent(approval_tools: frozenset[str] = frozenset()) -> Callable:
    """agent ─► hitl | tools | finalize | END"""
    def route(state: AgentGraphState) -> str:
        calls = state["messages"][-1].tool_calls
        real = [tc for tc in calls if tc["name"] != ANSWER]
        if real:
            return "hitl" if any(tc["name"] in approval_tools for tc in real) else "tools"
        return "finalize" if calls else END
    return route


def route_after_finalize(done: str = END) -> Callable:
    """finalize ─► done (card valid) | agent (retry)"""
    return lambda state: done if state.get("structured_response") else "agent"
