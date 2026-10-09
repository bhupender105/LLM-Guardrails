"""Trace helpers: stamp events with the phase they ran in, and print a turn as BEFORE / AGENT / AFTER."""
from typing import Any

PHASES = ("input", "tools", "output")
_ICON = {"pass": "✓", "blocked": "✕", "redacted": "✎", "flagged": "⚠", "pending": "⏸", "info": "ℹ", "error": "!"}


def stamp(events: list[dict], phase: str) -> list[dict]:
    return [{**e, "phase": phase} for e in events]


def _lines(events: list[dict]) -> list[str]:
    out = []
    for e in events:
        ms = f"{e['ms']:>5} ms" if e.get("ms") is not None else "        "
        out.append(f"   {_ICON.get(e['status'], '·')} {e['layer']:<10} {e['status']:<9} {ms}  {e['detail']}")
    return out


def _total(events: list[dict]) -> int:
    return sum(e["ms"] or 0 for e in events if e.get("ms"))


def format_turn(res: Any) -> str:
    """res: agents.runner.TurnResult. Returns a multi-line before / agent / after trace."""
    by_phase = {p: [e for e in res.events if e.get("phase") == p] for p in PHASES}
    blocked = next((e for e in res.events if e["status"] == "blocked"), None)
    guard_ms = _total(res.events)
    lines = [f"┌─ BEFORE AGENT · trustlayer_input · {_total(by_phase['input'])} ms", *_lines(by_phase["input"])]

    if blocked:
        lines += [f"├─ AGENT · skipped — blocked by `{blocked['layer']}`, the LLM was never called"]
    else:
        calls = [t for t in res.tools if t["name"]]
        agent_ms = max(res.ms - guard_ms, 0)
        lines.append(f"├─ AGENT · ~{agent_ms} ms · {res.llm_calls} LLM call(s) · {len(calls)} tool call(s)")
        for t in calls:
            arg = t["args"].get("query") or ", ".join(f"{k}={v!r}" for k, v in t["args"].items())
            lines.append(f"   🔧 {t['name']}  {' '.join(str(arg).split())[:110]}")
        if by_phase["tools"]:
            lines += [f"   └ trustlayer_tools · {_total(by_phase['tools'])} ms", *_lines(by_phase["tools"])]
        if res.interrupt:
            a = res.interrupt["action_requests"][0]
            lines.append(f"   ⏸ paused for human approval → {a['name']}({a['args']})")

    if not res.interrupt:
        lines += [f"└─ AFTER AGENT · trustlayer_output · {_total(by_phase['output'])} ms", *_lines(by_phase["output"])]
        if not by_phase["output"]:
            lines.append("   (nothing to check)")
    lines.append(f"   total {res.ms} ms · guardrail overhead {guard_ms} ms")
    return "\n".join(lines)
