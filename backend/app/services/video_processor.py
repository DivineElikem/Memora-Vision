"""Video processing pipeline for Memora Vision.

Processes uploaded videos frame-by-frame, using YOLO for object detection
and the VLM as the primary intelligence for rich scene understanding.
Every sampled frame gets a VLM caption with previous-caption context for
scene-change awareness.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import cv2

from app.services.alert_engine import maybe_trigger_alerts
from app.services.captioner import BaseCaptioner, TemplateCaptioner, build_captioner
from app.services.detector import BaseDetector, Detection, build_detector
from app.services.repository import Repository
from app.services.text import caption_similarity, extract_activity_tags, normalize_object_label

logger = logging.getLogger(__name__)

# Minimum caption similarity to consider a frame "unchanged" (skip event creation)
SIMILARITY_THRESHOLD = 0.85

# Thumbnail width for timeline display
THUMBNAIL_WIDTH = 320


@dataclass(slots=True)
class TrackState:
    track_id: str
    label: str
    bbox: tuple[int, int, int, int]
    last_seen_frame: int


class SimpleTracker:
    def __init__(self) -> None:
        self.next_id = 1
        self.active: dict[str, TrackState] = {}

    def assign(self, detections: list[Detection], frame_index: int) -> list[tuple[Detection, str]]:
        assignments: list[tuple[Detection, str]] = []
        remaining = dict(self.active)
        updated: dict[str, TrackState] = {}
        for detection in detections:
            matched_id = None
            matched_score = 0.0
            for track_id, track in remaining.items():
                if track.label != detection.label:
                    continue
                score = iou(track.bbox, detection.bbox)
                if score > matched_score:
                    matched_id = track_id
                    matched_score = score
            if matched_id and matched_score > 0.1:
                track_id = matched_id
                remaining.pop(track_id, None)
            else:
                track_id = f"t{self.next_id}"
                self.next_id += 1
            updated[track_id] = TrackState(track_id=track_id, label=detection.label, bbox=detection.bbox, last_seen_frame=frame_index)
            assignments.append((detection, track_id))
        self.active = updated
        return assignments


def iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    return inter / float(area_a + area_b - inter)


def build_processors(settings) -> tuple[BaseDetector, BaseCaptioner]:
    detector = build_detector(settings.vision_mock_mode)
    captioner = build_captioner(settings.vlm_base_url, settings.vlm_api_key, settings.vlm_model)
    return detector, captioner


def _save_thumbnail(frame: Any, path: Path) -> None:
    """Save a resized thumbnail for the timeline UI."""
    h, w = frame.shape[:2]
    scale = THUMBNAIL_WIDTH / w
    thumb = cv2.resize(frame, (THUMBNAIL_WIDTH, int(h * scale)), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(path), thumb, [cv2.IMWRITE_JPEG_QUALITY, 75])


def process_video(
    repo: Repository,
    settings,
    video_id: str,
    file_path: Path,
    location: str,
    recording_start_time: str,
    ws_broadcast=None,
) -> None:
    """Process a video file, creating events for each meaningful scene change.

    Args:
        ws_broadcast: Optional async callable to push real-time updates to WebSocket clients.
    """
    detector, captioner = build_processors(settings)
    fallback_captioner = TemplateCaptioner()
    tracker = SimpleTracker()
    cap = cv2.VideoCapture(str(file_path))
    if not cap.isOpened():
        repo.update_video_status(video_id, "failed", 1.0, error="Unable to open uploaded video")
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    sample_stride = max(1, int(round(fps * settings.frame_sample_seconds)))
    last_caption = ""
    last_event_time = -999.0
    frame_index = 0
    created_any = False

    try:
        repo.update_video_status(video_id, "processing", 0.01)

        while True:
            ok, frame = cap.read()
            if not ok:
                break
            current_time_seconds = frame_index / fps
            if frame_index % sample_stride != 0:
                frame_index += 1
                continue

            # ── 1. Object detection (structured metadata) ──
            detections = detector.detect(frame, frame_index)
            detections = [d for d in detections if normalize_object_label(d.label)]
            assignments = tracker.assign(detections, frame_index)
            objects = sorted({normalize_object_label(d.label) for d, _ in assignments})
            track_ids = [track_id for _, track_id in assignments]

            # ── 2. Save keyframe + thumbnail ──
            frame_dir = settings.keyframe_dir / video_id
            frame_dir.mkdir(parents=True, exist_ok=True)
            frame_path = frame_dir / f"frame_{frame_index:06d}.jpg"
            thumb_path = frame_dir / f"thumb_{frame_index:06d}.jpg"
            cv2.imwrite(str(frame_path), frame)
            _save_thumbnail(frame, thumb_path)

            # ── 3. VLM captioning (primary intelligence) ──
            try:
                caption_result = captioner.caption(
                    frame, objects, location, frame_index, previous_caption=last_caption
                )
            except Exception as exc:
                logger.warning("VLM caption failed, using fallback: %s", exc)
                caption_result = fallback_captioner.caption(
                    frame, objects, location, frame_index, previous_caption=last_caption
                )

            timestamp_iso = iso_from_start(recording_start_time, current_time_seconds)
            caption = caption_result.caption
            activity_tags = caption_result.activity_tags

            # ── 4. Scene-change significance ──
            similarity = caption_similarity(caption, last_caption)
            objects_changed = set(objects) != set()  # Any objects present is interesting
            caption_is_new = similarity < SIMILARITY_THRESHOLD
            heartbeat = (current_time_seconds - last_event_time) >= 10.0

            if not created_any or caption_is_new or heartbeat:
                event = repo.add_event(
                    video_id=video_id,
                    timestamp_seconds=current_time_seconds,
                    timestamp_iso=timestamp_iso,
                    objects=objects,
                    track_ids=track_ids,
                    caption=caption,
                    location=location,
                    frame_path=str(frame_path),
                    confidence_summary={d.label: d.confidence for d in detections},
                    activity_tags=activity_tags,
                    thumbnail_path=str(thumb_path),
                )
                maybe_trigger_alerts(repo, event, cooldown_override=settings.alert_cooldown_seconds)
                created_any = True
                last_caption = caption
                last_event_time = current_time_seconds

                # Push to WebSocket if available
                if ws_broadcast:
                    try:
                        import asyncio
                        asyncio.run(ws_broadcast("new_event", {
                            "event_id": event.id,
                            "video_id": video_id,
                            "caption": caption,
                            "timestamp_iso": timestamp_iso,
                        }))
                    except Exception:
                        pass

            progress = min(0.99, frame_index / max(total_frames, 1)) if total_frames else 0.5
            repo.update_video_status(video_id, "processing", progress, current_time_seconds=current_time_seconds)
            frame_index += 1

        repo.update_video_status(video_id, "completed", 1.0, current_time_seconds=frame_index / fps)

        # ── 5. Post-processing: generate scene summaries ──
        try:
            from app.services.summarizer import generate_scene_summaries
            generate_scene_summaries(repo, settings, video_id)
        except Exception as exc:
            logger.warning("Scene summarization failed: %s", exc)

    except Exception as exc:  # pragma: no cover - demo safety
        logger.exception("Video processing failed")
        repo.update_video_status(
            video_id, "failed",
            min(0.99, frame_index / max(total_frames, 1)),
            current_time_seconds=frame_index / fps,
            error=str(exc),
        )
    finally:
        cap.release()


def iso_from_start(recording_start_time: str, offset_seconds: float) -> str:
    try:
        start = datetime.fromisoformat(recording_start_time)
    except ValueError:
        start = datetime.now(UTC)
    return (start + timedelta(seconds=offset_seconds)).astimezone(UTC).isoformat()
