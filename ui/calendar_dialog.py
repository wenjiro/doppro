# -*- coding: utf-8 -*-
"""Неделя занятий столбиками по дням. Выбранные дни подсвечены, праздник переносит занятие."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

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
from ui.theme import Glyph, theme
from ui.widgets import Banner, Button, Combo, alert, checkbox, label, run_async

_MONTHS = (
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
)
_DOW = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
_STARTS = [f"{hour:02d}:{minute:02d}" for hour in range(8, 20) for minute in (0, 30)]
_FIRST_HOUR = 8
_HOUR_PX = 48
_HEADER_PX = 56
_TIME_W = 58


def _font(px: int, bold: bool = False) -> QFont:
    font = QFont("Segoe UI")
    font.setPixelSize(px)
    font.setBold(bold)
    return font


class WeekGrid(QWidget):
    """Сетка недели: столбец на день, блок занятия по времени начала."""

    week_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.monday = date.today()
        self.days: set[int] = set()
        self.placed: dict[date, str] = {}
        self.holidays: list[str] = [""] * 7
        self.teaching = False
        self.start_min = 15 * 60
        self.duration = 90
        self._header_bottom = _HEADER_PX
        self._last_hour = 21
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

    def set_state(self, monday, days, placed, holidays, teaching, start_min, duration) -> None:
        self.monday, self.days, self.placed = monday, set(days), dict(placed)
        self.holidays, self.teaching = list(holidays), teaching
        self.start_min, self.duration = start_min, duration
        end_min = start_min + duration
        self._last_hour = max(21, (end_min + 59) // 60)
        self._header_bottom = _HEADER_PX + (30 if any(holidays) else 0)
        self.setMinimumHeight(self._header_bottom + (self._last_hour - _FIRST_HOUR) * _HOUR_PX + 14)
        self.update()

    def mousePressEvent(self, event) -> None:
        point = event.position()
        if point.y() <= self._header_bottom and point.x() >= _TIME_W:
            self.week_clicked.emit()

    def paintEvent(self, _event) -> None:
        p = theme.p
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        width, height = self.width(), self.height()
        painter.fillRect(self.rect(), QColor(p["surface"]))
        day_w = (width - _TIME_W) / 7
        header_bottom = self._header_bottom
        today = date.today()
        end_min = self.start_min + self.duration

        for offset in range(7):
            day = self.monday + timedelta(days=offset)
            x0 = _TIME_W + offset * day_w
            chosen = day.weekday() in self.days
            if day == today:
                column = p["today"]
            elif chosen and self.teaching:
                column = p["class_week"]
            elif chosen:
                column = p["class_day"]
            elif day.weekday() >= 5:
                column = p["weekend"]
            else:
                column = p["surface"]
            painter.fillRect(QRectF(x0, 0, day_w, height), QColor(column))
            painter.setPen(QColor(p["muted"]))
            painter.setFont(_font(12))
            painter.drawText(QRectF(x0, 6, day_w, 18), Qt.AlignCenter, _DOW[offset])
            circle = QRectF(x0 + day_w / 2 - 13, 26, 26, 26)
            if day == today:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(p["primary"]))
                painter.drawEllipse(circle)
                painter.setPen(QColor("#FFFFFF"))
                painter.setFont(_font(13, True))
            else:
                painter.setPen(QColor(p["text"]))
                painter.setFont(_font(14))
            painter.drawText(circle, Qt.AlignCenter, str(day.day))
            if self.holidays[offset]:
                box = QRectF(x0 + 4, _HEADER_PX + 2, day_w - 8, header_bottom - _HEADER_PX - 4)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(p["holiday_bg"]))
                painter.drawRoundedRect(box, 5, 5)
                painter.setPen(QColor(p["holiday_text"]))
                painter.setFont(_font(11))
                text = painter.fontMetrics().elidedText(self.holidays[offset], Qt.ElideRight, int(box.width() - 12))
                painter.drawText(box.adjusted(6, 0, -6, 0), Qt.AlignVCenter | Qt.AlignLeft, text)

        painter.setFont(_font(11))
        for hour in range(_FIRST_HOUR, self._last_hour + 1):
            y = header_bottom + (hour - _FIRST_HOUR) * _HOUR_PX
            painter.setPen(QPen(QColor(p["grid"]), 1))
            painter.drawLine(_TIME_W, int(y), width, int(y))
            painter.setPen(QColor(p["muted"]))
            painter.drawText(QRectF(0, y - 9, _TIME_W - 8, 18), Qt.AlignRight | Qt.AlignVCenter, f"{hour:02d}:00")

        shown = [self.monday + timedelta(days=offset) for offset in range(7)]
        blocks = [(day, self.placed[day]) for day in shown if day in self.placed]
        colors = theme.lesson_colors()
        if blocks:
            for day, kind in blocks:
                offset = (day - self.monday).days
                y0 = header_bottom + (self.start_min - _FIRST_HOUR * 60) / 60 * _HOUR_PX
                y1 = header_bottom + (end_min - _FIRST_HOUR * 60) / 60 * _HOUR_PX
                box = QRectF(_TIME_W + offset * day_w + 4, y0, day_w - 8, max(y1 - y0, 24))
                color = p["shift"] if kind == "shift" else colors[day.weekday() % len(colors)]
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(color))
                painter.drawRoundedRect(box, 7, 7)
                painter.setPen(QColor("#FFFFFF"))
                painter.setFont(_font(12, True))
                painter.drawText(box.adjusted(8, 6, -4, 0), Qt.AlignTop | Qt.AlignLeft,
                                 "Перенос" if kind == "shift" else "Занятие")
                if box.height() > 40:
                    painter.setFont(_font(11))
                    painter.drawText(
                        box.adjusted(8, 24, -4, 0), Qt.AlignTop | Qt.AlignLeft,
                        f"{self.start_min // 60:02d}:{self.start_min % 60:02d}–{end_min // 60:02d}:{end_min % 60:02d}",
                    )
        elif not self.teaching:
            painter.setPen(QColor(p["muted"]))
            painter.setFont(_font(13))
            painter.drawText(
                QRectF(_TIME_W + 16, header_bottom + 18, width - _TIME_W - 32, 44), Qt.AlignLeft | Qt.TextWordWrap,
                "Неделя не учебная. Нажмите на строку с датами или поставьте галочку, чтобы поставить сюда занятия.",
            )

        now = datetime.now()
        if self.monday <= now.date() <= self.monday + timedelta(days=6):
            minute = now.hour * 60 + now.minute
            if _FIRST_HOUR * 60 <= minute <= self._last_hour * 60:
                y = header_bottom + (minute - _FIRST_HOUR * 60) / 60 * _HOUR_PX
                painter.setPen(QPen(QColor("#D93025"), 2))
                painter.drawLine(_TIME_W, int(y), width, int(y))
        painter.end()


class MiniMonth(QWidget):
    """Маленький месяц слева. Нажатие на день открывает его неделю."""

    day_clicked = Signal(object)
    _CELL = 32

    def __init__(self):
        super().__init__()
        self.shown = date.today()
        self.monday = date.today()
        self.days: set[int] = set()
        self.placed: dict[date, str] = {}
        self.mondays: set[date] = set()
        self.is_holiday = lambda _day: False
        self.setFixedSize(self._CELL * 7, 22 + self._CELL * 6)
        self.setCursor(Qt.PointingHandCursor)

    def _first(self) -> date:
        first = self.shown.replace(day=1)
        return first - timedelta(days=first.weekday())

    def mousePressEvent(self, event) -> None:
        point = event.position()
        column, row = int(point.x() // self._CELL), int((point.y() - 22) // self._CELL)
        if point.y() < 22 or not (0 <= column < 7 and 0 <= row < 6):
            return
        self.day_clicked.emit(self._first() + timedelta(days=row * 7 + column))

    def paintEvent(self, _event) -> None:
        p = theme.p
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(_font(11))
        painter.setPen(QColor(p["muted"]))
        for column, name in enumerate(_DOW):
            painter.drawText(QRectF(column * self._CELL, 0, self._CELL, 20), Qt.AlignCenter, name)
        cursor = self._first()
        week_days = {self.monday + timedelta(days=offset) for offset in range(7)}
        painter.setFont(_font(12))
        for row in range(6):
            for column in range(7):
                current = cursor
                cursor += timedelta(days=1)
                box = QRectF(column * self._CELL + 2, 22 + row * self._CELL + 2, self._CELL - 4, self._CELL - 4)
                in_month = current.month == self.shown.month
                holiday = self.is_holiday(current)
                kind = self.placed.get(current, "")
                fill, text = None, p["muted"] if in_month else p["line_strong"]
                if kind == "plan" and in_month:
                    fill, text = p["primary"], "#FFFFFF"
                elif kind == "shift" and in_month:
                    fill, text = p["shift"], "#FFFFFF"
                elif current in week_days and in_month:
                    fill, text = (p["class_week"] if current.weekday() in self.days and not holiday else p["soft"]), p["text"]
                if holiday and in_month and not kind:
                    text = p["warn"]
                if current - timedelta(days=current.weekday()) not in self.mondays:
                    text = p["line_strong"]
                    fill = None
                if fill:
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QColor(fill))
                    painter.drawRoundedRect(box, 7, 7)
                painter.setPen(QColor(text))
                painter.drawText(box, Qt.AlignCenter, str(current.day))
        painter.end()


class CalendarDialog(QDialog):
    def __init__(self, window, on_apply):
        super().__init__(window)
        self.window_ = window
        self.model = window.session.model
        self.on_apply = on_apply
        self.setWindowTitle("Недели занятий")
        self.setModal(True)
        self.setMinimumSize(940, 600)
        self.resize(1160, 790)
        self._waiting = False
        self._mute = False
        model = self.model
        self.mondays = period_mondays(model.year, model.calendar_mode, model.years)
        chosen = set(model.class_weeks)
        if not chosen:
            chosen = set(suggest_class_weeks(
                model.year, model.calendar_mode, model.study_weeks, model.region, model.years,
                active_holiday_extra(model),
            ))
        valid = {day.isoformat() for day in self.mondays}
        self.selected = {day for day in chosen if day in valid} or set(chosen)
        self.days = set(effective_class_days(model.class_days, model.lessons_per_week))
        self._placed: dict[date, str] = {}
        self.monday = self._initial_monday()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QFrame()
        surface.setObjectName("dialogSurface")
        outer.addWidget(surface)
        box = QVBoxLayout(surface)
        box.setContentsMargins(22, 18, 22, 16)
        box.setSpacing(10)

        box.addWidget(label("Недели занятий", "h1"))
        box.addWidget(label(
            "Отмеченные дни подсвечены. Нажмите на строку с датами, чтобы включить или выключить неделю. "
            "Праздник переносит занятие на следующий свободный день.", "muted", wrap=True))
        self.scope = label("", "small", wrap=True)
        box.addWidget(self.scope)
        self.status = Banner("info")
        self.status.hide()
        box.addWidget(self.status)

        tools = QHBoxLayout()
        tools.setSpacing(8)
        tools.addWidget(Button("Сегодня", on=self._today))
        tools.addWidget(Button("", glyph=Glyph.LEFT, on=lambda: self._shift(-1), tip="Предыдущая неделя"))
        tools.addWidget(Button("", glyph=Glyph.RIGHT, on=lambda: self._shift(1), tip="Следующая неделя"))
        self.range_label = label("", "h2")
        tools.addSpacing(6)
        tools.addWidget(self.range_label)
        tools.addStretch(1)
        self.week_on = checkbox("Эта неделя учебная")
        self.week_on.clicked.connect(self._toggle_from_box)
        tools.addWidget(self.week_on)
        tools.addSpacing(14)
        tools.addWidget(label("Начало", "muted"))
        self.start_combo = Combo(_STARTS)
        self.start_combo.setFixedWidth(116)
        self.start_combo.set_value(model.lesson_start if model.lesson_start in _STARTS else "15:00")
        self.start_combo.activated.connect(self._start_changed)
        tools.addWidget(self.start_combo)
        box.addLayout(tools)

        body = QHBoxLayout()
        body.setSpacing(16)
        side = QVBoxLayout()
        side.setSpacing(8)
        side.addWidget(label("Дни занятий", "label"))
        self.day_buttons: list[Button] = []
        for chunk in (range(0, 4), range(4, 7)):
            line = QHBoxLayout()
            line.setSpacing(6)
            for index in chunk:
                chip = Button(_DOW[index], "chip", on=self._day_toggled)
                chip.setCheckable(True)
                chip.setChecked(index in self.days)
                self.day_buttons.append(chip)
                line.addWidget(chip)
            line.addStretch(1)
            side.addLayout(line)
        side.addSpacing(6)
        self.mini_title = label("", "h3")
        side.addWidget(self.mini_title)
        self.mini = MiniMonth()
        self.mini.mondays = set(self.mondays)
        self.mini.is_holiday = lambda day: bool(self._holiday(day))
        self.mini.day_clicked.connect(self._jump)
        side.addWidget(self.mini)
        self.counter = label("", "label")
        side.addWidget(self.counter)
        side.addWidget(label(
            "Подсвеченный столбец — день занятий. Блок «Перенос» стоит вместо праздника. "
            "Плашка под датой — сам праздник.", "small", wrap=True))
        side.addStretch(1)
        side_holder = QWidget()
        side_holder.setLayout(side)
        side_holder.setFixedWidth(232)
        side.setContentsMargins(0, 0, 0, 0)
        body.addWidget(side_holder)

        self.grid = WeekGrid()
        self.grid.week_clicked.connect(self._toggle_week)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(self.grid)
        scroll.setStyleSheet(f"QScrollArea {{ border: 1px solid {theme.p['line']}; border-radius: 10px; }}")
        body.addWidget(scroll, 1)
        box.addLayout(body, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.ask_button = Button("Уточнить праздники", glyph=Glyph.SPARK, on=self._ask,
                                 tip="Спросит у нейросети дополнительные праздничные дни вашего региона. Нужен ключ в «Настройках».")
        actions.addWidget(self.ask_button)
        actions.addWidget(Button("Отметить учебные", on=self._suggest,
                                 tip="Отметит первые учебные недели графика по числу недель с прошлого шага."))
        actions.addWidget(Button("Снять все", "ghost", on=self._clear))
        actions.addStretch(1)
        actions.addWidget(Button("Отмена", on=self.reject))
        done = Button("Готово", "primary", on=self._apply)
        done.setMinimumWidth(120)
        actions.addWidget(done)
        box.addLayout(actions)
        self.scope.setText(self._scope_text())
        self._draw()

    # ---------- данные ----------

    def _scope_text(self) -> str:
        title = region_holiday_title(self.model.region)
        extra = active_holiday_extra(self.model)
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

    def _holiday(self, day: date) -> str:
        return holiday_map(day.year, self.model.region, active_holiday_extra(self.model)).get(day, "")

    def _clock(self) -> int:
        parts = self.start_combo.value().split(":")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]) * 60 + int(parts[1])
        return 15 * 60

    def _duration(self) -> int:
        model = self.model
        lessons = max(1, model.lesson_hours or 1)
        minutes = model.academic_minutes if model.academic_minutes > 0 else 45
        pause = model.break_minutes if model.break_minutes > 0 else 0
        return lessons * minutes + max(0, lessons - 1) * pause

    # ---------- действия ----------

    def _today(self) -> None:
        self.monday = self._initial_monday()
        self._draw()

    def _shift(self, step: int) -> None:
        if not self.mondays:
            return
        try:
            index = self.mondays.index(self.monday)
        except ValueError:
            index = 0
        self.monday = self.mondays[max(0, min(len(self.mondays) - 1, index + step))]
        self._draw()

    def _jump(self, day: date) -> None:
        monday = day - timedelta(days=day.weekday())
        if monday in self.mondays:
            self.monday = monday
            self._draw()

    def _toggle_from_box(self) -> None:
        key = self.monday.isoformat()
        if self.week_on.isChecked():
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

    def _start_changed(self, _index: int = 0) -> None:
        self.model.lesson_start = self.start_combo.value()
        self._draw()

    def _day_toggled(self) -> None:
        self.days = {index for index, chip in enumerate(self.day_buttons) if chip.isChecked()}
        self._draw()

    def _draw(self) -> None:
        self.range_label.setText(week_label(self.monday))
        self.week_on.setChecked(self.monday.isoformat() in self.selected)
        self._placed = class_placements(
            self.mondays, self.days, lambda day: bool(self._holiday(day)), self.selected
        )
        holidays = [self._holiday(self.monday + timedelta(days=offset)) for offset in range(7)]
        self.grid.set_state(
            self.monday, self.days, self._placed, holidays,
            self.monday.isoformat() in self.selected, self._clock(), self._duration(),
        )
        self.mini_title.setText(f"{_MONTHS[self.monday.month - 1].capitalize()} {self.monday.year}")
        self.mini.shown, self.mini.monday = self.monday, self.monday
        self.mini.days, self.mini.placed = set(self.days), dict(self._placed)
        self.mini.update()
        valid = {day.isoformat() for day in self.mondays}
        self.counter.setText(f"Отмечено недель: {len([w for w in self.selected if w in valid])}")

    def _suggest(self) -> None:
        model = self.model
        self.selected = set(suggest_class_weeks(
            model.year, model.calendar_mode, model.study_weeks, model.region, model.years,
            active_holiday_extra(model),
        ))
        self._draw()

    def _clear(self) -> None:
        self.selected.clear()
        self._draw()

    def _ask(self) -> None:
        if self._waiting:
            return
        model = self.model
        region = model.region.strip()
        if len(region) < 2:
            alert(self, "Сначала укажите регион", "Он задаётся на шаге «Паспорт».", "warn")
            return
        start, finish = period_bounds(model.year, model.calendar_mode, model.years)
        self._waiting = True
        self.ask_button.setEnabled(False)
        self.status.show_message("info", f"Спрашиваю праздники региона «{region}»…")
        run_async(self, lambda: generate_holidays(region, start.year, finish.year), self._holidays_ready, self._holidays_failed)

    def _holidays_failed(self, error) -> None:
        self._waiting = False
        self.ask_button.setEnabled(True)
        text = str(error)
        if not isinstance(error, GenerationError):
            text = f"Не удалось получить праздники.\n\n{text}"
        self.status.show_message("error", text)

    def _holidays_ready(self, ready) -> None:
        self._waiting = False
        self.ask_button.setEnabled(True)
        ready = ready or []
        model = self.model
        start, finish = period_bounds(model.year, model.calendar_mode, model.years)
        model.holiday_days = ready
        model.holiday_key = holiday_query_key(model.region, start, finish)
        self.window_.session.touch()
        if ready:
            self.status.show_message(
                "ok", f"Модель добавила {len(ready)} дополнительных дней. Общероссийские праздники оставлены как есть."
            )
        else:
            self.status.show_message(
                "ok", "Модель не назвала дополнительных праздников этого региона. В календаре остаются праздники России."
            )
        self.scope.setText(self._scope_text())
        self._draw()

    def _apply(self) -> None:
        model = self.model
        old = model.lessons_per_week
        days = sorted(self.days)
        model.class_days = days
        model.lessons_per_week = len(days)
        lesson_hours = model.lesson_hours if model.lesson_hours in (1, 2, 3, 4) else 0
        if lesson_hours and days and model.hours_per_week == old * lesson_hours:
            model.hours_per_week = len(days) * lesson_hours
        model.lesson_start = self.start_combo.value()
        valid = {day.isoformat() for day in self.mondays}
        weeks = sorted(day for day in self.selected if day in valid)
        self.on_apply(weeks)
        self.accept()
