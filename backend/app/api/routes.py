"""Memora Vision API routes."""

from __future__ import annotations

import shutil
import threading
from datetime import UTC, datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import Settings
from app.models.schemas import (
    AlertRuleIn,
    AlertRuleOut,
    AlertsOut,
    ConversationOut,
    ChatMessageOut,
    EventOut,
    HealthOut,
    QueryIn,
    QueryOut,
    SceneSummaryOut,
    SeedOut,
    StatusOut,
    UploadOut,
)
from app.services.alert_engine import compile_rule
from app.services.query_engine import QueryEngine
from app.services.repository import Repository
from app.services.video_processor import process_video


def create_router(settings: Settings, repo: Repository) -> APIRouter:
    router = APIRouter()

    @router.get("/health", response_model=HealthOut)
    def health() -> HealthOut:
        return HealthOut(app_name=settings.app_name)

    # ── Video Upload & Status ─────────────────────────────────────────

    @router.post("/upload", response_model=UploadOut)
    def upload(
        file: UploadFile = File(...),
        location: str = Form("office"),
        recording_start_time: str = Form(""),
    ) -> UploadOut:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Missing filename")
        if not recording_start_time:
            recording_start_time = datetime.now(UTC).isoformat()
        video = repo.create_video(file.filename, location, recording_start_time)
        destination = settings.upload_dir / video.id / file.filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        repo.update_video_status(video.id, "queued", 0.01)
        thread = threading.Thread(
            target=process_video,
            args=(repo, settings, video.id, destination, location, recording_start_time),
            daemon=True,
        )
        thread.start()
        return UploadOut(video=repo.get_video(video.id))

    @router.get("/videos/{video_id}/status", response_model=StatusOut)
    def video_status(video_id: str) -> StatusOut:
        try:
            return repo.get_status(video_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Video not found") from exc

    # ── Events ────────────────────────────────────────────────────────

    @router.get("/events", response_model=list[EventOut])
    def events(video_id: str | None = None, object: str | None = None, limit: int = 100) -> list[EventOut]:
        return repo.list_events(video_id=video_id, object_name=object, limit=limit)

    # ── Query (Conversational) ────────────────────────────────────────

    @router.post("/query", response_model=QueryOut)
    def query(payload: QueryIn) -> QueryOut:
        engine = QueryEngine(repo, settings.llm_base_url, settings.llm_api_key, settings.llm_model)
        answer, events, used_fallback, conversation_id = engine.answer(
            payload.question, payload.video_id, payload.conversation_id
        )
        return QueryOut(
            answer=answer,
            supporting_events=events,
            used_fallback=used_fallback,
            conversation_id=conversation_id,
        )

    # ── Conversations ─────────────────────────────────────────────────

    @router.get("/conversations", response_model=list[ConversationOut])
    def list_conversations() -> list[ConversationOut]:
        return repo.list_conversations()

    @router.get("/conversations/{conversation_id}/messages", response_model=list[ChatMessageOut])
    def conversation_messages(conversation_id: str) -> list[ChatMessageOut]:
        return repo.get_conversation_messages(conversation_id)

    # ── Scene Summaries ───────────────────────────────────────────────

    @router.get("/summaries", response_model=list[SceneSummaryOut])
    def summaries(video_id: str | None = None) -> list[SceneSummaryOut]:
        return repo.list_scene_summaries(video_id=video_id)

    # ── Alerts ────────────────────────────────────────────────────────

    @router.post("/alert", response_model=AlertRuleOut)
    def create_alert(payload: AlertRuleIn) -> AlertRuleOut:
        cooldown = payload.cooldown_seconds or settings.alert_cooldown_seconds
        compiled = compile_rule(payload.text, cooldown)
        rule = repo.create_alert_rule(
            payload.text, compiled.keywords, compiled.cooldown_seconds,
            requires_llm=compiled.requires_llm,
        )
        return rule

    @router.get("/alerts", response_model=AlertsOut)
    def alerts() -> AlertsOut:
        return AlertsOut(rules=repo.list_alert_rules(), hits=repo.list_alert_hits())

    @router.delete("/alerts/rules/{rule_id}")
    def delete_alert_rule(rule_id: str) -> dict:
        repo.delete_alert_rule(rule_id)
        return {"ok": True}

    @router.delete("/alerts/hits")
    def clear_alert_hits() -> dict:
        repo.clear_alert_hits()
        return {"ok": True}

    # ── Seed (Demo) ───────────────────────────────────────────────────

    @router.post("/seed", response_model=SeedOut)
    def seed() -> SeedOut:
        created_events = 0
        created_rules = 0
        created_hits = 0
        video = repo.create_video("seed-demo.mp4", "Main Office", datetime.now(UTC).isoformat())

        demo_events = [
            (["person"], "A person in a dark jacket entered the main office through the front door, looking around the room.",
             ["entering", "looking"], 0.0),
            (["person", "bag"], "The same person placed a black backpack on the desk near the window and sat down at the workstation.",
             ["placing", "sitting"], 12.0),
            (["person", "bag", "laptop"], "The person opened a laptop from the bag and began typing. A water bottle is visible on the desk.",
             ["using device", "sitting"], 24.0),
            (["person"], "The person stood up and walked toward the exit, leaving the bag and laptop on the desk.",
             ["standing", "leaving"], 45.0),
            (["bag", "laptop"], "The office is now empty. A black backpack and open laptop remain unattended on the desk near the window.",
             ["unattended object", "idle"], 60.0),
            (["person", "bag"], "A different person entered and picked up the backpack from the desk.",
             ["entering", "picking up"], 80.0),
        ]

        for objects, caption, tags, ts in demo_events:
            event = repo.add_event(
                video_id=video.id,
                timestamp_seconds=ts,
                timestamp_iso=datetime.now(UTC).isoformat(),
                objects=objects,
                track_ids=[f"seed-t{int(ts)}"],
                caption=caption,
                location="Main Office",
                frame_path=None,
                confidence_summary={obj: 0.9 for obj in objects},
                activity_tags=tags,
            )
            created_events += 1
            created_hits += _maybe_seed_alert(repo, event)

        rule = repo.create_alert_rule("notify me when someone enters", ["person"], settings.alert_cooldown_seconds)
        created_rules += 1
        first_events = repo.list_events(video_id=video.id, limit=1)
        if first_events:
            repo.add_alert_hit(rule.id, first_events[0].id, "Someone entered the Main Office", datetime.now(UTC).isoformat())
            created_hits += 1

        return SeedOut(video_id=video.id, created_events=created_events, created_rules=created_rules, created_hits=created_hits)

    return router


def _maybe_seed_alert(repo: Repository, event) -> int:
    count = 0
    for rule in repo.list_alert_rules():
        if any(keyword in event.objects for keyword in rule.object_keywords):
            repo.add_alert_hit(rule.id, event.id, f"{rule.text} — {event.caption}", event.timestamp_iso)
            count += 1
    return count
