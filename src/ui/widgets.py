"""Componentes visuais reutilizáveis."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QVBoxLayout,
)


class MetricCard(QFrame):
    def __init__(self, title: str, value: str = "—") -> None:
        super().__init__()
        self.setObjectName("metricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        title_label = QLabel(title)
        title_label.setObjectName("metricTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("metricValue")
        layout.addWidget(title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str, state: str = "neutral") -> None:
        colors = {"good": "#44d19d", "warn": "#f6c85f", "bad": "#ff7b72", "neutral": "#e6edf3"}
        self.value_label.setText(value)
        self.value_label.setStyleSheet(f"color: {colors.get(state, colors['neutral'])};")


class ConsentDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Consentimento e limitações")
        self.setModal(True)
        self.resize(600, 410)
        layout = QVBoxLayout(self)
        heading = QLabel("Antes de ligar a câmera")
        heading.setObjectName("dialogHeading")
        body = QLabel(
            "Este protótipo estima somente variações de ativação fisiológica a partir de sinais visuais. "
            "Ele não diagnostica ansiedade, não detecta mentira, não identifica pessoas e não determina emoções.\n\n"
            "Calor, exercício, cafeína, movimento, iluminação, doenças e medicamentos podem alterar os sinais. "
            "Os resultados são experimentais e não substituem avaliação clínica.\n\n"
            "O vídeo é processado localmente e não é gravado. Por padrão, nenhuma sessão é salva; quando "
            "habilitado, somente métricas numéricas são armazenadas no computador."
        )
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.confirm = QCheckBox("Li, compreendi e autorizo o uso da câmera para esta sessão.")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText("Concordar e continuar")
        ok.setEnabled(False)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        self.confirm.toggled.connect(ok.setEnabled)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(heading)
        layout.addWidget(body, 1)
        layout.addWidget(self.confirm)
        layout.addWidget(buttons)


APP_STYLE = """
QMainWindow, QDialog { background: #0d1117; color: #e6edf3; }
QWidget { font-family: 'Segoe UI'; font-size: 10pt; color: #e6edf3; }
QFrame#sidebar, QFrame#panel, QFrame#metricCard { background: #161b22; border: 1px solid #30363d; border-radius: 8px; }
QLabel#appTitle { font-size: 20pt; font-weight: 700; color: #ffffff; }
QLabel#subtitle, QLabel#metricTitle { color: #8b949e; }
QLabel#metricValue { font-size: 16pt; font-weight: 650; }
QLabel#activation { font-size: 22pt; font-weight: 700; padding: 12px; border-radius: 8px; background: #21262d; }
QLabel#dialogHeading { font-size: 17pt; font-weight: 700; }
QPushButton { background: #238636; border: 1px solid #2ea043; border-radius: 6px; padding: 8px 14px; font-weight: 600; }
QPushButton:hover { background: #2ea043; }
QPushButton:disabled { background: #21262d; border-color: #30363d; color: #6e7681; }
QPushButton#stopButton, QPushButton#deleteButton { background: #8e2a2a; border-color: #da3633; }
QComboBox, QSpinBox { background: #0d1117; border: 1px solid #30363d; border-radius: 5px; padding: 6px; }
QProgressBar { border: 1px solid #30363d; border-radius: 5px; background: #0d1117; text-align: center; }
QProgressBar::chunk { background: #1f6feb; border-radius: 4px; }
QTableWidget { background: #0d1117; alternate-background-color: #161b22; gridline-color: #30363d; }
QHeaderView::section { background: #21262d; padding: 6px; border: 0; }
QCheckBox { spacing: 8px; }
"""
