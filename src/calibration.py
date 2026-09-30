"""Linha de base individual, sem classificação clínica."""

from __future__ import annotations

import math
import statistics
import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class MetricBaseline:
    mean: float
    std: float
    count: int


@dataclass(slots=True)
class Calibrator:
    duration_seconds: float = 60.0
    started_at: float | None = None
    samples: dict[str, list[float]] = field(default_factory=dict)
    baseline: dict[str, MetricBaseline] = field(default_factory=dict)

    def start(self, now: float | None = None) -> None:
        self.started_at = time.monotonic() if now is None else now
        self.samples.clear()
        self.baseline.clear()

    @property
    def active(self) -> bool:
        return self.started_at is not None and not self.baseline

    def progress(self, now: float | None = None) -> float:
        if self.started_at is None:
            return 0.0
        current = time.monotonic() if now is None else now
        return min(1.0, max(0.0, (current - self.started_at) / self.duration_seconds))

    def add(self, values: dict[str, float | None], quality: float) -> None:
        if not self.active or quality < 0.55:
            return
        for name, value in values.items():
            if value is not None and math.isfinite(value):
                self.samples.setdefault(name, []).append(float(value))

    def finish(self) -> dict[str, MetricBaseline]:
        result: dict[str, MetricBaseline] = {}
        for name, values in self.samples.items():
            if len(values) >= 5:
                mean = statistics.fmean(values)
                std = statistics.stdev(values) if len(values) > 1 else 0.0
                result[name] = MetricBaseline(mean, max(std, 0.05), len(values))
        self.baseline = result
        self.started_at = None
        return result

    def z_score(self, name: str, value: float | None) -> float | None:
        reference = self.baseline.get(name)
        if reference is None or value is None:
            return None
        return (value - reference.mean) / reference.std
