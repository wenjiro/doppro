# -*- coding: utf-8 -*-
"""Нерабочие праздничные дни России и субъектов, где выходных больше.

Даты Ураза-байрам и Курбан-байрам — те, которые уже объявило правительство
республики. На год без такого постановления религиозный день в календарь не ставится:
его дата сдвигается, и выдумывать её нельзя.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta

# Объявленные даты. Башкортостан: постановления правительства республики.
_URAZA = {
    2024: date(2024, 4, 10),
    2025: date(2025, 3, 30),
    2026: date(2026, 3, 20),
}
_KURBAN = {
    2024: date(2024, 6, 16),
    2025: date(2025, 6, 6),
    2026: date(2026, 5, 27),
}

_MONTHS = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def region_code(region: str) -> str:
    text = region.casefold().replace("ё", "е")
    if "башкортостан" in text or "башкир" in text:
        return "bashkortostan"
    if "татарстан" in text:
        return "tatarstan"
    return ""


def region_holiday_title(region: str) -> str:
    code = region_code(region)
    if code == "bashkortostan":
        return "Республики Башкортостан"
    if code == "tatarstan":
        return "Республики Татарстан"
    return ""


_FEDERAL = {(1, day) for day in (1, 2, 3, 4, 5, 6, 7, 8)} | {(2, 23), (3, 8), (5, 1), (5, 9), (6, 12), (11, 4)}


class HolidayParseError(ValueError):
    """Ответ модели не удалось разобрать как перечень дат."""


def holiday_query_key(region: str, start: date, finish: date) -> str:
    """Связывает сохранённый перечень с регионом и сроком. После смены региона он не применяется."""
    return f"{region.strip().casefold()}|{start.isoformat()}|{finish.isoformat()}"


def holiday_map(year: int, region: str = "", extra: list | None = None) -> dict[date, str]:
    """День → название. Если праздник попал на субботу или воскресенье, следующий рабочий день тоже выходной.

    extra — даты, которые назвала модель. Общероссийские дни она не заменяет.
    """
    if year < 1992 or year > 2100:
        return {}
    days: dict[date, str] = {}
    for day_number in (1, 2, 3, 4, 5, 6, 8):
        days[date(year, 1, day_number)] = "Новогодние каникулы"
    days[date(year, 1, 7)] = "Рождество Христово"
    days[date(year, 2, 23)] = "День защитника Отечества"
    days[date(year, 3, 8)] = "Международный женский день"
    days[date(year, 5, 1)] = "Праздник Весны и Труда"
    days[date(year, 5, 9)] = "День Победы"
    days[date(year, 6, 12)] = "День России"
    days[date(year, 11, 4)] = "День народного единства"
    code = region_code(region)
    if code == "bashkortostan":
        days[date(year, 10, 11)] = "День Республики Башкортостан"
    elif code == "tatarstan":
        days[date(year, 8, 30)] = "День Республики Татарстан"
        days[date(year, 11, 6)] = "День Конституции Республики Татарстан"
    if code in {"bashkortostan", "tatarstan"}:
        if year in _URAZA:
            days[_URAZA[year]] = "Ураза-байрам"
        if year in _KURBAN:
            days[_KURBAN[year]] = "Курбан-байрам"
    for item in extra or []:
        added = _extra_day(item, year)
        if added is None or added[0] in days:
            continue
        days[added[0]] = added[1]
    _add_transfers(days)
    return days


def holiday_dates(year: int, region: str = "", extra: list | None = None) -> set[date]:
    return set(holiday_map(year, region, extra))


def holidays_between(
    start: date,
    finish: date,
    region: str,
    extra: list | None = None,
) -> list[tuple[date, str]]:
    found: list[tuple[date, str]] = []
    for year in range(start.year, finish.year + 1):
        for day, name in holiday_map(year, region, extra).items():
            if start <= day <= finish:
                found.append((day, name))
    found.sort(key=lambda item: item[0])
    return found


def parse_holiday_answer(raw: str, start_year: int, finish_year: int) -> list[dict[str, str]]:
    """Оставляет даты субъекта внутри срока программы. Общероссийские дни и переносы отбрасывает."""
    data = _load_holiday_json(raw)
    items = data.get("holidays")
    if items is None:
        items = data.get("days")
    if not isinstance(items, list):
        raise HolidayParseError("Сервис не прислал перечень праздников. Повторите запрос.")
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            raw_day = str(item.get("date") or "")
            raw_name = str(item.get("name") or item.get("title") or "")
        else:
            continue
        day = _parse_day(raw_day)
        name = " ".join(raw_name.split()).strip(" .;—-")
        if day is None or not (start_year <= day.year <= finish_year):
            continue
        if (day.month, day.day) in _FEDERAL:
            continue
        folded = name.casefold()
        if len(name) < 3 or len(name) > 80 or folded.startswith("выходной"):
            continue
        if "№" in name or "http" in folded or "перенос" in folded:
            continue
        key = day.isoformat()
        if key in seen:
            continue
        seen.add(key)
        found.append({"date": key, "name": name})
        if len(found) >= 40:
            break
    return found


def _extra_day(item, year: int) -> tuple[date, str] | None:
    if not isinstance(item, dict):
        return None
    day = _parse_day(str(item.get("date") or ""))
    name = " ".join(str(item.get("name") or "").split()).strip(" .;—-")
    if day is None or day.year != year or len(name) < 3 or name.casefold().startswith("выходной"):
        return None
    return day, name[:80]


def _parse_day(text: str) -> date | None:
    text = text.strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if not match:
        return None
    try:
        return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    except ValueError:
        return None


def _load_holiday_json(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise HolidayParseError("Сервис вернул текст не в виде перечня дат. Повторите запрос.") from exc
    if not isinstance(data, dict):
        raise HolidayParseError("Сервис вернул не тот формат. Повторите запрос.")
    return data


def format_day(day: date) -> str:
    return f"{day.day} {_MONTHS[day.month - 1]}"


def week_label(monday: date) -> str:
    sunday = monday + timedelta(days=6)
    if monday.month == sunday.month and monday.year == sunday.year:
        return f"{monday.day}–{sunday.day} {_MONTHS[monday.month - 1]} {monday.year}"
    if monday.year == sunday.year:
        return f"{monday.day} {_MONTHS[monday.month - 1]} – {sunday.day} {_MONTHS[sunday.month - 1]} {sunday.year}"
    return (
        f"{monday.day} {_MONTHS[monday.month - 1]} {monday.year} – "
        f"{sunday.day} {_MONTHS[sunday.month - 1]} {sunday.year}"
    )


def _add_transfers(days: dict[date, str]) -> None:
    """Суббота или воскресенье праздника переносят выходной на ближайший рабочий день."""
    transfers: dict[date, str] = {}
    for day, name in list(days.items()):
        if day.month == 1 and day.day <= 8:
            continue
        if day.weekday() < 5 or name.startswith("выходной за"):
            continue
        moved = day + timedelta(days=1)
        occupied = set(days) | set(transfers)
        while moved.weekday() >= 5 or moved in occupied:
            moved += timedelta(days=1)
        transfers[moved] = f"выходной за {name}"
    days.update(transfers)
