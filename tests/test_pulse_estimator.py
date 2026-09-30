"""Testes unitários para o estimador de pulso experimental (rPPG)."""

import math
import unittest

from src.pulse_estimator import PulseEstimator

try:
    import numpy as np
except ImportError:
    np = None


class PulseEstimatorTests(unittest.TestCase):
    def test_empty_or_none_returns_none(self):
        estimator = PulseEstimator()
        bpm, quality = estimator.add(1.0, None)
        self.assertIsNone(bpm)
        self.assertEqual(quality, 0.0)

    def test_insufficient_samples_returns_none(self):
        estimator = PulseEstimator()
        for i in range(50):
            bpm, quality = estimator.add(i * 0.033, 120.0)
        self.assertIsNone(bpm)
        self.assertEqual(quality, 0.0)

    def test_reset_clears_history(self):
        estimator = PulseEstimator()
        for i in range(30):
            estimator.add(i * 0.033, 120.0)
        self.assertEqual(len(estimator.times), 30)
        estimator.reset()
        self.assertEqual(len(estimator.times), 0)
        self.assertEqual(len(estimator.green), 0)

    @unittest.skipIf(np is None, "numpy não está instalado neste interpretador")
    def test_synthetic_pulse_detection(self):
        estimator = PulseEstimator(window_seconds=12.0)
        target_hz = 1.2  # 72 BPM
        target_bpm = target_hz * 60.0
        fps = 30.0
        total_samples = int(10.0 * fps)
        bpm = None
        quality = 0.0
        for i in range(total_samples):
            t = i / fps
            val = 120.0 + 3.0 * math.sin(2.0 * math.pi * target_hz * t)
            bpm, quality = estimator.add(t, val)

        self.assertIsNotNone(bpm)
        self.assertAlmostEqual(bpm, target_bpm, delta=4.0)
        self.assertGreater(quality, 0.35)

    @unittest.skipIf(np is None, "numpy não está instalado neste interpretador")
    def test_flat_signal_rejected(self):
        estimator = PulseEstimator(window_seconds=12.0)
        for i in range(100):
            bpm, quality = estimator.add(i * 0.033, 120.0)
        self.assertIsNone(bpm)
        self.assertEqual(quality, 0.0)


if __name__ == "__main__":
    unittest.main()
