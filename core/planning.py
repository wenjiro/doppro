# -*- coding: utf-8 -*-
"""Расчёт часов, календарной сетки и ролей разделов.

Здесь нет текста документа — только арифметика, чтобы сумма часов
в учебном плане, графике и календарно-тематическом плане совпадала.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from functools import lru_cache

from core.data_model import ModuleItem
from core.holidays import (
    holiday_dates,
    holiday_map,
    holiday_query_key,
    holidays_between,
    region_holiday_title,
    week_label,
)
from core.paths import modules_path


def plural(number: int, forms: tuple[str, str, str]) -> str:
    """forms: (1 час, 2 часа, 5 часов)."""
    value = abs(int(number))
    tail = value % 10
    hundred = value % 100
    if tail == 1 and hundred != 11:
        return forms[0]
    if tail in (2, 3, 4) and hundred not in (12, 13, 14):
        return forms[1]
    return forms[2]


def hours_word(number: int) -> str:
    return plural(number, ("час", "часа", "часов"))


def years_word(number: int) -> str:
    return plural(number, ("год", "года", "лет"))


def lessons_word(number: int) -> str:
    return plural(number, ("занятие", "занятия", "занятий"))


def largest_remainder(total: int, weights: list[int]) -> list[int]:
    """Делит целое total пропорционально весам. Сумма результата равна total."""
    if not weights:
        return []
    if total <= 0:
        return [0 for _ in weights]
    safe = [max(int(weight), 0) for weight in weights]
    if sum(safe) <= 0:
        safe = [1 for _ in safe]
    weight_sum = sum(safe)
    raw = [total * weight / weight_sum for weight in safe]
    floors = [int(item) for item in raw]
    left = total - sum(floors)
    order = sorted(
        range(len(raw)),
        key=lambda index: (raw[index] - floors[index], safe[index]),
        reverse=True,
    )
    for index in order[:left]:
        floors[index] += 1
    return floors


def split_hours(total: int, lesson_hours: int) -> list[int]:
    """Режет часы раздела на занятия. Последнее занятие может быть короче."""
    if total <= 0:
        return []
    size = lesson_hours if lesson_hours > 0 else 1
    chunks: list[int] = []
    left = total
    while left > 0:
        take = min(size, left)
        chunks.append(take)
        left -= take
    return chunks


def study_day_loads(theory: int, practice: int, lesson_hours: int) -> list[tuple[int, int]]:
    """Часы теории и практики по учебным дням. Суммы совпадают с разделом.

    Пока в разделе остаются и теория, и практика, день получает обе части:
    хотя бы час лекции и остаток на практику. Когда одна часть кончается,
    следующие дни отдаются оставшейся.
    """
    theory = max(int(theory), 0)
    practice = max(int(practice), 0)
    chunks = split_hours(theory + practice, lesson_hours)
    theory_left = theory
    practice_left = practice
    loads: list[tuple[int, int]] = []
    for index, chunk in enumerate(chunks):
        days_after = len(chunks) - index - 1
        take_theory = 0
        take_practice = 0
        if theory_left and practice_left and chunk >= 2:
            spare = chunk - 1
            must_keep = max(0, theory_left - days_after * spare)
            take_theory = min(theory_left, spare, max(1, must_keep))
            take_practice = min(practice_left, chunk - take_theory)
            if take_theory + take_practice < chunk and theory_left > take_theory:
                take_theory += min(theory_left - take_theory, chunk - take_theory - take_practice)
        elif theory_left:
            take_theory = min(theory_left, chunk)
            take_practice = min(practice_left, chunk - take_theory)
        else:
            take_practice = min(practice_left, chunk)
        gap = chunk - take_theory - take_practice
        if gap and theory_left > take_theory:
            extra = min(gap, theory_left - take_theory)
            take_theory += extra
            gap -= extra
        if gap and practice_left > take_practice:
            take_practice += min(gap, practice_left - take_practice)
        theory_left -= take_theory
        practice_left -= take_practice
        loads.append((take_theory, take_practice))
    if loads and (theory_left or practice_left):
        last_theory, last_practice = loads[-1]
        loads[-1] = (last_theory + theory_left, last_practice + practice_left)
    return loads


def detect_role(name: str) -> str:
    """По названию раздела выбирает готовый тип формулировок."""
    folded = name.lower().replace("ё", "е")
    if "аттестац" in folded or re.search(r"\bзачет", folded):
        return "attestation"
    tokens = re.findall(r"[а-яa-z0-9-]+", folded)
    if any(token in {"проба", "пробы", "пробу", "пробе", "пробой"} or token.startswith("профессион") for token in tokens):
        return "trials"
    if "регионал" in folded or "мини-проект" in folded or "минипроект" in folded:
        return "regional"
    if "проект" in folded:
        return "project"
    if "введен" in folded or "вводн" in folded:
        return "intro"
    if any(part in folded for part in ("практикум", "практическ", "трениров", "репетиц", "соревнован")):
        return "practice"
    return "theory"


@lru_cache(maxsize=1)
def _module_book() -> dict:
    return json.loads(modules_path().read_text(encoding="utf-8"))


def module_specs(direction: str) -> list[dict]:
    book = _module_book()
    directions = book.get("directions", {})
    specs = directions.get(direction) or directions.get("техническая") or []
    return list(specs)


def default_modules(direction: str, total_hours: int) -> list[ModuleItem]:
    """Типовые разделы направленности, часы уже сведены к объёму программы."""
    specs = module_specs(direction)
    if not specs:
        specs = [{"name": "Основной раздел", "weight": 1, "theory_ratio": 0.4}]
    hours = largest_remainder(max(total_hours, 0), [int(item.get("weight", 1)) for item in specs])
    result: list[ModuleItem] = []
    for spec, section_hours in zip(specs, hours):
        ratio = float(spec.get("theory_ratio", 0.4))
        theory = int(round(section_hours * ratio))
        theory = max(0, min(section_hours, theory))
        result.append(ModuleItem(name=str(spec["name"]), theory=theory, practice=section_hours - theory))
    return result


def scale_modules(modules: list[ModuleItem], total_hours: int) -> list[ModuleItem]:
    """Сохраняет названия и долю теории, заново раскладывает общий объём."""
    if not modules or total_hours <= 0:
        return modules
    weights = [item.hours if item.hours > 0 else 1 for item in modules]
    hours = largest_remainder(total_hours, weights)
    scaled: list[ModuleItem] = []
    for item, section_hours in zip(modules, hours):
        ratio = (item.theory / item.hours) if item.hours else 0.4
        theory = int(round(section_hours * ratio))
        theory = max(0, min(section_hours, theory))
        scaled.append(
            ModuleItem(
                name=item.name,
                theory=theory,
                practice=section_hours - theory,
                lectures=list(item.lectures),
                practices=list(item.practices),
            )
        )
    return scaled


# Веса месяцев учебного года ближе к реальной сетке: в январе недель меньше.
_ACADEMIC_MONTHS = [
    ("сентябрь", 4),
    ("октябрь", 5),
    ("ноябрь", 4),
    ("декабрь", 4),
    ("январь", 3),
    ("февраль", 4),
    ("март", 4),
    ("апрель", 4),
    ("май", 4),
]
_SUMMER_MONTHS = [("июнь", 1), ("июль", 1), ("август", 1)]
_CIVIL_MONTHS = [
    ("январь", 1),
    ("февраль", 1),
    ("март", 1),
    ("апрель", 1),
    ("май", 1),
    ("июнь", 1),
    ("июль", 1),
    ("август", 1),
    ("сентябрь", 1),
    ("октябрь", 1),
    ("ноябрь", 1),
    ("декабрь", 1),
]


def calendar_months(mode: str) -> list[tuple[str, int]]:
    if mode.startswith("лето"):
        return list(_SUMMER_MONTHS)
    if mode.startswith("календарный"):
        return list(_CIVIL_MONTHS)
    return list(_ACADEMIC_MONTHS)


def period_bounds(year: int, mode: str, years: int = 1) -> tuple[date, date]:
    count = years if years > 0 else 1
    if mode.startswith("лето"):
        return date(year, 6, 1), date(year + count - 1, 8, 31)
    if mode.startswith("календарный"):
        return date(year, 1, 1), date(year + count - 1, 12, 31)
    return date(year, 9, 1), date(year + count, 5, 31)


def period_mondays(year: int, mode: str, years: int = 1) -> list[date]:
    start, finish = period_bounds(year, mode, years)
    monday = start - timedelta(days=start.weekday())
    weeks: list[date] = []
    while monday <= finish:
        weeks.append(monday)
        monday += timedelta(days=7)
    return weeks


def active_holiday_extra(program) -> list | None:
    """Перечень модели, если он запрошен для этого региона и этого срока."""
    days = getattr(program, "holiday_days", None)
    key = str(getattr(program, "holiday_key", "") or "")
    if not key or not isinstance(days, list):
        return None
    start, finish = period_bounds(program.year, program.calendar_mode, program.years)
    if key != holiday_query_key(program.region, start, finish):
        return None
    return list(days)


def suggest_class_weeks(
    year: int,
    mode: str,
    count: int,
    region: str = "",
    years: int = 1,
    extra: list | None = None,
) -> list[str]:
    """Первые учебные недели периода, в которых есть хотя бы один будний день без праздника."""
    wanted = count if count > 0 else 36
    chosen: list[str] = []
    for monday in period_mondays(year, mode, years):
        if _week_has_class_day(monday, region, extra):
            chosen.append(monday.isoformat())
        if len(chosen) >= wanted:
            break
    return chosen


def class_week_rows(
    year: int,
    mode: str,
    years: int,
    region: str,
    extra: list | None = None,
) -> list[dict[str, str]]:
    start, finish = period_bounds(year, mode, years)
    rows: list[dict[str, str]] = []
    for monday in period_mondays(year, mode, years):
        names = []
        for offset in range(7):
            day = monday + timedelta(days=offset)
            title = holiday_map(day.year, region, extra).get(day)
            if title and start <= day <= finish:
                names.append(f"{day.day:02d}.{day.month:02d} — {title}")
        rows.append(
            {
                "monday": monday.isoformat(),
                "label": week_label(monday),
                "holidays": "; ".join(names),
                "open": "1" if _week_has_class_day(monday, region, extra) else "0",
            }
        )
    return rows


def _week_has_class_day(monday: date, region: str, extra: list | None = None) -> bool:
    for offset in range(5):
        day = monday + timedelta(days=offset)
        if day not in holiday_dates(day.year, region, extra):
            return True
    return False


def build_calendar_rows(
    mode: str,
    years: int,
    total_hours: int,
    year: int = 0,
    region: str = "",
    weeks: list[str] | None = None,
    extra: list | None = None,
) -> list[dict[str, str]]:
    """Строки календарного учебного графика. Сумма часов равна объёму программы."""
    custom = _calendar_from_weeks(mode, years, total_hours, year, region, weeks or [], extra)
    if custom:
        return custom
    months = calendar_months(mode)
    periods: list[str] = []
    weights: list[int] = []
    count_years = years if years > 0 else 1
    for year_index in range(1, count_years + 1):
        for name, weight in months:
            if count_years == 1:
                periods.append(name.capitalize())
            else:
                periods.append(f"{year_index}-й год — {name}")
            weights.append(weight)
    hours = largest_remainder(total_hours, weights)
    rows: list[dict[str, str]] = []
    last = len(periods) - 1
    for index, (period, section_hours) in enumerate(zip(periods, hours)):
        note = "учебные занятия по расписанию объединения"
        if index == 0:
            note = "старт программы, входная диагностика"
        elif index == last:
            note = "завершение программы, итоговая аттестация"
        elif "январь" in period:
            note = "учебные занятия с учётом каникул"
        rows.append({"period": period, "hours": str(section_hours), "note": note})
    return rows


def class_weekdays(per_week: int) -> set[int]:
    """Дни, если педагог их ещё не выбирал: одно — понедельник, два — пн и ср, три — пн, ср и пт."""
    count = max(1, min(int(per_week or 1), 6))
    return set((0, 2, 4, 1, 3, 5)[:count])


def effective_class_days(class_days: list | None, per_week: int) -> list[int]:
    """Дни, которые отметил педагог. Пустой список — прежняя схема по числу занятий."""
    found: list[int] = []
    for item in class_days or []:
        try:
            day = int(item)
        except (TypeError, ValueError):
            continue
        if 0 <= day <= 6 and day not in found:
            found.append(day)
    if found:
        return sorted(found)
    return sorted(class_weekdays(per_week))


def class_placements(
    mondays: list[date],
    weekdays: set[int],
    is_holiday,
    selected: set[str] | None = None,
) -> dict[date, str]:
    """Каждое занятие выбранных дней. Праздник или занятый день переносит его вперёд.

    Сначала ищется день той же недели, затем день следующей отмеченной учебной недели.
    «plan» — занятие в свой день, «shift» — перенос.
    """
    taken: dict[date, str] = {}
    chosen = {int(day) for day in weekdays if 0 <= int(day) <= 6}
    selected_weeks = set(selected) if selected is not None else None

    def free(day: date, origin: date) -> bool:
        if day in taken or is_holiday(day):
            return False
        week = day - timedelta(days=day.weekday())
        if week == origin:
            return True
        if selected_weeks is None:
            return True
        return week.isoformat() in selected_weeks

    for monday in sorted(mondays):
        if selected_weeks is not None and monday.isoformat() not in selected_weeks:
            continue
        for offset in sorted(chosen):
            planned = monday + timedelta(days=offset)
            slot = planned if free(planned, monday) else None
            if slot is None:
                cursor = planned + timedelta(days=1)
                for _ in range(60):
                    if free(cursor, monday):
                        slot = cursor
                        break
                    cursor += timedelta(days=1)
            if slot is None:
                continue
            taken[slot] = "plan" if slot == planned else "shift"
    return taken


def lesson_dates(
    year: int,
    count: int,
    per_week: int,
    mode: str,
    region: str = "",
    weeks: list[str] | None = None,
    years: int = 1,
    extra: list | None = None,
    weekdays: list[int] | None = None,
) -> list[str]:
    """Предполагаемые даты занятий. Праздник переносит занятие, а не отменяет его."""
    if count <= 0:
        return []
    chosen = effective_class_days(weekdays, per_week)
    start, finish = period_bounds(year, mode, years)
    if not weeks and not mode.startswith("лето") and not mode.startswith("календарный"):
        start = date(year, 9, 8)
    elif not weeks and mode.startswith("календарный"):
        start = date(year, 1, 8)
    mondays: list[date] = []
    if weeks:
        for item in weeks:
            try:
                mondays.append(date.fromisoformat(item))
            except ValueError:
                continue
    else:
        mondays = [
            monday
            for monday in period_mondays(year, mode, years)
            if monday + timedelta(days=6) >= start and monday <= finish
        ]
    selected = {monday.isoformat() for monday in mondays}

    def is_holiday(day: date) -> bool:
        return day in holiday_dates(day.year, region, extra)

    placed = class_placements(mondays, set(chosen), is_holiday, selected)
    found = [day.strftime("%d.%m.%Y") for day in sorted(placed) if start <= day <= finish]
    return found[:count]


def holiday_note(year: int, mode: str, region: str = "", years: int = 1, extra: list | None = None) -> str:
    start, finish = period_bounds(year, mode, years)
    found = holidays_between(start, finish, region, extra)
    shown = [f"{day.strftime('%d.%m.%Y')} — {name}" for day, name in found[:12]]
    if len(found) > 12:
        shown.append(f"ещё {len(found) - 12}")
    title = region_holiday_title(region)
    if extra is not None:
        scope = f"Учтены нерабочие дни России и {title}." if title else "Учтены нерабочие дни России."
        if extra:
            scope += " Дополнительные даты региона взяты у модели."
        else:
            scope += " Модель не добавила других праздников региона."
    elif title:
        scope = f"Учтены нерабочие дни России и {title}."
    else:
        scope = "Учтены нерабочие дни России. Для этого региона отдельный перечень праздников не подключён."
    listing = "; ".join(shown)
    tail = ""
    if extra is None and region_code_missing_religious(region, start.year, finish.year):
        tail = " Даты Ураза-байрам и Курбан-байрам на часть лет ещё не объявлены, их в сетку не ставили."
    return (
        f"{scope} В отмеченные недели занятия не ставятся в эти дни: {listing}. "
        "Если праздник попал на субботу или воскресенье, следующий рабочий день тоже выходной. "
        f"Перенос по отдельному постановлению Правительства на год можно убрать, сняв неделю.{tail}"
    )


def region_code_missing_religious(region: str, start_year: int, finish_year: int) -> bool:
    from core.holidays import region_code

    if region_code(region) not in {"bashkortostan", "tatarstan"}:
        return False
    return any(value not in _URAZA_YEARS for value in range(start_year, finish_year + 1))


_URAZA_YEARS = {2024, 2025, 2026}


def _calendar_from_weeks(
    mode: str,
    years: int,
    total_hours: int,
    year: int,
    region: str,
    weeks: list[str],
    extra: list | None = None,
) -> list[dict[str, str]]:
    if not weeks or year <= 0 or total_hours <= 0:
        return []
    start, finish = period_bounds(year, mode, years)
    counts: dict[str, int] = {}
    for item in sorted(weeks):
        try:
            monday = date.fromisoformat(item)
        except ValueError:
            continue
        for offset in range(5):
            day = monday + timedelta(days=offset)
            if day < start or day > finish or day in holiday_dates(day.year, region, extra):
                continue
            label = _month_label(day, year, years)
            counts[label] = counts.get(label, 0) + 1
    if not counts:
        return []
    periods = list(counts)
    hours = largest_remainder(total_hours, list(counts.values()))
    rows: list[dict[str, str]] = []
    last = len(periods) - 1
    for index, (period, section_hours) in enumerate(zip(periods, hours)):
        note = "учебные занятия в отмеченные недели"
        if index == 0:
            note = "старт программы, входная диагностика"
        elif index == last:
            note = "завершение программы, итоговая аттестация"
        rows.append({"period": period, "hours": str(section_hours), "note": note})
    return rows


_MONTH_NAME = (
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


def _month_label(day: date, start_year: int, years: int) -> str:
    name = _MONTH_NAME[day.month - 1].capitalize()
    if years <= 1:
        return name
    index = day.year - start_year + 1 if day.month >= 9 else day.year - start_year
    index = max(1, index)
    return f"{index}-й год — {name}"
