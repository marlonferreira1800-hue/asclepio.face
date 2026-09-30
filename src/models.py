"""Tipos compartilhados pelo pipeline local."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class FaceObservation:
    present: bool = False
    bbox: tuple[int, int, int, int] | None = None
    landmarks: dict[int, tuple[float, float]] = field(default_factory=dict)
    confidence: float = 0.0
    backend: str = "indisponível"


@dataclass(slots=True)
class FrameMetrics:
    timestamp: float
    face_present: bool
    brightness: float
    blur: float
    fps: float
    stability: float
    blink_rate: float | None = None
    head_motion: float | None = None
    pulse_bpm: float | None = None
    pulse_quality: float = 0.0
    quality: float = 0.0
    activation_score: float | None = None
    activation_level: str = "medição insuficiente"
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SessionSummary:
    started_at: str
    ended_at: str
    duration_seconds: float
    sample_count: int
    mean_quality: float
    level_counts: dict[str, int]
    blink_count: int
    saved: bool = False
