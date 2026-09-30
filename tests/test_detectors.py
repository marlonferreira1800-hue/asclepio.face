import unittest

from src.blink_detector import BlinkDetector, LEFT_EYE, eye_aspect_ratio
from src.motion_analyzer import MotionAnalyzer


def eye_points(open_height: float):
    coordinates = [(0, 0), (1, -open_height), (3, -open_height), (4, 0), (3, open_height), (1, open_height)]
    return dict(zip(LEFT_EYE, coordinates))


class DetectorTests(unittest.TestCase):
    def test_ear_changes_with_eye_height(self):
        self.assertGreater(eye_aspect_ratio(eye_points(1.0), LEFT_EYE), eye_aspect_ratio(eye_points(0.2), LEFT_EYE))

    def test_blink_needs_two_closed_frames(self):
        detector = BlinkDetector(threshold=0.2, minimum_frames=2)
        detector.update(eye_points(0.2), 0.0)
        detector.update(eye_points(0.2), 0.1)
        blink, _, rate = detector.update(eye_points(1.0), 0.2)
        self.assertTrue(blink)
        self.assertEqual(rate, 1)

    def test_blink_rate_extrapolation(self):
        detector = BlinkDetector(threshold=0.2, minimum_frames=2, extrapolate=True)
        # Piscar aos 5 segundos
        detector.update(eye_points(0.2), 4.8)
        detector.update(eye_points(0.2), 4.9)
        blink, _, rate = detector.update(eye_points(1.0), 5.0)
        self.assertTrue(blink)
        # 1 piscada em 5 segundos = taxa estimada de 12 piscadas/minuto
        self.assertEqual(rate, 12.0)

    def test_motion_is_scale_normalized(self):
        analyzer = MotionAnalyzer()
        self.assertEqual(analyzer.update((0, 0, 100, 100)), 0)
        motion = analyzer.update((10, 0, 100, 100))
        self.assertAlmostEqual(motion, 0.1)
        self.assertEqual(analyzer.stability(0), 1)


if __name__ == "__main__":
    unittest.main()


