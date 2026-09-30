"""Acesso pequeno e defensivo à webcam via OpenCV."""

from __future__ import annotations


class CameraError(RuntimeError):
    pass


class Camera:
    def __init__(self) -> None:
        self.capture = None
        self.cv2 = None

    @staticmethod
    def available_indices(limit: int = 5) -> list[int]:
        try:
            import cv2
        except ImportError:
            return []
        found: list[int] = []
        for index in range(limit):
            capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if capture.isOpened():
                found.append(index)
            capture.release()
        return found

    def open(self, index: int) -> None:
        try:
            import cv2
        except ImportError as exc:
            raise CameraError("OpenCV não está instalado") from exc
        self.cv2 = cv2
        self.capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not self.capture.isOpened():
            self.release()
            raise CameraError(f"Não foi possível abrir a câmera {index}")
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.capture.set(cv2.CAP_PROP_FPS, 30)

    def read(self):
        if self.capture is None:
            raise CameraError("Câmera não iniciada")
        ok, frame = self.capture.read()
        if not ok or frame is None:
            raise CameraError("Falha ao obter imagem da câmera")
        return frame

    def release(self) -> None:
        if self.capture is not None:
            self.capture.release()
        self.capture = None
