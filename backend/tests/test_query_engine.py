from datetime import UTC, datetime

from app.services.query_engine import QueryEngine
from app.services.repository import Repository
from app.storage.database import Database


def test_query_engine_fallback_last_seen(tmp_path):
    repo = Repository(Database(tmp_path / "query.sqlite3"))
    video = repo.create_video("demo.mp4", "office", datetime.now(UTC).isoformat())
    repo.add_event(
        video.id,
        timestamp_seconds=10,
        timestamp_iso=datetime.now(UTC).isoformat(),
        objects=["person", "bag"],
        track_ids=["t1"],
        caption="person placed bag on the table",
        location="office",
        frame_path=None,
        confidence_summary={"person": 0.9, "bag": 0.88},
    )
    engine = QueryEngine(repo, None, None, "demo")
    answer, events, used_fallback = engine.answer("Where was my bag last seen?", video.id)
    assert "bag was last seen" in answer.lower()
    assert events
    assert used_fallback is True
