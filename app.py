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

    import argparse

    parser = argparse.ArgumentParser(description="Face Inteligente")
    parser.add_argument("--autostart", action="store_true", help="Inicia a câmera automaticamente")
    parser.add_argument("--calibrate", action="store_true", help="Inicia calibração automaticamente")
    args, _ = parser.parse_known_args()

    app = QApplication(sys.argv)
    app.setApplicationName("Face Inteligente")
    app.setOrganizationName("Face Inteligente")
    try:
        window = MainWindow(autostart=args.autostart, auto_calibrate=args.calibrate)
        window.show()
        return app.exec()

    except Exception as exc:  # barreira final para falhas de inicialização
        QMessageBox.critical(None, "Falha ao iniciar", str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
