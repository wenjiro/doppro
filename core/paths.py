# -*- coding: utf-8 -*-
"""Пути к ресурсам программы.

В исходниках корень — папка проекта.
В собранном exe PyInstaller распаковывает данные во временную папку _MEIPASS.
Черновик педагога пишется в каталог пользователя, а не внутрь exe.
"""

from __future__ import annotations

import sys
from pathlib import Path

VERSION = "1.0.0"
APP_NAME = "ДопПро"
GITHUB_REPO = "wenjiro/doppro"
GITHUB_RELEASES = "https://github.com/wenjiro/doppro/releases"


def is_frozen() -> bool:
    """True, если программа запущена из собранного exe."""
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    """Корень с ресурсами: при сборке — временная папка PyInstaller."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent.parent


def assets_dir() -> Path:
    return project_root() / "assets"


def logo_path() -> Path:
    return assets_dir() / "logo.png"


def icon_path() -> Path:
    return assets_dir() / "icon.ico"


def template_path() -> Path:
    return project_root() / "templates" / "program_template.docx"


def text_blocks_dir() -> Path:
    return project_root() / "templates" / "text_blocks"


def modules_path() -> Path:
    return project_root() / "data" / "default_modules.json"


def user_data_dir() -> Path:
    """Каталог, куда можно писать: черновик и журнал ошибок."""
    import os

    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home()
    folder = root / "DopPro"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def draft_path() -> Path:
    return user_data_dir() / "draft.json"


def error_log_path() -> Path:
    return user_data_dir() / "error.log"


def settings_path() -> Path:
    """Ключ нейросети. В черновик программы и в docx он не пишется."""
    return user_data_dir() / "settings.json"


def onboarding_path() -> Path:
    """Отметка, что педагог уже видел знакомство с программой."""
    return user_data_dir() / "onboarding.json"
