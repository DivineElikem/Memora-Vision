"""Text utilities for Memora Vision.

Handles object label normalization, synonym expansion, activity tag extraction,
and caption similarity comparison.
"""

import re
from datetime import UTC, datetime
from difflib import SequenceMatcher


def format_human_time(timestamp_iso: str) -> str:
    try:
        dt = datetime.fromisoformat(timestamp_iso)
        return dt.astimezone(UTC).strftime("%H:%M:%S")
    except Exception:
        return timestamp_iso


# ── Object synonyms ──────────────────────────────────────────────────

OBJECT_SYNONYMS: dict[str, list[str]] = {
    "person": ["person", "people", "someone", "anyone", "man", "woman", "human", "individual", "figure", "pedestrian"],
    "bag": ["bag", "backpack", "handbag", "suitcase", "luggage", "purse", "briefcase", "rucksack"],
    "cell phone": ["phone", "cell phone", "mobile", "smartphone", "device"],
    "laptop": ["laptop", "computer", "notebook", "macbook"],
    "chair": ["chair", "seat", "stool"],
    "bottle": ["bottle", "water bottle"],
    "cup": ["cup", "mug", "glass"],
    "book": ["book", "notebook", "journal"],
    "car": ["car", "vehicle", "automobile", "sedan"],
    "dog": ["dog", "puppy", "canine"],
    "cat": ["cat", "kitten", "feline"],
    "bicycle": ["bicycle", "bike", "cycle"],
    "motorcycle": ["motorcycle", "motorbike", "scooter"],
    "bus": ["bus"],
    "truck": ["truck", "van", "lorry"],
    "umbrella": ["umbrella"],
    "clock": ["clock", "watch"],
    "tv": ["tv", "television", "monitor", "screen", "display"],
    "keyboard": ["keyboard"],
    "mouse": ["mouse"],
    "couch": ["couch", "sofa", "loveseat"],
    "bed": ["bed"],
    "dining table": ["table", "desk", "dining table", "counter", "workstation"],
    "potted plant": ["plant", "potted plant", "flower"],
    "remote": ["remote", "remote control"],
}


# ── Activity tags ─────────────────────────────────────────────────────

ACTIVITY_PATTERNS: list[tuple[str, list[str]]] = [
    (r"\b(enter|entering|entered|arrives?|arriving|arrived|came in|walks? in|walked in)\b", ["entering"]),
    (r"\b(leav|leaving|left|exit|exiting|exited|depart|walks? out|walked out|went out|goes out)\b", ["leaving"]),
    (r"\b(plac|placing|placed|put|puts|putting|set down|setting down|left behind)\b", ["placing"]),
    (r"\b(pick|picking|picked up|grab|grabbing|grabbed|retriev|collecting|collected)\b", ["picking up"]),
    (r"\b(sit|sitting|sat|seated)\b", ["sitting"]),
    (r"\b(stand|standing|stood)\b", ["standing"]),
    (r"\b(walk|walking|walked|moving|moved|pacing)\b", ["walking"]),
    (r"\b(run|running|ran|rushing|hurrying)\b", ["running"]),
    (r"\b(talk|talking|convers|speaking|chatting|discussing)\b", ["talking"]),
    (r"\b(typ|typing|typed|using|operat)\b", ["using device"]),
    (r"\b(carry|carrying|carried|holding|held)\b", ["carrying"]),
    (r"\b(look|looking|watched|watching|observ|gazing|staring)\b", ["looking"]),
    (r"\b(open|opening|opened|clos|closing|closed)\b", ["interacting"]),
    (r"\b(wait|waiting|waited|paused|lingering)\b", ["waiting"]),
    (r"\b(empty|vacant|quiet|no one|unoccupied|idle)\b", ["idle"]),
    (r"\b(unattended|left behind|abandoned)\b", ["unattended object"]),
]


def extract_activity_tags(caption: str) -> list[str]:
    """Extract activity keywords from a VLM caption."""
    lowered = caption.lower()
    found: list[str] = []
    for pattern, tags in ACTIVITY_PATTERNS:
        if re.search(pattern, lowered):
            found.extend(tags)
    return sorted(set(found)) if found else ["observed"]


# ── Object normalization ──────────────────────────────────────────────

_NORMALIZE_MAP: dict[str, str] = {
    "backpack": "bag",
    "handbag": "bag",
    "suitcase": "bag",
}


def normalize_object_label(label: str) -> str:
    normalized = label.strip().lower()
    return _NORMALIZE_MAP.get(normalized, normalized)


def extract_object_keywords(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for canonical, synonyms in OBJECT_SYNONYMS.items():
        if any(re.search(rf"\b{re.escape(word)}\b", lowered) for word in synonyms):
            found.append(canonical)
    return sorted(set(found))


def summarize_objects(objects: list[str]) -> str:
    if not objects:
        return "nothing notable"
    if len(objects) == 1:
        return objects[0]
    if len(objects) == 2:
        return f"{objects[0]} and {objects[1]}"
    return ", ".join(objects[:-1]) + f", and {objects[-1]}"


# ── Caption similarity ───────────────────────────────────────────────

def caption_similarity(a: str, b: str) -> float:
    """Return 0.0–1.0 similarity between two captions using SequenceMatcher."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


# ── Time parsing ──────────────────────────────────────────────────────

TIME_RANGE_PATTERNS: list[tuple[str, tuple[int, int]]] = [
    (r"\bmorning\b", (6, 12)),
    (r"\bafternoon\b", (12, 17)),
    (r"\bevening\b", (17, 21)),
    (r"\bnight\b", (21, 6)),
    (r"\btoday\b", (0, 24)),
]


def parse_time_hint(text: str) -> tuple[int, int] | None:
    """Extract a time-of-day range hint from a query. Returns (start_hour, end_hour) or None."""
    lowered = text.lower()
    for pattern, hours in TIME_RANGE_PATTERNS:
        if re.search(pattern, lowered):
            return hours
    return None
