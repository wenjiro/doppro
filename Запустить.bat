@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Создаю окружение и ставлю зависимости, это один раз...
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
)
start "" ".venv\Scripts\pythonw.exe" main.py
