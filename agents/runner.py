"""Invoke an agent and flatten the result into what the UI renders."""
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from agents.schemas import AnswerCard

WRITE_TOOLS = {"update_student_records", "delete_student_records"}


@dataclass
class TurnResult:
    card: AnswerCard | None = None
    events: list[dict] = field(default_factory=list)
    tools: list[dict] = field(default_factory=list)
    interrupt: dict | None = None
    error: str | None = None
    ms: int = 0
    llm_calls: int = 0
    thread_id: str = ""
    decision: dict | None = None


def _turn_messages(messages: list) -> list:
    start = max((i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=0)
    return messages[start:]


def _tool_log(messages: list) -> list[dict]:
    outputs = {m.tool_call_id: m.content for m in messages if isinstance(m, ToolMessage)}
    log = []
    for m in messages:
        if isinstance(m, AIMessage):
            for tc in m.tool_calls:
                if tc["name"] == "AnswerCard":
                    continue
                out = outputs.get(tc["id"])
                log.append({
                    "name": tc["name"],
                    "args": tc["args"],
                    "output": out if isinstance(out, str) else (str(out) if out is not None else None),
                    "write": tc["name"] in WRITE_TOOLS or (
                        tc["name"] == "run_sql_query"
                        and any(k in str(tc["args"].get("query", "")).upper() for k in ("DROP ", "DELETE ", "UPDATE ", "ALTER ", "INSERT "))
                    ),
                })
    return log


def _flatten(raw: dict, started: float, thread_id: str) -> TurnResult:
    msgs = _turn_messages(raw.get("messages", []))
    res = TurnResult(
        card=raw.get("structured_response"),
        events=raw.get("guard_events", []),
        tools=_tool_log(msgs),
        ms=round((time.perf_counter() - started) * 1000),
        llm_calls=sum(1 for m in msgs if isinstance(m, AIMessage) and m.response_metadata),
        thread_id=thread_id,
    )
    if raw.get("__interrupt__"):
        res.interrupt = raw["__interrupt__"][0].value
        res.card = None
    if res.card is None and not res.interrupt:
        last = next((m for m in reversed(msgs) if isinstance(m, AIMessage) and m.content), None)
        text = last.content if last and isinstance(last.content, str) else "The agent returned no answer."
        res.card = AnswerCard(title="Response", emoji="💬", summary=text)
    return res


def _is_transient(e: Exception) -> bool:
    msg = str(e)
    return any(code in msg for code in ("500 INTERNAL", "503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "DEADLINE_EXCEEDED"))


def _invoke_with_retry(agent, payload, config, attempts: int = 3):
    for i in range(attempts):
        try:
            return agent.invoke(payload, config)
        except Exception as e:
            if i == attempts - 1 or not _is_transient(e):
                raise
            time.sleep(2 ** (i + 1))  # 2s, 4s


def run_turn(agent, question: str) -> TurnResult:
    thread_id = str(uuid.uuid4())  # fresh thread per question keeps scenarios independent
    started = time.perf_counter()
    try:
        raw = _invoke_with_retry(agent, {"messages": [{"role": "user", "content": question}]},
                                 {"configurable": {"thread_id": thread_id}})
        return _flatten(raw, started, thread_id)
    except Exception as e:  # surfaced as an error card, never a crash on stage
        traceback.print_exc()
        return TurnResult(error=f"{type(e).__name__}: {e}", ms=round((time.perf_counter() - started) * 1000),
                          thread_id=thread_id)


def resume_turn(agent, thread_id: str, decision: dict[str, Any], prior_events: list[dict]) -> TurnResult:
    started = time.perf_counter()
    try:
        raw = _invoke_with_retry(agent, Command(resume={"decisions": [decision]}), {"configurable": {"thread_id": thread_id}})
        res = _flatten(raw, started, thread_id)
    except Exception as e:
        traceback.print_exc()
        res = TurnResult(error=f"{type(e).__name__}: {e}", thread_id=thread_id, events=prior_events)
    res.decision = decision
    return res
