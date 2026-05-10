"""Scene summarization service for Memora Vision.

After video processing, groups events into activity segments and generates
narrative summaries using the LLM. Also supports deterministic fallback
when the LLM is unavailable.
"""

import logging

import httpx

from app.services.repository import Repository
from app.services.text import format_human_time, summarize_objects

logger = logging.getLogger(__name__)

# Group events into segments of this many seconds
SEGMENT_DURATION_SECONDS = 60.0


def generate_scene_summaries(repo: Repository, settings, video_id: str) -> int:
    """Generate scene summaries for a processed video. Returns count of summaries created."""
    events = repo.list_events(video_id=video_id, limit=500)
    if not events:
        return 0

    # Sort chronologically
    events_sorted = sorted(events, key=lambda e: e.timestamp_seconds)

    # Group into time segments
    segments: list[list] = []
    current_segment: list = [events_sorted[0]]

    for event in events_sorted[1:]:
        if event.timestamp_seconds - current_segment[0].timestamp_seconds > SEGMENT_DURATION_SECONDS:
            segments.append(current_segment)
            current_segment = [event]
        else:
            current_segment.append(event)
    if current_segment:
        segments.append(current_segment)

    created = 0
    for segment in segments:
        if not segment:
            continue

        start_event = segment[0]
        end_event = segment[-1]

        # Collect unique objects and activities across the segment
        all_objects: set[str] = set()
        all_activities: set[str] = set()
        captions: list[str] = []
        for event in segment:
            all_objects.update(event.objects)
            all_activities.update(event.activity_tags)
            captions.append(event.caption)

        # Try LLM summarization, fall back to deterministic
        summary = _llm_summarize(settings, captions, list(all_objects), start_event.location)
        if not summary:
            summary = _deterministic_summary(segment, list(all_objects), list(all_activities))

        repo.create_scene_summary(
            video_id=video_id,
            start_seconds=start_event.timestamp_seconds,
            end_seconds=end_event.timestamp_seconds,
            start_iso=start_event.timestamp_iso,
            end_iso=end_event.timestamp_iso,
            summary=summary,
            event_count=len(segment),
            key_objects=sorted(all_objects),
            key_activities=sorted(all_activities),
        )
        created += 1

    return created


def _llm_summarize(
    settings,
    captions: list[str],
    objects: list[str],
    location: str,
) -> str | None:
    """Use the LLM to create a narrative summary from event captions."""
    if not settings.llm_base_url:
        return None

    caption_text = "\n".join(f"- {c}" for c in captions[:20])  # Limit context
    prompt = (
        f"Summarize the following sequence of scene observations from {location} "
        f"into a brief narrative paragraph (2-3 sentences). "
        f"Focus on the key activities and movements.\n\n"
        f"Objects present: {', '.join(objects)}\n\n"
        f"Observations:\n{caption_text}"
    )

    headers = {}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    try:
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": "You are a concise scene summarizer. Write brief, clear narratives."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 200,
        }
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.warning("LLM summarization failed: %s", exc)
        return None


def _deterministic_summary(
    segment: list,
    objects: list[str],
    activities: list[str],
) -> str:
    """Generate a deterministic summary when the LLM is unavailable."""
    start_time = format_human_time(segment[0].timestamp_iso)
    end_time = format_human_time(segment[-1].timestamp_iso)
    location = segment[0].location

    parts = [f"Between {start_time} and {end_time} in {location}"]

    if objects:
        parts.append(f"{summarize_objects(objects)} {'were' if len(objects) > 1 else 'was'} observed")

    if activities:
        activity_str = ", ".join(activities[:4])
        parts.append(f"with activities including {activity_str}")

    parts.append(f"across {len(segment)} recorded moments")

    return ". ".join(parts) + "."
