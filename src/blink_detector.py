"""Detecção local de piscadas por razão de aspecto ocular (EAR)."""

from __future__ import annotations

import math
from collections import deque


LEFT_EYE = (33, 160, 158, 133, 153, 144)
RIGHT_EYE = (362, 385, 387, 263, 373, 380)


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def eye_aspect_ratio(points: dict[int, tuple[float, float]], indices: tuple[int, ...]) -> float | None:
    if any(index not in points for index in indices):
        return None
    p1, p2, p3, p4, p5, p6 = (points[index] for index in indices)
    horizontal = 2.0 * _distance(p1, p4)
    return None if horizontal <= 1e-9 else (_distance(p2, p6) + _distance(p3, p5)) / horizontal


class BlinkDetector:
    def __init__(self, threshold: float = 0.21, minimum_frames: int = 2, extrapolate: bool = False) -> None:
        self.threshold = threshold
        self.minimum_frames = minimum_frames
        self.extrapolate = extrapolate
        self.closed_frames = 0
        self.total = 0
        self.events: deque[float] = deque()
        self.first_timestamp: float | None = None

    def reset(self) -> None:
        self.closed_frames = 0
        self.total = 0
        self.events.clear()
        self.first_timestamp = None

    def update(self, landmarks: dict[int, tuple[float, float]], timestamp: float) -> tuple[bool, float | None, float | None]:
        if self.first_timestamp is None:
            self.first_timestamp = timestamp
        left = eye_aspect_ratio(landmarks, LEFT_EYE)
        right = eye_aspect_ratio(landmarks, RIGHT_EYE)
        values = [value for value in (left, right) if value is not None]
        if not values:
            return False, None, None
        ear = sum(values) / len(values)
        blink = False
        if ear < self.threshold:
            self.closed_frames += 1
        else:
            if self.closed_frames >= self.minimum_frames:
                self.total += 1
                self.events.append(timestamp)
                blink = True
            self.closed_frames = 0
        while self.events and timestamp - self.events[0] > 60.0:
            self.events.popleft()

        if self.extrapolate:
            elapsed = max(5.0, min(60.0, timestamp - self.first_timestamp))
            rate = (len(self.events) / elapsed) * 60.0 if self.events else 0.0
            return blink, ear, round(rate, 1)

        return blink, ear, float(len(self.events))

