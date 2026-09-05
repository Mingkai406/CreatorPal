"""Task-scoped state and atomic result commits. This is not a distributed task scheduler."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class ResearchState:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS bindings (id INTEGER PRIMARY KEY, fingerprint TEXT);
                CREATE TABLE IF NOT EXISTS items (kind TEXT, key TEXT, value TEXT,
                    PRIMARY KEY(kind,key));
                CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, kind TEXT, data TEXT);
                CREATE TABLE IF NOT EXISTS reports (task_id TEXT PRIMARY KEY, payload TEXT);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def bind(self, configuration):
        fingerprint = digest(configuration)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT fingerprint FROM bindings WHERE id=1").fetchone()
            if old and old[0] != fingerprint:
                raise ValueError("State belongs to a different task, corpus, or skill version")
            db.execute("INSERT OR IGNORE INTO bindings VALUES(1,?)", (fingerprint,))

    def put(self, kind, key, value):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO items VALUES(?,?,?)", (kind, key, json.dumps(value)))

    def get(self, kind, key):
        with self.connect() as db:
            row = db.execute(
                "SELECT value FROM items WHERE kind=? AND key=?", (kind, key)
            ).fetchone()
            return json.loads(row[0]) if row else None

    def all(self, kind):
        with self.connect() as db:
            return {
                key: json.loads(value)
                for key, value in db.execute(
                    "SELECT key,value FROM items WHERE kind=? ORDER BY key", (kind,)
                )
            }

    def once(self, key):
        with self.connect() as db:
            return (
                db.execute(
                    "INSERT OR IGNORE INTO items VALUES('markers',?,'true')", (key,)
                ).rowcount
                == 1
            )

    def event(self, kind, **data):
        with self.connect() as db:
            db.execute("INSERT INTO events(kind,data) VALUES(?,?)", (kind, json.dumps(data)))

    def events(self):
        with self.connect() as db:
            return [
                {"seq": s, "kind": k, **json.loads(d)}
                for s, k, d in db.execute("SELECT seq,kind,data FROM events ORDER BY seq")
            ]

    def commit_report(self, task_id, report):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT payload FROM reports WHERE task_id=?", (task_id,)).fetchone()
            if prior:
                if digest(json.loads(prior[0])) != digest(report):
                    raise ValueError("Task report already committed with another payload")
                db.execute(
                    "INSERT INTO events(kind,data) VALUES('report_reused',?)",
                    (json.dumps({"task_id": task_id}),),
                )
                return json.loads(prior[0]), False
            db.execute("INSERT INTO reports VALUES(?,?)", (task_id, json.dumps(report)))
            db.execute(
                "INSERT INTO events(kind,data) VALUES('report_committed',?)",
                (json.dumps({"task_id": task_id}),),
            )
            return report, True

    def reports(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT payload FROM reports")]
