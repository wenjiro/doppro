# -*- coding: utf-8 -*-
"""Шаг 2. Кому и сколько: возраст, срок, часы, группа, календарь."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from core.data_model import CALENDAR_MODES, STUDY_FORMS, suggest_age_spans
from core.holidays import region_holiday_title
from core.planning import active_holiday_extra, effective_class_days
from ui.pages.base import StepPage
from ui.theme import Glyph
from ui.widgets import Banner, Button, Card, Combo, IntEdit, checkbox, label

_DAY_NAMES = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


class LearnersPage(StepPage):
    index = 1
    ERR_MAP = (
        ("ромежут", "spans"),
        ("Возраст", "age_from"),
        ("Срок реализации", "years"),
        ("Объём программы", "total"),
        ("Нагрузка в неделю", "weekly"),
        ("Не сходится режим", "weekly"),
        ("Длительность занятия", "lesson"),
        ("Одно занятие", "lesson"),
        ("аполняемость", "group_min"),
        ("В группе", "group_min"),
        ("форму обучения", "study_form"),
        ("календарный режим", "calendar"),
        ("дни занятий", "days"),
        ("академического часа", "minutes"),
        ("Перерыв", "break"),
        ("Учебных недель", "weeks"),
    )

    def __init__(self, window):
        super().__init__(
            window,
            "Обучающиеся, срок и объём",
            "От этих чисел зависят календарный график и количество занятий.",
        )
        self._class_weeks: list[str] = []
        self._custom_weeks = False
        self._span_rows: list[tuple[QWidget, IntEdit, IntEdit]] = []

        # Возраст и группа
        card = Card("Возраст и группа")
        self.age_from = IntEdit(2)
        self.age_to = IntEdit(2)
        self.group_min = IntEdit(2)
        self.group_max = IntEdit(2)
        card.row(
            self.field("age_from", "Возраст от, лет", self.age_from, True),
            self.field("age_to", "Возраст до, лет", self.age_to, True),
            self.field("group_min", "Наполняемость от, чел.", self.group_min, True),
            self.field("group_max", "Наполняемость до, чел.", self.group_max, True),
        )
        self.no_prior = checkbox(
            "Без предварительной подготовки, свободный набор",
            "В адресате будет сказано, что до первого занятия отбора и подготовки нет.",
        )
        self.watch(self.no_prior)
        card.body.addWidget(self.no_prior)
        self.differentiate = checkbox(
            "Дифференцировать задания по возрастным промежуткам",
            "Промежутки задаёте сами. В таблицу и в текст попадут именно они, от младшего к старшему.",
        )
        self.differentiate.clicked.connect(self._toggle_spans)
        self.watch(self.differentiate)
        card.body.addWidget(self.differentiate)

        self.spans_box = QWidget()
        spans = QVBoxLayout(self.spans_box)
        spans.setContentsMargins(27, 0, 0, 0)
        spans.setSpacing(8)
        self.span_rows = QVBoxLayout()
        self.span_rows.setSpacing(6)
        rows_holder = QWidget()
        rows_holder.setLayout(self.span_rows)
        self.span_rows.setContentsMargins(0, 0, 0, 0)
        spans.addWidget(self.field(
            "spans", "Промежутки внутри возраста программы, лет", rows_holder,
            note="Каждый промежуток попадёт в документ отдельной строкой. Промежутки не должны пересекаться.",
        ))
        actions = QHBoxLayout()
        actions.addWidget(Button("Добавить промежуток", glyph=Glyph.ADD, on=self._add_empty_span,
                                 tip="Ещё одна строка «от» и «до»."))
        actions.addWidget(Button("Разбить по возрасту программы", "ghost", on=self._fill_suggested,
                                 tip="Подставит черновик по полям «Возраст от» и «Возраст до». Потом цифры можно поправить."))
        actions.addStretch(1)
        spans.addLayout(actions)
        self.span_note = label("", "small", wrap=True)
        self.span_note.hide()
        spans.addWidget(self.span_note)
        card.body.addWidget(self.spans_box)
        self.add(card)

        # Режим занятий
        card = Card("Режим занятий", "Часы в неделю считаются сами: дни × длительность занятия.")
        days_holder = QWidget()
        days_row = QHBoxLayout(days_holder)
        days_row.setContentsMargins(0, 0, 0, 0)
        days_row.setSpacing(6)
        self.day_buttons: list[Button] = []
        for name in _DAY_NAMES:
            chip = Button(name, "chip", on=self._days_changed)
            chip.setCheckable(True)
            days_row.addWidget(chip)
            self.day_buttons.append(chip)
        days_row.addStretch(1)
        days_field = self.field("days", "Дни занятий", days_holder, True)
        self.days_count = label("", "small")
        days_field.layout().addWidget(self.days_count)
        self.lesson = Combo(["1", "2", "3", "4"])
        self.lesson.activated.connect(lambda _i: self._days_changed())
        self.weekly = IntEdit(2)
        card.row(
            days_field,
            self.field("lesson", "Занятие, ак. ч.", self.lesson, True),
            self.field("weekly", "Часов в неделю", self.weekly, True),
            stretch=(5, 2, 2),
        )
        self.years = Combo(["1", "2", "3", "4", "5"])
        self.minutes = Combo(["30", "35", "40", "45"])
        self.break_minutes = Combo(["0", "5", "10", "15"])
        self.study_form = Combo(STUDY_FORMS)
        card.row(
            self.field("years", "Срок реализации, лет", self.years, True),
            self.field("minutes", "Академический час, мин.", self.minutes, True),
            self.field("break", "Перерыв, мин.", self.break_minutes, True),
            self.field("study_form", "Форма обучения", self.study_form, True),
            stretch=(2, 2, 2, 4),
        )
        self.add(card)

        # Объём и календарь
        card = Card("Объём и календарь")
        self.total = IntEdit(4)
        self.weeks = IntEdit(2)
        self.weeks.textEdited.connect(self._weeks_edited)
        self.calendar = Combo(CALENDAR_MODES)
        card.row(
            self.field("total", "Общий объём, часов", self.total, True,
                       "С этим числом должны сойтись часы всех разделов на следующем шаге."),
            self.field("weeks", "Учебных недель", self.weeks, True),
            self.field("calendar", "Календарный график", self.calendar, True,
                       "Летняя смена: в документе месяцы будут июнь–август."),
            stretch=(2, 2, 4),
        )
        self.calc_hint = Banner("info")
        card.body.addWidget(self.calc_hint)
        line = QHBoxLayout()
        line.setSpacing(14)
        self.calendar_button = Button(
            "Недели занятий", "teal", Glyph.CALENDAR, on=self._open_calendar,
            tip="Сначала отметьте дни недели. Календарь подсветит их. Если день праздничный, занятие сдвигается на следующий свободный.",
        )
        line.addWidget(self.calendar_button)
        self.calendar_note = label("", "muted", wrap=True)
        line.addWidget(self.calendar_note, 1)
        card.body.addLayout(line)
        self.add(card)

        self.add(label(
            "Если измените общий объём часов, на следующем шаге нажмите «Распределить часы», "
            "чтобы сумма разделов совпала с программой.", "small", wrap=True))
        for editor in (self.total, self.weekly):
            editor.textEdited.connect(lambda _t: self._refresh_calc())
        self.years.activated.connect(lambda _i: self._refresh_calc())
        self.finish()

    # ---------- модель ----------

    def load(self) -> None:
        model = self.model
        self.age_from.set_value(model.age_from)
        self.age_to.set_value(model.age_to)
        self.years.set_value(str(model.years) if model.years > 0 else "1")
        self.lesson.set_value(str(model.lesson_hours) if model.lesson_hours > 0 else "2")
        self._show_days(effective_class_days(model.class_days, model.lessons_per_week))
        self.minutes.set_value(str(model.academic_minutes) if model.academic_minutes > 0 else "45")
        self.break_minutes.set_value(str(model.break_minutes))
        self.total.set_value(model.total_hours)
        self.weeks.set_value(model.study_weeks if model.study_weeks > 0 else 36)
        self._class_weeks = list(model.class_weeks)
        self._custom_weeks = bool(self._class_weeks)
        self.weekly.set_value(model.hours_per_week)
        self.group_min.set_value(model.group_min)
        self.group_max.set_value(model.group_max)
        self.study_form.set_value(model.study_form)
        self.calendar.set_value(model.calendar_mode)
        self.differentiate.setChecked(model.differentiate)
        self.no_prior.setChecked(model.no_prior_training)
        self._show_spans(model.age_spans or suggest_age_spans(model.age_from, model.age_to))
        self.spans_box.setVisible(model.differentiate)
        self._refresh_calendar_note()
        self._refresh_calc()

    def commit(self) -> None:
        model = self.model
        model.age_from = self.age_from.value()
        model.age_to = self.age_to.value()
        model.years = int(self.years.value())
        model.lesson_hours = int(self.lesson.value())
        days = self._selected_days()
        model.class_days = days
        model.lessons_per_week = len(days)
        model.academic_minutes = int(self.minutes.value())
        model.break_minutes = int(self.break_minutes.value())
        model.total_hours = self.total.value()
        typed_weeks = self.weeks.value()
        if self._custom_weeks and typed_weeks == len(self._class_weeks):
            model.class_weeks = list(self._class_weeks)
        else:
            model.class_weeks = []
        model.study_weeks = typed_weeks
        model.hours_per_week = self.weekly.value()
        model.group_min = self.group_min.value()
        model.group_max = self.group_max.value()
        model.study_form = self.study_form.value()
        model.calendar_mode = self.calendar.value()
        model.differentiate = self.differentiate.isChecked()
        model.age_spans = self._collect_spans()
        model.no_prior_training = self.no_prior.isChecked()

    # ---------- дни ----------

    def _selected_days(self) -> list[int]:
        return [index for index, chip in enumerate(self.day_buttons) if chip.isChecked()]

    def _show_days(self, days: list[int]) -> None:
        chosen = set(days)
        for index, chip in enumerate(self.day_buttons):
            chip.setChecked(index in chosen)
        self._refresh_days_label()

    def _days_changed(self) -> None:
        if self._loading:
            return
        days = self._selected_days()
        hours = int(self.lesson.value())
        if days and hours > 0:
            self.weekly.set_value(len(days) * hours)
        self._refresh_days_label()
        self._refresh_calc()
        self._edited()

    def _refresh_days_label(self) -> None:
        names = [name for name, chip in zip(_DAY_NAMES, self.day_buttons) if chip.isChecked()]
        if names:
            self.days_count.setText(f"{len(names)} в неделю: {', '.join(names)}")
        else:
            self.days_count.setText("Отметьте хотя бы один день")

    # ---------- календарь ----------

    def _weeks_edited(self, _text: str = "") -> None:
        if self._custom_weeks and self.weeks.value() != len(self._class_weeks):
            self._custom_weeks = False
            self._refresh_calendar_note()

    def _open_calendar(self) -> None:
        from ui.calendar_dialog import CalendarDialog

        self.commit()
        CalendarDialog(self.window_, self._apply_weeks).exec()

    def _apply_weeks(self, weeks: list[str]) -> None:
        model = self.model
        self._loading = True
        self._class_weeks = list(weeks)
        self._custom_weeks = True
        if weeks:
            self.weeks.set_value(len(weeks))
        self._show_days(list(model.class_days))
        if model.hours_per_week > 0:
            self.weekly.set_value(model.hours_per_week)
        self._loading = False
        self._refresh_calendar_note()
        self._refresh_calc()
        self._edited()

    def _refresh_calendar_note(self) -> None:
        model = self.model
        title = region_holiday_title(model.region)
        extra = active_holiday_extra(model)
        if extra:
            scope = f"праздники России и {len(extra)} дополнительных дней региона от модели"
        elif title:
            scope = f"праздники России и {title}"
        else:
            scope = "праздники России. Дополнительные дни региона запрашиваются в «Неделях занятий»"
        if self._custom_weeks and self._class_weeks:
            text = f"Отмечено недель: {len(self._class_weeks)}. Праздничный день переносит занятие. Учитываются {scope}."
        else:
            text = f"Недели пока не выбраны: возьмутся первые учебные недели графика. Учитываются {scope}."
        self.calendar_note.setText(text)

    # ---------- возрастные промежутки ----------

    def _set_span_note(self, text: str) -> None:
        self.span_note.setText(text)
        self.span_note.setVisible(bool(text))

    def _toggle_spans(self) -> None:
        on = self.differentiate.isChecked()
        self.spans_box.setVisible(on)
        if on and not self._span_rows:
            self._fill_suggested()

    def _show_spans(self, spans: list[dict]) -> None:
        for row, _start, _end in self._span_rows:
            row.setParent(None)
            row.deleteLater()
        self._span_rows.clear()
        for span in spans:
            self._add_span_row(int(span.get("from", -1)), int(span.get("to", -1)))
        self._set_span_note("")

    def _add_span_row(self, start: int, end: int) -> None:
        row = QWidget()
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(8)
        line.addWidget(label("от", "muted"))
        start_edit = IntEdit(2, 64)
        start_edit.set_value(start)
        line.addWidget(start_edit)
        line.addWidget(label("до", "muted"))
        end_edit = IntEdit(2, 64)
        end_edit.set_value(end)
        line.addWidget(end_edit)
        line.addWidget(label("лет", "muted"))
        remove = Button("", "icon", Glyph.DELETE, tip="Убрать промежуток")
        remove.clicked.connect(lambda _c=False, current=row: self._remove_span(current))
        line.addWidget(remove)
        line.addStretch(1)
        start_edit.textEdited.connect(self._edited)
        end_edit.textEdited.connect(self._edited)
        self.span_rows.addWidget(row)
        self._span_rows.append((row, start_edit, end_edit))

    def _add_empty_span(self) -> None:
        collected = self._collect_spans()
        age_to = self.age_to.value()
        start = collected[-1]["to"] + 1 if collected else self.age_from.value()
        end = start if age_to < start else min(start + 2, age_to)
        if start < 0:
            start, end = 0, 0
        self._add_span_row(start, end)
        self._edited()

    def _remove_span(self, row: QWidget) -> None:
        self._span_rows = [item for item in self._span_rows if item[0] is not row]
        row.setParent(None)
        row.deleteLater()
        self._edited()

    def _fill_suggested(self) -> None:
        spans = suggest_age_spans(self.age_from.value(), self.age_to.value())
        if not spans:
            self._set_span_note("Сначала укажите возраст программы целыми годами от 5 до 18.")
            return
        self._show_spans(spans)
        self._set_span_note("Это черновик по возрасту программы. Поправьте годы, если промежутки другие.")
        self._edited()

    def _collect_spans(self) -> list[dict[str, int]]:
        spans: list[dict[str, int]] = []
        for _row, start_edit, end_edit in self._span_rows:
            start, end = start_edit.value(), end_edit.value()
            if start < 0 and end < 0:
                continue
            spans.append({"from": start, "to": end})
        return spans

    # ---------- ориентир ----------

    def _refresh_calc(self) -> None:
        weekly = self.weekly.value()
        years = int(self.years.value())
        total = self.total.value()
        if weekly > 0 and years > 0 and total > 0:
            estimate = weekly * 36 * years
            self.calc_hint.show_message(
                "info",
                f"Ориентир учебного года: {weekly} ч/нед. × 36 недель × {years} = около {estimate} ч. "
                f"В программе указано {total} ч. Расхождение допустимо: в документ пойдёт именно {total} ч.",
            )
        else:
            self.calc_hint.show_message(
                "info", "Укажите объём, часы в неделю и срок — здесь появится ориентир на учебный год."
            )
