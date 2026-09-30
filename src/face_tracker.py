"""Rastreamento MediaPipe com fallback local para classificador Haar."""

from __future__ import annotations

from .models import FaceObservation


class FaceTracker:
    def __init__(self) -> None:
        self.backend = "indisponível"
        self.mesh = None
        self.cascade = None
        try:
            import mediapipe as mp

            solutions = getattr(mp, "solutions", None)
            if solutions is not None:
                self.mesh = solutions.face_mesh.FaceMesh(
                    static_image_mode=False,
                    max_num_faces=1,
                    refine_landmarks=True,
                    min_detection_confidence=0.55,
                    min_tracking_confidence=0.55,
                )
                self.backend = "MediaPipe Face Mesh"
                return
        except (ImportError, AttributeError):
            pass
        try:
            import cv2

            self.cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            if not self.cascade.empty():
                self.backend = "OpenCV Haar (modo reduzido)"
        except ImportError:
            pass

    def process(self, frame) -> FaceObservation:
        import cv2

        height, width = frame.shape[:2]
        if self.mesh is not None:
            result = self.mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if not result.multi_face_landmarks:
                return FaceObservation(backend=self.backend)
            raw = result.multi_face_landmarks[0].landmark
            points = {i: (point.x * width, point.y * height) for i, point in enumerate(raw)}
            xs, ys = [p[0] for p in points.values()], [p[1] for p in points.values()]
            bbox = (int(min(xs)), int(min(ys)), int(max(xs) - min(xs)), int(max(ys) - min(ys)))
            return FaceObservation(True, bbox, points, 1.0, self.backend)
        if self.cascade is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(100, 100))
            if len(faces):
                x, y, w, h = max(faces, key=lambda item: item[2] * item[3])
                return FaceObservation(True, (int(x), int(y), int(w), int(h)), {}, 0.6, self.backend)
        return FaceObservation(backend=self.backend)

    def close(self) -> None:
        if self.mesh is not None:
            self.mesh.close()
