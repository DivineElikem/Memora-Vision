"""SQLite database layer for Memora Vision.

Stores videos, events, scene summaries, alert rules, alert hits,
conversations, and chat messages.
"""

import json
import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    location TEXT NOT NULL,
    recording_start_time TEXT NOT NULL,
    status TEXT NOT NULL,
    progress REAL NOT NULL DEFAULT 0,
    current_time_seconds REAL NOT NULL DEFAULT 0,
    error TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    timestamp_seconds REAL NOT NULL,
    timestamp_iso TEXT NOT NULL,
    objects_json TEXT NOT NULL,
    track_ids_json TEXT NOT NULL,
    caption TEXT NOT NULL,
    location TEXT NOT NULL,
    frame_path TEXT,
    confidence_json TEXT NOT NULL,
    activity_tags_json TEXT NOT NULL DEFAULT '[]',
    thumbnail_path TEXT,
    FOREIGN KEY(video_id) REFERENCES videos(id)
);

CREATE INDEX IF NOT EXISTS idx_events_video_time ON events(video_id, timestamp_seconds);
CREATE INDEX IF NOT EXISTS idx_events_caption ON events(caption);

CREATE TABLE IF NOT EXISTS scene_summaries (
    id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    start_seconds REAL NOT NULL,
    end_seconds REAL NOT NULL,
    start_iso TEXT NOT NULL,
    end_iso TEXT NOT NULL,
    summary TEXT NOT NULL,
    event_count INTEGER NOT NULL,
    key_objects_json TEXT NOT NULL DEFAULT '[]',
    key_activities_json TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY(video_id) REFERENCES videos(id)
);

CREATE TABLE IF NOT EXISTS alert_rules (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    object_keywords_json TEXT NOT NULL,
    cooldown_seconds INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    requires_llm INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS alert_hits (
    id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    message TEXT NOT NULL,
    timestamp_iso TEXT NOT NULL,
    FOREIGN KEY(rule_id) REFERENCES alert_rules(id),
    FOREIGN KEY(event_id) REFERENCES events(id)
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    video_id TEXT,
    title TEXT NOT NULL DEFAULT 'New Conversation',
    created_iso TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp_iso TEXT NOT NULL,
    supporting_event_ids_json TEXT DEFAULT '[]',
    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
);
"""

# Migration: add columns that may not exist in old databases
_MIGRATIONS = [
    "ALTER TABLE events ADD COLUMN activity_tags_json TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE events ADD COLUMN thumbnail_path TEXT",
    "ALTER TABLE alert_rules ADD COLUMN requires_llm INTEGER NOT NULL DEFAULT 0",
]


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
        # Run safe migrations for existing DBs
        for migration in _MIGRATIONS:
            try:
                with self.connect() as conn:
                    conn.execute(migration)
            except sqlite3.OperationalError:
                pass  # Column already exists

    def execute(self, query: str, params: Iterable[Any] = ()) -> None:
        with self.connect() as conn:
            conn.execute(query, tuple(params))

    def fetchone(self, query: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(query, tuple(params)).fetchone()
            return dict(row) if row else None

    def fetchall(self, query: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(row) for row in rows]


def dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"))


def loads(value: str) -> Any:
    return json.loads(value)
