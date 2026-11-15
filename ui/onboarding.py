# -*- coding: utf-8 -*-
"""Короткое знакомство при первом запуске. Потом его открывает кнопка «Помощь»."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QVBoxLayout

from core.paths import onboarding_path
from ui.theme import Glyph
from ui.widgets import Button, GlyphLabel, label, set_prop

PAGES = (
    (
        "С чего начать",
        "ДопПро собирает дополнительную общеобразовательную программу в файл Word.\n\n"
        "Впереди пять шагов. Поля со звёздочкой обязательны. Серый текст внутри поля — пример: "
        "в документ он не попадёт, пока вы его не впишете.\n\n"
        "Всё введённое сохраняется само на этом компьютере. Шаги слева можно открывать в любом порядке: "
        "галочка у шага значит, что он заполнен, жёлтая цифра — сколько мест осталось поправить. "
        "Все ваши программы лежат на экране «Мои программы».",
    ),
    (
        "Паспорт",
        "Укажите название, направленность, свою организацию и свои данные. "
        "Краткое название организации попадает в строку составителя.\n\n"
        "Регион и населённый пункт можно выбрать из списка или вписать свои. "
        "Серый текст в пустом поле — только подсказка. В документ он не попадает.",
    ),
    (
        "Обучающиеся и план",
        "На втором шаге задаются возраст, дни недели, часы и размер группы. "
        "Календарь подсвечивает эти дни. Праздник переносит занятие на следующий учебный день графика, "
        "а не на ближайший календарный: остальные занятия сдвигаются по тем же дням. "
        "Свои праздники региона можно запросить у модели в окне «Недели занятий». "
        "Галочка дифференциации берёт ваши промежутки возраста, а не готовые 11–13 и 14–17.\n\n"
        "На третьем шаге сумма часов разделов должна совпасть с общим объёмом. "
        "«Распределить часы» делает это само. «Составить план по названию» пишет разделы по вашей теме, "
        "если в настройках указан ключ. Фамилия и организация в запрос не отправляются.",
    ),
    (
        "Условия и сборка",
        "На четвёртом шаге по названию можно составить оборудование, расходные материалы, "
        "программы и профессии проб. Пустые поля закроет типовой перечень направленности.\n\n"
        "«Собрать программу» создаёт Word и без интернета. "
        "«Сформулировать под эту программу» просит у нейросети цель, задачи, пункт 1.4 и литературу по ГОСТ "
        "по всем уже заполненным шагам. "
        "Без ключа эти места остаются напоминанием, остальной текст берётся из направленности.",
    ),
    (
        "Где это найти потом",
        "Ключ нейросети хранится в «Настройках» и остаётся только на этом компьютере. "
        "Там же можно проверить, что ключ работает, и выбрать светлую или тёмную тему.\n\n"
        "Это окно можно открыть снова кнопкой «Помощь» в левой панели. "
        "Подсказка к кнопке или полю появляется, если задержать на нём курсор.",
    ),
)

_GLYPHS = (Glyph.PLAY, Glyph.DOCUMENT, Glyph.CALENDAR, Glyph.LIST, Glyph.SETTINGS)


def onboarding_seen() -> bool:
    path = onboarding_path()
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(data.get("seen"))


def mark_onboarding_seen() -> None:
    try:
        onboarding_path().write_text(json.dumps({"seen": True}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        return


class OnboardingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.page = 0
        self.setWindowTitle("ДопПро — знакомство")
        self.setModal(True)
        self.setFixedSize(660, 470)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QFrame()
        surface.setObjectName("dialogSurface")
        outer.addWidget(surface)
        box = QVBoxLayout(surface)
        box.setContentsMargins(32, 28, 32, 22)
        box.setSpacing(12)

        head = QHBoxLayout()
        head.setSpacing(12)
        self.icon = GlyphLabel(_GLYPHS[0], "teal", 26)
        head.addWidget(self.icon)
        self.heading = label("", "h1")
        head.addWidget(self.heading, 1)
        box.addLayout(head)

        self.body = label("", wrap=True)
        self.body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.body.setStyleSheet("font-size: 15px; line-height: 150%;")
        box.addWidget(self.body, 1)

        foot = QHBoxLayout()
        self.dots: list[QLabel] = []
        for _ in PAGES:
            dot = QLabel()
            dot.setFixedSize(8, 8)
            dot.setProperty("role", "index")
            self.dots.append(dot)
            foot.addWidget(dot)
        foot.addStretch(1)
        self.back = Button("Назад", on=self._back)
        self.next = Button("Далее", "primary", on=self._next)
        self.next.setDefault(True)
        foot.addWidget(self.back)
        foot.addWidget(self.next)
        box.addLayout(foot)
        self._show()

    def _show(self) -> None:
        from ui.theme import theme

        title, text = PAGES[self.page]
        self.heading.setText(title)
        self.body.setText(text)
        self.icon.set_glyph(_GLYPHS[self.page], "teal")
        for index, dot in enumerate(self.dots):
            color = theme.p["teal"] if index == self.page else theme.p["line_strong"]
            dot.setStyleSheet(f"background: {color}; border-radius: 4px;")
        self.back.setEnabled(self.page > 0)
        self.next.setText("Понятно" if self.page == len(PAGES) - 1 else "Далее")
        set_prop(self.next, "kind", "primary")

    def _back(self) -> None:
        if self.page:
            self.page -= 1
            self._show()

    def _next(self) -> None:
        if self.page < len(PAGES) - 1:
            self.page += 1
            self._show()
            return
        self.accept()

    def done(self, code: int) -> None:
        mark_onboarding_seen()
        super().done(code)
