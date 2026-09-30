"""Estimativa experimental de pulso por variação da cor da pele (rPPG)."""

from __future__ import annotations

from collections import deque


class PulseEstimator:
    """Mantém o valor oculto quando duração, cadência ou pico espectral são ruins."""

    def __init__(self, window_seconds: float = 12.0) -> None:
        self.window_seconds = window_seconds
        self.times: deque[float] = deque()
        self.green: deque[float] = deque()

    def reset(self) -> None:
        self.times.clear()
        self.green.clear()

    def add(self, timestamp: float, green_mean: float | None) -> tuple[float | None, float]:
        if green_mean is None:
            return None, 0.0
        self.times.append(timestamp)
        self.green.append(green_mean)
        while self.times and timestamp - self.times[0] > self.window_seconds:
            self.times.popleft()
            self.green.popleft()
        if len(self.times) < 80 or self.times[-1] - self.times[0] < 8.0:
            return None, 0.0
        try:
            import numpy as np
        except ImportError:
            return None, 0.0
        times = np.asarray(self.times, dtype=float)
        signal = np.asarray(self.green, dtype=float)
        fps = (len(times) - 1) / max(times[-1] - times[0], 1e-6)
        if fps < 10 or np.std(signal) < 0.05:
            return None, 0.0
        uniform_t = np.linspace(times[0], times[-1], len(times))
        uniform = np.interp(uniform_t, times, signal)
        uniform = uniform - np.polyval(np.polyfit(uniform_t, uniform, 2), uniform_t)
        uniform *= np.hanning(len(uniform))
        spectrum = np.abs(np.fft.rfft(uniform)) ** 2
        frequencies = np.fft.rfftfreq(len(uniform), d=1.0 / fps)
        mask = (frequencies >= 0.75) & (frequencies <= 3.0)
        band = spectrum[mask]
        if not band.any():
            return None, 0.0
        peak_index = int(np.argmax(band))
        peak_power = float(band[peak_index])
        quality = peak_power / max(float(np.sum(band)), 1e-9)
        bpm = float(frequencies[mask][peak_index] * 60.0)
        if quality < 0.35 or not 45 <= bpm <= 180:
            return None, round(quality, 3)
        return round(bpm, 1), round(min(1.0, quality), 3)
