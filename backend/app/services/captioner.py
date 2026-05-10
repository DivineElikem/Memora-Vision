"""VLM-based scene captioning for Memora Vision.

The VLM is the PRIMARY intelligence source — every sampled frame gets a rich
scene description that captures actions, appearances, and spatial relationships.
"""

import base64
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.services.text import summarize_objects


SCENE_ANALYSIS_PROMPT = (
    "You are Memora, an AI visual memory assistant analyzing camera footage.\n"
    "Describe what you see in this frame in a single detailed paragraph.\n"
    "Focus on:\n"
    "- WHO: People present — describe appearance (clothing, posture, gender if apparent)\n"
    "- WHAT: Actions being performed, objects being interacted with\n"
    "- WHERE: Spatial context — position in the scene, nearby furniture/objects\n"
    "- CHANGE: How the scene differs from the previous observation\n\n"
    "Previous observation: {previous_caption}\n"
    "Location: {location}\n"
    "Detected objects: {objects}\n\n"
    "Be specific and concrete. Write a single descriptive paragraph, no bullet points."
)


@dataclass(slots=True)
class CaptionResult:
    caption: str
    used_fallback: bool
    activity_tags: list[str] = field(default_factory=list)


class BaseCaptioner:
    def caption(
        self,
        frame: Any,
        objects: list[str],
        location: str,
        frame_index: int,
        previous_caption: str = "",
    ) -> CaptionResult:
        raise NotImplementedError


class TemplateCaptioner(BaseCaptioner):
    """Generates realistic mock captions for demo/offline mode."""

    _SCENARIOS = [
        ("entered the area and looked around cautiously", ["entering", "looking"]),
        ("walked toward the desk carrying a bag", ["walking", "carrying"]),
        ("placed a bag on the table and stepped back", ["placing", "leaving object"]),
        ("sat down at the desk and opened a laptop", ["sitting", "using device"]),
        ("stood up and moved toward the exit", ["standing", "leaving"]),
        ("picked up the bag from the table", ["picking up", "retrieving"]),
        ("remained seated, typing on the laptop", ["sitting", "working"]),
        ("walked past the camera quickly", ["walking", "passing"]),
        ("paused near the doorway", ["standing", "waiting"]),
        ("the room appears empty with a bag left on the table", ["unattended object"]),
    ]

    def caption(
        self,
        frame: Any,
        objects: list[str],
        location: str,
        frame_index: int,
        previous_caption: str = "",
    ) -> CaptionResult:
        scenario_idx = (frame_index // 45) % len(self._SCENARIOS)
        template, tags = self._SCENARIOS[scenario_idx]

        if objects:
            subject = "A person" if "person" in objects else summarize_objects(objects).capitalize()
            caption = f"{subject} {template} in {location}."
        else:
            caption = f"The {location} area is quiet with no notable activity."
            tags = ["idle"]

        return CaptionResult(caption=caption, used_fallback=True, activity_tags=tags)


class OpenAICaptioner(BaseCaptioner):
    """Calls an OpenAI-compatible VLM (e.g. Qwen2.5-VL) for rich scene captions."""

    def __init__(self, base_url: str, api_key: str | None, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def caption(
        self,
        frame: Any,
        objects: list[str],
        location: str,
        frame_index: int,
        previous_caption: str = "",
    ) -> CaptionResult:
        _, encoded = cv2_imencode(frame)
        user_prompt = SCENE_ANALYSIS_PROMPT.format(
            previous_caption=previous_caption or "No previous observation.",
            location=location,
            objects=", ".join(objects) if objects else "none detected by object detector",
        )

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a precise visual scene analyst. "
                        "Describe scenes concretely and specifically. "
                        "Never refuse to describe a scene. "
                        "Keep responses to 2-3 sentences maximum."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                        },
                    ],
                },
            ],
            "temperature": 0.3,
            "max_tokens": 256,
        }
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self.base_url}/chat/completions", json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()

        try:
            caption = data["choices"][0]["message"]["content"].strip()
        except Exception:
            obj_summary = summarize_objects(objects).capitalize()
            caption = f"{obj_summary} observed in {location}."

        # Extract activity tags from the caption
        from app.services.text import extract_activity_tags

        tags = extract_activity_tags(caption)

        return CaptionResult(caption=caption, used_fallback=False, activity_tags=tags)


def build_captioner(
    base_url: str | None, api_key: str | None, model: str
) -> BaseCaptioner:
    if not base_url:
        return TemplateCaptioner()
    return OpenAICaptioner(base_url, api_key, model)


def cv2_imencode(frame: Any) -> tuple[bool, str]:
    import cv2

    ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        raise RuntimeError("Failed to encode frame")
    return ok, base64.b64encode(buffer.tobytes()).decode("ascii")
