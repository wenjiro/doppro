@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [1/3] Установка зависимостей...
python -m pip install -r requirements.txt
if errorlevel 1 goto fail

echo [2/3] Логотип, иконка и шаблон документа...
python tools\prepare_assets.py
if errorlevel 1 goto fail

echo [3/3] Сборка одного exe...
python -m PyInstaller --noconfirm --clean build.spec
if errorlevel 1 goto fail

echo.
echo Готово: dist\ДопПро.exe
echo Этот файл можно отдать педагогу. Python на его компьютере не нужен.
pause
exit /b 0

:fail
echo.
echo Сборка остановилась из-за ошибки. Смотрите текст выше.
pause
exit /b 1
