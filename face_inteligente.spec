# Empacotamento futuro: pyinstaller --clean face_inteligente.spec
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("mediapipe") if __import__("importlib").util.find_spec("mediapipe") else []

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=["pyqtgraph"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="FaceInteligente",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="assets/icon.ico",
)

