# -*- coding: utf-8 -*-
"""Точка входа «ДопПро».

Запуск из исходников: python main.py
Запуск у педагога: ДопПро.exe, Python на его компьютере не нужен.
"""

from __future__ import annotations

import traceback


def _report(exc: BaseException) -> None:
    """Пишет журнал и показывает короткое окно, если интерфейс ещё не успел открыться."""
    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    try:
        from core.paths import error_log_path

        error_log_path().write_text(text, encoding="utf-8")
        where = str(error_log_path())
    except Exception:
        where = "журнал ошибок недоступен"
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "ДопПро",
            "Не удалось запустить программу.\nПодробности записаны в файл:\n" + where,
        )
        root.destroy()
    except Exception:
        pass


def main() -> None:
    try:
        from core.assets_prep import ensure

        ensure()
        from gui.app import run

        run()
    except Exception as exc:
        _report(exc)
        raise


if __name__ == "__main__":
    main()
