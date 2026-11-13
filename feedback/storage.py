"""SQLite storage: rehearsals, takes, the facts and diagnoses behind every report.

Tables follow the backend guide (users, rehearsals, files, takes, turns, facts,
diagnoses). Reports and raw metrics are also kept as JSON on the take so the
results page loads in one query.
"""

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, name TEXT, email TEXT, auth_id TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS rehearsals (
    id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), title TEXT, occasion TEXT,
    time_limit INTEGER, audience TEXT, details TEXT, mode TEXT, created_at REAL
);
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY, rehearsal_id INTEGER REFERENCES rehearsals(id) ON DELETE CASCADE,
    filename TEXT, kind TEXT, extracted_text TEXT
);
CREATE TABLE IF NOT EXISTS takes (
    id INTEGER PRIMARY KEY, rehearsal_id INTEGER REFERENCES rehearsals(id) ON DELETE CASCADE,
    number INTEGER, mode TEXT, video_path TEXT, duration REAL, score INTEGER,
    status TEXT, step TEXT, error TEXT, created_at REAL, finished_at REAL,
    metrics_json TEXT, report_json TEXT, playback_key TEXT
);
CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY, take_id INTEGER REFERENCES takes(id) ON DELETE CASCADE,
    speaker TEXT, text TEXT, start REAL, "end" REAL
);
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY, take_id INTEGER REFERENCES takes(id) ON DELETE CASCADE,
    fact_no INTEGER, name TEXT, value TEXT, start REAL, "end" REAL, source TEXT, tags TEXT
);
CREATE TABLE IF NOT EXISTS diagnoses (
    id INTEGER PRIMARY KEY, take_id INTEGER REFERENCES takes(id) ON DELETE CASCADE,
    rule_id INTEGER, key TEXT, kind TEXT, severity REAL, score REAL, rank INTEGER,
    fact_ids TEXT, tip TEXT
);
CREATE INDEX IF NOT EXISTS idx_takes_rehearsal ON takes(rehearsal_id);
CREATE INDEX IF NOT EXISTS idx_facts_take ON facts(take_id);
"""

DEMO_USER = 1


def storage_dir() -> Path:
    path = Path(os.getenv("PODIUM_STORAGE_DIR", "storage"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return storage_dir() / "podium.db"


@contextmanager
def connect():
    conn = sqlite3.connect(db_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# Columns added after the first release; older databases get them on startup.
MIGRATIONS = [("users", "auth_id", "TEXT"), ("takes", "playback_key", "TEXT")]


def init_db() -> None:
    with connect() as c:
        c.executescript(SCHEMA)
        for table, column, kind in MIGRATIONS:
            cols = {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}
            if column not in cols:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_auth ON users(auth_id)")
        c.execute("INSERT OR IGNORE INTO users (id, name, email) VALUES (?, 'Demo user', NULL)", (DEMO_USER,))


# --- users --------------------------------------------------------------------

def user_for_auth(auth_id: str, email: str | None) -> int:
    """Local user id for a Supabase account, created on first sign in."""
    with connect() as c:
        row = c.execute("SELECT id, email FROM users WHERE auth_id = ?", (auth_id,)).fetchone()
        if row:
            if email and row["email"] != email:
                c.execute("UPDATE users SET email = ? WHERE id = ?", (email, row["id"]))
            return row["id"]
        return c.execute("INSERT INTO users (name, email, auth_id) VALUES (?, ?, ?)",
                         ((email or "").split("@")[0] or None, email, auth_id)).lastrowid


def _row(r) -> dict | None:
    return dict(r) if r else None


# --- rehearsals ---------------------------------------------------------------

def create_rehearsal(title, occasion, mode, time_limit=None, audience=None, details=None,
                     user_id: int = DEMO_USER) -> dict:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO rehearsals (user_id, title, occasion, mode, time_limit, audience, details, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, title, occasion, mode, time_limit, audience, details, time.time()),
        )
        rid = cur.lastrowid
    return get_rehearsal(rid)


def get_rehearsal(rid: int) -> dict | None:
    with connect() as c:
        return _row(c.execute("SELECT * FROM rehearsals WHERE id = ?", (rid,)).fetchone())


def list_rehearsals(user_id: int = DEMO_USER) -> list[dict]:
    """Sidebar: this user's rehearsals, newest first, with the latest take's score."""
    with connect() as c:
        rows = c.execute("""
            SELECT r.*, (SELECT COUNT(*) FROM takes t WHERE t.rehearsal_id = r.id) AS take_count,
                   (SELECT t.score FROM takes t WHERE t.rehearsal_id = r.id AND t.status = 'done'
                    ORDER BY t.number DESC LIMIT 1) AS last_score
            FROM rehearsals r WHERE r.user_id = ? ORDER BY r.created_at DESC
        """, (user_id,)).fetchall()
    return [dict(r) for r in rows]


def delete_rehearsal(rid: int) -> list[dict]:
    """Delete a rehearsal and everything under it. Returns its takes' {id, playback_key} for media cleanup."""
    with connect() as c:
        takes = [dict(r) for r in c.execute("SELECT id, playback_key FROM takes WHERE rehearsal_id = ?", (rid,))]
        c.execute("DELETE FROM rehearsals WHERE id = ?", (rid,))
    return takes


def processing_count(user_id: int) -> int:
    """How many of this user's takes are being analyzed right now."""
    with connect() as c:
        return c.execute("SELECT COUNT(*) FROM takes t JOIN rehearsals r ON r.id = t.rehearsal_id "
                         "WHERE r.user_id = ? AND t.status = 'processing'", (user_id,)).fetchone()[0]


# --- files --------------------------------------------------------------------

def add_file(rid: int, filename: str, kind: str, text: str) -> dict:
    with connect() as c:
        cur = c.execute("INSERT INTO files (rehearsal_id, filename, kind, extracted_text) VALUES (?, ?, ?, ?)",
                        (rid, filename, kind, text))
        return {"id": cur.lastrowid, "filename": filename, "kind": kind, "chars": len(text)}


def list_files(rid: int) -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM files WHERE rehearsal_id = ?", (rid,))]


# --- takes --------------------------------------------------------------------

def create_take(rid: int, mode: str) -> dict:
    with connect() as c:
        number = c.execute("SELECT COALESCE(MAX(number), 0) + 1 FROM takes WHERE rehearsal_id = ?",
                           (rid,)).fetchone()[0]
        cur = c.execute("INSERT INTO takes (rehearsal_id, number, mode, status, created_at) VALUES (?, ?, ?, ?, ?)",
                        (rid, number, mode, "recording", time.time()))
        tid = cur.lastrowid
    return get_take(tid)


def get_take(tid: int) -> dict | None:
    with connect() as c:
        take = _row(c.execute("SELECT * FROM takes WHERE id = ?", (tid,)).fetchone())
    if take:
        take["report"] = json.loads(take.pop("report_json") or "null")
        take["metrics"] = json.loads(take.pop("metrics_json") or "null")
    return take


def list_takes(rid: int) -> list[dict]:
    with connect() as c:
        rows = c.execute("SELECT id, number, mode, status, score, duration, created_at, metrics_json "
                         "FROM takes WHERE rehearsal_id = ? ORDER BY number", (rid,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["metrics"] = json.loads(d.pop("metrics_json") or "null")
        out.append(d)
    return out


def update_take(tid: int, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    with connect() as c:
        c.execute(f"UPDATE takes SET {cols} WHERE id = ?", (*fields.values(), tid))


def previous_done_takes(rid: int, before_number: int) -> list[dict]:
    """Earlier finished takes of the same rehearsal, oldest first."""
    with connect() as c:
        rows = c.execute(
            "SELECT id, number, score, metrics_json, report_json FROM takes "
            "WHERE rehearsal_id = ? AND number < ? AND status = 'done' ORDER BY number",
            (rid, before_number)).fetchall()
    out = []
    for r in rows:
        report = json.loads(r["report_json"] or "{}")
        out.append({
            "id": r["id"], "number": r["number"], "score": r["score"],
            "summary": json.loads(r["metrics_json"] or "{}").get("summary", {}),
            "focus_rule_ids": [f["rule_id"] for f in report.get("focus", [])],
        })
    return out


# --- turns (live mode conversation) -------------------------------------------

def add_turn(tid: int, speaker: str, text: str, start: float | None = None, end: float | None = None) -> int:
    with connect() as c:
        return c.execute('INSERT INTO turns (take_id, speaker, text, start, "end") VALUES (?, ?, ?, ?, ?)',
                         (tid, speaker, text, start, end)).lastrowid


def update_turn_times(turn_id: int, start: float | None, end: float | None) -> None:
    with connect() as c:
        c.execute('UPDATE turns SET start = ?, "end" = ? WHERE id = ?', (start, end, turn_id))


def list_turns(tid: int) -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute('SELECT * FROM turns WHERE take_id = ? ORDER BY id', (tid,))]


# --- facts and diagnoses ------------------------------------------------------

def save_analysis(tid: int, facts: list[dict], result: dict) -> None:
    with connect() as c:
        c.execute("DELETE FROM facts WHERE take_id = ?", (tid,))
        c.execute("DELETE FROM diagnoses WHERE take_id = ?", (tid,))
        c.executemany(
            'INSERT INTO facts (take_id, fact_no, name, value, start, "end", source, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            [(tid, f["id"], f["name"], json.dumps(f["value"]), f["start"], f["end"], f["source"],
              json.dumps(f["tags"])) for f in facts])
        ranked = result["focus"] + result["secondary"] + result["strengths"]
        c.executemany(
            "INSERT INTO diagnoses (take_id, rule_id, key, kind, severity, score, rank, fact_ids, tip)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(tid, d["rule_id"], d["key"], d["kind"], d["severity"], d["score"], i + 1,
              json.dumps(d["fact_ids"]), d["tip"]) for i, d in enumerate(ranked)])


def get_facts(tid: int, ids: list[int] | None = None) -> list[dict]:
    with connect() as c:
        rows = c.execute('SELECT fact_no, name, value, start, "end", source, tags FROM facts WHERE take_id = ?'
                         ' ORDER BY fact_no', (tid,)).fetchall()
    wanted = set(ids or [])
    return [
        {"id": r["fact_no"], "name": r["name"], "value": json.loads(r["value"]), "start": r["start"],
         "end": r["end"], "source": r["source"], "tags": json.loads(r["tags"])}
        for r in rows if not wanted or r["fact_no"] in wanted
    ]


# --- privacy ------------------------------------------------------------------

def expire_videos(older_than_days: int) -> list[dict]:
    """Forget video for old takes; computed numbers stay. Returns [{id, playback_key}] to delete."""
    cutoff = time.time() - older_than_days * 86400
    with connect() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT id, playback_key FROM takes WHERE (playback_key IS NOT NULL OR video_path IS NOT NULL)"
            " AND created_at < ?", (cutoff,))]
        c.executemany("UPDATE takes SET playback_key = NULL, video_path = NULL WHERE id = ?",
                      [(r["id"],) for r in rows])
    return rows
