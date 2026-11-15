# -*- coding: utf-8 -*-
"""Открытая программа и её автосохранение.

Черновик пишется после каждой правки. Программа с названием сама попадает
в «Мои программы» и обновляется там же. Ключ нейросети сюда не входит.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal

from core.data_model import ProgramData
from core.library import save_program

STEP_TITLES = ("Паспорт", "Обучающиеся", "Учебный план", "Условия", "Сборка")


class Session(QObject):
    changed = Signal()  # педагог что-то поправил
    replaced = Signal()  # открыта другая программа
    saved = Signal(str)  # текст для строки состояния

    def __init__(self) -> None:
        super().__init__()
        self.model, self.draft_used = ProgramData.load_draft()
        self.touched: set[int] = set()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(700)
        self._timer.timeout.connect(self.flush)
        self._dirty = False

    def touch(self) -> None:
        """Отмечает правку. Запись на диск идёт с небольшой задержкой."""
        self._dirty = True
        self._timer.start()
        self.changed.emit()

    def flush(self) -> None:
        self._timer.stop()
        if not self._dirty:
            return
        self._dirty = False
        try:
            if self.model.title.strip() or self.model.library_id:
                save_program(self.model)
            self.model.save_draft()
        except OSError:
            self.saved.emit("Не удалось сохранить черновик")
            return
        self.saved.emit("Сохранено в " + datetime.now().strftime("%H:%M"))

    def replace(self, program: ProgramData, keep_current: bool = True) -> None:
        if keep_current:
            self.flush()
        else:
            self._timer.stop()
            self._dirty = False
        self.model = program
        self.touched = set()
        self.draft_used = False
        self._dirty = True
        self.flush()
        self.replaced.emit()

    def step_errors(self, index: int) -> list[str]:
        model = self.model
        if index == 0:
            return model.errors_passport()
        if index == 1:
            return model.errors_learners()
        if index == 2:
            return model.errors_plan()
        if index == 3:
            return model.errors_conditions()
        return model.validate()
