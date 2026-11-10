# -*- coding: utf-8 -*-
"""Модель данных программы.

Педагог заполняет один объект ProgramData.
Из него шаблоны собирают текст, а генератор — файл .docx.
Нейросеть не используется: в модели только факты и переключатели.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Шесть направленностей дополнительного образования.
DIRECTIONS = [
    "техническая",
    "естественнонаучная",
    "физкультурно-спортивная",
    "художественная",
    "туристско-краеведческая",
    "социально-гуманитарная",
]

# Уровни из порядка реализации дополнительных программ.
# В документе к стартовому и продвинутому добавляются привычные синонимы.
LEVELS = ["стартовый", "базовый", "продвинутый"]

LEVEL_FULL = {
    "стартовый": "стартовый (ознакомительный)",
    "базовый": "базовый",
    "продвинутый": "продвинутый (углублённый)",
}

# Как именно звучит степень самостоятельности на каждом уровне.
LEVEL_METHOD = {
    "стартовый": "по образцу и вместе с педагогом",
    "базовый": "по инструкции и в частично изменённой ситуации",
    "продвинутый": "самостоятельно, перенося освоенный способ на новый замысел",
}

STUDY_FORMS = [
    "очная",
    "очно-заочная",
    "заочная",
    "очная с применением дистанционных технологий",
]

CALENDAR_MODES = [
    "учебный год (сентябрь–май)",
    "лето (июнь–август)",
    "календарный год (январь–декабрь)",
]

ATTESTATION_FORMS = [
    "защита итогового проекта",
    "выставка или творческий показ",
    "зачёт",
    "соревнование или сдача нормативов",
    "представление исследования",
    "конференция объединения",
]

_INT_FIELDS = (
    "age_from",
    "age_to",
    "years",
    "total_hours",
    "hours_per_week",
    "lesson_hours",
    "group_min",
    "group_max",
    "year",
    "lessons_per_week",
    "academic_minutes",
    "break_minutes",
    "study_weeks",
)

_BOOL_FIELDS = (
    "differentiate",
    "professional_trials",
    "regional_project",
    "final_project",
    "interim_attestation",
    "excursions",
    "no_prior_training",
)


@dataclass
class ModuleItem:
    """Один раздел учебного плана."""

    name: str = ""
    theory: int = 0
    practice: int = 0
    lectures: list[str] = field(default_factory=list)
    practices: list[str] = field(default_factory=list)

    @property
    def hours(self) -> int:
        return int(self.theory) + int(self.practice)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "theory": int(self.theory),
            "practice": int(self.practice),
            "lectures": list(self.lectures),
            "practices": list(self.practices),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ModuleItem":
        return cls(
            name=str(raw.get("name", "")).strip(),
            theory=_as_int(raw.get("theory", 0)),
            practice=_as_int(raw.get("practice", 0)),
            lectures=_as_lines(raw.get("lectures")),
            practices=_as_lines(raw.get("practices")),
        )


@dataclass
class ProgramData:
    """Все ответы мастера. Это единственный источник для документа."""

    title: str = ""
    direction: str = "техническая"
    level: str = "базовый"
    organization: str = ""
    teacher_name: str = ""
    teacher_position: str = "педагог дополнительного образования"
    region: str = ""
    city: str = ""
    regional_notes: str = ""
    age_from: int = 11
    age_to: int = 17
    differentiate: bool = True
    years: int = 1
    total_hours: int = 144
    hours_per_week: int = 4
    lesson_hours: int = 2
    group_min: int = 8
    group_max: int = 12
    study_form: str = "очная"
    calendar_mode: str = "учебный год (сентябрь–май)"
    modules: list[ModuleItem] = field(default_factory=list)
    professional_trials: bool = False
    regional_project: bool = False
    final_project: bool = True
    interim_attestation: bool = True
    excursions: bool = False
    equipment: str = ""
    software: str = ""
    attestation_form: str = "защита итогового проекта"
    year: int = field(default_factory=lambda: datetime.now().year)
    # Поля шапки и условий по образцу полной программы.
    authority: str = ""
    department: str = ""
    org_short: str = ""
    director_position: str = "директор"
    director_name: str = ""
    lessons_per_week: int = 2
    academic_minutes: int = 45
    break_minutes: int = 10
    study_weeks: int = 36
    no_prior_training: bool = True
    partners: str = ""
    consumables: str = ""
    room: str = ""
    subjects: str = ""
    professions: str = ""
    upbringing_base: str = ""
    # Тексты, полученные по названию программы. Пустой словарь — остаются тексты направленности.
    generated: dict = field(default_factory=dict)
    # Связь с записью в «Моих программах». В текст документа и в запрос нейросети не входит.
    library_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "direction": self.direction,
            "level": self.level,
            "organization": self.organization,
            "teacher_name": self.teacher_name,
            "teacher_position": self.teacher_position,
            "region": self.region,
            "city": self.city,
            "regional_notes": self.regional_notes,
            "age_from": self.age_from,
            "age_to": self.age_to,
            "differentiate": self.differentiate,
            "years": self.years,
            "total_hours": self.total_hours,
            "hours_per_week": self.hours_per_week,
            "lesson_hours": self.lesson_hours,
            "group_min": self.group_min,
            "group_max": self.group_max,
            "study_form": self.study_form,
            "calendar_mode": self.calendar_mode,
            "modules": [item.to_dict() for item in self.modules],
            "professional_trials": self.professional_trials,
            "regional_project": self.regional_project,
            "final_project": self.final_project,
            "interim_attestation": self.interim_attestation,
            "excursions": self.excursions,
            "equipment": self.equipment,
            "software": self.software,
            "attestation_form": self.attestation_form,
            "year": self.year,
            "authority": self.authority,
            "department": self.department,
            "org_short": self.org_short,
            "director_position": self.director_position,
            "director_name": self.director_name,
            "lessons_per_week": self.lessons_per_week,
            "academic_minutes": self.academic_minutes,
            "break_minutes": self.break_minutes,
            "study_weeks": self.study_weeks,
            "no_prior_training": self.no_prior_training,
            "partners": self.partners,
            "consumables": self.consumables,
            "room": self.room,
            "subjects": self.subjects,
            "professions": self.professions,
            "upbringing_base": self.upbringing_base,
            "generated": self.generated if isinstance(self.generated, dict) else {},
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ProgramData":
        data = cls()
        modules_raw = raw.get("modules", [])
        for key, value in raw.items():
            if key in {"modules", "library_id"} or not hasattr(data, key):
                continue
            setattr(data, key, value)
        data.modules = []
        if isinstance(modules_raw, list):
            for item in modules_raw:
                if isinstance(item, dict):
                    data.modules.append(ModuleItem.from_dict(item))
        for name in _INT_FIELDS:
            setattr(data, name, _as_int(getattr(data, name)))
        for name in _BOOL_FIELDS:
            setattr(data, name, bool(getattr(data, name)))
        for name in (
            "title",
            "direction",
            "level",
            "organization",
            "teacher_name",
            "teacher_position",
            "region",
            "city",
            "regional_notes",
            "study_form",
            "calendar_mode",
            "equipment",
            "software",
            "attestation_form",
            "authority",
            "department",
            "org_short",
            "director_position",
            "director_name",
            "partners",
            "consumables",
            "room",
            "subjects",
            "professions",
            "upbringing_base",
        ):
            setattr(data, name, str(getattr(data, name) or "").strip())
        if not isinstance(data.generated, dict):
            data.generated = {}
        return data

    def save_draft(self) -> None:
        """Сохраняет черновик в профиле пользователя."""
        from core.paths import draft_path

        path = draft_path()
        temporary = path.with_suffix(".tmp")
        payload = {"version": 1, "library_id": self.library_id, "program": self.to_dict()}
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    @classmethod
    def load_draft(cls) -> tuple["ProgramData", bool]:
        """Возвращает черновик и признак, что файл удалось прочитать."""
        from core.paths import draft_path

        path = draft_path()
        if not path.exists():
            return cls(), False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            program = payload.get("program", payload)
            if not isinstance(program, dict):
                raise ValueError("Черновик повреждён")
            loaded = cls.from_dict(program)
            loaded.library_id = str(payload.get("library_id") or "")
            return loaded, True
        except Exception:
            backup = path.with_suffix(".bak")
            try:
                path.replace(backup)
            except OSError:
                pass
            return cls(), False

    def validate(self) -> list[str]:
        """Полная проверка перед сборкой документа."""
        errors: list[str] = []
        errors.extend(self.errors_passport())
        errors.extend(self.errors_learners())
        errors.extend(self.errors_plan())
        errors.extend(self.errors_conditions())
        return errors

    def errors_passport(self) -> list[str]:
        errors: list[str] = []
        if len(self.title.strip()) < 3:
            errors.append("Укажите название программы — не короче 3 символов.")
        elif len(self.title.strip()) > 200:
            errors.append("Название программы длиннее 200 символов.")
        if self.direction not in DIRECTIONS:
            errors.append("Выберите направленность из списка.")
        if self.level not in LEVELS:
            errors.append("Выберите уровень программы из списка.")
        if len(self.organization.strip()) < 3:
            errors.append("Укажите полное наименование организации.")
        elif len(self.organization) > 300:
            errors.append("Наименование организации длиннее 300 символов.")
        if len(self.teacher_name.strip()) < 3:
            errors.append("Укажите ФИО педагога.")
        if len(self.teacher_position.strip()) < 3:
            errors.append("Укажите должность педагога.")
        if len(self.region.strip()) < 2:
            errors.append("Укажите регион (субъект Российской Федерации).")
        if len(self.city.strip()) < 2:
            errors.append("Укажите город или населённый пункт.")
        if self.year < 2020 or self.year > 2040:
            errors.append("Год программы должен быть в пределах 2020–2040.")
        return errors

    def errors_learners(self) -> list[str]:
        errors: list[str] = []
        if self.age_from < 0 or self.age_to < 0:
            errors.append("Возраст нужно указать целыми числами.")
        elif not (5 <= self.age_from <= 18 and 5 <= self.age_to <= 18):
            errors.append("Возраст обучающихся должен быть в пределах от 5 до 18 лет.")
        elif self.age_from > self.age_to:
            errors.append("Возраст «от» не может быть больше возраста «до».")
        if self.years < 1 or self.years > 5:
            errors.append("Срок реализации — от 1 до 5 лет.")
        if self.total_hours < 8 or self.total_hours > 2000:
            errors.append("Объём программы — от 8 до 2000 часов.")
        if self.hours_per_week < 1 or self.hours_per_week > 40:
            errors.append("Нагрузка в неделю — от 1 до 40 часов.")
        if self.lesson_hours not in (1, 2, 3, 4):
            errors.append("Длительность занятия — 1, 2, 3 или 4 академических часа.")
        elif self.total_hours > 0 and self.lesson_hours > self.total_hours:
            errors.append("Одно занятие не может быть длиннее всего объёма программы.")
        if self.group_min < 0 or self.group_max < 0:
            errors.append("Наполняемость группы нужно указать целыми числами.")
        elif self.group_min < 1 or self.group_max < 1:
            errors.append("В группе должен быть хотя бы один обучающийся.")
        elif self.group_min > self.group_max:
            errors.append("Минимальная наполняемость больше максимальной.")
        elif self.group_max > 40:
            errors.append("Максимальная наполняемость — не больше 40 человек.")
        if self.study_form not in STUDY_FORMS:
            errors.append("Выберите форму обучения из списка.")
        if self.calendar_mode not in CALENDAR_MODES:
            errors.append("Выберите календарный режим из списка.")
        if self.lessons_per_week < 1 or self.lessons_per_week > 6:
            errors.append("Занятий в неделю — от 1 до 6.")
        elif self.lesson_hours in (1, 2, 3, 4) and self.hours_per_week > 0:
            expected = self.lessons_per_week * self.lesson_hours
            if expected != self.hours_per_week:
                errors.append(
                    f"Не сходится режим: {self.lessons_per_week} зан. × {self.lesson_hours} ч. = {expected} ч., "
                    f"а в неделю указано {self.hours_per_week} ч."
                )
        if self.academic_minutes not in (30, 35, 40, 45):
            errors.append("Длительность академического часа — 30, 35, 40 или 45 минут.")
        if self.break_minutes < 0 or self.break_minutes > 20:
            errors.append("Перерыв — от 0 до 20 минут.")
        if self.study_weeks < 1 or self.study_weeks > 40:
            errors.append("Учебных недель — от 1 до 40.")
        return errors

    def errors_plan(self) -> list[str]:
        errors: list[str] = []
        if not self.modules:
            errors.append("Добавьте хотя бы один раздел учебного плана.")
            return errors
        total = 0
        for index, module in enumerate(self.modules, start=1):
            if module.theory < 0 or module.practice < 0:
                errors.append(f"В разделе {index} часы должны быть целыми числами больше либо равными нулю.")
                continue
            if not module.name.strip():
                errors.append(f"Укажите название раздела {index}.")
            elif len(module.name.strip()) > 200:
                errors.append(f"Название раздела {index} длиннее 200 символов.")
            if module.hours <= 0:
                errors.append(f"У раздела «{module.name or index}» не указаны часы.")
            total += max(module.hours, 0)
        if self.total_hours > 0 and total != self.total_hours:
            errors.append(
                f"Сумма часов разделов ({total}) не равна объёму программы ({self.total_hours}). "
                "Нажмите «Распределить часы» или поправьте строки."
            )
        return errors

    def errors_conditions(self) -> list[str]:
        errors: list[str] = []
        if self.attestation_form not in ATTESTATION_FORMS:
            errors.append("Выберите форму итоговой аттестации из списка.")
        if "проект" in self.attestation_form and not self.final_project:
            errors.append(
                "Итоговая форма — защита проекта, но итоговый проект выключен. "
                "Включите его на шаге учебного плана или выберите другую форму аттестации."
            )
        if len(self.equipment) > 4000:
            errors.append("Текст об оборудовании длиннее 4000 символов.")
        if len(self.software) > 4000:
            errors.append("Текст о программном обеспечении длиннее 4000 символов.")
        if len(self.regional_notes) > 4000:
            errors.append("Текст о региональных особенностях длиннее 4000 символов.")
        for label, value in (
            ("о партнёрах и экскурсиях", self.partners),
            ("о расходных материалах", self.consumables),
            ("о помещении", self.room),
            ("о межпредметных связях", self.subjects),
            ("о профессиях", self.professions),
        ):
            if len(value) > 2000:
                errors.append(f"Текст {label} длиннее 2000 символов.")
        return errors


def _as_lines(value: Any) -> list[str]:
    """Список коротких тем: из списка или из текста, где каждая тема с новой строки."""
    if isinstance(value, str):
        source = value.splitlines()
    elif isinstance(value, list):
        source = value
    else:
        return []
    lines: list[str] = []
    for item in source:
        text = " ".join(str(item or "").split())
        if len(text) < 3:
            continue
        lines.append(text[:180])
        if len(lines) >= 24:
            break
    return lines


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1
