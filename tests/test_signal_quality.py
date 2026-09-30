import unittest

from src.signal_quality import assess_quality, clamp


class SignalQualityTests(unittest.TestCase):
    def test_good_signal_is_sufficient(self):
        result = assess_quality(face_present=True, brightness=130, blur=150, fps=30, stability=0.9)
        self.assertTrue(result.sufficient)
        self.assertGreater(result.score, 0.8)

    def test_missing_face_blocks_measurement(self):
        result = assess_quality(face_present=False, brightness=130, blur=150, fps=30, stability=0.9)
        self.assertFalse(result.sufficient)
        self.assertEqual(result.score, 0)

    def test_bad_image_reports_reasons(self):
        result = assess_quality(face_present=True, brightness=10, blur=5, fps=3, stability=0.2)
        self.assertFalse(result.sufficient)
        self.assertGreaterEqual(len(result.reasons), 3)

    def test_clamp(self):
        self.assertEqual(clamp(-2), 0)
        self.assertEqual(clamp(2), 1)


if __name__ == "__main__":
    unittest.main()
