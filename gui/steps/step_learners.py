# -*- coding: utf-8 -*-
"""Шаг 2. Кому и сколько: возраст, срок, часы, группа."""

from __future__ import annotations

import customtkinter as ctk

from core.data_model import CALENDAR_MODES, STUDY_FORMS
from gui.theme import FONT_S, MUTED
from gui.tooltip import tooltip
from gui.widgets import LabeledCombo, LabeledEntry, caption, card, checkbox, hint, parse_int, set_checkbox


class StepLearners(ctk.CTkScrollableFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        caption(self, "Обучающиеся, срок и объём")
        hint(
            self,
            "Дифференциация делит содержание на две линии: 11–13 лет и 14–17 лет. "
            "В документ попадут только те границы, которые входят в указанный возраст.",
        )

        body = card(self)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        self.age_from = LabeledEntry(body, "Возраст от", required=True)
        self.age_from.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=(0, 10))
        self.age_to = LabeledEntry(body, "Возраст до", required=True)
        self.age_to.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))

        self.years = LabeledCombo(body, "Срок реализации, лет", ["1", "2", "3", "4", "5"], required=True)
        self.years.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(0, 10))
        self.lesson = LabeledCombo(body, "Длительность занятия, ак. ч.", ["1", "2", "3", "4"], required=True)
        self.lesson.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))

        self.per_week = LabeledCombo(body, "Занятий в неделю", ["1", "2", "3", "4", "5", "6"], required=True)
        self.per_week.grid(row=2, column=0, sticky="ew", padx=(0, 8), pady=(0, 10))
        self.weekly = LabeledEntry(body, "Часов в неделю", required=True)
        self.weekly.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))

        self.minutes = LabeledCombo(body, "Академический час, минут", ["30", "35", "40", "45"], required=True)
        self.minutes.grid(row=3, column=0, sticky="ew", padx=(0, 8), pady=(0, 10))
        self.break_minutes = LabeledCombo(body, "Перерыв, минут", ["0", "5", "10", "15"], required=True)
        self.break_minutes.grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))

        self.total = LabeledEntry(
            body,
            "Общий объём, часов",
            required=True,
            tip="С этим числом должны сойтись часы всех разделов на следующем шаге.",
        )
        self.total.grid(row=4, column=0, sticky="ew", padx=(0, 8), pady=(0, 10))
        self.weeks = LabeledEntry(body, "Учебных недель", required=True)
        self.weeks.grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))

        self.group_min = LabeledEntry(body, "Наполняемость от", required=True)
        self.group_min.grid(row=5, column=0, sticky="ew", padx=(0, 8), pady=(0, 10))
        self.group_max = LabeledEntry(body, "Наполняемость до", required=True)
        self.group_max.grid(row=5, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))

        self.study_form = LabeledCombo(body, "Форма обучения", STUDY_FORMS, required=True)
        self.study_form.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.calendar = LabeledCombo(body, "Календарный график", CALENDAR_MODES, required=True)
        self.calendar.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        self.differentiate = checkbox(body, "Дифференцировать задания для 11–13 и 14–17 лет")
        self.differentiate.grid(row=8, column=0, columnspan=2, sticky="w", pady=(4, 0))
        tooltip(self.differentiate, "В документ попадут только те возрастные линии, которые входят в указанный возраст.")
        self.no_prior = checkbox(body, "Без предварительной подготовки, свободный набор")
        self.no_prior.grid(row=9, column=0, columnspan=2, sticky="w", pady=(4, 0))
        tooltip(self.no_prior, "В адресате будет сказано, что до первого занятия отбора и подготовки нет.")

        self.calc_hint = ctk.CTkLabel(
            self,
            text="",
            font=FONT_S,
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=860,
        )
        self.calc_hint.pack(fill="x", padx=22, pady=(0, 8))
        hint(
            self,
            "Если измените общий объём часов, на следующем шаге нажмите «Распределить часы», "
            "чтобы сумма разделов совпала с программой. Летнюю смену выберите в календарном графике: "
            "в документе месяцы будут июнь–август.",
        )
        for widget in (self.total.entry, self.weekly.entry):
            widget.bind("<KeyRelease>", lambda _event: self._refresh_calc())
        self.years.combo.configure(command=lambda _value: self._refresh_calc())

    def on_show(self) -> None:
        model = self.app.model
        self.age_from.set(str(model.age_from) if model.age_from > 0 else "")
        self.age_to.set(str(model.age_to) if model.age_to > 0 else "")
        self.years.set(str(model.years) if model.years > 0 else "1")
        self.lesson.set(str(model.lesson_hours) if model.lesson_hours > 0 else "2")
        self.per_week.set(str(model.lessons_per_week) if model.lessons_per_week > 0 else "2")
        self.minutes.set(str(model.academic_minutes) if model.academic_minutes > 0 else "45")
        self.break_minutes.set(str(model.break_minutes))
        self.total.set(str(model.total_hours) if model.total_hours > 0 else "")
        self.weeks.set(str(model.study_weeks) if model.study_weeks > 0 else "36")
        self.weekly.set(str(model.hours_per_week) if model.hours_per_week > 0 else "")
        self.group_min.set(str(model.group_min) if model.group_min > 0 else "")
        self.group_max.set(str(model.group_max) if model.group_max > 0 else "")
        self.study_form.set(model.study_form)
        self.calendar.set(model.calendar_mode)
        set_checkbox(self.differentiate, model.differentiate)
        set_checkbox(self.no_prior, model.no_prior_training)
        self._refresh_calc()

    def save(self) -> None:
        model = self.app.model
        model.age_from = parse_int(self.age_from.get())
        model.age_to = parse_int(self.age_to.get())
        model.years = parse_int(self.years.get())
        model.lesson_hours = parse_int(self.lesson.get())
        model.lessons_per_week = parse_int(self.per_week.get())
        model.academic_minutes = parse_int(self.minutes.get())
        model.break_minutes = parse_int(self.break_minutes.get())
        model.total_hours = parse_int(self.total.get())
        model.study_weeks = parse_int(self.weeks.get())
        model.hours_per_week = parse_int(self.weekly.get())
        model.group_min = parse_int(self.group_min.get())
        model.group_max = parse_int(self.group_max.get())
        model.study_form = self.study_form.get()
        model.calendar_mode = self.calendar.get()
        model.differentiate = bool(self.differentiate.get())
        model.no_prior_training = bool(self.no_prior.get())

    def validate(self) -> list[str]:
        return self.app.model.errors_learners()

    def _refresh_calc(self) -> None:
        weekly = parse_int(self.weekly.get())
        years = parse_int(self.years.get())
        total = parse_int(self.total.get())
        if weekly > 0 and years > 0 and total > 0:
            estimate = weekly * 36 * years
            self.calc_hint.configure(
                text=(
                    f"Ориентир учебного года: {weekly} ч/нед. × 36 недель × {years} = около {estimate} ч. "
                    f"В программе указано {total} ч. Расхождение допустимо: в документ пойдёт именно {total} ч."
                )
            )
        else:
            self.calc_hint.configure(text="Укажите объём, часы в неделю и срок — здесь появится ориентир на учебный год.")
