"""Pydantic models for Memora Vision API."""

from pydantic import BaseModel, Field


# ── Video ────────────────────────────────────────────────────────────

class VideoOut(BaseModel):
    id: str
    filename: str
    location: str
    recording_start_time: str
    status: str
    progress: float
    video_url: str | None = None


class VideoStatus(BaseModel):
    video_id: str
    status: str
    progress: float
    current_time_seconds: float
    event_count: int
    alert_count: int
    error: str | None = None


# ── Events ───────────────────────────────────────────────────────────

class EventOut(BaseModel):
    id: str
    video_id: str
    timestamp_seconds: float
    timestamp_iso: str
    objects: list[str]
    track_ids: list[str]
    caption: str
    location: str
    frame_path: str | None = None
    confidence_summary: dict[str, float] = Field(default_factory=dict)
    activity_tags: list[str] = Field(default_factory=list)
    thumbnail_url: str | None = None


# ── Scene Summaries ──────────────────────────────────────────────────

class SceneSummaryOut(BaseModel):
    id: str
    video_id: str
    start_seconds: float
    end_seconds: float
    start_iso: str
    end_iso: str
    summary: str
    event_count: int
    key_objects: list[str] = Field(default_factory=list)
    key_activities: list[str] = Field(default_factory=list)


# ── Alerts ───────────────────────────────────────────────────────────

class AlertRuleIn(BaseModel):
    text: str
    cooldown_seconds: int | None = None


class AlertRuleOut(BaseModel):
    id: str
    text: str
    object_keywords: list[str]
    cooldown_seconds: int
    enabled: bool
    requires_llm: bool = False


class AlertHitOut(BaseModel):
    id: str
    rule_id: str
    event_id: str
    message: str
    timestamp_iso: str


class AlertsOut(BaseModel):
    rules: list[AlertRuleOut]
    hits: list[AlertHitOut]


# ── Conversations ────────────────────────────────────────────────────

class ChatMessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    timestamp_iso: str
    supporting_event_ids: list[str] = Field(default_factory=list)


class ConversationOut(BaseModel):
    id: str
    video_id: str | None = None
    title: str
    created_iso: str
    messages: list[ChatMessageOut] = Field(default_factory=list)


# ── Query ────────────────────────────────────────────────────────────

class QueryIn(BaseModel):
    question: str
    video_id: str | None = None
    conversation_id: str | None = None


class QueryOut(BaseModel):
    answer: str
    supporting_events: list[EventOut]
    used_fallback: bool
    conversation_id: str | None = None


# ── Upload / Status / Seed / Health ──────────────────────────────────

class UploadOut(BaseModel):
    video: VideoOut


class StatusOut(VideoStatus):
    pass


class SeedOut(BaseModel):
    video_id: str
    created_events: int
    created_rules: int
    created_hits: int


class HealthOut(BaseModel):
    ok: bool = True
    app_name: str
