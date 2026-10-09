"""Print both agent graphs as Mermaid (paste into https://mermaid.live).

    uv run python scripts/show_graph.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402,F401
from agents.guarded import build_guarded_agent  # noqa: E402
from agents.unguarded import build_unguarded_agent  # noqa: E402

for name, agent in (("UNGUARDED", build_unguarded_agent()), ("GUARDED", build_guarded_agent())):
    print(f"\n%% ===== {name} =====")
    print(agent.get_graph().draw_mermaid())
