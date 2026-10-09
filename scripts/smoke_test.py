"""Headless rehearsal: every sidebar scenario against both agents.

    uv run python scripts/smoke_test.py            # all scenarios
    uv run python scripts/smoke_test.py injection  # only scenarios whose label matches
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402,F401
from agents.guarded import build_guarded_agent  # noqa: E402
from agents.runner import run_turn  # noqa: E402
from agents.unguarded import build_unguarded_agent  # noqa: E402
from data.seed_db import DB_PATHS, reset_dbs, row_count  # noqa: E402
from trustlayer.trace import format_turn  # noqa: E402
from ui.scenarios import SCENARIOS  # noqa: E402


def describe(r) -> str:
    if r.error:
        return f"ERROR {r.error[:160]}"
    if r.interrupt:
        a = r.interrupt["action_requests"][0]
        return f"⏸ HITL interrupt → {a['name']}({a['args']})"
    c = r.card
    return f"[{c.status}] {c.emoji} {c.title} | {c.summary[:160]!r}"


def main(filter_text: str = "") -> None:
    unguarded, guarded = build_unguarded_agent(), build_guarded_agent()
    for group, items in SCENARIOS:
        for label, prompt in items:
            if filter_text.lower() not in label.lower():
                continue
            reset_dbs()
            with ThreadPoolExecutor(2) as ex:
                fu, fg = ex.submit(run_turn, unguarded, prompt), ex.submit(run_turn, guarded, prompt)
                u, g = fu.result(), fg.result()
            print(f"\n=== {group} · {label}\n    Q: {prompt}")
            print(f"    🔓 {u.ms/1000:5.1f}s  {describe(u)}")
            writes = [t for t in u.tools if t['write']]
            if writes:
                print(f"       writes: {[(t['name'], t['args']) for t in writes]}  rows now: {row_count(DB_PATHS['unguarded'])}")
            print(f"    🛡️ {g.ms/1000:5.1f}s  {describe(g)}")
            print("\n".join("       " + l for l in format_turn(g).splitlines()))
            if g.card and g.card.table:
                print(f"       table row: {g.card.table.rows[:1]}")
            if u.card and u.card.table:
                print(f"       unguarded table row: {u.card.table.rows[:1]}")
    reset_dbs()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
