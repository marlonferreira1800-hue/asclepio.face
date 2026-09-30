"""Janela principal e orquestração do pipeline em tempo real."""

from __future__ import annotations

import json
import statistics
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QIcon, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..camera import Camera
from ..models import FrameMetrics, SessionSummary
from ..session_store import SessionStore
from .video_worker import VideoWorker
from .widgets import APP_STYLE, ConsentDialog, MetricCard


class MainWindow(QMainWindow):
    def __init__(self, autostart: bool = False, auto_calibrate: bool = False) -> None:
        super().__init__()
        self.setWindowTitle("Face Inteligente — protótipo local")
        self.resize(1280, 800)
        self.setMinimumSize(1050, 680)
        self.setStyleSheet(APP_STYLE)

        self._autostart = autostart
        self._auto_calibrate = auto_calibrate

        icon_path = Path("assets/icon.png")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.worker: VideoWorker | None = None
        self.store = SessionStore()
        self.samples: list[FrameMetrics] = []
        self.session_started_wall: datetime | None = None
        self.last_summary: SessionSummary | None = None
        self.last_saved_id: int | None = None

        self._build_ui()
        self._setup_shortcuts()
        self._refresh_cameras()
        self._refresh_history()

        if self._autostart:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(400, self._auto_start)


    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Face Inteligente")
        title.setObjectName("appTitle")
        subtitle = QLabel("Estimativa experimental de ativação fisiológica • processamento 100% local")
        subtitle.setObjectName("subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        self.privacy_label = QLabel("● Vídeo não gravado • Thread dedicada")
        self.privacy_label.setStyleSheet("color: #44d19d; font-weight: 600")
        header.addLayout(title_box)
        header.addStretch()
        header.addWidget(self.privacy_label)
        outer.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_monitor_tab(), "Monitor")
        self.tabs.addTab(self._build_history_tab(), "Sessões locais")
        self.tabs.addTab(self._build_about_tab(), "Limitações e privacidade")
        outer.addWidget(self.tabs)

    def _setup_shortcuts(self) -> None:
        # Espaço inicia ou para a câmera rapidamente
        self.toggle_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self.toggle_shortcut.activated.connect(self._toggle_camera)

    def _toggle_camera(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self._stop_camera()
        elif self.start_button.isEnabled():
            self._start_camera()

    def _build_monitor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        left = QFrame()
        left.setObjectName("sidebar")
        controls = QVBoxLayout(left)
        controls.addWidget(QLabel("Câmera"))
        camera_row = QHBoxLayout()
        self.camera_combo = QComboBox()
        refresh = QPushButton("Atualizar")
        refresh.clicked.connect(self._refresh_cameras)
        camera_row.addWidget(self.camera_combo, 1)
        camera_row.addWidget(refresh)
        controls.addLayout(camera_row)
        self.start_button = QPushButton("Iniciar câmera (Espaço)")
        self.start_button.clicked.connect(self._start_camera)
        self.stop_button = QPushButton("Parar")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_camera)
        button_row = QHBoxLayout()
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        controls.addLayout(button_row)

        controls.addSpacing(12)
        controls.addWidget(QLabel("Linha de base"))
        duration_row = QHBoxLayout()
        duration_row.addWidget(QLabel("Duração:"))
        self.duration = QSpinBox()
        self.duration.setRange(10, 120)
        self.duration.setValue(60)
        self.duration.setSuffix(" s")
        duration_row.addWidget(self.duration)
        controls.addLayout(duration_row)
        hint = QLabel("Recomendado: 60–90 segundos, em repouso e com iluminação constante.")
        hint.setWordWrap(True)
        hint.setObjectName("subtitle")
        controls.addWidget(hint)
        self.calibrate_button = QPushButton("Iniciar calibração")
        self.calibrate_button.setEnabled(False)
        self.calibrate_button.clicked.connect(self._start_calibration)
        self.calibration_progress = QProgressBar()
        self.calibration_progress.setRange(0, 100)
        controls.addWidget(self.calibrate_button)
        controls.addWidget(self.calibration_progress)
        self.save_metrics = QCheckBox("Salvar somente métricas ao parar")
        controls.addWidget(self.save_metrics)
        controls.addStretch()
        warning = QLabel(
            "Não é diagnóstico, detector de mentira ou leitura de emoções. Calor, exercício, cafeína, "
            "movimento, iluminação, doenças e medicamentos podem alterar os sinais."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #f6c85f; padding: 8px; background: #2d2415; border-radius: 6px")
        controls.addWidget(warning)
        left.setFixedWidth(285)

        center = QVBoxLayout()
        self.video = QLabel("Câmera desligada")
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setMinimumSize(640, 420)
        self.video.setStyleSheet("background: #05070a; border: 1px solid #30363d; border-radius: 8px; color: #8b949e")
        center.addWidget(self.video, 3)
        self.chart_container = QFrame()
        self.chart_container.setObjectName("panel")
        chart_layout = QVBoxLayout(self.chart_container)
        chart_layout.addWidget(QLabel("Tendência recente (normalizada)"))
        self.plot = None
        self.curves: dict[str, object] = {}
        try:
            import pyqtgraph as pg

            self.plot = pg.PlotWidget(background="#161b22")
            self.plot.setYRange(0, 1)
            self.plot.showGrid(x=True, y=True, alpha=0.2)
            self.plot.addLegend()
            self.curves["quality"] = self.plot.plot(pen="#58a6ff", name="qualidade")
            self.curves["activation"] = self.plot.plot(pen="#f0883e", name="ativação")
            chart_layout.addWidget(self.plot)
        except ImportError:
            chart_layout.addWidget(QLabel("Instale pyqtgraph para exibir o gráfico em tempo real."))
        center.addWidget(self.chart_container, 2)

        right = QFrame()
        right.setObjectName("panel")
        metrics_layout = QVBoxLayout(right)
        metrics_layout.addWidget(QLabel("ATIVAÇÃO FISIOLÓGICA ESTIMADA"))
        self.activation_label = QLabel("medição insuficiente")
        self.activation_label.setObjectName("activation")
        self.activation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.activation_label.setWordWrap(True)
        metrics_layout.addWidget(self.activation_label)
        grid = QGridLayout()
        self.cards = {
            "face": MetricCard("Rosto", "ausente"),
            "quality": MetricCard("Qualidade", "0%"),
            "light": MetricCard("Iluminação", "—"),
            "blur": MetricCard("Nitidez", "—"),
            "fps": MetricCard("FPS", "—"),
            "stability": MetricCard("Estabilidade", "—"),
            "blink": MetricCard("Piscadas/min", "—"),
            "pulse": MetricCard("Pulso experimental", "oculto"),
        }
        for index, card in enumerate(self.cards.values()):
            grid.addWidget(card, index // 2, index % 2)
        metrics_layout.addLayout(grid)
        self.status_detail = QLabel("Inicie a câmera e faça a calibração.")
        self.status_detail.setWordWrap(True)
        self.status_detail.setObjectName("subtitle")
        metrics_layout.addWidget(self.status_detail)
        metrics_layout.addStretch()
        right.setFixedWidth(310)

        layout.addWidget(left)
        layout.addLayout(center, 1)
        layout.addWidget(right)
        return tab

    def _build_history_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        note = QLabel("Somente métricas são armazenadas. Nenhuma imagem ou vídeo faz parte do banco local.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.history = QTableWidget(0, 7)
        self.history.setHorizontalHeaderLabels(["ID", "Início", "Duração", "Amostras", "Qualidade", "Piscadas", "Níveis"])
        self.history.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.history)
        row = QHBoxLayout()
        refresh = QPushButton("Atualizar")
        refresh.clicked.connect(self._refresh_history)
        export = QPushButton("Exportar CSV")
        export.clicked.connect(self._export_selected)
        delete = QPushButton("Excluir sessão")
        delete.setObjectName("deleteButton")
        delete.clicked.connect(self._delete_selected)
        row.addWidget(refresh)
        row.addWidget(export)
        row.addStretch()
        row.addWidget(delete)
        layout.addLayout(row)
        return tab

    def _build_about_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        text = QLabel(
            "<h2>O que este protótipo faz</h2>"
            "<p>Observa qualidade da imagem, movimento, piscadas (com MediaPipe) e, quando o sinal permite, "
            "uma estimativa experimental de pulso por rPPG. Após uma linha de base individual, uma regra "
            "simples combina desvios positivos e produz os estados <b>estável</b>, <b>moderada</b> ou "
            "<b>elevada</b>. Sem qualidade ou calibração suficientes, mostra <b>medição insuficiente</b>.</p>"
            "<h2>O que ele não faz</h2>"
            "<p>Não reconhece identidade, não diagnostica ansiedade, não detecta mentira e não afirma emoções. "
            "A associação entre sinais visuais e estado interno é limitada e sujeita a muitos fatores externos.</p>"
            "<h2>Privacidade</h2>"
            "<p>O processamento ocorre neste computador. O vídeo não é gravado nem enviado. O salvamento é "
            "desativado por padrão e, se habilitado, grava apenas métricas numéricas no SQLite local.</p>"
            "<h2>Fatores de confusão</h2>"
            "<p>Calor, exercício, cafeína, movimento, iluminação, doenças, medicamentos, características da "
            "pele, maquiagem, óculos e limitações da câmera podem mudar ou degradar os sinais.</p>"
        )
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(text)
        return tab

    def _refresh_cameras(self) -> None:
        self.camera_combo.clear()
        indices = Camera.available_indices()
        if not indices:
            self.camera_combo.addItem("Nenhuma câmera encontrada", None)
        else:
            for index in indices:
                self.camera_combo.addItem(f"Câmera {index}", index)
        is_running = self.worker is not None and self.worker.isRunning()
        self.start_button.setEnabled(bool(indices) and not is_running)

    def _start_camera(self) -> None:
        if ConsentDialog(self).exec() != QDialog.DialogCode.Accepted:
            return
        index = self.camera_combo.currentData()
        if index is None:
            QMessageBox.warning(self, "Câmera", "Nenhuma câmera disponível. Atualize a lista e tente novamente.")
            return

        self.samples.clear()
        self.session_started_wall = datetime.now().astimezone()

        self.worker = VideoWorker(int(index), float(self.duration.value()), self)
        self.worker.frame_ready.connect(self._on_frame_ready)
        self.worker.calibration_progress.connect(self._on_calibration_progress)
        self.worker.calibration_finished.connect(self._on_calibration_finished)
        self.worker.camera_error.connect(self._on_camera_error)
        self.worker.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.calibrate_button.setEnabled(True)
        self.status_detail.setText("Câmera ativa em thread dedicada. Faça a calibração em repouso.")

    def _auto_start(self) -> None:
        index = self.camera_combo.currentData()
        if index is None:
            return
        self.samples.clear()
        self.session_started_wall = datetime.now().astimezone()

        self.worker = VideoWorker(int(index), float(self.duration.value()), self)
        self.worker.frame_ready.connect(self._on_frame_ready)
        self.worker.calibration_progress.connect(self._on_calibration_progress)
        self.worker.calibration_finished.connect(self._on_calibration_finished)
        self.worker.camera_error.connect(self._on_camera_error)
        self.worker.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.calibrate_button.setEnabled(True)
        self.status_detail.setText("Câmera ativa automaticamente em thread dedicada. Faça a calibração em repouso.")

        if self._auto_calibrate:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1500, self._start_calibration)

    def _start_calibration(self) -> None:

        if self.worker is not None:
            self.worker.start_calibration(float(self.duration.value()))
            self.calibrate_button.setEnabled(False)
            self.calibration_progress.setValue(0)
            self.status_detail.setText("Calibrando: permaneça confortável, em repouso e olhando para a câmera.")

    def _on_calibration_progress(self, progress: float) -> None:
        self.calibration_progress.setValue(round(progress * 100))

    def _on_calibration_finished(self, baseline: dict) -> None:
        self.calibrate_button.setEnabled(True)
        if baseline:
            self.status_detail.setText("Linha de base concluída. A estimativa agora compara variações individuais.")
        else:
            self.status_detail.setText("Calibração sem amostras suficientes. Melhore o enquadramento e tente novamente.")

    def _on_camera_error(self, message: str) -> None:
        QMessageBox.warning(self, "Aviso da câmera", f"Ocorreu um erro na captura: {message}")
        self._stop_camera()

    def _on_frame_ready(self, image: QImage, metrics: FrameMetrics) -> None:
        pixmap = QPixmap.fromImage(image).scaled(
            self.video.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video.setPixmap(pixmap)
        self.samples.append(metrics)
        self._update_metrics(metrics)
        self._update_plot()

    def _update_metrics(self, item: FrameMetrics) -> None:
        good = item.quality >= 0.55
        self.cards["face"].set_value(
            "presente" if item.face_present else "ausente",
            "good" if item.face_present else "bad",
        )
        self.cards["quality"].set_value(f"{item.quality:.0%}", "good" if good else "warn")
        light_ok = 45 <= item.brightness <= 225
        self.cards["light"].set_value(f"{item.brightness:.0f}", "good" if light_ok else "warn")
        self.cards["blur"].set_value(f"{item.blur:.0f}", "good" if item.blur >= 45 else "warn")
        self.cards["fps"].set_value(f"{item.fps:.1f}", "good" if item.fps >= 15 else "warn")
        self.cards["stability"].set_value(f"{item.stability:.0%}", "good" if item.stability >= 0.55 else "warn")
        self.cards["blink"].set_value("—" if item.blink_rate is None else f"{item.blink_rate:.0f}")
        pulse = "oculto (sinal fraco)" if item.pulse_bpm is None else f"{item.pulse_bpm:.0f} bpm • {item.pulse_quality:.0%}"
        self.cards["pulse"].set_value(pulse, "good" if item.pulse_bpm else "neutral")
        self.activation_label.setText(item.activation_level)
        colors = {"estável": "#16382d", "moderada": "#463817", "elevada": "#4b2020", "medição insuficiente": "#21262d"}
        self.activation_label.setStyleSheet(f"background: {colors.get(item.activation_level, '#21262d')};")
        if item.notes:
            self.status_detail.setText("Qualidade: " + ", ".join(item.notes) + ".")

    def _update_plot(self) -> None:
        if self.plot is None:
            return
        recent = self.samples[-300:]
        x_values = [item.timestamp for item in recent]
        self.curves["quality"].setData(x_values, [item.quality for item in recent])
        self.curves["activation"].setData(x_values, [item.activation_score or 0.0 for item in recent])

    def _stop_camera(self) -> None:
        if self.worker is None and self.session_started_wall is None:
            return

        worker = self.worker
        total_blinks = 0
        if worker is not None:
            self.worker = None
            worker.stop()
            worker.wait(2000)
            total_blinks = worker.blinks.total

        ended = datetime.now().astimezone()
        start = self.session_started_wall or ended
        levels = Counter(item.activation_level for item in self.samples)
        self.last_summary = SessionSummary(
            started_at=start.isoformat(timespec="seconds"),
            ended_at=ended.isoformat(timespec="seconds"),
            duration_seconds=max(0.0, (ended - start).total_seconds()),
            sample_count=len(self.samples),
            mean_quality=statistics.fmean(item.quality for item in self.samples) if self.samples else 0.0,
            level_counts=dict(levels),
            blink_count=total_blinks,
        )
        self.last_saved_id = None
        if self.save_metrics.isChecked() and self.samples:
            try:
                self.last_saved_id = self.store.save(self.last_summary, self.samples)
                self.last_summary.saved = True
            except Exception as exc:
                QMessageBox.warning(self, "Falha ao salvar", f"A sessão terminou, mas as métricas não foram salvas: {exc}")

        self.video.clear()
        self.video.setText("Câmera desligada — nenhum vídeo foi gravado")
        self.start_button.setEnabled(self.camera_combo.currentData() is not None)
        self.stop_button.setEnabled(False)
        self.calibrate_button.setEnabled(False)
        self.calibration_progress.setValue(0)
        self.session_started_wall = None
        self._refresh_history()

        summary = self.last_summary
        saved = f"Métricas salvas localmente (sessão {self.last_saved_id})." if summary.saved else "Métricas não salvas."
        QMessageBox.information(
            self,
            "Resumo da sessão",
            f"Duração: {summary.duration_seconds:.0f} s\nAmostras: {summary.sample_count}\n"
            f"Qualidade média: {summary.mean_quality:.0%}\nPiscadas detectadas: {summary.blink_count}\n"
            f"Estados: {summary.level_counts}\n\n{saved}\nNenhuma imagem ou vídeo foi armazenado.",
        )

    def _refresh_history(self) -> None:
        try:
            sessions = self.store.list_sessions()
        except Exception:
            return
        self.history.setRowCount(len(sessions))
        for row_index, session in enumerate(sessions):
            values = [
                session["id"],
                session["started_at"],
                f"{session['duration_seconds']:.0f} s",
                session["sample_count"],
                f"{session['mean_quality']:.0%}",
                session["blink_count"],
                json.loads(str(session["level_counts"])),
            ]
            for column, value in enumerate(values):
                self.history.setItem(row_index, column, QTableWidgetItem(str(value)))

    def _selected_session_id(self) -> int | None:
        row = self.history.currentRow()
        return None if row < 0 else int(self.history.item(row, 0).text())

    def _export_selected(self) -> None:
        session_id = self._selected_session_id()
        if session_id is None:
            QMessageBox.information(self, "Exportar", "Selecione uma sessão.")
            return
        filename, _ = QFileDialog.getSaveFileName(self, "Exportar métricas", f"sessao-{session_id}.csv", "CSV (*.csv)")
        if filename:
            try:
                self.store.export_csv(session_id, Path(filename))
                QMessageBox.information(self, "Exportar", "CSV exportado com sucesso.")
            except Exception as exc:
                QMessageBox.warning(self, "Exportar", str(exc))

    def _delete_selected(self) -> None:
        session_id = self._selected_session_id()
        if session_id is None:
            QMessageBox.information(self, "Excluir", "Selecione uma sessão.")
            return
        answer = QMessageBox.question(self, "Excluir sessão", f"Excluir permanentemente a sessão {session_id}?")
        if answer == QMessageBox.StandardButton.Yes:
            self.store.delete(session_id)
            self._refresh_history()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.worker.wait(2000)
            self.worker = None
        self.store.close()
        event.accept()
