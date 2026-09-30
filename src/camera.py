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
        backends = [cv2.CAP_MSMF, cv2.CAP_ANY, cv2.CAP_DSHOW]
        for index in range(limit):
            for backend in backends:
                capture = cv2.VideoCapture(index, backend)
                if capture.isOpened():
                    found.append(index)
                    capture.release()
                    break
        return found

    def open(self, index: int) -> None:
        try:
            import cv2
        except ImportError as exc:
            raise CameraError("OpenCV não está instalado") from exc
        self.cv2 = cv2

        backends = [cv2.CAP_MSMF, cv2.CAP_ANY, cv2.CAP_DSHOW]
        chosen = None
        for backend in backends:
            cap = cv2.VideoCapture(index, backend)
            if cap.isOpened():
                # Configura propriedades de captura
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 30)

                # Verifica se o backend entrega imagem com iluminação
                ok, test_frame = cap.read()
                if ok and test_frame is not None and test_frame.mean() > 1.0:
                    chosen = cap
                    break
                if chosen is None:
                    chosen = cap
                else:
                    cap.release()

        if chosen is None or not chosen.isOpened():
            self.release()
            raise CameraError(f"Não foi possível abrir a câmera {index}")

        self.capture = chosen

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

