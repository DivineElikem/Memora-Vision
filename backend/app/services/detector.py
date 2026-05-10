"""Object detection via YOLO for Memora Vision.

YOLO provides structured object metadata (bounding boxes, labels, confidence)
that supplements the VLM's rich scene descriptions. The expanded class whitelist
covers common indoor and outdoor surveillance objects.
"""

from dataclasses import dataclass
from typing import Any

import cv2

from app.services.text import normalize_object_label

try:
    from ultralytics import YOLO  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    YOLO = None


# Expanded set of COCO classes relevant to surveillance/monitoring scenarios
ALLOWED_LABELS: set[str] = {
    "person", "bag", "cell phone", "laptop", "chair", "bottle", "cup", "book",
    "car", "dog", "cat", "bicycle", "motorcycle", "bus", "truck",
    "umbrella", "clock", "tv", "keyboard", "mouse", "scissors",
    "couch", "bed", "dining table", "potted plant", "remote",
}

# Minimum confidence to keep a detection
MIN_CONFIDENCE = 0.3


@dataclass(slots=True)
class Detection:
    label: str
    confidence: float
    bbox: tuple[int, int, int, int]


class BaseDetector:
    def detect(self, frame: Any, frame_index: int) -> list[Detection]:
        raise NotImplementedError


class MockDetector(BaseDetector):
    """Generates varied mock detections that create a realistic narrative."""

    def detect(self, frame: Any, frame_index: int) -> list[Detection]:
        height, width = frame.shape[:2]
        tick = frame_index // 30  # Roughly once per second of video

        if tick < 3:
            return []
        if 3 <= tick < 8:
            return [
                Detection(label="person", confidence=0.92,
                          bbox=(width // 4, height // 4, width // 2, height // 2)),
            ]
        if 8 <= tick < 15:
            return [
                Detection(label="person", confidence=0.94,
                          bbox=(width // 3, height // 4, width * 2 // 3, height * 2 // 3)),
                Detection(label="bag", confidence=0.88,
                          bbox=(width // 2, height // 2, width * 2 // 3, height * 3 // 4)),
            ]
        if 15 <= tick < 22:
            return [
                Detection(label="person", confidence=0.91,
                          bbox=(width // 3, height // 5, width * 2 // 3, height * 3 // 5)),
                Detection(label="bag", confidence=0.86,
                          bbox=(width // 2, height // 2, width * 2 // 3, height * 3 // 4)),
                Detection(label="laptop", confidence=0.79,
                          bbox=(width * 2 // 5, height * 2 // 5, width * 3 // 5, height // 2)),
            ]
        if 22 <= tick < 30:
            # Person leaves, objects remain
            return [
                Detection(label="bag", confidence=0.91,
                          bbox=(width // 2, height // 2, width * 2 // 3, height * 3 // 4)),
                Detection(label="laptop", confidence=0.82,
                          bbox=(width * 2 // 5, height * 2 // 5, width * 3 // 5, height // 2)),
            ]
        if 30 <= tick < 38:
            # New person enters
            return [
                Detection(label="person", confidence=0.85,
                          bbox=(width // 6, height // 4, width // 3, height * 2 // 3)),
                Detection(label="bag", confidence=0.89,
                          bbox=(width // 2, height // 2, width * 2 // 3, height * 3 // 4)),
            ]
        # Person picks up bag and leaves
        return [
            Detection(label="person", confidence=0.87,
                      bbox=(width // 3, height // 4, width // 2, height * 2 // 3)),
        ]


class YoloDetector(BaseDetector):
    def __init__(self, model_name: str = "yolov8n.pt"):
        if YOLO is None:
            raise RuntimeError("ultralytics is not available")
        self.model = YOLO(model_name)

    def detect(self, frame: Any, frame_index: int) -> list[Detection]:
        results = self.model.predict(frame, verbose=False)
        detections: list[Detection] = []
        for result in results:
            names = result.names
            for box in result.boxes:
                confidence = float(box.conf.item())
                if confidence < MIN_CONFIDENCE:
                    continue
                cls_idx = int(box.cls.item())
                label = normalize_object_label(names[cls_idx])
                if label not in ALLOWED_LABELS:
                    continue
                xyxy = box.xyxy[0].tolist()
                detections.append(
                    Detection(
                        label=label,
                        confidence=confidence,
                        bbox=(int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])),
                    )
                )
        return detections


def build_detector(mock_mode: bool, yolo_model_name: str = "yolov8n.pt") -> BaseDetector:
    if mock_mode:
        return MockDetector()
    return YoloDetector(yolo_model_name)
