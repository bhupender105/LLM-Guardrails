"""Build the demo SQLite databases from student_placements.csv.

master.db    — pristine copy, built once from the CSV (+ synthetic PII columns)
unguarded.db — working copy for the unguarded agent (it may delete / drop things)
guarded.db   — working copy for the guarded agent

The CSV has no contact details, so we add *synthetic, fake* PII (email, phone,
Aadhaar-style id, parent phone) to make the PII-leak demo realistic. The source
CSV is never modified.
"""
import random
import shutil
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import data_config  # noqa: E402

DATA_DIR = Path(data_config.DATA_DIR)
MASTER_DB = DATA_DIR / "master.db"
DB_PATHS = {"unguarded": DATA_DIR / "unguarded.db", "guarded": DATA_DIR / "guarded.db"}
TABLE = "students"


def _add_synthetic_pii(df: pd.DataFrame) -> pd.DataFrame:
    rng = random.Random(42)
    domains = ["gmail.com", "yahoo.co.in", "outlook.com", "rediffmail.com"]

    def email(row):
        first, *rest = row.student_name.lower().split()
        last = rest[-1] if rest else "student"
        return f"{first}.{last}{row.student_id[-3:]}@{rng.choice(domains)}"

    def phone():
        return f"+91 {rng.choice('6789')}{rng.randint(100000000, 999999999)}"

    def aadhaar():
        d = f"{rng.randint(2, 9)}{rng.randint(10**10, 10**11 - 1)}"
        return f"{d[:4]} {d[4:8]} {d[8:]}"

    df = df.copy()
    df["email"] = df.apply(email, axis=1)
    df["phone"] = [phone() for _ in range(len(df))]
    df["aadhaar_no"] = [aadhaar() for _ in range(len(df))]
    df["parent_phone"] = [phone() for _ in range(len(df))]
    return df


def build_master(force: bool = False) -> Path:
    if MASTER_DB.exists() and not force:
        return MASTER_DB
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(data_config.CSV_PATH)
    df = _add_synthetic_pii(df)
    MASTER_DB.unlink(missing_ok=True)
    with sqlite3.connect(MASTER_DB) as conn:
        df.to_sql(TABLE, conn, index=False)
    return MASTER_DB


def reset_dbs() -> None:
    """Restore both working copies from master.db (the 'Reset databases' button)."""
    build_master()
    for path in DB_PATHS.values():
        shutil.copyfile(MASTER_DB, path)


def ensure_dbs() -> None:
    build_master()
    for path in DB_PATHS.values():
        if not path.exists():
            shutil.copyfile(MASTER_DB, path)


def row_count(path: Path) -> int | None:
    """Rows in the students table, or None when the table is gone (e.g. dropped)."""
    try:
        with sqlite3.connect(path) as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]
    except sqlite3.Error:
        return None


if __name__ == "__main__":
    build_master(force=True)
    reset_dbs()
    with sqlite3.connect(MASTER_DB) as conn:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({TABLE})")]
        sample = conn.execute(f"SELECT student_name, email, phone, aadhaar_no FROM {TABLE} LIMIT 3").fetchall()
    print(f"Built {MASTER_DB} — {row_count(MASTER_DB)} rows, {len(cols)} columns")
    for s in sample:
        print("  ", s)
