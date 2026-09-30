"""Avaliação explícita da qualidade antes de qualquer inferência."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QualityResult:
    score: float
    sufficient: bool
    reasons: tuple[str, ...]


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def assess_quality(
    *,
    face_present: bool,
    brightness: float,
    blur: float,
    fps: float,
    stability: float,
) -> QualityResult:
    """Combina critérios observáveis, com faixas deliberadamente conservadoras."""
    reasons: list[str] = []
    if not face_present:
        return QualityResult(0.0, False, ("rosto não encontrado",))

    light = clamp(1.0 - abs(brightness - 130.0) / 110.0)
    sharpness = clamp(blur / 120.0)
    cadence = clamp(fps / 20.0)
    stable = clamp(stability)
    if brightness < 45:
        reasons.append("ambiente escuro")
    elif brightness > 225:
        reasons.append("luz excessiva")
    if blur < 45:
        reasons.append("imagem desfocada")
    if fps < 10:
        reasons.append("taxa de quadros baixa")
    if stability < 0.45:
        reasons.append("movimento excessivo")

    score = 0.25 * light + 0.25 * sharpness + 0.2 * cadence + 0.3 * stable
    hard_failure = brightness < 25 or brightness > 245 or blur < 18 or fps < 5
    return QualityResult(round(clamp(score), 3), score >= 0.55 and not hard_failure, tuple(reasons))
