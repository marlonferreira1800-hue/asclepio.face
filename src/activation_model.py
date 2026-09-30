"""Modelo transparente de ativação fisiológica estimada."""

from __future__ import annotations

from dataclasses import dataclass

from .calibration import MetricBaseline
from .signal_quality import clamp


@dataclass(frozen=True, slots=True)
class ActivationResult:
    level: str
    score: float | None
    contributions: dict[str, float]
    explanation: str


class ActivationModel:
    """Soma desvios positivos da linha de base; não infere emoção ou diagnóstico."""

    weights = {"blink_rate": 0.25, "head_motion": 0.35, "pulse_bpm": 0.40}

    def evaluate(
        self,
        metrics: dict[str, float | None],
        baseline: dict[str, MetricBaseline],
        quality: float,
    ) -> ActivationResult:
        if quality < 0.55:
            return ActivationResult("medição insuficiente", None, {}, "qualidade de sinal insuficiente")

        contributions: dict[str, float] = {}
        available_weight = 0.0
        for name, weight in self.weights.items():
            value = metrics.get(name)
            reference = baseline.get(name)
            if value is None or reference is None:
                continue
            z = (value - reference.mean) / max(reference.std, 0.05)
            contributions[name] = clamp(max(0.0, z) / 3.0) * weight
            available_weight += weight

        if available_weight < 0.25:
            return ActivationResult("medição insuficiente", None, contributions, "linha de base incompleta")
        score = clamp(sum(contributions.values()) / available_weight)
        if score < 0.28:
            level = "estável"
        elif score < 0.62:
            level = "moderada"
        else:
            level = "elevada"
        return ActivationResult(level, round(score, 3), contributions, "desvio relativo à linha de base individual")
