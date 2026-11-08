"""Akses SQLite (stdlib sqlite3, tanpa ORM).

Tabel:
  cvs          -> satu baris per CV (data terkini, JSON)
  cv_versions  -> snapshot otomatis setiap kali PDF di-generate,
                  jadi CV versi lama selalu bisa dibuat ulang / dipulihkan.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .sections import new_cv_data, normalize

SCHEMA = """
CREATE TABLE IF NOT EXISTS cvs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,             -- label internal, mis. "Budi - Backend Dev"
    template    TEXT    NOT NULL DEFAULT 'ats',
    lang        TEXT    NOT NULL DEFAULT 'id',
    accent      TEXT    NOT NULL DEFAULT '#1f3a5f',
    photo       TEXT,                         -- nama file di data/photos
    data        TEXT    NOT NULL,             -- JSON isi CV
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS cv_versions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cv_id       INTEGER NOT NULL REFERENCES cvs(id) ON DELETE CASCADE,
    template    TEXT    NOT NULL,
    lang        TEXT    NOT NULL,
    accent      TEXT    NOT NULL,
    data        TEXT    NOT NULL,
    note        TEXT,
    created_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_versions_cv ON cv_versions(cv_id, created_at DESC);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class DB:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        try:
            yield c
            c.commit()
        finally:
            c.close()

    # ---------------------------------------------------------------- CV
    @staticmethod
    def _row(r: sqlite3.Row | None) -> dict | None:
        if r is None:
            return None
        d = dict(r)
        d["data"] = normalize(json.loads(d["data"]))
        return d

    def list_cvs(self) -> list[dict]:
        with self.conn() as c:
            rows = c.execute(
                """SELECT c.id, c.name, c.template, c.lang, c.updated_at,
                          json_extract(c.data, '$.personal.name') AS person,
                          json_extract(c.data, '$.personal.headline') AS headline,
                          (SELECT COUNT(*) FROM cv_versions v WHERE v.cv_id = c.id) AS versions
                   FROM cvs c ORDER BY c.updated_at DESC"""
            ).fetchall()
        return [dict(r) for r in rows]

    def get(self, cv_id: int) -> dict | None:
        with self.conn() as c:
            return self._row(c.execute("SELECT * FROM cvs WHERE id = ?", (cv_id,)).fetchone())

    def create(self, name: str, template="ats", lang="id", accent="#1f3a5f",
               data: dict | None = None, photo: str | None = None) -> int:
        now = _now()
        with self.conn() as c:
            cur = c.execute(
                """INSERT INTO cvs (name, template, lang, accent, photo, data, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, template, lang, accent, photo,
                 json.dumps(normalize(data or new_cv_data()), ensure_ascii=False), now, now),
            )
            return cur.lastrowid

    def update(self, cv_id: int, **fields) -> None:
        allowed = {"name", "template", "lang", "accent", "photo", "data"}
        sets, vals = [], []
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k == "data":
                v = json.dumps(normalize(v), ensure_ascii=False)
            sets.append(f"{k} = ?")
            vals.append(v)
        if not sets:
            return
        sets.append("updated_at = ?")
        vals += [_now(), cv_id]
        with self.conn() as c:
            c.execute(f"UPDATE cvs SET {', '.join(sets)} WHERE id = ?", vals)

    def delete(self, cv_id: int) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM cvs WHERE id = ?", (cv_id,))

    # ---------------------------------------------------------- versions
    def add_version(self, cv: dict, note: str = "") -> int:
        with self.conn() as c:
            cur = c.execute(
                """INSERT INTO cv_versions (cv_id, template, lang, accent, data, note, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (cv["id"], cv["template"], cv["lang"], cv["accent"],
                 json.dumps(cv["data"], ensure_ascii=False), note, _now()),
            )
            return cur.lastrowid

    def list_versions(self, cv_id: int) -> list[dict]:
        with self.conn() as c:
            rows = c.execute(
                "SELECT id, template, lang, note, created_at FROM cv_versions "
                "WHERE cv_id = ? ORDER BY id DESC", (cv_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_version(self, cv_id: int, version_id: int) -> dict | None:
        with self.conn() as c:
            r = c.execute("SELECT * FROM cv_versions WHERE id = ? AND cv_id = ?",
                          (version_id, cv_id)).fetchone()
        if r is None:
            return None
        d = dict(r)
        d["data"] = normalize(json.loads(d["data"]))
        return d

    def delete_version(self, cv_id: int, version_id: int) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM cv_versions WHERE id = ? AND cv_id = ?", (version_id, cv_id))
