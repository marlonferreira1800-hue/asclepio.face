import unittest

from src.activation_model import ActivationModel
from src.calibration import Calibrator, MetricBaseline


class CalibrationTests(unittest.TestCase):
    def test_calibration_ignores_low_quality_and_builds_baseline(self):
        calibrator = Calibrator(duration_seconds=10)
        calibrator.start(now=0)
        calibrator.add({"head_motion": 99.0}, quality=0.2)
        for value in [0.09, 0.10, 0.11, 0.10, 0.09, 0.10]:
            calibrator.add({"head_motion": value}, quality=0.9)
        result = calibrator.finish()
        self.assertIn("head_motion", result)
        self.assertAlmostEqual(result["head_motion"].mean, 0.0983, places=3)
        self.assertEqual(result["head_motion"].count, 6)


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.model = ActivationModel()
        self.baseline = {
            "blink_rate": MetricBaseline(15, 3, 100),
            "head_motion": MetricBaseline(0.02, 0.01, 100),
            "pulse_bpm": MetricBaseline(70, 5, 100),
        }

    def test_low_quality_never_generates_level(self):
        result = self.model.evaluate({"blink_rate": 50, "head_motion": 1, "pulse_bpm": 150}, self.baseline, 0.3)
        self.assertEqual(result.level, "medição insuficiente")
        self.assertIsNone(result.score)

    def test_baseline_values_are_stable(self):
        result = self.model.evaluate({"blink_rate": 15, "head_motion": 0.02, "pulse_bpm": 70}, self.baseline, 0.9)
        self.assertEqual(result.level, "estável")
        self.assertEqual(result.score, 0)

    def test_large_positive_deviation_is_elevated(self):
        result = self.model.evaluate({"blink_rate": 30, "head_motion": 0.08, "pulse_bpm": 100}, self.baseline, 0.9)
        self.assertEqual(result.level, "elevada")


if __name__ == "__main__":
    unittest.main()
