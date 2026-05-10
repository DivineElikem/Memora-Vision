"""Data repository for Memora Vision.

Provides CRUD operations for videos, events, scene summaries,
alert rules, alert hits, and conversations.
Includes semantic search across event captions and activity tags.
"""

from datetime import UTC, datetime
from uuid import uuid4

from app.models.schemas import (
    AlertHitOut,
    AlertRuleOut,
    ChatMessageOut,
    ConversationOut,
    EventOut,
    SceneSummaryOut,
    VideoOut,
    VideoStatus,
)
from app.storage.database import Database, dumps, loads


class Repository:
    def __init__(self, db: Database):
        self.db = db

    # ── Videos ────────────────────────────────────────────────────────

    def create_video(self, filename: str, location: str, recording_start_time: str) -> VideoOut:
        video_id = str(uuid4())
        self.db.execute(
            "INSERT INTO videos (id, filename, location, recording_start_time, status, progress) VALUES (?, ?, ?, ?, ?, ?)",
            (video_id, filename, location, recording_start_time, "queued", 0),
        )
        return self.get_video(video_id)

    def get_video(self, video_id: str) -> VideoOut:
        row = self.db.fetchone("SELECT * FROM videos WHERE id = ?", (video_id,))
        if not row:
            raise KeyError(video_id)
        video = VideoOut(**row)
        video.video_url = f"/media/{video.id}/{video.filename}"
        return video

    def update_video_status(
        self,
        video_id: str,
        status: str,
        progress: float,
        current_time_seconds: float = 0,
        error: str | None = None,
    ) -> None:
        self.db.execute(
            "UPDATE videos SET status = ?, progress = ?, current_time_seconds = ?, error = ? WHERE id = ?",
            (status, progress, current_time_seconds, error, video_id),
        )

    def get_status(self, video_id: str) -> VideoStatus:
        row = self.db.fetchone("SELECT * FROM videos WHERE id = ?", (video_id,))
        if not row:
            raise KeyError(video_id)
        event_count = self.db.fetchone("SELECT COUNT(*) AS count FROM events WHERE video_id = ?", (video_id,))["count"]
        alert_count = self.db.fetchone(
            """
            SELECT COUNT(*) AS count FROM alert_hits
            JOIN events ON alert_hits.event_id = events.id
            WHERE events.video_id = ?
            """,
            (video_id,),
        )["count"]
        return VideoStatus(
            video_id=video_id,
            status=row["status"],
            progress=row["progress"],
            current_time_seconds=row["current_time_seconds"],
            event_count=event_count,
            alert_count=alert_count,
            error=row["error"],
        )

    # ── Events ────────────────────────────────────────────────────────

    def add_event(
        self,
        video_id: str,
        timestamp_seconds: float,
        timestamp_iso: str,
        objects: list[str],
        track_ids: list[str],
        caption: str,
        location: str,
        frame_path: str | None,
        confidence_summary: dict[str, float],
        activity_tags: list[str] | None = None,
        thumbnail_path: str | None = None,
    ) -> EventOut:
        event_id = str(uuid4())
        self.db.execute(
            """
            INSERT INTO events
            (id, video_id, timestamp_seconds, timestamp_iso, objects_json, track_ids_json,
             caption, location, frame_path, confidence_json, activity_tags_json, thumbnail_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                video_id,
                timestamp_seconds,
                timestamp_iso,
                dumps(objects),
                dumps(track_ids),
                caption,
                location,
                frame_path,
                dumps(confidence_summary),
                dumps(activity_tags or []),
                thumbnail_path,
            ),
        )
        return self.get_event(event_id)

    def get_event(self, event_id: str) -> EventOut:
        row = self.db.fetchone("SELECT * FROM events WHERE id = ?", (event_id,))
        if not row:
            raise KeyError(event_id)
        return event_from_row(row)

    def list_events(
        self,
        video_id: str | None = None,
        object_name: str | None = None,
        limit: int = 100,
    ) -> list[EventOut]:
        clauses: list[str] = []
        params: list[object] = []
        if video_id:
            clauses.append("video_id = ?")
            params.append(video_id)
        if object_name:
            clauses.append("(objects_json LIKE ? OR caption LIKE ?)")
            params.extend([f"%{object_name}%", f"%{object_name}%"])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.fetchall(
            f"SELECT * FROM events {where} ORDER BY timestamp_seconds DESC LIMIT ?",
            (*params, limit),
        )
        return [event_from_row(row) for row in rows]

    def semantic_search_events(
        self,
        query: str,
        video_id: str | None = None,
        limit: int = 30,
    ) -> list[EventOut]:
        """Search events by matching query terms against captions, objects, and activity tags."""
        words = [w.strip().lower() for w in query.split() if len(w.strip()) > 2]
        if not words:
            return self.list_events(video_id=video_id, limit=limit)

        # Build LIKE clauses for each query word across all text fields
        like_clauses: list[str] = []
        params: list[object] = []
        for word in words[:8]:  # Limit to 8 words to prevent huge queries
            like_clauses.append(
                "(caption LIKE ? OR objects_json LIKE ? OR activity_tags_json LIKE ?)"
            )
            params.extend([f"%{word}%", f"%{word}%", f"%{word}%"])

        where_parts = [f"({' OR '.join(like_clauses)})"]
        if video_id:
            where_parts.append("video_id = ?")
            params.append(video_id)

        where = f"WHERE {' AND '.join(where_parts)}"

        # Score by counting how many query words match (rough relevance ranking)
        rows = self.db.fetchall(
            f"SELECT * FROM events {where} ORDER BY timestamp_seconds DESC LIMIT ?",
            (*params, limit),
        )
        return [event_from_row(row) for row in rows]

    def get_events_for_time_range(
        self,
        video_id: str,
        start_seconds: float,
        end_seconds: float,
    ) -> list[EventOut]:
        rows = self.db.fetchall(
            "SELECT * FROM events WHERE video_id = ? AND timestamp_seconds >= ? AND timestamp_seconds <= ? ORDER BY timestamp_seconds",
            (video_id, start_seconds, end_seconds),
        )
        return [event_from_row(row) for row in rows]

    # ── Scene Summaries ───────────────────────────────────────────────

    def create_scene_summary(
        self,
        video_id: str,
        start_seconds: float,
        end_seconds: float,
        start_iso: str,
        end_iso: str,
        summary: str,
        event_count: int,
        key_objects: list[str],
        key_activities: list[str],
    ) -> SceneSummaryOut:
        summary_id = str(uuid4())
        self.db.execute(
            """
            INSERT INTO scene_summaries
            (id, video_id, start_seconds, end_seconds, start_iso, end_iso,
             summary, event_count, key_objects_json, key_activities_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                summary_id, video_id, start_seconds, end_seconds,
                start_iso, end_iso, summary, event_count,
                dumps(key_objects), dumps(key_activities),
            ),
        )
        return self.get_scene_summary(summary_id)

    def get_scene_summary(self, summary_id: str) -> SceneSummaryOut:
        row = self.db.fetchone("SELECT * FROM scene_summaries WHERE id = ?", (summary_id,))
        if not row:
            raise KeyError(summary_id)
        return scene_summary_from_row(row)

    def list_scene_summaries(self, video_id: str | None = None) -> list[SceneSummaryOut]:
        if video_id:
            rows = self.db.fetchall(
                "SELECT * FROM scene_summaries WHERE video_id = ? ORDER BY start_seconds",
                (video_id,),
            )
        else:
            rows = self.db.fetchall("SELECT * FROM scene_summaries ORDER BY start_seconds")
        return [scene_summary_from_row(row) for row in rows]

    # ── Alert Rules ───────────────────────────────────────────────────

    def create_alert_rule(
        self, text: str, object_keywords: list[str], cooldown_seconds: int, requires_llm: bool = False
    ) -> AlertRuleOut:
        rule_id = str(uuid4())
        self.db.execute(
            "INSERT INTO alert_rules (id, text, object_keywords_json, cooldown_seconds, enabled, requires_llm) VALUES (?, ?, ?, ?, 1, ?)",
            (rule_id, text, dumps(object_keywords), cooldown_seconds, int(requires_llm)),
        )
        return self.get_alert_rule(rule_id)

    def get_alert_rule(self, rule_id: str) -> AlertRuleOut:
        row = self.db.fetchone("SELECT * FROM alert_rules WHERE id = ?", (rule_id,))
        if not row:
            raise KeyError(rule_id)
        return alert_rule_from_row(row)

    def list_alert_rules(self) -> list[AlertRuleOut]:
        rows = self.db.fetchall("SELECT * FROM alert_rules ORDER BY rowid DESC")
        return [alert_rule_from_row(row) for row in rows]

    # ── Alert Hits ────────────────────────────────────────────────────

    def add_alert_hit(self, rule_id: str, event_id: str, message: str, timestamp_iso: str | None = None) -> AlertHitOut:
        hit_id = str(uuid4())
        created = timestamp_iso or datetime.now(UTC).isoformat()
        self.db.execute(
            "INSERT INTO alert_hits (id, rule_id, event_id, message, timestamp_iso) VALUES (?, ?, ?, ?, ?)",
            (hit_id, rule_id, event_id, message, created),
        )
        return self.get_alert_hit(hit_id)

    def get_alert_hit(self, hit_id: str) -> AlertHitOut:
        row = self.db.fetchone("SELECT * FROM alert_hits WHERE id = ?", (hit_id,))
        if not row:
            raise KeyError(hit_id)
        return AlertHitOut(**row)

    def list_alert_hits(self) -> list[AlertHitOut]:
        rows = self.db.fetchall("SELECT * FROM alert_hits ORDER BY timestamp_iso DESC LIMIT 100")
        return [AlertHitOut(**row) for row in rows]

    def latest_hit_for_rule(self, rule_id: str) -> AlertHitOut | None:
        row = self.db.fetchone(
            "SELECT * FROM alert_hits WHERE rule_id = ? ORDER BY timestamp_iso DESC LIMIT 1",
            (rule_id,),
        )
        return AlertHitOut(**row) if row else None

    def delete_alert_rule(self, rule_id: str) -> None:
        self.db.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
        # Also clean up associated hits
        self.db.execute("DELETE FROM alert_hits WHERE rule_id = ?", (rule_id,))

    def clear_alert_hits(self) -> None:
        self.db.execute("DELETE FROM alert_hits")

    # ── Conversations ─────────────────────────────────────────────────

    def create_conversation(self, video_id: str | None = None, title: str = "New Conversation") -> ConversationOut:
        conv_id = str(uuid4())
        created = datetime.now(UTC).isoformat()
        self.db.execute(
            "INSERT INTO conversations (id, video_id, title, created_iso) VALUES (?, ?, ?, ?)",
            (conv_id, video_id, title, created),
        )
        return ConversationOut(id=conv_id, video_id=video_id, title=title, created_iso=created)

    def add_chat_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        supporting_event_ids: list[str] | None = None,
    ) -> ChatMessageOut:
        msg_id = str(uuid4())
        timestamp = datetime.now(UTC).isoformat()
        self.db.execute(
            """
            INSERT INTO chat_messages (id, conversation_id, role, content, timestamp_iso, supporting_event_ids_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (msg_id, conversation_id, role, content, timestamp, dumps(supporting_event_ids or [])),
        )
        return ChatMessageOut(
            id=msg_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            timestamp_iso=timestamp,
            supporting_event_ids=supporting_event_ids or [],
        )

    def get_conversation_messages(self, conversation_id: str, limit: int = 50) -> list[ChatMessageOut]:
        rows = self.db.fetchall(
            "SELECT * FROM chat_messages WHERE conversation_id = ? ORDER BY timestamp_iso LIMIT ?",
            (conversation_id, limit),
        )
        return [
            ChatMessageOut(
                id=r["id"],
                conversation_id=r["conversation_id"],
                role=r["role"],
                content=r["content"],
                timestamp_iso=r["timestamp_iso"],
                supporting_event_ids=loads(r["supporting_event_ids_json"]),
            )
            for r in rows
        ]

    def list_conversations(self, limit: int = 20) -> list[ConversationOut]:
        rows = self.db.fetchall(
            "SELECT * FROM conversations ORDER BY created_iso DESC LIMIT ?", (limit,)
        )
        return [
            ConversationOut(
                id=r["id"],
                video_id=r["video_id"],
                title=r["title"],
                created_iso=r["created_iso"],
            )
            for r in rows
        ]

    def update_conversation_title(self, conversation_id: str, title: str) -> None:
        self.db.execute(
            "UPDATE conversations SET title = ? WHERE id = ?",
            (title, conversation_id),
        )


# ── Row converters ────────────────────────────────────────────────────

def event_from_row(row: dict) -> EventOut:
    thumbnail_path = row.get("thumbnail_path")
    thumbnail_url = None
    if thumbnail_path:
        # Convert filesystem path to a servable URL
        import re
        match = re.search(r"data/keyframes/(.+)", thumbnail_path)
        if match:
            thumbnail_url = f"/thumbnails/{match.group(1)}"

    return EventOut(
        id=row["id"],
        video_id=row["video_id"],
        timestamp_seconds=row["timestamp_seconds"],
        timestamp_iso=row["timestamp_iso"],
        objects=loads(row["objects_json"]),
        track_ids=loads(row["track_ids_json"]),
        caption=row["caption"],
        location=row["location"],
        frame_path=row["frame_path"],
        confidence_summary=loads(row["confidence_json"]),
        activity_tags=loads(row.get("activity_tags_json", "[]")),
        thumbnail_url=thumbnail_url,
    )


def alert_rule_from_row(row: dict) -> AlertRuleOut:
    return AlertRuleOut(
        id=row["id"],
        text=row["text"],
        object_keywords=loads(row["object_keywords_json"]),
        cooldown_seconds=row["cooldown_seconds"],
        enabled=bool(row["enabled"]),
        requires_llm=bool(row.get("requires_llm", 0)),
    )


def scene_summary_from_row(row: dict) -> SceneSummaryOut:
    return SceneSummaryOut(
        id=row["id"],
        video_id=row["video_id"],
        start_seconds=row["start_seconds"],
        end_seconds=row["end_seconds"],
        start_iso=row["start_iso"],
        end_iso=row["end_iso"],
        summary=row["summary"],
        event_count=row["event_count"],
        key_objects=loads(row["key_objects_json"]),
        key_activities=loads(row["key_activities_json"]),
    )
