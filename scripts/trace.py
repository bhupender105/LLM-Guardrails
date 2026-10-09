"""Run ONE question through the guarded agent and print what happened before / during / after the agent.

    uv run python scripts/trace.py "Top 5 companies by average CTC"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402,F401
from agents.guarded import build_guarded_agent  # noqa: E402
from agents.runner import run_turn  # noqa: E402
from data.seed_db import reset_dbs  # noqa: E402
from trustlayer.trace import format_turn  # noqa: E402

reset_dbs()
res = run_turn(build_guarded_agent(), " ".join(sys.argv[1:]) or "Placement rate by department for the 2024 batch")
print(format_turn(res))
if res.card:
    print(f"\n[{res.card.status}] {res.card.emoji} {res.card.title}\n{res.card.summary}")
if res.error:
    print("ERROR", res.error)
reset_dbs()
