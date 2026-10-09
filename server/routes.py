"""Extra HTTP routes mounted into the LangGraph dev server: the DB badge and the reset button of the chat UI."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starlette.applications import Starlette  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402
from starlette.routing import Route  # noqa: E402

from data.seed_db import DB_PATHS, reset_dbs, row_count  # noqa: E402

BASELINE = 800


def stats(_request) -> JSONResponse:
    return JSONResponse({side: {"rows": row_count(path), "baseline": BASELINE} for side, path in DB_PATHS.items()})


def reset(request) -> JSONResponse:
    reset_dbs()
    return stats(request)


app = Starlette(routes=[Route("/arena/stats", stats), Route("/arena/reset", reset, methods=["POST"])])
