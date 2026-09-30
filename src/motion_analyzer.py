"""Movimento relativo do rosto, independente da resolução."""

from __future__ import annotations

import math
from collections import deque


class MotionAnalyzer:
    def __init__(self, smoothing: int = 12) -> None:
        self.previous: tuple[float, float, float] | None = None
        self.values: deque[float] = deque(maxlen=smoothing)

    def update(self, bbox: tuple[int, int, int, int] | None) -> float | None:
        if bbox is None:
            self.previous = None
            self.values.clear()
            return None
        x, y, width, height = bbox
        current = (x + width / 2.0, y + height / 2.0, max(width, height, 1))
        if self.previous is None:
            self.previous = current
            return 0.0
        px, py, scale = self.previous
        displacement = math.hypot(current[0] - px, current[1] - py) / max(scale, current[2], 1)
        self.previous = current
        self.values.append(displacement)
        return sum(self.values) / len(self.values)

    @staticmethod
    def stability(motion: float | None) -> float:
        return 0.0 if motion is None else max(0.0, min(1.0, 1.0 - motion * 12.0))
