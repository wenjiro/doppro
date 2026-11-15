# -*- mode: python ; coding: utf-8 -*-
"""Сборка одного exe «ДопПро» для Windows.

Запуск: python -m PyInstaller --noconfirm --clean build.spec
Или просто build_exe.bat
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH)

datas = []
datas += collect_data_files("docx")
datas += [
    (str(root / "assets"), "assets"),
    (str(root / "templates"), "templates"),
    (str(root / "data"), "data"),
    (str(root / "certs"), "certs"),
]

hiddenimports = collect_submodules("docxtpl")
hiddenimports += [
    "jinja2",
    "jinja2.ext",
    "lxml",
    "lxml.etree",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
]

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtOpenGL",
        "PySide6.QtOpenGLWidgets",
        "PySide6.QtPdf",
        "PySide6.QtSql",
        "PySide6.QtSvg",
        "PySide6.QtTest",
        "PySide6.QtXml",
        "PySide6.QtDBus",
        "PySide6.QtConcurrent",
        "PySide6.QtPrintSupport",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ДопПро",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(root / "assets" / "icon.ico"),
)
