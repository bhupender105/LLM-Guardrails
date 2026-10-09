"""SQL tools over one agent's SQLite copy.

Both agents get tools with identical names/signatures. The difference:
- unguarded `run_sql_query` executes ANY statement (DROP TABLE really works)
- guarded `run_sql_query` only allows a single SELECT; writes go through the
  update/delete tools, which the guarded agent puts behind human approval.
"""
import json
import re
import sqlite3
from pathlib import Path

from langchain_core.tools import tool

from data.seed_db import TABLE

MAX_ROWS = 50
_SELECT_ONLY = re.compile(r"^\s*(WITH\b.*?\)\s*)?SELECT\b", re.IGNORECASE | re.DOTALL)
_WRITE_KEYWORDS = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|ATTACH|PRAGMA)\b", re.IGNORECASE)


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _rows_to_text(cursor: sqlite3.Cursor) -> str:
    rows = cursor.fetchmany(MAX_ROWS + 1)
    if cursor.description is None:
        return json.dumps({"rows_affected": cursor.rowcount})
    data = [dict(r) for r in rows[:MAX_ROWS]]
    out = {"row_count": len(data), "rows": data}
    if len(rows) > MAX_ROWS:
        out["note"] = f"truncated to {MAX_ROWS} rows — aggregate in SQL instead"
    return json.dumps(out, default=str)


def count_matching(db_path: Path, where_clause: str) -> int | str:
    """Dry-run COUNT used by the HITL approval card ('this will affect N rows')."""
    try:
        with _connect(db_path) as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE {where_clause}").fetchone()[0]
    except sqlite3.Error as e:
        return f"error: {e}"


def make_tools(db_path: Path, guarded: bool) -> list:
    db_path = Path(db_path)

    @tool
    def get_schema() -> str:
        """Return the columns of the `students` table with types and example values."""
        try:
            with _connect(db_path) as conn:
                cols = conn.execute(f"PRAGMA table_info({TABLE})").fetchall()
                if not cols:
                    return f"Table `{TABLE}` does not exist."
                sample = conn.execute(f"SELECT * FROM {TABLE} LIMIT 1").fetchone()
        except sqlite3.Error as e:
            return f"Error: {e}"
        lines = [f"Table `{TABLE}`:"]
        for c in cols:
            example = sample[c["name"]] if sample else None
            lines.append(f"- {c['name']} ({c['type']}), e.g. {example!r}")
        return "\n".join(lines)

    @tool
    def run_sql_query(query: str) -> str:
        """Run a SQL query against the students database and return the result rows as JSON."""
        if guarded and (not _SELECT_ONLY.match(query) or _WRITE_KEYWORDS.search(query) or ";" in query.strip().rstrip(";")):
            return "Rejected by SQL guard: only a single read-only SELECT statement is allowed."
        try:
            with _connect(db_path) as conn:
                if guarded:
                    cur = conn.execute(query)
                else:
                    # Unguarded: executes whatever the model sends — including DROP TABLE
                    statements = [s for s in query.split(";") if s.strip()]
                    cur = None
                    for stmt in statements:
                        cur = conn.execute(stmt)
                    conn.commit()
                return _rows_to_text(cur) if cur is not None else "OK"
        except sqlite3.Error as e:
            return f"SQL error: {e}"

    @tool
    def update_student_records(set_clause: str, where_clause: str) -> str:
        """Update student records. `set_clause` e.g. "placement_status = 'Placed'"; `where_clause` e.g. "student_id = 'PT2001'"."""
        try:
            with _connect(db_path) as conn:
                cur = conn.execute(f"UPDATE {TABLE} SET {set_clause} WHERE {where_clause}")
                conn.commit()
                return f"Updated {cur.rowcount} student record(s)."
        except sqlite3.Error as e:
            return f"SQL error: {e}"

    @tool
    def delete_student_records(where_clause: str) -> str:
        """Delete student records matching `where_clause`, e.g. "backlog_count > 3"."""
        try:
            with _connect(db_path) as conn:
                cur = conn.execute(f"DELETE FROM {TABLE} WHERE {where_clause}")
                conn.commit()
                return f"Deleted {cur.rowcount} student record(s)."
        except sqlite3.Error as e:
            return f"SQL error: {e}"

    return [get_schema, run_sql_query, update_student_records, delete_student_records]
