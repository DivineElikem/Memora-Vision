"""Intelligent alert engine for Memora Vision.

Two-tier matching:
1. Fast path — keyword matching for simple rules (e.g., "notify me when a person enters")
2. Smart path — LLM evaluation for semantic rules (e.g., "alert me when something unusual happens")
"""

import logging
from dataclasses import dataclass

import httpx

from app.services.repository import Repository
from app.services.text import extract_object_keywords, format_human_time
from app.services.notifier import send_alert_email

logger = logging.getLogger(__name__)

# Keywords that indicate a rule needs LLM evaluation (semantic matching)
_SEMANTIC_INDICATORS = [
    "unusual", "suspicious", "strange", "abnormal", "weird", "unexpected",
    "dangerous", "threatening", "emergency", "unsafe", "wrong",
    "crowded", "busy", "empty for too long",
    "running", "fighting", "arguing", "falling",
]


@dataclass(slots=True)
class CompiledRule:
    keywords: list[str]
    cooldown_seconds: int
    requires_llm: bool


def compile_rule(text: str, cooldown_seconds: int) -> CompiledRule:
    """Compile a natural-language alert rule into structured matchers.

    Rules containing semantic concepts (e.g., 'unusual', 'suspicious') are
    flagged as requiring LLM evaluation.
    """
    keywords = extract_object_keywords(text)
    lowered = text.lower()
    requires_llm = any(indicator in lowered for indicator in _SEMANTIC_INDICATORS)

    # If no keywords found and it's not semantic, try to treat the whole text
    # as a description for LLM matching
    if not keywords and not requires_llm:
        requires_llm = True

    return CompiledRule(keywords=keywords, cooldown_seconds=cooldown_seconds, requires_llm=requires_llm)


def event_matches_rule(objects: list[str], caption: str, keywords: list[str]) -> bool:
    """Fast-path keyword matching."""
    if not keywords:
        return False
    haystack = " ".join([*objects, caption]).lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def _llm_evaluate_rule(
    rule_text: str,
    caption: str,
    objects: list[str],
    settings,
) -> bool:
    """Use the LLM to evaluate whether a scene matches a semantic alert rule."""
    if not settings.llm_base_url:
        return False

    prompt = (
        f"Does the following scene match this alert condition?\n\n"
        f"Alert condition: \"{rule_text}\"\n\n"
        f"Scene description: {caption}\n"
        f"Objects present: {', '.join(objects) if objects else 'none'}\n\n"
        f"Answer with only YES or NO."
    )

    headers = {}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    try:
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": "You are an alert evaluation system. Answer only YES or NO."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 10,
        }
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            answer = data["choices"][0]["message"]["content"].strip().upper()
            return answer.startswith("YES")
    except Exception as exc:
        logger.warning("LLM alert evaluation failed: %s", exc)
        return False


def maybe_trigger_alerts(
    repo: Repository,
    event,
    cooldown_override: int | None = None,
    settings=None,
) -> int:
    """Check all enabled rules against a new event and create alert hits.

    Args:
        settings: Required for LLM-based alert evaluation. If None, only
                  keyword matching is used.
    """
    created = 0
    rules = repo.list_alert_rules()
    for rule in rules:
        if not rule.enabled:
            continue

        # Check cooldown first (cheap operation)
        cooldown_seconds = cooldown_override or rule.cooldown_seconds
        latest = repo.latest_hit_for_rule(rule.id)
        if latest:
            last_event = repo.get_event(latest.event_id)
            delta = event.timestamp_seconds - last_event.timestamp_seconds
            if delta < cooldown_seconds:
                continue

        # Two-tier matching
        matched = False

        # Fast path: keyword matching
        if rule.object_keywords:
            matched = event_matches_rule(event.objects, event.caption, rule.object_keywords)

        # Smart path: LLM evaluation (only if fast path didn't match and rule needs LLM)
        if not matched and rule.requires_llm and settings:
            matched = _llm_evaluate_rule(
                rule.text, event.caption, event.objects, settings
            )

        if not matched:
            continue

        message = f"{rule.text} — {event.caption} ({format_human_time(event.timestamp_iso)})"
        repo.add_alert_hit(rule.id, event.id, message, event.timestamp_iso)
        send_alert_email(rule.text, message)
        created += 1

    return created
