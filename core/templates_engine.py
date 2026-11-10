# -*- coding: utf-8 -*-
"""Сборка текста программы из готовых формулировок.

Все абзацы берутся из templates/text_blocks и подставляются факты педагога:
название, город, возраст, часы, переключатели. Генерации «с нуля» нет.
"""

from __future__ import annotations

import json
from functools import lru_cache

from core.data_model import LEVEL_FULL, LEVEL_METHOD, ProgramData
from core.generator import normalize_module_row
from core.paths import text_blocks_dir
from core.planning import (
    build_calendar_rows,
    detect_role,
    holiday_note,
    hours_word,
    lesson_dates,
    study_day_loads,
    years_word,
)


@lru_cache(maxsize=1)
def _phrases() -> dict:
    path = text_blocks_dir() / "phrases.json"
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _profiles() -> dict:
    path = text_blocks_dir() / "profiles.json"
    return json.loads(path.read_text(encoding="utf-8"))


def profile_for(direction: str) -> dict:
    profiles = _profiles()
    if direction not in profiles:
        raise KeyError(f"Нет текстового профиля направленности: {direction}")
    return profiles[direction]


@lru_cache(maxsize=1)
def _direction_texts() -> dict:
    path = text_blocks_dir() / "direction_texts.json"
    return json.loads(path.read_text(encoding="utf-8"))


def direction_text(direction: str) -> dict:
    """Тексты пояснительной записки, свои для каждой направленности."""
    texts = _direction_texts()
    if direction not in texts:
        raise KeyError(f"Нет текстов направленности: {direction}")
    return texts[direction]


def fmt(template: str, mapping: dict) -> str:
    """Подстановка {полей}. Недостающий ключ должен всплыть сразу, а не попасть в документ."""
    return template.format_map(mapping)


def _show(template: str, mapping: dict) -> str:
    """Формулировка модели уже готова. Шаблон с {полями} по-прежнему подставляется."""
    if "{" not in template:
        return template
    try:
        return fmt(template, mapping)
    except (KeyError, ValueError, IndexError):
        return template


def _band_label(age_from: int, age_to: int) -> str:
    return f"{age_from}\u2013{age_to} лет"


_EXPLAIN = {
    "young": "коротко, с показом и образцом",
    "middle": "показ, затем разбор одного шага своими словами",
    "old": "с разбором шагов, ошибок и причин",
    "common": "показ и образец, мера помощи — по ходу занятия",
}
_INDEPENDENCE = {
    "young": "пошаговая инструкция, частая проверка",
    "middle": "инструкция на часть работы, свой выбор в оставшейся",
    "old": "свой план и правка до показа",
    "common": "помощь уменьшается, когда шаг уже получается",
}


def _span_tone(index: int, count: int, differentiate: bool) -> str:
    if not differentiate or count <= 1:
        return "common"
    if index == 0:
        return "young"
    if index == count - 1:
        return "old"
    return "middle"


def age_bands(program: ProgramData, profile: dict | None = None) -> list[dict[str, str]]:
    """Линии по промежуткам, которые задал педагог. Без галочки — один промежуток на весь возраст."""
    spans = program.effective_age_spans()
    if not spans:
        spans = [{"from": program.age_from, "to": program.age_to}]
    count = len(spans)
    bands: list[dict[str, str]] = []
    for index, span in enumerate(spans):
        tone = _span_tone(index, count, program.differentiate)
        junior = (profile or {}).get("junior", "работа по образцу")
        senior = (profile or {}).get("senior", "больше самостоятельности")
        if tone == "young":
            support = junior
        elif tone == "old":
            support = senior
        elif tone == "middle":
            support = "часть работы по образцу и показу, часть — своим планом"
        else:
            support = f"сначала {junior}; когда шаг получается — {senior}"
        bands.append(
            {
                "kind": tone,
                "tone": tone,
                "label": _band_label(int(span["from"]), int(span["to"])),
                "support": support,
                "explain": _EXPLAIN[tone],
                "independence": _INDEPENDENCE[tone],
                "product": support,
            }
        )
    return bands


def _join_labels(labels: list[str]) -> str:
    if len(labels) <= 1:
        return labels[0] if labels else ""
    return ", ".join(labels[:-1]) + " и " + labels[-1]


def _base_mapping(program: ProgramData, profile: dict, practice_percent: int) -> dict[str, str]:
    age_text = _band_label(program.age_from, program.age_to)
    if program.group_min == program.group_max:
        group_text = f"{program.group_min} чел."
    else:
        group_text = f"от {program.group_min} до {program.group_max} человек"
    return {
        "title": program.title.strip(),
        "direction": program.direction,
        "direction_gen": profile["name_gen"],
        "level": program.level,
        "level_full": LEVEL_FULL.get(program.level, program.level),
        "level_method": LEVEL_METHOD.get(program.level, "по инструкции педагога"),
        "age_text": age_text,
        "years_text": f"{program.years} {years_word(program.years)}",
        "total_hours": str(program.total_hours),
        "hours_word": hours_word(program.total_hours),
        "hours_per_week": str(program.hours_per_week),
        "hours_per_week_word": hours_word(program.hours_per_week),
        "lesson_hours": str(program.lesson_hours),
        "lesson_hours_word": hours_word(program.lesson_hours),
        "group_text": group_text,
        "study_form": program.study_form,
        "organization": program.organization.strip(),
        "teacher_name": program.teacher_name.strip(),
        "teacher_position": program.teacher_position.strip(),
        "city": program.city.strip(),
        "region": program.region.strip(),
        "year": str(program.year),
        "focus_gen": profile["focus_gen"],
        "activity_nom": profile["activity_nom"],
        "product_nom": profile["product_nom"],
        "product_gen": profile["product_gen"],
        "skills": profile["skills"],
        "junior": profile["junior"],
        "senior": profile["senior"],
        "practice_percent": str(practice_percent),
        "attestation_form": program.attestation_form,
        "regional_notes": program.regional_notes.strip(),
        "calendar_mode": program.calendar_mode,
        "academic_year": f"{program.year}\u2013{program.year + max(program.years, 1)} учебный год",
        "director_position": program.director_position.strip() or "директор",
        "director_name": program.director_name.strip() or "____________",
        "org_short": program.org_short.strip() or program.organization.strip(),
    }


def _options_paragraph(program: ProgramData, phrases: dict, mapping: dict) -> str:
    parts: list[str] = []
    if program.professional_trials:
        parts.append(fmt(phrases["opt_trials"], mapping))
    if program.regional_project:
        parts.append(fmt(phrases["opt_regional"], mapping))
    if program.final_project:
        parts.append(fmt(phrases["opt_final"], mapping))
    if program.interim_attestation:
        parts.append(fmt(phrases["opt_interim"], mapping))
    if program.excursions:
        parts.append(fmt(phrases["opt_excursions"], mapping))
    if not parts:
        parts.append(fmt(phrases["opt_none"], mapping))
    return " ".join(parts)


def _differentiation_paragraph(program: ProgramData, phrases: dict, mapping: dict, bands: list[dict[str, str]]) -> str:
    if not program.differentiate or len(bands) < 2:
        return fmt(phrases["diff_off"], mapping)
    supports = " ".join(f"Для {band['label']} опора — {band['support']}." for band in bands)
    return (
        f"В программе выделены возрастные промежутки: {_join_labels([band['label'] for band in bands])}. "
        "Цель одна. Меняются длина объяснения, самостоятельность и сложность продукта. "
        + supports
    )


def _trials_paragraph(program: ProgramData, phrases: dict, mapping: dict, bands: list[dict[str, str]]) -> str | None:
    if not program.professional_trials:
        return None
    if len(bands) < 2:
        return fmt(phrases["trials_young"], mapping)
    younger = _join_labels([band["label"] for band in bands[:-1]])
    oldest = bands[-1]["label"]
    return (
        f"Для обучающихся {younger} проба ознакомительная: один понятный шаг вместе с педагогом. "
        f"Для {oldest} проба ближе к роли: короткое задание и разбор нужных умений. "
        "Это знакомство с делом, а не профессиональное обучение."
    )


def _regional_paragraph(program: ProgramData, phrases: dict, mapping: dict) -> str:
    if program.regional_notes.strip():
        return fmt(phrases["regional_custom"], mapping)
    return fmt(phrases["regional_default"], mapping)


def _calendar_sentence(mode: str) -> str:
    if mode.startswith("лето"):
        return "Календарный учебный график рассчитан на летние месяцы: июнь, июль и август."
    if mode.startswith("календарный"):
        return "Календарный учебный график рассчитан на календарный год, с января по декабрь."
    return "Календарный учебный график рассчитан на учебный год, с сентября по май."


def _lecture_bank(role: str, phrases: dict) -> list[str]:
    topics = phrases["topics"]
    if role in {"intro", "theory", "attestation", "project", "trials", "regional"}:
        bank = list(topics.get(role, []))
    else:
        bank = list(topics.get("theory", []))
    if not bank:
        bank = ["Объяснение по разделу «{module}»"]
    return bank


def _practice_bank(
    role: str, profile: dict, phrases: dict, program: ProgramData, roles_present: set[str]
) -> list[str]:
    topics = phrases["topics"]
    bank = list(topics.get("practice", []))
    if role == "practice":
        bank = list(profile.get("signature_topics", [])) + bank
    if role == "project" and program.professional_trials and "trials" not in roles_present:
        bank = list(topics["trials"])[:2] + bank
    if role == "project" and program.regional_project and "regional" not in roles_present:
        bank = list(topics["regional"])[:2] + bank
    if role in {"project", "attestation", "trials", "regional"}:
        bank = list(topics.get(role, []))[:3] + bank
    if not bank:
        bank = ["Практическая работа по разделу «{module}»"]
    return bank


def _day_title(pool: list[str], index: int, local: dict) -> str:
    title = _show(pool[index % len(pool)], local)
    cycle = index // len(pool)
    if cycle:
        title += f" (часть {cycle + 1})"
    return title


def _control_and_form(role: str, attestation_form: str) -> tuple[str, str]:
    control = {
        "intro": "наблюдение, стартовое задание",
        "theory": "опрос, учебная карточка",
        "practice": "практическая работа",
        "project": "представление результата",
        "attestation": attestation_form,
        "trials": "лист пробы и устное обсуждение",
        "regional": "представление мини-проекта",
    }
    form = {
        "intro": "беседа и учебное занятие",
        "theory": "учебное занятие",
        "practice": "практическое занятие",
        "project": "проектное занятие",
        "attestation": "аттестация",
        "trials": "профессиональная проба",
        "regional": "практическое занятие",
    }
    return control.get(role, "наблюдение"), form.get(role, "учебное занятие")


def _task_pair(role: str) -> tuple[str, str]:
    """Обязательное задание и задание с усложнением — как в образце программы."""
    pairs = {
        "intro": (
            "выполнить стартовое действие по образцу педагога и сохранить результат.",
            "добавить к образцу один свой элемент.",
        ),
        "theory": (
            "повторить приём по инструкции и назвать правило своими словами.",
            "применить тот же приём в немного изменённом задании.",
        ),
        "practice": (
            "выполнить работу по образцу и проверить её по критериям.",
            "изменить один параметр работы и объяснить, что изменилось.",
        ),
        "project": (
            "довести продукт до показа: замысел, выполнение, короткий рассказ.",
            "усложнить продукт и рассказать, что можно улучшить.",
        ),
        "trials": (
            "выполнить пробное задание вместе с педагогом.",
            "назвать, какие умения понадобились в этой роли.",
        ),
        "regional": (
            "включить в работу один понятный местный пример.",
            "пояснить, как этот пример связан с результатом.",
        ),
        "attestation": (
            "представить результат по критериям, которые были объявлены заранее.",
            "добавить к рассказу, что получилось и что стоило бы переделать.",
        ),
    }
    return pairs.get(role, pairs["practice"])


def _short_title(title: str, limit: int = 70) -> str:
    compact = " ".join(title.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def build_context(program: ProgramData) -> dict:
    """Готовый контекст для шаблона docx. Строки уже собраны, шаблону остаётся расставить их."""
    phrases = _phrases()
    profile = profile_for(program.direction)
    theory_sum = sum(max(item.theory, 0) for item in program.modules)
    practice_sum = sum(max(item.practice, 0) for item in program.modules)
    module_sum = theory_sum + practice_sum
    base_total = module_sum or program.total_hours or 1
    practice_percent = round(practice_sum * 100 / base_total) if base_total else 0
    mapping = _base_mapping(program, profile, practice_percent)
    bands = age_bands(program, profile)

    roles = [detect_role(item.name) for item in program.modules]
    roles_present = set(roles)

    voice = direction_text(program.direction)
    spoken = _spoken(program)
    overview = [
        fmt(phrases["annotation"], mapping),
        fmt(phrases["direction_line"], mapping),
        fmt(phrases["org_line"], mapping),
        fmt(phrases["author_line"], mapping),
        fmt(phrases["normative"], mapping),
    ]
    relevance = spoken.get("relevance") or [fmt(item, mapping) for item in voice["relevance"]]
    if "relevance" not in spoken:
        relevance.append(_level_close(program.level))
    novelty = spoken.get("novelty") or [fmt(item, mapping) for item in voice["novelty"]]
    novelty.append(_options_paragraph(program, phrases, mapping))
    expediency = spoken.get("expediency") or [fmt(item, mapping) for item in voice["expediency"]]
    if spoken.get("addressee"):
        addressee = list(spoken["addressee"])
    else:
        addressee = [fmt(phrases["addressee"], mapping)]
    addressee.append(_differentiation_paragraph(program, phrases, mapping, bands))
    study_days = program.study_weeks * max(program.lessons_per_week, 1)
    volume = [
        fmt(phrases["volume"], mapping),
        (
            f"Срок в календарной сетке — {program.study_weeks} учебных недель, {study_days} учебных дней. "
            f"Занятия: {program.lessons_per_week} раза в неделю по {program.lesson_hours} {hours_word(program.lesson_hours)}. "
            f"Академический час — {program.academic_minutes} минут, перерыв — {program.break_minutes} минут. "
            "При электронном обучении или дистанционных технологиях академический час может быть короче — по локальному акту организации."
        ),
        _calendar_sentence(program.calendar_mode),
        holiday_note(program.year, program.calendar_mode),
    ]
    features = [fmt(phrases["features_base"], mapping), _regional_paragraph(program, phrases, mapping)]
    if program.no_prior_training:
        features.append(
            "Набор свободный: специальная подготовка до первого занятия не требуется. "
            "Предварительного отбора нет."
        )
    features.append(
        "Программа реализуется без сетевой формы."
        if not program.partners.strip()
        else "Программа реализуется без сетевой формы. " + program.partners.strip()
    )
    if "дистанц" in program.study_form:
        features.append(fmt(phrases["features_distance"], mapping))
    trials_text = _trials_paragraph(program, phrases, mapping, bands)
    if trials_text:
        features.append(trials_text)

    if spoken.get("tasks"):
        teaching = list(spoken["tasks"])
    else:
        teaching = [fmt(item, mapping) for item in voice["tasks"]]
        teaching.extend(fmt(item, mapping) for item in phrases["tasks_teaching"])
    if program.differentiate and len(bands) >= 2:
        pieces = "; ".join(f"для {band['label']} — {band['support']}" for band in bands)
        teaching.append(f"Учитывать возрастные промежутки программы: {pieces}.")
    if program.professional_trials:
        teaching.append(fmt(phrases["task_trials"], mapping))
    if program.regional_project:
        teaching.append(fmt(phrases["task_regional"], mapping))

    goal_text = str(spoken.get("goal") or "").strip()
    goal = [goal_text] if goal_text else []
    goal_manual = not goal
    if spoken.get("developing_tasks"):
        developing = list(spoken["developing_tasks"])
    else:
        developing = [fmt(item, mapping) for item in phrases["tasks_developing"]]
        developing.append(spoken.get("developing") or fmt(voice["developing"], mapping))
    if spoken.get("educating"):
        educating = list(spoken["educating"])
    else:
        educating = [fmt(item, mapping) for item in phrases["tasks_educating"]]

    module_views: list[dict[str, str]] = []
    ktp_rows: list[dict[str, str]] = []
    lesson_number = 1
    for index, module in enumerate(program.modules):
        role = roles[index]
        control, lesson_form = _control_and_form(role, program.attestation_form)
        local = dict(mapping)
        local["module"] = module.name.strip()
        local["name"] = module.name.strip()
        lecture_pool = [_show(item, local) for item in module.lectures] or [
            fmt(item, local) for item in _lecture_bank(role, phrases)
        ]
        practice_pool = [_show(item, local) for item in module.practices] or [
            fmt(item, local) for item in _practice_bank(role, profile, phrases, program, roles_present)
        ]
        day_rows: list[dict[str, str]] = []
        lecture_index = 0
        practice_index = 0
        for theory_hours, practice_hours in study_day_loads(module.theory, module.practice, program.lesson_hours):
            lecture = _day_title(lecture_pool, lecture_index, local) if theory_hours else "—"
            practice_title = _day_title(practice_pool, practice_index, local) if practice_hours else "—"
            if theory_hours:
                lecture_index += 1
            if practice_hours:
                practice_index += 1
            day_hours = theory_hours + practice_hours
            if theory_hours and practice_hours:
                day_form = "лекция и практика"
            elif practice_hours:
                day_form = "практическое занятие"
            else:
                day_form = lesson_form
            row = {
                "num": str(lesson_number),
                "date": "",
                "section": module.name.strip(),
                "lecture": lecture,
                "practice": practice_title,
                "topic": module.name.strip(),
                "hours": str(day_hours),
                "theory_hours": str(theory_hours),
                "practice_hours": str(practice_hours),
                "form": day_form,
                "control": control,
            }
            day_rows.append(row)
            ktp_rows.append(row)
            lesson_number += 1
        blurb_bank = voice.get("blurbs", {})
        blurb = fmt(blurb_bank.get(role) or phrases["blurbs"].get(role, phrases["blurbs"]["theory"]), local)
        extra = ""
        if role == "project" and program.professional_trials and "trials" not in roles_present:
            extra += " Часть часов раздела отведена на профессиональные пробы."
        if role == "project" and program.regional_project and "regional" not in roles_present:
            extra += " В этот же раздел входит региональный мини-проект."
        mandatory, enrichment = _task_pair(role)
        custom = _module_speech(spoken, index)
        name = module.name.strip()
        easy_label = "Задание стартового уровня" if program.level == "стартовый" else "Задание базового уровня"
        theory_text = _labeled("Теория", custom.get("theory") or blurb)
        practice_text = _labeled(
            "Практика",
            custom.get("practice") or f"Обучающиеся выполняют работу {mapping['level_method']}.{extra}",
        )
        form_body = (custom.get("form") or lesson_form).rstrip(".")
        if "контрол" not in form_body.casefold():
            form_body = f"{form_body}. Форма контроля — {control}"
        form_text = _labeled("Форма занятий", form_body)
        basic_text = _labeled(easy_label, custom.get("basic") or mandatory)
        advanced_text = _labeled("Усложнённое задание", custom.get("advanced") or enrichment)
        skills_text = _labeled("Навыки", custom.get("skills") or f"{profile['skills']} по теме «{name}»")
        abilities_text = _labeled(
            "Умения",
            custom.get("abilities")
            or "концентрация внимания на шаге задания, переключение с объяснения на практику, работа в паре или в группе",
        )
        lines = [theory_text, practice_text, form_text, basic_text, advanced_text, skills_text, abilities_text]
        module_views.append(
            {
                "num": str(index + 1),
                "name": name,
                "theory": str(module.theory),
                "practice": str(module.practice),
                "hours": str(module.hours),
                "control": control,
                "heading": f"Раздел {index + 1}. «{name.strip('«»')}» ({module.hours} {hours_word(module.hours)})",
                "text": " ".join(lines),
                "theory_text": theory_text,
                "practice_text": practice_text,
                "form_text": form_text,
                "basic_text": basic_text,
                "advanced_text": advanced_text,
                "skills_text": skills_text,
                "abilities_text": abilities_text,
            }
        )

    for row, planned in zip(ktp_rows, lesson_dates(program.year, len(ktp_rows), program.lessons_per_week, program.calendar_mode)):
        row["date"] = planned

    results: list[str] = [fmt(phrases["subject_intro"], mapping), "Личностные результаты:"]
    results.extend(f"— {fmt(item, mapping)}" for item in phrases["personal_results"])
    results.append("Метапредметные результаты:")
    results.extend(f"— {fmt(item, mapping)}" for item in phrases["meta_results"])
    for band in bands:
        results.append(f"Предметные результаты для обучающихся {band['label']}:")
        pool = list(spoken.get("subject") or [fmt(item, mapping) for item in voice["subject"]])
        pool.extend(phrases["subject_common"])
        if band["tone"] == "young":
            pool.extend(phrases["subject_junior"])
            support = phrases["subject_support_junior"]
        elif band["tone"] == "old":
            pool.extend(phrases["subject_senior"])
            support = phrases["subject_support_senior"]
        elif band["tone"] == "middle":
            pool.extend(phrases["subject_middle"])
            support = phrases["subject_support_middle"]
        else:
            support = phrases["subject_support_common"]
        results.extend(f"— {_show(item, mapping)}" for item in pool)
        results.append(fmt(support, mapping))

    equipment = program.equipment.strip() or profile["equipment"]
    material = [
        equipment,
        phrases["conditions_material_extra"],
    ]
    information = [phrases["conditions_software_extra"]]
    staffing = [fmt(phrases["conditions_staff"], mapping)]
    sanitary = [fmt(phrases["conditions_sanitary"], mapping)]
    methodical = [spoken.get("method") or fmt(voice["method"], mapping), phrases["conditions_method"]]

    upbringing_tasks = [fmt(item, mapping) for item in phrases["upbringing_tasks"]]
    upbringing_results = [f"— {fmt(item, mapping)}" for item in phrases["upbringing_results"]]
    events: list[dict[str, str]] = []
    for event in phrases["events"]:
        events.append(
            {
                "when": fmt(event["when"], mapping),
                "name": fmt(event["name"], mapping),
                "form": fmt(event["form"], mapping),
            }
        )
    if program.regional_project:
        event = phrases["event_regional"]
        events.append({key: fmt(event[key], mapping) for key in ("when", "name", "form")})
    if program.professional_trials:
        event = phrases["event_trials"]
        events.append({key: fmt(event[key], mapping) for key in ("when", "name", "form")})
    parent_event = phrases["event_parents"]
    events.append({key: fmt(parent_event[key], mapping) for key in ("when", "name", "form")})

    assessment = [fmt(item, mapping) for item in phrases["assessment_intro"]]
    if program.interim_attestation:
        # Вставляем перед абзацем про итоговую аттестацию — он четвёртый в списке (индекс 3).
        assessment.insert(3, fmt(phrases["assessment_interim"], mapping))

    criteria: list[dict[str, str]] = []
    for item in phrases["criteria"]:
        criteria.append({key: fmt(item[key], mapping) for key in ("name", "low", "mid", "high")})
    if program.final_project:
        item = phrases["criterion_product"]
        criteria.append({key: fmt(item[key], mapping) for key in ("name", "low", "mid", "high")})
    if program.professional_trials:
        item = phrases["criterion_trials"]
        criteria.append({key: fmt(item[key], mapping) for key in ("name", "low", "mid", "high")})
    if program.regional_project:
        item = phrases["criterion_regional"]
        criteria.append({key: fmt(item[key], mapping) for key in ("name", "low", "mid", "high")})

    calendar_rows = build_calendar_rows(program.calendar_mode, program.years, program.total_hours)
    ktp_hours = sum(int(row["hours"]) for row in ktp_rows)

    bullet = lambda lines: [f"— {line}" if not line.startswith("—") else line for line in lines]
    normative_items = _normative_items(program, mapping)
    distinctive_items = _distinctive_items(
        program, mapping, practice_percent, voice, spoken.get("distinctive"), bands
    )
    level_paragraphs = [
        (
            f"Программа реализуется на {mapping['level_full']} уровне. "
            f"Она рассчитана на обучающихся, которые осваивают содержание {mapping['level_method']}. "
            f"Объём — {program.total_hours} {mapping['hours_word']} ({mapping['years_text']})."
        )
    ]
    direction_paragraphs = [f"Программа имеет {program.direction} направленность."]
    age_rows = [
        {
            "label": band["label"],
            "explain": band["explain"],
            "independence": band["independence"],
            "product": band["product"],
        }
        for band in bands
    ]
    link_rows = []
    for task, tool in zip(teaching[:4], ("наблюдение и стартовое задание", "практическая работа", "представление результата", "беседа и мини-проект")):
        link_rows.append({"task": task, "result": "действие видно на занятии и в продукте раздела", "tool": tool})
    blank_count = min(max(program.group_max, 1), 12)
    blank_rows = [{"num": str(index), "fio": ""} for index in range(1, blank_count + 1)]
    software_items = _split_lines(program.software.strip() or profile["software"])
    consumable_paragraphs = _split_lines(program.consumables.strip()) or [
        "Расходные материалы — по теме программы и заявке педагога на учебный год."
    ]
    room_paragraphs = [
        program.room.strip()
        or (
            f"Кабинет организации «{mapping['organization']}» должен соответствовать СП 2.4.2.4283-26 "
            "и СанПиН 1.2.3685-21. Занятия с оборудованием, где нужна особая осторожность, идут под наблюдением педагога."
        )
    ]
    staff_extra = (
        "К реализации допускаются лица, которые соответствуют требованиям к педагогическим работникам "
        "дополнительного образования и могут вести программу этой направленности."
    )
    subjects_paragraphs = [
        program.subjects.strip()
        or "Межпредметные связи педагог проводит через практические задания: труд (технология), математика и язык направления."
    ]
    professions_paragraphs = _profession_paragraphs(program, mapping)
    schedule_rows = [
        {
            "group": "1",
            "study_year": mapping["academic_year"],
            "start": _period_edge(program, start=True),
            "finish": _period_edge(program, start=False),
            "weeks": str(program.study_weeks),
            "days": str(study_days),
            "hours": str(program.total_hours),
            "mode": (
                f"{program.lessons_per_week} раза в неделю по {program.lesson_hours} ч., "
                f"час {program.academic_minutes} мин., перерыв {program.break_minutes} мин."
            ),
        }
    ]
    literature = list(spoken.get("literature") or [])
    literature_manual = not literature

    preview = [
        f"Название: {mapping['title']}",
        f"Направленность: {program.direction}. Уровень: {mapping['level_full']}.",
        (
            f"Возраст: {mapping['age_text']}. Промежутки: "
            + (", ".join(band["label"] for band in bands) if program.differentiate and len(bands) >= 2 else "без деления")
            + "."
        ),
        f"Срок: {mapping['years_text']}. Объём: {program.total_hours} {mapping['hours_word']}. В неделю: {program.hours_per_week}.",
        f"Группа: {mapping['group_text']}. Форма: {program.study_form}.",
        f"Организация: {mapping['organization']}.",
        f"Педагог: {mapping['teacher_name']}, {mapping['teacher_position']}.",
        f"Место: {mapping['city']}, {mapping['region']}.",
        f"Итоговая аттестация: {program.attestation_form}.",
        "Разделы:",
        *[f"• {item['name']} — {item['hours']} ч. (теория {item['theory']}, практика {item['practice']})" for item in module_views],
        f"Сумма разделов: {module_sum} ч.",
        "Цель:",
        goal_text or "Цель появится после формулировки нейросетью.",
    ]

    return {
        "has_logo": True,
        "organization": mapping["organization"],
        "year": mapping["year"],
        "title": mapping["title"],
        "direction": program.direction,
        "direction_gen": profile["name_gen"],
        "level_full": mapping["level_full"],
        "age_text": mapping["age_text"],
        "years_text": mapping["years_text"],
        "total_hours": str(program.total_hours),
        "hours_word": mapping["hours_word"],
        "teacher_name": mapping["teacher_name"],
        "teacher_position": mapping["teacher_position"],
        "city": mapping["city"],
        "region": mapping["region"],
        "authority": program.authority.strip(),
        "department": program.department.strip(),
        "org_short": mapping["org_short"],
        "director_position": mapping["director_position"],
        "director_name": mapping["director_name"],
        "academic_year": mapping["academic_year"],
        "header_short": _short_title(mapping["title"]),
        "study_form": program.study_form,
        "attestation_form": program.attestation_form,
        "normative_items": normative_items,
        "distinctive_items": distinctive_items,
        "level_paragraphs": level_paragraphs,
        "direction_paragraphs": direction_paragraphs,
        "overview_paragraphs": overview,
        "relevance_paragraphs": relevance,
        "novelty_paragraphs": novelty,
        "expediency_paragraphs": expediency,
        "addressee_paragraphs": addressee,
        "volume_paragraphs": volume,
        "features_paragraphs": features,
        "goal_paragraphs": goal,
        "goal_manual": goal_manual,
        "goal_ready": not goal_manual,
        "tasks_teaching": bullet(teaching),
        "tasks_developing": bullet(developing),
        "tasks_educating": bullet(educating),
        "modules": module_views,
        "modules_total_theory": str(theory_sum),
        "modules_total_practice": str(practice_sum),
        "modules_total_hours": str(module_sum),
        "curriculum_note": fmt(phrases["curriculum_note"], mapping),
        "result_paragraphs": results,
        "age_rows": age_rows,
        "link_rows": link_rows,
        "blank_rows": blank_rows,
        "software_items": software_items,
        "consumable_paragraphs": consumable_paragraphs,
        "room_paragraphs": room_paragraphs,
        "subjects_paragraphs": subjects_paragraphs,
        "professions_paragraphs": professions_paragraphs,
        "schedule_rows": schedule_rows,
        "staff_extra": staff_extra,
        "material_paragraphs": material,
        "information_paragraphs": information,
        "staffing_paragraphs": staffing,
        "sanitary_paragraphs": sanitary,
        "methodical_paragraphs": methodical,
        "upbringing_goal_paragraphs": [fmt(phrases["upbringing_goal"], mapping)],
        "upbringing_tasks": bullet(upbringing_tasks),
        "upbringing_forms_paragraphs": [
            fmt(phrases["upbringing_forms"], mapping),
            fmt(phrases["upbringing_parents"], mapping),
        ],
        "events": events,
        "upbringing_results": upbringing_results,
        "assessment_paragraphs": assessment,
        "criteria": criteria,
        "calendar_rows": calendar_rows,
        "kug_note": phrases["kug_note"] + " " + _calendar_sentence(program.calendar_mode),
        "ktp_rows": ktp_rows,
        "ktp_hours": str(ktp_hours),
        "ktp_note": fmt(phrases["ktp_note"], mapping),
        "literature": literature,
        "literature_manual": literature_manual,
        "literature_ready": not literature_manual,
        "upbringing_base": program.upbringing_base.strip()
        or f"программа воспитания {mapping['org_short']}",
        "preview_lines": preview,
    }


def _period_edge(program: ProgramData, start: bool) -> str:
    if program.calendar_mode.startswith("лето"):
        return f"01.06.{program.year}" if start else f"31.08.{program.year}"
    if program.calendar_mode.startswith("календарный"):
        return f"08.01.{program.year}" if start else f"20.12.{program.year}"
    return f"08.09.{program.year}" if start else f"31.05.{program.year + 1}"


def _split_lines(text: str) -> list[str]:
    parts = [part.strip(" ;\t") for part in text.replace(";", "\n").splitlines()]
    return [part for part in parts if part]


def _normative_items(program: ProgramData, mapping: dict) -> list[str]:
    return [
        "Федеральный закон от 29.12.2012 № 273-ФЗ «Об образовании в Российской Федерации».",
        "Концепция развития дополнительного образования детей до 2030 года, утверждённая распоряжением Правительства Российской Федерации от 31.03.2022 № 678-р (в редакции распоряжения от 01.07.2025 № 1745-р).",
        "Приказ Министерства просвещения Российской Федерации от 27.07.2022 № 629 «Об утверждении Порядка организации и осуществления образовательной деятельности по дополнительным общеобразовательным программам».",
        "Приказ Министерства просвещения Российской Федерации от 03.09.2019 № 467 «Об утверждении Целевой модели развития региональных систем дополнительного образования детей».",
        "Санитарные правила СП 2.4.2.4283-26 «Санитарно-эпидемиологические требования к организациям воспитания и обучения, отдыха и оздоровления детей и молодёжи» (постановление Главного государственного санитарного врача Российской Федерации от 02.06.2026 № 19, вступают в силу с 01.09.2026).",
        "СанПиН 1.2.3685-21 «Гигиенические нормативы и требования к обеспечению безопасности и (или) безвредности для человека факторов среды обитания» (постановление Главного государственного санитарного врача Российской Федерации от 28.01.2021 № 2).",
        "Письмо Министерства просвещения Российской Федерации от 23.01.2026 № АБ-254/06.",
        "Письмо Министерства просвещения Российской Федерации от 29.09.2023 № АБ-3935/06.",
        "Письмо Министерства образования и науки Российской Федерации от 18.11.2015 № 09-3242 «О направлении информации» (методические рекомендации по проектированию дополнительных общеразвивающих программ).",
        f"Локальные нормативные акты {mapping['organization']}.",
    ]


def _level_close(level: str) -> str:
    notes = {
        "стартовый": "На стартовом уровне задача — узнать дело и довести до конца образец. Профессию программа не даёт.",
        "базовый": "На базовом уровне обучающийся применяет приём в задании, которое уже не повторяет образец шаг в шаг.",
        "продвинутый": "На продвинутом уровне обучающийся сам выбирает способ и объясняет, почему он подходит к этой работе.",
    }
    return notes.get(level, notes["базовый"])


def _spoken(program: ProgramData) -> dict:
    """Готовые формулировки под название. Пустые поля остаются на тексте направленности."""
    raw = program.generated if isinstance(program.generated, dict) else {}
    spoken: dict = {}
    for key in ("relevance", "novelty", "distinctive", "expediency", "tasks", "subject", "addressee", "educating"):
        items = _plain_list(raw.get(key))
        if items:
            spoken[key] = items
    developing = raw.get("developing")
    if isinstance(developing, list):
        items = _plain_list(developing)
        if items:
            spoken["developing_tasks"] = items
    elif str(developing or "").strip():
        spoken["developing"] = str(developing).strip()
    goal = str(raw.get("goal") or raw.get("goal_note") or "").strip()
    if goal:
        spoken["goal"] = goal
    literature = _plain_list(raw.get("literature"))
    if literature:
        spoken["literature"] = literature
    for key in ("goal_note", "method"):
        text = str(raw.get(key) or "").strip()
        if text:
            spoken[key] = text
    modules = raw.get("modules")
    if isinstance(modules, list):
        spoken["modules"] = modules
    return spoken


def _plain_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _module_speech(spoken: dict, index: int) -> dict[str, str]:
    rows = spoken.get("modules")
    if not isinstance(rows, list) or index >= len(rows) or not isinstance(rows[index], dict):
        return {}
    return normalize_module_row(rows[index])


def _labeled(label: str, text: str) -> str:
    body = " ".join(str(text or "").split()).strip()
    if not body:
        return ""
    if body[-1] not in ".!?":
        body += "."
    if body.casefold().startswith(label.casefold()):
        return body
    return f"{label}: {body}"


def _distinctive_items(
    program: ProgramData,
    mapping: dict,
    practice_percent: int,
    voice: dict,
    custom: list[str] | None,
    bands: list[dict[str, str]] | None = None,
) -> list[str]:
    items = list(custom) if custom else [fmt(item, mapping) for item in voice["distinctive"]]
    if program.differentiate and bands and len(bands) >= 2:
        pieces = "; ".join(f"для {band['label']} — {band['support']}" for band in bands)
        items.append(f"Возрастные промежутки этой программы: {pieces}.")
    items.append(f"Практическая доля — около {practice_percent} % часов.")
    items.append("У каждого раздела есть теория, практика, обязательное задание, задание с усложнением и форма контроля.")
    if program.professional_trials:
        items.append("В программу включены профессиональные пробы.")
    if program.regional_project:
        items.append(f"Есть региональный компонент: {mapping['city']}, {mapping['region']}.")
    return items


def _profession_paragraphs(program: ProgramData, mapping: dict) -> list[str]:
    if program.professions.strip():
        return [
            f"Обучающиеся знакомятся с ролями: {program.professions.strip()} "
            "Знакомство не заменяет профессиональное обучение."
        ]
    return [
        f"Профессии и роли педагог называет через практические задания направления «{mapping['activity_nom']}». "
        "Это знакомство, а не профессиональное обучение."
    ]


