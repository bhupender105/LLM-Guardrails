"""Entry points for `langgraph dev` (see langgraph.json) — the chat UI talks to these two assistants."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402,F401  (loads .env keys into os.environ)
from agents.guarded import build_guarded_agent  # noqa: E402
from agents.unguarded import build_unguarded_agent  # noqa: E402
from data.seed_db import ensure_dbs  # noqa: E402

ensure_dbs()
unguarded = build_unguarded_agent(checkpointer=None)
guarded = build_guarded_agent(checkpointer=None)
