# -*- coding: utf-8 -*-
"""Неделя занятий столбиками по дням. Выбранные дни подсвечены, праздник переносит занятие."""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import messagebox

import customtkinter as ctk

from core.generator import GenerationError, generate_holidays
from core.holidays import holiday_map, holiday_query_key, region_holiday_title, week_label
from core.planning import (
    active_holiday_extra,
    class_placements,
    effective_class_days,
    period_bounds,
    period_mondays,
    suggest_class_weeks,
)
from gui.theme import DANGER, FONT, FONT_S, LINE, MUTED, NAVY, OK
from gui.widgets import primary_button, secondary_button, set_checkbox

_MONTHS = (
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
)
_DOW = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
_LESSON_COLORS = ("#1B3A6F", "#0E7C74", "#3D5A80", "#1B6CA8", "#0B655E", "#2457A6")
_STARTS = [f"{hour:02d}:{minute:02d}" for hour in range(8, 20) for minute in (0, 30)]
_FIRST_HOUR = 8
_HOUR_PX = 48
_HEADER_PX = 52


class CalendarDialog(ctk.CTkToplevel):
    def __init__(self, app, on_apply):
        super().__init__(app)
        self.app = app
        self.on_apply = on_apply
        self.title("Недели занятий")
        self.resizable(True, True)
        self.minsize(880, 560)
        self.configure(fg_color="white")
        self.geometry("1120x760")
        self.transient(app)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._result = None
        self._error = None
        self._waiting = False
        self._mute = False
        self._canvas_width = 0
        self._header_bottom = _HEADER_PX
        self._time_w = 56
        self._day_w = 80
        model = app.model
        self.mondays = period_mondays(model.year, model.calendar_mode, model.years)
        chosen = set(model.class_weeks)
        if not chosen:
            chosen = set(
                suggest_class_weeks(
                    model.year,
                    model.calendar_mode,
                    model.study_weeks,
                    model.region,
                    model.years,
                    active_holiday_extra(model),
                )
            )
        valid = {day.isoformat() for day in self.mondays}
        self.selected = {day for day in chosen if day in valid} or set(chosen)
        self.days = set(effective_class_days(model.class_days, model.lessons_per_week))
        self._placed: dict[date, str] = {}
        self.monday = self._initial_monday()

        ctk.CTkLabel(
            self,
            text="Отмеченные дни подсвечены. Нажмите дату, чтобы включить неделю. Праздник переносит занятие на следующий свободный день.",
            font=FONT,
            text_color=NAVY,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 0))
        self.scope = ctk.CTkLabel(
            self,
            text="",
            font=FONT_S,
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=1000,
        )
        self.scope.grid(row=1, column=0, sticky="ew", padx=16, pady=(2, 0))
        self.status = ctk.CTkLabel(self, text="", font=FONT_S, text_color=NAVY, anchor="w", justify="left", wraplength=1000)
        self.status.grid(row=2, column=0, sticky="ew", padx=16)

        body = ctk.CTkFrame(self, fg_color="white")
        body.grid(row=3, column=0, sticky="nsew", padx=12, pady=(4, 4))
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(1, weight=1)

        tools = ctk.CTkFrame(body, fg_color="white")
        tools.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        secondary_button(tools, "Сегодня", self._today).pack(side="left", padx=(0, 6))
        secondary_button(tools, "‹", self._prev).pack(side="left")
        secondary_button(tools, "›", self._next).pack(side="left", padx=(4, 10))
        self.range_label = ctk.CTkLabel(tools, text="", font=FONT, text_color=NAVY)
        self.range_label.pack(side="left", padx=(4, 16))
        self.week_on = ctk.CTkCheckBox(
            tools,
            text="Эта неделя учебная",
            font=FONT,
            text_color="#1A1A1A",
            fg_color=NAVY,
            hover_color="#0B655E",
            border_color=LINE,
            checkmark_color="white",
            command=self._toggle_from_box,
        )
        self.week_on.pack(side="left", padx=(0, 16))
        ctk.CTkLabel(tools, text="Начало", font=FONT_S, text_color=MUTED).pack(side="left", padx=(0, 6))
        self.start_combo = ctk.CTkComboBox(
            tools,
            values=_STARTS,
            width=96,
            height=32,
            font=FONT,
            dropdown_font=FONT,
            state="readonly",
            border_color=LINE,
            fg_color="white",
            button_color=NAVY,
            button_hover_color="#0B655E",
            text_color="#1A1A1A",
            command=self._start_changed,
        )
        self.start_combo.pack(side="left")
        self.start_combo.set(model.lesson_start if model.lesson_start in _STARTS else "15:00")

        side = ctk.CTkFrame(body, fg_color="white", width=236)
        side.grid(row=1, column=0, sticky="ns", padx=(0, 8))
        side.grid_propagate(False)
        ctk.CTkLabel(side, text="Дни занятий", font=FONT, text_color=NAVY, anchor="w").pack(anchor="w")
        self.day_boxes: list[ctk.CTkCheckBox] = []
        day_line = ctk.CTkFrame(side, fg_color="white")
        day_line.pack(anchor="w", pady=(2, 8))
        for index, name in enumerate(_DOW):
            if index == 4:
                day_line = ctk.CTkFrame(side, fg_color="white")
                day_line.pack(anchor="w", pady=(0, 8))
            box = ctk.CTkCheckBox(
                day_line,
                text=name,
                width=52,
                font=FONT_S,
                text_color="#1A1A1A",
                fg_color=NAVY,
                hover_color="#0B655E",
                border_color=LINE,
                checkmark_color="white",
                command=self._day_toggled,
            )
            box.pack(side="left", padx=(0, 2))
            self.day_boxes.append(box)
        self._mute = True
        for index, box in enumerate(self.day_boxes):
            set_checkbox(box, index in self.days)
        self._mute = False
        self.mini_title = ctk.CTkLabel(side, text="", font=FONT, text_color=NAVY)
        self.mini_title.pack(anchor="w", pady=(0, 4))
        dow = ctk.CTkFrame(side, fg_color="white")
        dow.pack(fill="x")
        for name in _DOW:
            ctk.CTkLabel(dow, text=name, width=30, font=("Segoe UI", 11), text_color=MUTED).pack(side="left")
        self.mini_days = ctk.CTkFrame(side, fg_color="white")
        self.mini_days.pack(fill="x", pady=(2, 8))
        ctk.CTkLabel(
            side,
            text="Бирюзовый столбец — день занятий. Блок «Перенос» стоит вместо праздника. Полоска сверху — сам праздник.",
            font=("Segoe UI", 12),
            text_color=MUTED,
            justify="left",
            wraplength=220,
            anchor="w",
        ).pack(anchor="w", pady=(8, 0))

        grid = ctk.CTkFrame(body, fg_color="white")
        grid.grid(row=1, column=1, sticky="nsew")
        grid.grid_rowconfigure(0, weight=1)
        grid.grid_columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(grid, bg="white", highlightthickness=0, bd=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scroll = tk.Scrollbar(grid, orient="vertical", command=self.canvas.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<MouseWheel>", self._wheel)

        actions = ctk.CTkFrame(self, fg_color="white")
        actions.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.ask_button = secondary_button(actions, "Уточнить праздники", self._ask)
        self.ask_button.pack(side="left", padx=(0, 8))
        secondary_button(actions, "Отметить учебные", self._suggest).pack(side="left", padx=(0, 8))
        secondary_button(actions, "Снять все", self._clear).pack(side="left")
        primary_button(actions, "Готово", self._apply).pack(side="right")
        self.scope.configure(text=self._scope_text())
        self.after(30, self._draw)
        self.grab_set()

    def _scope_text(self) -> str:
        model = self.app.model
        title = region_holiday_title(model.region)
        extra = active_holiday_extra(model)
        if extra:
            return "Праздники России уже стоят в сетке. Дополнительные дни региона получены у модели."
        if extra is not None:
            return "Праздники России уже стоят в сетке. Модель не назвала других праздников этого региона."
        if title:
            return f"В сетке праздники России и {title}."
        return "В сетке праздники России. «Уточнить праздники» спросит у модели дни этого региона."

    def _initial_monday(self) -> date:
        today = date.today()
        current = today - timedelta(days=today.weekday())
        if current in self.mondays:
            return current
        for item in sorted(self.selected):
            try:
                found = date.fromisoformat(item)
            except ValueError:
                continue
            if found in self.mondays:
                return found
        return self.mondays[0] if self.mondays else current

    def _extra(self):
        return active_holiday_extra(self.app.model)

    def _holiday(self, day: date) -> str:
        model = self.app.model
        return holiday_map(day.year, model.region, self._extra()).get(day, "")

    def _clock(self) -> tuple[int, int]:
        text = self.start_combo.get().strip()
        parts = text.split(":")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            hour, minute = int(parts[0]), int(parts[1])
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return hour, minute
        return 15, 0

    def _duration(self) -> int:
        model = self.app.model
        lessons = max(1, model.lesson_hours or 1)
        minutes = model.academic_minutes if model.academic_minutes > 0 else 45
        pause = model.break_minutes if model.break_minutes > 0 else 0
        return lessons * minutes + max(0, lessons - 1) * pause

    def _on_resize(self, event) -> None:
        if event.width < 200 or abs(event.width - self._canvas_width) < 8:
            return
        self._canvas_width = event.width
        self._draw()

    def _wheel(self, event) -> None:
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _prev(self) -> None:
        self._shift(-1)

    def _next(self) -> None:
        self._shift(1)

    def _today(self) -> None:
        self.monday = self._initial_monday()
        today = date.today()
        current = today - timedelta(days=today.weekday())
        if current in self.mondays:
            self.monday = current
        self._draw()

    def _shift(self, step: int) -> None:
        if not self.mondays:
            return
        try:
            index = self.mondays.index(self.monday)
        except ValueError:
            index = 0
        index = max(0, min(len(self.mondays) - 1, index + step))
        self.monday = self.mondays[index]
        self._draw()

    def _jump(self, day: date) -> None:
        monday = day - timedelta(days=day.weekday())
        if monday in self.mondays:
            self.monday = monday
            self._draw()

    def _toggle_from_box(self) -> None:
        if self._mute:
            return
        key = self.monday.isoformat()
        if self.week_on.get():
            self.selected.add(key)
        else:
            self.selected.discard(key)
        self._draw()

    def _toggle_week(self) -> None:
        key = self.monday.isoformat()
        if key in self.selected:
            self.selected.discard(key)
        else:
            self.selected.add(key)
        self._draw()

    def _start_changed(self, _value: str) -> None:
        self.app.model.lesson_start = self.start_combo.get()
        self._draw()

    def _day_toggled(self) -> None:
        if self._mute:
            return
        self.days = {index for index, box in enumerate(self.day_boxes) if box.get()}
        self._draw()

    def _sync_box(self) -> None:
        self._mute = True
        set_checkbox(self.week_on, self.monday.isoformat() in self.selected)
        self._mute = False

    def _paint_mini(self) -> None:
        for child in self.mini_days.winfo_children():
            child.destroy()
        shown = self.monday
        self.mini_title.configure(text=f"{_MONTHS[shown.month - 1].capitalize()} {shown.year}")
        first = shown.replace(day=1)
        cursor = first - timedelta(days=first.weekday())
        week_days = {self.monday + timedelta(days=offset) for offset in range(7)}
        for _week in range(6):
            row = ctk.CTkFrame(self.mini_days, fg_color="white")
            row.pack(fill="x")
            for _col in range(7):
                current = cursor
                holiday = bool(self._holiday(current))
                in_month = current.month == shown.month
                in_week = current in week_days
                kind = self._placed.get(current, "")
                if kind == "plan" and in_month:
                    fg, text_color = NAVY, "white"
                elif kind == "shift" and in_month:
                    fg, text_color = "#0E7C74", "white"
                elif in_week and current.weekday() in self.days and in_month and not holiday:
                    fg, text_color = "#D7F0EC", NAVY
                elif in_week and in_month:
                    fg, text_color = "#E8EEF5", NAVY
                else:
                    fg, text_color = "white", MUTED if in_month else "#C5D0DC"
                if holiday and in_month and not kind:
                    text_color = "#9A6700"
                button = ctk.CTkButton(
                    row,
                    text=str(current.day),
                    width=30,
                    height=26,
                    font=("Segoe UI", 12),
                    fg_color=fg,
                    hover_color="#D5DEEA",
                    text_color=text_color,
                    corner_radius=6,
                    command=lambda day=current: self._jump(day),
                )
                if current - timedelta(days=current.weekday()) not in self.mondays:
                    button.configure(state="disabled")
                button.pack(side="left", padx=0, pady=1)
                cursor += timedelta(days=1)

    def _draw(self) -> None:
        if not self.winfo_exists():
            return
        self.range_label.configure(text=week_label(self.monday))
        self._sync_box()
        self._placed = class_placements(
            self.mondays,
            self.days,
            lambda day: bool(self._holiday(day)),
            self.selected,
        )
        self._paint_mini()
        canvas = self.canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), self._canvas_width, 760)
        time_w = 56
        day_w = (width - time_w) / 7
        self._time_w = time_w
        self._day_w = day_w
        teaching = self.monday.isoformat() in self.selected
        start_h, start_m = self._clock()
        start_min = start_h * 60 + start_m
        duration = self._duration()
        end_min = start_min + duration
        last_hour = max(21, (end_min + 59) // 60)
        holidays = [self._holiday(self.monday + timedelta(days=offset)) for offset in range(7)]
        allday = 28 if any(holidays) else 0
        header_bottom = _HEADER_PX + allday
        self._header_bottom = header_bottom
        height = header_bottom + (last_hour - _FIRST_HOUR) * _HOUR_PX + 12
        canvas.configure(scrollregion=(0, 0, width, height))
        today = date.today()

        for offset in range(7):
            day = self.monday + timedelta(days=offset)
            x0 = time_w + offset * day_w
            x1 = x0 + day_w
            weekend = day.weekday() >= 5
            chosen = day.weekday() in self.days
            if day == today:
                column = "#E8F0FE"
            elif chosen and teaching:
                column = "#D7F0EC"
            elif chosen:
                column = "#F3FBFA"
            elif weekend:
                column = "#F7F8FA"
            else:
                column = "white"
            canvas.create_rectangle(x0, 0, x1, height, fill=column, outline="")
            canvas.create_text(x0 + day_w / 2, 14, text=_DOW[offset], fill=MUTED, font=("Segoe UI", 11))
            number = str(day.day)
            if day == today:
                canvas.create_oval(x0 + day_w / 2 - 12, 26, x0 + day_w / 2 + 12, 50, fill=NAVY, outline="")
                canvas.create_text(x0 + day_w / 2, 38, text=number, fill="white", font=("Segoe UI", 12, "bold"))
            else:
                canvas.create_text(x0 + day_w / 2, 38, text=number, fill="#1A1A1A", font=("Segoe UI", 13))
            if holidays[offset]:
                canvas.create_rectangle(x0 + 4, _HEADER_PX + 2, x1 - 4, header_bottom - 2, fill="#FDE7C7", outline="")
                canvas.create_text(
                    x0 + 8,
                    _HEADER_PX + 14,
                    text=holidays[offset],
                    anchor="w",
                    fill="#7A4E00",
                    font=("Segoe UI", 10),
                    width=day_w - 16,
                )

        for hour in range(_FIRST_HOUR, last_hour + 1):
            y = header_bottom + (hour - _FIRST_HOUR) * _HOUR_PX
            canvas.create_line(time_w, y, width, y, fill="#E6EAF0")
            canvas.create_text(time_w - 8, y, text=f"{hour:02d}:00", anchor="e", fill=MUTED, font=("Segoe UI", 10))

        shown = [self.monday + timedelta(days=offset) for offset in range(7)]
        blocks = [(day, self._placed[day]) for day in shown if day in self._placed]
        if blocks:
            for day, kind in blocks:
                offset = (day - self.monday).days
                y0 = header_bottom + (start_min - _FIRST_HOUR * 60) / 60 * _HOUR_PX
                y1 = header_bottom + (end_min - _FIRST_HOUR * 60) / 60 * _HOUR_PX
                x0 = time_w + offset * day_w + 4
                x1 = time_w + (offset + 1) * day_w - 4
                color = "#B86E00" if kind == "shift" else _LESSON_COLORS[day.weekday() % len(_LESSON_COLORS)]
                canvas.create_rectangle(x0, y0, x1, max(y1, y0 + 22), fill=color, outline="")
                title = "Перенос" if kind == "shift" else "Занятие"
                label = f"{start_h:02d}:{start_m:02d}–{end_min // 60:02d}:{end_min % 60:02d}"
                canvas.create_text(x0 + 6, y0 + 8, text=title, anchor="nw", fill="white", font=("Segoe UI", 11, "bold"))
                if y1 - y0 > 32:
                    canvas.create_text(x0 + 6, y0 + 26, text=label, anchor="nw", fill="white", font=("Segoe UI", 10))
        elif not teaching:
            canvas.create_text(
                time_w + 16,
                header_bottom + 24,
                text="Неделя не учебная. Нажмите дату или поставьте галочку, чтобы поставить сюда занятия.",
                anchor="nw",
                fill=MUTED,
                font=("Segoe UI", 12),
            )

        now = datetime.now()
        if self.monday <= now.date() <= self.monday + timedelta(days=6):
            minute = now.hour * 60 + now.minute
            if _FIRST_HOUR * 60 <= minute <= last_hour * 60:
                y = header_bottom + (minute - _FIRST_HOUR * 60) / 60 * _HOUR_PX
                canvas.create_line(time_w, y, width, y, fill="#D93025", width=2)

    def _on_click(self, event) -> None:
        y = self.canvas.canvasy(event.y)
        x = self.canvas.canvasx(event.x)
        if y <= self._header_bottom and x >= self._time_w:
            self._toggle_week()

    def _suggest(self) -> None:
        model = self.app.model
        self.selected = set(
            suggest_class_weeks(
                model.year,
                model.calendar_mode,
                model.study_weeks,
                model.region,
                model.years,
                self._extra(),
            )
        )
        self._draw()

    def _clear(self) -> None:
        self.selected.clear()
        self._draw()

    def _ask(self) -> None:
        if self._waiting:
            return
        model = self.app.model
        region = model.region.strip()
        if len(region) < 2:
            messagebox.showwarning("ДопПро", "Сначала укажите регион на шаге «Паспорт».", parent=self)
            return
        start, finish = period_bounds(model.year, model.calendar_mode, model.years)
        self._waiting = True
        self._result = None
        self._error = None
        self.ask_button.configure(state="disabled")
        self.status.configure(text=f"Спрашиваю праздники региона «{region}»…", text_color=NAVY)

        def work() -> None:
            try:
                self._result = generate_holidays(region, start.year, finish.year)
            except Exception as exc:
                self._error = exc

        threading.Thread(target=work, daemon=True).start()
        self.after(200, self._poll)

    def _poll(self) -> None:
        if not self.winfo_exists():
            return
        if self._result is None and self._error is None:
            self.after(200, self._poll)
            return
        self._waiting = False
        self.ask_button.configure(state="normal")
        if self._error is not None:
            text = str(self._error)
            if not isinstance(self._error, GenerationError):
                text = f"Не удалось получить праздники.\n\n{text}"
            self.status.configure(text=text, text_color=DANGER)
            self._error = None
            messagebox.showerror("ДопПро", text, parent=self)
            return
        ready = self._result or []
        self._result = None
        model = self.app.model
        start, finish = period_bounds(model.year, model.calendar_mode, model.years)
        model.holiday_days = ready
        model.holiday_key = holiday_query_key(model.region, start, finish)
        try:
            model.save_draft()
        except OSError:
            pass
        if ready:
            self.status.configure(
                text=f"Модель добавила {len(ready)} дополнительных дней. Общероссийские праздники оставлены как есть.",
                text_color=OK,
            )
        else:
            self.status.configure(
                text="Модель не назвала дополнительных праздников этого региона. В календаре остаются праздники России.",
                text_color=OK,
            )
        self._draw()

    def _apply(self) -> None:
        model = self.app.model
        old = model.lessons_per_week
        days = sorted(self.days)
        model.class_days = days
        model.lessons_per_week = len(days)
        lesson_hours = model.lesson_hours if model.lesson_hours in (1, 2, 3, 4) else 0
        if lesson_hours and days and model.hours_per_week == old * lesson_hours:
            model.hours_per_week = len(days) * lesson_hours
        model.lesson_start = self.start_combo.get()
        valid = {day.isoformat() for day in self.mondays}
        weeks = sorted(day for day in self.selected if day in valid)
        self.on_apply(weeks)
        try:
            self.app.model.save_draft()
        except OSError:
            pass
        self.destroy()
