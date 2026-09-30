"""Ponto de entrada do Face Inteligente."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except ImportError:
        print(
            "PySide6 não está instalado. Crie um ambiente virtual e execute "
            "`pip install -r requirements.txt`.",
            file=sys.stderr,
        )
        return 1

    from src.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Face Inteligente")
    app.setOrganizationName("Face Inteligente")
    try:
        window = MainWindow()
        window.show()
        return app.exec()
    except Exception as exc:  # barreira final para falhas de inicialização
        QMessageBox.critical(None, "Falha ao iniciar", str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
