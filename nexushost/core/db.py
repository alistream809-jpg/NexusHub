"""SQLite persistence for server configurations and application settings."""
import sqlite3
import threading
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS servers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    mc_version TEXT NOT NULL,
    ram_mb INTEGER NOT NULL,
    port INTEGER NOT NULL,
    path TEXT NOT NULL UNIQUE,
    jar_file TEXT NOT NULL DEFAULT '',
    java_major INTEGER NOT NULL DEFAULT 17,
    jvm_args TEXT NOT NULL DEFAULT '',
    auto_stop_enabled INTEGER NOT NULL DEFAULT 1,
    auto_stop_seconds INTEGER NOT NULL DEFAULT 420,
    created_at TEXT NOT NULL,
    last_started TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass
class ServerRecord:
    id: int
    name: str
    type: str
    mc_version: str
    ram_mb: int
    port: int
    path: str
    jar_file: str = ""
    java_major: int = 17
    jvm_args: str = ""
    auto_stop_enabled: bool = True
    auto_stop_seconds: int = 420
    created_at: str = ""
    last_started: str = None

    @property
    def folder(self) -> Path:
        return Path(self.path)


_COLUMNS = {f.name for f in fields(ServerRecord)} - {"id"}


class Database:
    def __init__(self, path):
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    @staticmethod
    def _to_record(row) -> ServerRecord:
        data = dict(row)
        data["auto_stop_enabled"] = bool(data["auto_stop_enabled"])
        return ServerRecord(**data)

    def add_server(self, **values) -> ServerRecord:
        values.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
        bad = set(values) - _COLUMNS
        if bad:
            raise ValueError(f"Unknown columns: {bad}")
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        with self._lock:
            cur = self._conn.execute(f"INSERT INTO servers ({cols}) VALUES ({marks})", list(values.values()))
            self._conn.commit()
            return self.get_server(cur.lastrowid)

    def get_server(self, server_id: int):
        with self._lock:
            row = self._conn.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone()
        return self._to_record(row) if row else None

    def list_servers(self):
        with self._lock:
            rows = self._conn.execute("SELECT * FROM servers ORDER BY id").fetchall()
        return [self._to_record(r) for r in rows]

    def update_server(self, server_id: int, **values):
        bad = set(values) - _COLUMNS
        if bad:
            raise ValueError(f"Unknown columns: {bad}")
        if not values:
            return
        sets = ", ".join(f"{k} = ?" for k in values)
        params = [int(v) if isinstance(v, bool) else v for v in values.values()]
        with self._lock:
            self._conn.execute(f"UPDATE servers SET {sets} WHERE id = ?", params + [server_id])
            self._conn.commit()

    def delete_server(self, server_id: int):
        with self._lock:
            self._conn.execute("DELETE FROM servers WHERE id = ?", (server_id,))
            self._conn.commit()

    def get_setting(self, key: str, default: str = ""):
        with self._lock:
            row = self._conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value):
        with self._lock:
            self._conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )
            self._conn.commit()

    def close(self):
        with self._lock:
            self._conn.close()
