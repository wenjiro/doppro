# -*- coding: utf-8 -*-
"""Шаг 3. Разделы, часы и опции: пробы, мини-проект, итоговая работа."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QProgressBar, QVBoxLayout, QWidget

from core.data_model import ModuleItem
from core.generator import GenerationError, generate_plan
from core.planning import default_modules, scale_modules
from ui.pages.base import StepPage
from ui.theme import Glyph
from ui.widgets import Banner, Button, Card, IntEdit, LineEdit, TextArea, alert, ask, checkbox, label, run_async, set_prop


class ModuleCard(QFrame):
    """Один раздел: название, часы, темы лекций и практик."""

    edited = Signal()
    move = Signal(int, int)
    remove = Signal(int)
    toggled = Signal(int, bool)

    def __init__(self, index: int, module: ModuleItem, opened: bool, last: bool):
        super().__init__()
        self.index = index
        self.setObjectName("subcard")
        box = QVBoxLayout(self)
        box.setContentsMargins(14, 12, 12, 12)
        box.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(10)
        number = label(str(index + 1), "index")
        number.setFixedSize(28, 28)
        number.setAlignment(Qt.AlignCenter)
        head.addWidget(number)
        self.name = LineEdit("Название раздела", 220)
        self.name.setText(module.name)
        head.addWidget(self.name, 1)
        up = Button("", "icon", Glyph.UP, tip="Поднять раздел выше")
        up.setEnabled(index > 0)
        up.clicked.connect(lambda: self.move.emit(self.index, -1))
        down = Button("", "icon", Glyph.DOWN, tip="Опустить раздел ниже")
        down.setEnabled(not last)
        down.clicked.connect(lambda: self.move.emit(self.index, 1))
        delete = Button("", "icon", Glyph.DELETE, tip="Удалить раздел")
        delete.clicked.connect(lambda: self.remove.emit(self.index))
        for item in (up, down, delete):
            head.addWidget(item)
        box.addLayout(head)

        hours = QHBoxLayout()
        hours.setSpacing(8)
        hours.addSpacing(38)
        hours.addWidget(label("Теория", "muted"))
        self.theory = IntEdit(4, 70)
        self.theory.setText(str(module.theory))
        hours.addWidget(self.theory)
        hours.addSpacing(8)
        hours.addWidget(label("Практика", "muted"))
        self.practice = IntEdit(4, 70)
        self.practice.setText(str(module.practice))
        hours.addWidget(self.practice)
        self.total = label("", "chip")
        hours.addSpacing(6)
        hours.addWidget(self.total)
        hours.addStretch(1)
        self.toggle = Button("", "ghost", on=self._toggle)
        hours.addWidget(self.toggle)
        box.addLayout(hours)

        self.topics = QWidget()
        topics = QHBoxLayout(self.topics)
        topics.setContentsMargins(38, 0, 0, 0)
        topics.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(4)
        left.addWidget(label("Темы лекций — по одной на строку", "small"))
        self.lectures = TextArea(96, "Если пусто, программа составит темы сама")
        self.lectures.setPlainText("\n".join(module.lectures))
        left.addWidget(self.lectures)
        right = QVBoxLayout()
        right.setSpacing(4)
        right.addWidget(label("Темы практик — по одной на строку", "small"))
        self.practices = TextArea(96, "Если пусто, программа составит темы сама")
        self.practices.setPlainText("\n".join(module.practices))
        right.addWidget(self.practices)
        topics.addLayout(left, 1)
        topics.addLayout(right, 1)
        box.addWidget(self.topics)
        self._opened = opened
        self.topics.setVisible(opened)

        self.name.textEdited.connect(lambda _t: self.edited.emit())
        self.theory.textEdited.connect(lambda _t: self._hours_changed())
        self.practice.textEdited.connect(lambda _t: self._hours_changed())
        self.lectures.textChanged.connect(self._topics_changed)
        self.practices.textChanged.connect(self._topics_changed)
        self._refresh()

    def _hours_changed(self) -> None:
        self._refresh()
        self.edited.emit()

    def _topics_changed(self) -> None:
        self._refresh()
        self.edited.emit()

    def _toggle(self) -> None:
        self._opened = not self._opened
        self.topics.setVisible(self._opened)
        self._refresh()
        self.toggled.emit(self.index, self._opened)

    def _refresh(self) -> None:
        theory, practice = self.hours()
        self.total.setText("часы?" if theory < 0 or practice < 0 else f"{theory + practice} ч.")
        count_l, count_p = len(self.lectures.lines()), len(self.practices.lines())
        topics = f"лекций {count_l}, практик {count_p}" if count_l or count_p else "составит программа"
        self.toggle.setText(("Скрыть темы" if self._opened else f"Темы занятий: {topics}") + ("  ▴" if self._opened else "  ▾"))

    def hours(self) -> tuple[int, int]:
        theory_raw = self.theory.text().strip()
        practice_raw = self.practice.text().strip()
        return (self.theory.value() if theory_raw else 0, self.practice.value() if practice_raw else 0)

    def item(self) -> ModuleItem:
        theory, practice = self.hours()
        return ModuleItem(
            name=self.name.value(),
            theory=theory,
            practice=practice,
            lectures=self.lectures.lines(),
            practices=self.practices.lines(),
        )


class PlanPage(StepPage):
    index = 2

    def __init__(self, window):
        super().__init__(
            window,
            "Учебный план",
            "Часы всех разделов должны сойтись с общим объёмом. Каждый учебный день получает тему лекции и тему практики.",
        )
        self._cards: list[ModuleCard] = []
        self._opened: dict[int, bool] = {}
        self._waiting = False

        tools = Card()
        row = QHBoxLayout()
        row.setSpacing(10)
        self.sum_label = label("", "h3")
        row.addWidget(self.sum_label, 1)
        row.addWidget(Button("Распределить часы", glyph=Glyph.BALANCE, on=self._scale,
                             tip="Раскладывает уже указанные часы так, чтобы сумма совпала с общим объёмом."))
        tools.body.addLayout(row)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        tools.body.addWidget(self.bar)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(Button("Добавить раздел", glyph=Glyph.ADD, on=self._add,
                             tip="Пустой раздел в конец списка. Часы потом нужно свести с общим объёмом."))
        row.addWidget(Button("Типовые разделы", glyph=Glyph.LIST, on=self._load_defaults,
                             tip="Заменяет разделы типовым набором выбранной направленности, не вашей темой."))
        row.addStretch(1)
        self.plan_button = Button("Составить план по названию", "teal", Glyph.SPARK, on=self._start_plan,
                                  tip="Просит у нейросети разделы, темы лекций и практик по названию. Нужен ключ в «Настройках». "
                                      "Фамилия и организация в запрос не входят.")
        row.addWidget(self.plan_button)
        tools.body.addLayout(row)
        self.plan_status = Banner("info")
        self.plan_status.hide()
        tools.body.addWidget(self.plan_status)
        self.add(tools)

        self.list_box = QVBoxLayout()
        self.list_box.setSpacing(10)
        holder = QWidget()
        holder.setLayout(self.list_box)
        self.list_box.setContentsMargins(0, 0, 0, 0)
        self.add(holder)
        self.empty = label("Разделов пока нет. Добавьте раздел или подставьте типовой набор.", "muted")
        self.add(self.empty)

        options = Card("Что включить в программу",
                       "Отдельные часы под опции не добавляются — они входят в практические и проектные разделы.")
        self.trials = checkbox("Профессиональные пробы",
                               "Добавляет знакомство с ролью специалиста. Отдельные часы под это не выделяются.")
        self.regional = checkbox("Региональный мини-проект", "Связывает один раздел с городом из паспорта.")
        self.final = checkbox("Итоговый проект или итоговый продукт",
                              "Нужно включить, если итоговая аттестация — защита проекта.")
        self.interim = checkbox("Промежуточная аттестация по разделам",
                                "В середине срока появится промежуточная проверка по разделам.")
        self.excursions = checkbox("Экскурсии или выездные занятия",
                                   "Отметьте, если выезды есть. Их часы входят в практические разделы.")
        for box in (self.trials, self.regional, self.final, self.interim, self.excursions):
            options.body.addWidget(box)
            self.watch(box)
        options.body.addWidget(label(
            "Если на предыдущем шаге несколько возрастных промежутков, проба для младших остаётся коротким шагом, "
            "а для старшего — ближе к роли.", "small", wrap=True))
        self.add(options)
        self.finish()

    # ---------- модель ----------

    def load(self) -> None:
        model = self.model
        if not model.modules:
            hours = model.total_hours if model.total_hours > 0 else 144
            model.modules = default_modules(model.direction, hours)
        self._draw()
        self.trials.setChecked(model.professional_trials)
        self.regional.setChecked(model.regional_project)
        self.final.setChecked(model.final_project)
        self.interim.setChecked(model.interim_attestation)
        self.excursions.setChecked(model.excursions)

    def commit(self) -> None:
        model = self.model
        model.modules = [card.item() for card in self._cards]
        model.professional_trials = self.trials.isChecked()
        model.regional_project = self.regional.isChecked()
        model.final_project = self.final.isChecked()
        model.interim_attestation = self.interim.isChecked()
        model.excursions = self.excursions.isChecked()

    def show_errors(self, errors: list[str]) -> None:
        # Про сумму часов уже говорит полоса над разделами.
        super().show_errors([text for text in errors if not text.startswith("Сумма часов")])

    def _draw(self) -> None:
        was_loading = self._loading
        self._loading = True
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards = []
        modules = self.model.modules
        for index, module in enumerate(modules):
            card = ModuleCard(index, module, self._opened.get(index, False), index == len(modules) - 1)
            card.edited.connect(self._card_edited)
            card.move.connect(self._move)
            card.remove.connect(self._delete)
            card.toggled.connect(lambda i, state: self._opened.__setitem__(i, state))
            self.list_box.addWidget(card)
            self._cards.append(card)
        self.empty.setVisible(not modules)
        self._loading = was_loading
        self._refresh_sum()

    def _card_edited(self) -> None:
        self._refresh_sum()
        self._edited()

    def _refresh_sum(self) -> None:
        total = 0
        broken = False
        for card in self._cards:
            theory, practice = card.hours()
            if theory < 0 or practice < 0:
                broken = True
                continue
            total += theory + practice
        target = self.model.total_hours
        self.bar.setRange(0, max(target, 1))
        self.bar.setValue(min(total, max(target, 1)))
        if broken:
            self.sum_label.setText("В часах раздела должны быть целые числа")
            set_prop(self.sum_label, "role", "danger")
            set_prop(self.bar, "state", "over")
        elif target > 0 and total == target:
            self.sum_label.setText(f"Часов в разделах: {total} из {target} — сходится")
            set_prop(self.sum_label, "role", "ok")
            set_prop(self.bar, "state", "ok")
        else:
            diff = target - total
            tail = f"не хватает {diff}" if diff > 0 else f"лишних {-diff}"
            self.sum_label.setText(f"Часов в разделах: {total} из {target} — {tail}")
            set_prop(self.sum_label, "role", "warn" if diff > 0 else "danger")
            set_prop(self.bar, "state", "" if diff > 0 else "over")

    def _changed_structure(self) -> None:
        self._draw()
        self.session.touch()

    # ---------- действия ----------

    def _add(self) -> None:
        self.commit()
        self.model.modules.append(ModuleItem("Новый раздел", 0, 2))
        self._opened[len(self.model.modules) - 1] = True
        self._changed_structure()

    def _delete(self, index: int) -> None:
        self.commit()
        modules = self.model.modules
        if len(modules) <= 1:
            alert(self, "В программе нужен хотя бы один раздел", kind="warn")
            return
        name = modules[index].name.strip() or f"раздел {index + 1}"
        if not ask(self, f"Удалить «{name}»?", "Часы и темы этого раздела пропадут.", yes="Удалить", danger=True):
            return
        del modules[index]
        self._opened = {}
        self._changed_structure()

    def _move(self, index: int, shift: int) -> None:
        self.commit()
        target = index + shift
        modules = self.model.modules
        if target < 0 or target >= len(modules):
            return
        modules[index], modules[target] = modules[target], modules[index]
        self._opened[index], self._opened[target] = self._opened.get(target, False), self._opened.get(index, False)
        self._changed_structure()

    def _load_defaults(self) -> None:
        self.commit()
        if any(item.name.strip() for item in self.model.modules):
            if not ask(self, "Заменить разделы типовым набором?",
                       "Текущие разделы заменит типовой набор выбранной направленности.", yes="Заменить"):
                return
        hours = self.model.total_hours if self.model.total_hours > 0 else 144
        self.model.modules = default_modules(self.model.direction, hours)
        self._opened = {}
        self._changed_structure()

    def _scale(self) -> None:
        self.commit()
        hours = self.model.total_hours
        if hours <= 0:
            alert(self, "Сначала укажите общий объём часов", "Он задаётся на шаге «Обучающиеся».", "warn")
            return
        if not self.model.modules:
            return
        self.model.modules = scale_modules(self.model.modules, hours)
        self._changed_structure()

    def _start_plan(self) -> None:
        if self._waiting:
            return
        self.commit()
        model = self.model
        if not model.title.strip():
            alert(self, "Сначала укажите название программы", "Оно задаётся на шаге «Паспорт».", "warn")
            return
        if any(item.name.strip() for item in model.modules):
            if not ask(self, "Заменить разделы планом по названию?",
                       "Текущие разделы будут заменены. Часы будут сведены с общим объёмом.", yes="Заменить"):
                return
        self._waiting = True
        self.plan_button.setEnabled(False)
        self.plan_status.show_message("info", f"Составляю разделы по названию «{model.title.strip()}»…")
        run_async(self, lambda: generate_plan(model), self._plan_ready, self._plan_failed)

    def _plan_failed(self, error) -> None:
        self._waiting = False
        self.plan_button.setEnabled(True)
        text = str(error)
        if not isinstance(error, GenerationError):
            text = f"Не удалось составить план.\n\n{text}"
        self.plan_status.show_message("error", text)

    def _plan_ready(self, modules) -> None:
        self._waiting = False
        self.plan_button.setEnabled(True)
        self.model.modules = modules
        self.model.generated = {}
        self._opened = {}
        self.plan_status.show_message(
            "ok",
            "Разделы составлены по названию, часы сведены с объёмом. "
            "Тексты разделов на шаге сборки нужно сформулировать заново.",
        )
        self._changed_structure()
