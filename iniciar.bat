@echo off
title Face Inteligente
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Ambiente virtual .venv nao encontrado. Criando...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install -r requirements.txt
    python -m pip install -r requirements-optional.txt
)
start "" ".venv\Scripts\python.exe" app.py
