from datetime import UTC, datetime

from app.services.alert_engine import compile_rule, event_matches_rule, maybe_trigger_alerts
from app.services.repository import Repository
from app.storage.database import Database


def test_compile_rule_extracts_keywords():
    rule = compile_rule("notify me when a person or bag enters", 20)
    assert rule.keywords == ["bag", "person"]


def test_event_matches_rule():
    assert event_matches_rule(["person", "bag"], "person placed bag", ["person"])
    assert not event_matches_rule(["chair"], "chair only", ["person"])


def test_alert_trigger_respects_cooldown(tmp_path):
    repo = Repository(Database(tmp_path / "demo.sqlite3"))
    video = repo.create_video("demo.mp4", "office", datetime.now(UTC).isoformat())
    repo.create_alert_rule("notify me when someone enters", ["person"], 20)
    first = repo.add_event(
        video.id,
        timestamp_seconds=1,
        timestamp_iso=datetime.now(UTC).isoformat(),
        objects=["person"],
        track_ids=["t1"],
        caption="person enters",
        location="office",
        frame_path=None,
        confidence_summary={"person": 0.9},
    )
    assert maybe_trigger_alerts(repo, first, cooldown_override=20) == 1
    second = repo.add_event(
        video.id,
        timestamp_seconds=2,
        timestamp_iso=datetime.now(UTC).isoformat(),
        objects=["person"],
        track_ids=["t2"],
        caption="person still here",
        location="office",
        frame_path=None,
        confidence_summary={"person": 0.91},
    )
    assert maybe_trigger_alerts(repo, second, cooldown_override=20) == 0

