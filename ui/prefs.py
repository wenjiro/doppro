# -*- coding: utf-8 -*-
"""Мелкие настройки окна: тема и последняя папка. Ключей нейросети здесь нет."""

from __future__ import annotations

import json

from core.paths import user_data_dir


def _path():
    return user_data_dir() / "ui.json"


def load() -> dict:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def get(key: str, default=None):
    return load().get(key, default)


def put(key: str, value) -> None:
    data = load()
    data[key] = value
    try:
        _path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return
