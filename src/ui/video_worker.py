"""Worker assíncrono para captura e processamento de vídeo em thread dedicada."""

from __future__ import annotations

import time
from collections import deque

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from ..activation_model import ActivationModel
from ..blink_detector import BlinkDetector
from ..calibration import Calibrator
from ..camera import Camera, CameraError
from ..face_tracker import FaceTracker
from ..models import FrameMetrics
from ..motion_analyzer import MotionAnalyzer
from ..pulse_estimator import PulseEstimator
from ..signal_quality import assess_quality


class VideoWorker(QThread):
    frame_ready = Signal(QImage, FrameMetrics)
    calibration_progress = Signal(float)
    calibration_finished = Signal(dict)
    camera_error = Signal(str)
    stopped = Signal()

    def __init__(
        self,
        camera_index: int,
        calibration_duration: float = 60.0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.camera_index = camera_index
        self.calibration_duration = calibration_duration
        self._is_running = False

        self.camera = Camera()
        self.tracker: FaceTracker | None = None
        self.blinks = BlinkDetector(extrapolate=True)
        self.motion = MotionAnalyzer()
        self.pulse = PulseEstimator()
        self.calibrator = Calibrator(calibration_duration)
        self.activation = ActivationModel()

        self.samples: list[FrameMetrics] = []
        self.frame_times: deque[float] = deque(maxlen=45)
        self.session_started_mono: float | None = None

    def start_calibration(self, duration: float) -> None:
        self.calibration_duration = duration
        self.calibrator.duration_seconds = duration
        self.calibrator.start()

    def stop(self) -> None:
        self._is_running = False

    @staticmethod
    def _extract_forehead_roi(frame_shape: tuple[int, ...], observation) -> tuple[int, int, int, int] | None:
        if not observation or not observation.present:
            return None
        h, w = frame_shape[:2]
        points = observation.landmarks
        # Se temos pontos anatômicos do MediaPipe Face Mesh
        if points and 10 in points and 9 in points and 109 in points and 338 in points:
            x_min = min(points[109][0], points[67][0] if 67 in points else points[109][0])
            x_max = max(points[338][0], points[297][0] if 297 in points else points[338][0])
            y_top = points[10][1]
            y_bottom = points[9][1]
            dx = (x_max - x_min) * 0.18
            dy = (y_bottom - y_top) * 0.15
            x1 = max(0, int(x_min + dx))
            x2 = min(w, int(x_max - dx))
            y1 = max(0, int(y_top + dy))
            y2 = min(h, int(y_bottom - dy))
            if x2 > x1 and y2 > y1:
                return (x1, y1, x2, y2)
        # Fallback para bounding box
        if observation.bbox:
            x, y, width, height = observation.bbox
            x1 = max(0, x + width * 3 // 10)
            x2 = min(w, x + width * 7 // 10)
            y1 = max(0, y + height // 8)
            y2 = min(h, y + height * 3 // 10)
            if x2 > x1 and y2 > y1:
                return (x1, y1, x2, y2)
        return None

    @staticmethod
    def _forehead_green(frame, roi: tuple[int, int, int, int] | None) -> float | None:
        if roi is None:
            return None
        x1, y1, x2, y2 = roi
        region = frame[y1:y2, x1:x2]
        return None if region.size == 0 else float(region[:, :, 1].mean())

    @staticmethod
    def _draw_overlay(
        frame,
        observation,
        sufficient: bool,
        forehead_roi: tuple[int, int, int, int] | None = None,
    ) -> None:
        import cv2

        if observation and observation.bbox:
            x, y, w, h = observation.bbox
            color = (70, 200, 130) if sufficient else (50, 190, 245)
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(
                frame,
                "sinal adequado" if sufficient else "ajuste o sinal",
                (x, max(24, y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
                cv2.LINE_AA,
            )
            if forehead_roi:
                fx1, fy1, fx2, fy2 = forehead_roi
                cv2.rectangle(frame, (fx1, fy1), (fx2, fy2), (180, 220, 100), 1)
                cv2.putText(
                    frame,
                    "rPPG",
                    (fx1, max(14, fy1 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (180, 220, 100),
                    1,
                    cv2.LINE_AA,
                )
        else:
            cv2.putText(
                frame,
                "posicione o rosto no centro",
                (24, 38),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (50, 190, 245),
                2,
                cv2.LINE_AA,
            )

    def run(self) -> None:
        try:
            import cv2
        except ImportError:
            self.camera_error.emit("OpenCV não está instalado")
            return

        try:
            self.camera.open(self.camera_index)
            self.tracker = FaceTracker()
        except Exception as exc:
            self.camera_error.emit(str(exc))
            return

        self._is_running = True
        self.session_started_mono = time.monotonic()
        camera_failures = 0

        try:
            while self._is_running:
                loop_start = time.monotonic()
                try:
                    frame = self.camera.read()
                    camera_failures = 0
                except CameraError as exc:
                    camera_failures += 1
                    if camera_failures >= 5:
                        self.camera_error.emit(str(exc))
                        break
                    time.sleep(0.03)
                    continue

                now = time.monotonic()
                self.frame_times.append(now)
                fps = 0.0
                if len(self.frame_times) > 1:
                    fps = (len(self.frame_times) - 1) / max(self.frame_times[-1] - self.frame_times[0], 1e-6)

                observation = self.tracker.process(frame) if self.tracker else None
                face_present = bool(observation and observation.present)
                bbox = observation.bbox if observation else None

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                brightness = float(gray.mean())
                blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())

                head_motion = self.motion.update(bbox)
                stability = self.motion.stability(head_motion)
                _, _, blink_rate = (
                    self.blinks.update(observation.landmarks, now)
                    if observation
                    else (False, None, None)
                )

                forehead_roi = self._extract_forehead_roi(frame.shape, observation)
                green_mean = self._forehead_green(frame, forehead_roi)
                pulse_bpm, pulse_quality = self.pulse.add(
                    now, green_mean if stability > 0.65 else None
                )

                quality_result = assess_quality(
                    face_present=face_present,
                    brightness=brightness,
                    blur=blur,
                    fps=fps,
                    stability=stability,
                )

                raw_metrics = {
                    "blink_rate": blink_rate,
                    "head_motion": head_motion,
                    "pulse_bpm": pulse_bpm,
                }

                if self.calibrator.active:
                    self.calibrator.add(raw_metrics, quality_result.score)
                    progress = self.calibrator.progress(now)
                    self.calibration_progress.emit(progress)
                    if progress >= 1.0:
                        baseline = self.calibrator.finish()
                        self.calibration_finished.emit(baseline)

                result = self.activation.evaluate(
                    raw_metrics, self.calibrator.baseline, quality_result.score
                )

                metrics = FrameMetrics(
                    timestamp=now - (self.session_started_mono or now),
                    face_present=face_present,
                    brightness=brightness,
                    blur=blur,
                    fps=fps,
                    stability=stability,
                    blink_rate=blink_rate,
                    head_motion=head_motion,
                    pulse_bpm=pulse_bpm,
                    pulse_quality=pulse_quality,
                    quality=quality_result.score,
                    activation_score=result.score,
                    activation_level=result.level,
                    notes=list(quality_result.reasons),
                )
                self.samples.append(metrics)

                self._draw_overlay(frame, observation, quality_result.sufficient, forehead_roi)

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                height, width, channels = rgb.shape
                image = QImage(rgb.data, width, height, channels * width, QImage.Format.Format_RGB888).copy()

                self.frame_ready.emit(image, metrics)

                elapsed = time.monotonic() - loop_start
                if elapsed < 0.033:
                    time.sleep(0.033 - elapsed)
        finally:
            self.camera.release()
            if self.tracker:
                self.tracker.close()
            self._is_running = False
            self.stopped.emit()
