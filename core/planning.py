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


def build_calendar_rows(mode: str, years: int, total_hours: int) -> list[dict[str, str]]:
    """Строки календарного учебного графика. Сумма часов равна объёму программы."""
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


def lesson_dates(year: int, count: int, per_week: int, mode: str) -> list[str]:
    """Предполагаемые даты занятий. Праздничные дни пропускаются."""
    if count <= 0:
        return []
    per_week = max(1, min(int(per_week or 1), 6))
    weekdays = set((0, 2, 4, 1, 3, 5)[:per_week])
    if mode.startswith("лето"):
        start = date(year, 6, 1)
    elif mode.startswith("календарный"):
        start = date(year, 1, 8)
    else:
        # 1–7 сентября в образце оставлены на комплектование.
        start = date(year, 9, 8)
    holidays = _holidays(year)
    found: list[str] = []
    day = start
    limit = date(year + 3, 1, 1)
    while len(found) < count and day < limit:
        if day.weekday() in weekdays and day not in holidays:
            found.append(day.strftime("%d.%m.%Y"))
        day += timedelta(days=1)
    return found


def holiday_note(year: int, mode: str) -> str:
    if mode.startswith("лето"):
        return "В летнем режиме занятия ставятся в июне–августе, кроме 12 июня, если этот день попадает на занятие."
    if mode.startswith("календарный"):
        return (
            f"В {year} году занятия не ставятся на нерабочие праздничные дни: "
            "1–8 января, 23 февраля, 8 марта, 1 и 9 мая, 12 июня, 4 ноября."
        )
    return (
        f"Учебный год {year}–{year + 1}: занятия не ставятся на нерабочие праздничные дни "
        "(4 ноября, 1–8 января, 23 февраля, 8 марта, 1 и 9 мая). "
        "1–7 сентября оставлены на комплектование групп, занятия в расчёте начинаются с 8 сентября."
    )


def _holidays(year: int) -> set[date]:
    days: set[date] = set()
    for value in (year, year + 1):
        for day_number in range(1, 9):
            days.add(date(value, 1, day_number))
        days.update(
            {
                date(value, 2, 23),
                date(value, 3, 8),
                date(value, 5, 1),
                date(value, 5, 9),
                date(value, 6, 12),
                date(value, 11, 4),
            }
        )
    return days
