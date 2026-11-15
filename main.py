# -*- coding: utf-8 -*-
"""Точка входа «ДопПро».

Запуск из исходников: python main.py
Запуск у педагога: ДопПро.exe, Python на его компьютере не нужен.
"""

from __future__ import annotations

import sys
import traceback


def _report(exc: BaseException) -> None:
    """Пишет журнал и показывает короткое окно, если интерфейс не смог открыться."""
    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    try:
        from core.paths import error_log_path

        error_log_path().write_text(text, encoding="utf-8")
        where = str(error_log_path())
    except Exception:
        where = "журнал ошибок недоступен"
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            0, "Не удалось запустить программу.\nПодробности записаны в файл:\n" + where, "ДопПро", 0x10
        )
    except Exception:
        pass


def main() -> int:
    try:
        from core.assets_prep import ensure

        ensure()
        from PySide6.QtWidgets import QApplication

        from ui import prefs
        from ui.main_window import MainWindow
        from ui.theme import base_font, theme

        app = QApplication(sys.argv)
        app.setApplicationName("ДопПро")
        app.setStyle("Fusion")
        app.setFont(base_font())
        theme.apply("dark" if prefs.get("theme") == "dark" else "light")
        window = MainWindow()
        saved = prefs.get("window")
        if isinstance(saved, list) and len(saved) == 3:
            window.resize(max(1040, int(saved[0])), max(680, int(saved[1])))
            if saved[2]:
                window.showMaximized()
            else:
                window.show()
        else:
            window.show()
        return app.exec()
    except Exception as exc:
        _report(exc)
        raise


if __name__ == "__main__":
    sys.exit(main())
