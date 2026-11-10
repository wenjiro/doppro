# -*- coding: utf-8 -*-
"""Регионы России и населённые пункты для паспорта программы.

Названия пунктов взяты из открытого справочника GeoNames (CC BY 4.0,
https://www.geonames.org/) и дополнены списком городов. Координат в программе нет.
Если пункта нет в списке, педагог вписывает его сам.
"""

from __future__ import annotations

import json
from functools import lru_cache

from core.paths import places_path


def fold_search(text: str) -> str:
    """Сравнение для поиска: без регистра, ё и разных тире."""
    return " ".join(
        str(text or "")
        .casefold()
        .replace("ё", "е")
        .replace("—", " ")
        .replace("–", " ")
        .replace("-", " ")
        .split()
    )


def regions() -> list[str]:
    return list(_catalog()["regions"])


def places_for(region: str) -> list[str]:
    """Пункты выбранного региона. Незнакомый регион — пустой список, поле остаётся свободным."""
    name = resolve_region(region)
    if not name:
        return []
    return list(_catalog()["places"].get(name, []))


def resolve_region(text: str) -> str:
    """Официальное имя, если введённое совпадает с одним регионом. Иначе пусто."""
    needle = fold_search(text)
    if not needle:
        return ""
    names = regions()
    exact = [name for name in names if fold_search(name) == needle]
    if len(exact) == 1:
        return exact[0]
    found = [name for name in names if needle in fold_search(name)]
    if len(found) == 1:
        return found[0]
    return ""


@lru_cache(maxsize=1)
def _catalog() -> dict:
    path = places_path()
    empty = {"regions": [], "places": {}}
    if not path.exists():
        return empty
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty
    if not isinstance(payload, dict):
        return empty
    names = payload.get("regions")
    places = payload.get("places")
    if not isinstance(names, list) or not isinstance(places, dict):
        return empty
    return {"regions": [str(name) for name in names], "places": places}
