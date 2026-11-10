# -*- coding: utf-8 -*-
"""Шаг 2. Кому и сколько: возраст, срок, часы, группа."""

from __future__ import annotations

import customtkinter as ctk

from core.data_model import CALENDAR_MODES, STUDY_FORMS, suggest_age_spans
from gui.theme import FONT, FONT_S, LINE, MUTED, NAVY
from gui.tooltip import tooltip
from gui.widgets import (
    LabeledCombo,
    LabeledEntry,
    bind_text_shortcuts,
    caption,
    card,
    checkbox,
    hint,
    parse_int,
    secondary_button,
    set_checkbox,
)


class StepLearners(ctk.CTkScrollableFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        caption(self, "Обучающиеся, срок и объём")
        hint(
            self,
            "Дифференциация идёт по вашим промежуткам внутри «возраст от — до», а не по готовым 11–13 и 14–17. "
            "Каждый промежуток попадёт в документ отдельной строкой.",
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

        self.differentiate = checkbox(body, "Дифференцировать задания по возрастным промежуткам")
        self.differentiate.grid(row=8, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.differentiate.configure(command=self._toggle_spans)
        tooltip(
            self.differentiate,
            "Промежутки задаёте сами. В таблицу и в текст попадут именно они, от младшего к старшему.",
        )

        self.spans_box = ctk.CTkFrame(body, fg_color="white")
        self.spans_box.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.spans_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self.spans_box,
            text="Промежутки внутри возраста программы, лет",
            font=FONT_S,
            text_color=NAVY,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self.span_rows_frame = ctk.CTkFrame(self.spans_box, fg_color="white")
        self.span_rows_frame.grid(row=1, column=0, sticky="ew", pady=(6, 4))
        actions = ctk.CTkFrame(self.spans_box, fg_color="white")
        actions.grid(row=2, column=0, sticky="w")
        add = secondary_button(actions, "Добавить промежуток", self._add_empty_span)
        add.pack(side="left", padx=(0, 8))
        split = secondary_button(actions, "Разбить по возрасту программы", self._fill_suggested)
        split.pack(side="left")
        tooltip(add, "Ещё одна строка «от» и «до». Промежутки не должны пересекаться.")
        tooltip(split, "Подставит черновик по полям «Возраст от» и «Возраст до». Потом цифры можно поправить.")
        self.span_note = ctk.CTkLabel(
            self.spans_box,
            text="",
            font=FONT_S,
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=820,
        )
        self.span_note.grid(row=3, column=0, sticky="w", pady=(6, 0))
        self._span_rows: list[tuple[ctk.CTkFrame, ctk.CTkEntry, ctk.CTkEntry]] = []

        self.no_prior = checkbox(body, "Без предварительной подготовки, свободный набор")
        self.no_prior.grid(row=10, column=0, columnspan=2, sticky="w", pady=(8, 0))
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
        spans = model.age_spans or suggest_age_spans(model.age_from, model.age_to)
        self._show_spans(spans)
        self._toggle_spans()
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
        model.age_spans = self._collect_spans()
        model.no_prior_training = bool(self.no_prior.get())

    def validate(self) -> list[str]:
        return self.app.model.errors_learners()

    def _toggle_spans(self) -> None:
        if bool(self.differentiate.get()):
            self.spans_box.grid()
            if not self._span_rows:
                self._fill_suggested()
        else:
            self.spans_box.grid_remove()

    def _show_spans(self, spans: list[dict]) -> None:
        for row, _start, _end in self._span_rows:
            row.destroy()
        self._span_rows.clear()
        for span in spans:
            self._add_span_row(str(span.get("from", "")), str(span.get("to", "")))
        self.span_note.configure(text="")

    def _add_span_row(self, start: str, end: str) -> None:
        row = ctk.CTkFrame(self.span_rows_frame, fg_color="white")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text="от", font=FONT_S, text_color=MUTED).pack(side="left", padx=(0, 6))
        start_entry = ctk.CTkEntry(row, width=72, height=34, font=FONT, border_color=LINE, fg_color="white")
        start_entry.pack(side="left")
        bind_text_shortcuts(start_entry)
        if start:
            start_entry.insert(0, start)
        ctk.CTkLabel(row, text="до", font=FONT_S, text_color=MUTED).pack(side="left", padx=(10, 6))
        end_entry = ctk.CTkEntry(row, width=72, height=34, font=FONT, border_color=LINE, fg_color="white")
        end_entry.pack(side="left")
        bind_text_shortcuts(end_entry)
        if end:
            end_entry.insert(0, end)
        remove = ctk.CTkButton(
            row,
            text="Убрать",
            width=84,
            height=34,
            font=FONT_S,
            fg_color="#E8EEF5",
            hover_color="#D5DEEA",
            text_color=NAVY,
            command=lambda current=row: self._remove_span(current),
        )
        remove.pack(side="left", padx=(12, 0))
        self._span_rows.append((row, start_entry, end_entry))

    def _add_empty_span(self) -> None:
        collected = self._collect_spans()
        age_to = parse_int(self.age_to.get())
        if collected:
            start = collected[-1]["to"] + 1
        else:
            start = parse_int(self.age_from.get())
        end = start if age_to < start else min(start + 2, age_to)
        if start < 0:
            start, end = 0, 0
        self._add_span_row("" if start <= 0 else str(start), "" if end <= 0 else str(end))

    def _remove_span(self, row: ctk.CTkFrame) -> None:
        self._span_rows = [item for item in self._span_rows if item[0] is not row]
        row.destroy()

    def _fill_suggested(self) -> None:
        start = parse_int(self.age_from.get())
        end = parse_int(self.age_to.get())
        spans = suggest_age_spans(start, end)
        if not spans:
            self.span_note.configure(text="Сначала укажите возраст программы целыми годами от 5 до 18.")
            return
        self._show_spans(spans)
        self.span_note.configure(text="Это черновик по возрасту программы. Поправьте годы, если промежутки другие.")

    def _collect_spans(self) -> list[dict[str, int]]:
        spans: list[dict[str, int]] = []
        for _row, start_entry, end_entry in self._span_rows:
            start = parse_int(start_entry.get())
            end = parse_int(end_entry.get())
            if start < 0 and end < 0:
                continue
            spans.append({"from": start, "to": end})
        return spans

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
