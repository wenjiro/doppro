# -*- coding: utf-8 -*-
"""Проверка сборки документа без открытия окна.

Запуск: python tools/selfcheck.py
"""

from __future__ import annotations

import json
import re
import ssl
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from docx import Document

from core.data_model import DIRECTIONS, ProgramData
from core.generator import anonymous_brief, equipment_brief, normalize_module_row, parse_equipment, parse_plan, parse_sections, plan_brief
from core.document_builder import build_document
from core.planning import default_modules, study_day_loads
from core.library import duplicate_program, export_program, import_program, list_programs, load_program, save_program
from core.paths import project_root
from core.updates import is_newer
from gui.onboarding import PAGES, onboarding_seen
from core.templates_engine import build_context, profile_for
from core.tls import app_ssl_context


_MARKERS = {
    "техническая": "схем",
    "естественнонаучная": "наблюден",
    "физкультурно-спортивная": "разминк",
    "художественная": "эскиз",
    "туристско-краеведческая": "карточк",
    "социально-гуманитарная": "договор",
}


def _sample(direction: str) -> ProgramData:
    program = ProgramData(
        title="Техническая мастерская города" if direction == "техническая" else f"Проба {direction}",
        direction=direction,
        level="базовый",
        organization="МБУ ДО «Дворец творчества»",
        teacher_name="Иванова Мария Сергеевна",
        teacher_position="педагог дополнительного образования",
        region="Свердловская область",
        city="Екатеринбург",
        regional_notes="Берём городские примеры, без выхода на производство без допуска.",
        age_from=11,
        age_to=17,
        differentiate=True,
        years=1,
        total_hours=144,
        hours_per_week=4,
        lesson_hours=2,
        group_min=8,
        group_max=12,
        study_form="очная",
        calendar_mode="учебный год (сентябрь–май)",
        professional_trials=True,
        regional_project=True,
        final_project=True,
        interim_attestation=True,
        excursions=True,
        software="Scratch & LibreOffice (офлайн)",
        attestation_form="защита итогового проекта",
        year=2026,
    )
    program.modules = default_modules(direction, program.total_hours)
    return program


def _text(document: Document) -> str:
    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


def _table_with(document: Document, header: str):
    for table in document.tables:
        if not table.rows:
            continue
        if any(header in cell.text for cell in table.rows[0].cells):
            return table
    raise AssertionError(f"Нет таблицы с заголовком «{header}»")


def check_direction(direction: str, folder: Path) -> None:
    program = _sample(direction)
    assert not program.validate(), program.validate()
    context = build_context(program)
    assert context["modules_total_hours"] == "144"
    assert sum(int(row["hours"]) for row in context["ktp_rows"]) == 144
    assert any(row["lecture"] != "—" and row["practice"] != "—" for row in context["ktp_rows"])
    assert sum(int(row["theory_hours"]) for row in context["ktp_rows"]) == sum(item.theory for item in program.modules)
    assert sum(int(row["practice_hours"]) for row in context["ktp_rows"]) == sum(item.practice for item in program.modules)
    assert sum(int(row["hours"]) for row in context["calendar_rows"]) == 144
    profile_for(direction)

    target = folder / f"{direction}.docx"
    build_document(program, str(target))
    document = Document(str(target))
    text = _text(document)
    assert "{%" not in text and "{{" not in text, direction
    assert program.title in text
    assert "Екатеринбург" in text
    assert "Иванова Мария Сергеевна" in text
    assert "11–13" in text and "14–17" in text
    assert "профессиональн" in text.lower()
    assert text.count("Scratch & LibreOffice") == 1, direction
    assert "СП 2.4.2.4283-26" in text
    assert "Бланк 1" in text
    assert "Нормативно-правовая база" in text
    assert _MARKERS[direction] in text.lower(), direction
    assert re.search(r"\d{2}\.\d{2}\.\d{4}", context["ktp_rows"][0]["date"])
    assert "ДопПро" in document.sections[0].header.paragraphs[0].text
    assert "Укажите литературу вручную" in text
    assert "Цель формулирует нейросеть" in text
    assert "освоение обучающимися" not in text
    assert "TOC" in document.element.xml
    assert "PAGE" in document.sections[0].footer._element.xml
    section_heading = next(paragraph for paragraph in document.paragraphs if paragraph.text.startswith("Раздел 1."))
    assert not section_heading.paragraph_format.page_break_before
    assert "«" in section_heading.text
    joined = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "Теория:" in joined and "Практика:" in joined and "Форма занятий:" in joined
    assert "Усложнённое задание:" in joined and "Навыки:" in joined and "Умения:" in joined

    curriculum = _table_with(document, "Раздел / тема")
    body_hours = 0
    total_cell = ""
    for row in curriculum.rows[1:]:
        cells = [cell.text.strip() for cell in row.cells]
        if cells[1] == "Итого":
            total_cell = cells[2]
            continue
        if cells[2].isdigit():
            body_hours += int(cells[2])
    assert body_hours == 144, (direction, body_hours)
    assert total_cell == "144"

    ktp = _table_with(document, "Тема лекции")
    ktp_hours = 0
    saw_both = False
    for row in ktp.rows[1:]:
        cells = [cell.text.strip() for cell in row.cells]
        if "Итого" in cells:
            assert "144" in cells
            continue
        if len(cells) > 5 and cells[4] not in {"", "—"} and cells[5] not in {"", "—"}:
            saw_both = True
        if len(cells) > 3 and cells[3].isdigit():
            ktp_hours += int(cells[3])
    assert ktp_hours == 144, (direction, ktp_hours)
    assert saw_both, direction
    images = [rel for rel in document.part.rels.values() if "image" in rel.reltype]
    assert images, direction


def main() -> None:
    assert len(PAGES) == 5 and all(title and len(text) > 40 for title, text in PAGES)
    assert onboarding_seen() in (True, False)
    assert is_newer("v1.2.0", "1.0.0")
    assert not is_newer("1.0.0", "1.0.0")
    assert not is_newer("v0.9.0", "1.0.0")
    with tempfile.TemporaryDirectory() as folder_name:
        folder = Path(folder_name)
        first = ProgramData(title="Хореография", direction="художественная")
        second = ProgramData(title="Робототехника", direction="техническая")
        save_program(first, folder)
        save_program(second, folder)
        assert first.library_id and first.library_id != second.library_id
        assert "library_id" not in first.to_dict()
        titles = {item.title for item in list_programs(folder)}
        assert titles == {"Хореография", "Робототехника"}
        copy_id = duplicate_program(first.library_id, folder)
        assert load_program(copy_id, folder).title == "Хореография — копия"
        exported = folder / "out.json"
        export_program(first, exported)
        blob = exported.read_text(encoding="utf-8")
        assert "gemini_api_key" not in blob
        imported = import_program(exported, folder)
        assert imported.title == "Хореография"
        assert imported.library_id not in {first.library_id, second.library_id, copy_id}
    bundle = (project_root() / "certs" / "russian_trusted_ca.pem").read_text(encoding="utf-8")
    assert bundle.count("BEGIN CERTIFICATE") == 3
    assert app_ssl_context().verify_mode == ssl.CERT_REQUIRED
    empty = ProgramData()
    assert empty.validate(), "пустая программа должна не проходить проверку"
    probe = _sample("техническая")
    brief_blob = json.dumps(anonymous_brief(probe), ensure_ascii=False)
    assert "Иванова" not in brief_blob
    assert "Дворец" not in brief_blob
    assert anonymous_brief(probe)["age_spans"] == ["11–13", "14–17"]
    custom = _sample("художественная")
    custom.age_from = 6
    custom.age_to = 12
    custom.age_spans = [{"from": 6, "to": 8}, {"from": 9, "to": 10}, {"from": 11, "to": 12}]
    assert not custom.errors_learners(), custom.errors_learners()
    custom_context = build_context(custom)
    assert [row["label"] for row in custom_context["age_rows"]] == ["6–8 лет", "9–10 лет", "11–12 лет"]
    custom_text = "\n".join(custom_context["addressee_paragraphs"] + custom_context["distinctive_items"])
    assert "6–8" in custom_text and "9–10" in custom_text and "11–12" in custom_text
    assert "11–13" not in custom_text and "14–17" not in custom_text
    assert anonymous_brief(custom)["age_spans"] == ["6–8", "9–10", "11–12"]
    overlap = _sample("техническая")
    overlap.age_spans = [{"from": 11, "to": 14}, {"from": 14, "to": 17}]
    assert any("пересек" in item for item in overlap.errors_learners())
    made = parse_sections(
        json.dumps(
            {
                "relevance": [
                    "Программа про 3D-моделирование учит собирать модель в Blender и проверять её перед печатью на занятии кружка.",
                    "Второй абзац объясняет, чем печать отличается от рисунка. Приказ Минпросвещения № 629 сюда не входит.",
                ],
                "novelty": [
                    "Новизна в цикле модель, слайс, печать и разбор одной ошибки, а не в общем рассказе о технике.",
                    "Для младших есть образец детали, для старших свой корпус и объяснение, почему выбрана такая форма.",
                ],
                "distinctive": [
                    "Результат раздела — модель, которую можно отправить на печать.",
                    "Ошибка ищется пробной печатью или проверкой сетки.",
                    "Слайсер используется только после готовой модели.",
                ],
                "expediency": ["Целесообразность в том, что понятие закрепляется моделью, а не пересказом."],
                "goal_note": "К концу срока обучающийся печатает простую деталь и объясняет, что поправил.",
                "tasks": [
                    "Научить собирать простую модель в редакторе.",
                    "Научить готовить модель к печати и находить одну ошибку сетки.",
                ],
                "addressee": [
                    "Программа адресована подросткам, которые хотят собирать и печатать простую деталь, без отбора до первого занятия.",
                ],
                "developing": [
                    "Развивать привычку сверять модель с критериями до печати.",
                    "Развивать умение объяснить, какую ошибку сетки нашёл.",
                ],
                "educating": [
                    "Воспитывать аккуратность при работе с оборудованием кабинета.",
                    "Воспитывать ответственность за свой результат на занятии.",
                ],
                "literature": [
                    "Копосов, Д. Г. Технология. 3D-моделирование, прототипирование и макетирование : учебник / Д. Г. Копосов. — Москва : Просвещение, 2021. — 160 с.",
                ],
                "method": "Занятие идёт от эскиза к модели, затем к проверке сетки и одной правке.",
                "subject": [
                    "собирает простую модель по образцу",
                    "находит ошибку сетки",
                    "готовит модель к печати",
                    "объясняет одну правку",
                ],
                "modules": [
                    {"theory": "Теория вводного раздела про интерфейс редактора.", "practice": "Практика: сохранить первую модель.", "tasks": "Обязательно повторить образец. Усложнение — изменить одну деталь."},
                    {"theory": "Теория второго раздела.", "practice": "Практика второго раздела.", "tasks": "Задание второго раздела с обязательной частью и усложнением."},
                    {"theory": "Теория третьего раздела.", "practice": "Практика третьего раздела.", "tasks": "Задание третьего раздела с обязательной частью и усложнением."},
                    {"theory": "Теория четвёртого раздела.", "practice": "Практика четвёртого раздела.", "tasks": "Задание четвёртого раздела с обязательной частью и усложнением."},
                    {"theory": "Теория пятого раздела.", "practice": "Практика пятого раздела.", "tasks": "Задание пятого раздела с обязательной частью и усложнением."},
                ],
            },
            ensure_ascii=False,
        ),
        5,
    )
    assert "629" not in " ".join(made["relevance"])
    planned = parse_plan(
        json.dumps(
            {
                "modules": [
                    {"name": "Введение в Blender и безопасность", "theory": 1, "practice": 1},
                    {"name": "Моделирование простой детали", "theory": 2, "practice": 10},
                    {"name": "Подготовка модели к печати", "theory": 2, "practice": 8},
                    {"name": "Пробная печать", "theory": 1, "practice": 6},
                    {"name": "Итоговая модель и защита", "theory": 2, "practice": 4},
                ]
            },
            ensure_ascii=False,
        ),
        144,
    )
    assert sum(item.hours for item in planned) == 144
    assert planned[0].name.startswith("Введение в Blender")
    assert all(item.hours > 0 for item in planned)
    titled = parse_plan(
        json.dumps(
            {
                "modules": [
                    {
                        "name": "Введение и безопасность",
                        "theory": 2,
                        "practice": 6,
                        "lectures": ["Правила кабинета"],
                        "practices": ["Первая деталь по образцу", "Проверка сетки"],
                    },
                    {"name": "Основной приём", "theory": 4, "practice": 20},
                    {"name": "Сборка изделия", "theory": 4, "practice": 16},
                    {"name": "Пробная работа", "theory": 2, "practice": 12},
                    {"name": "Итог и защита", "theory": 4, "practice": 8},
                ]
            },
            ensure_ascii=False,
        ),
        144,
    )
    assert titled[0].lectures == ["Правила кабинета"]
    assert titled[0].practices[0].startswith("Первая деталь")
    loads = study_day_loads(8, 34, 2)
    assert sum(item[0] for item in loads) == 8
    assert sum(item[1] for item in loads) == 34
    assert all(item[0] + item[1] == 2 for item in loads)
    assert loads[0] == (1, 1)
    probe.generated = made
    spoken = build_context(probe)
    assert "Blender" in spoken["relevance_paragraphs"][0]
    assert "печатает простую деталь" in spoken["goal_paragraphs"][0]
    assert "подросткам" in spoken["addressee_paragraphs"][0]
    assert any("критериями до печати" in item for item in spoken["tasks_developing"])
    assert any("аккуратность" in item for item in spoken["tasks_educating"])
    assert spoken["literature"][0].startswith("Копосов")
    dance = _sample("художественная")
    dance.title = "Современная хореография"
    dance.software = "Blender — моделирование"
    dance.professions = "3D-моделлер; оператор 3D-принтера"
    dance_brief = plan_brief(dance)
    assert dance_brief["title"] == "Современная хореография"
    assert dance_brief["software"] == ""
    assert dance_brief["professions"] == ""
    assert "modules" not in dance_brief
    dance.modules[0].name = "Моделирование в Blender"
    outfit = equipment_brief(dance)
    assert "software" not in outfit
    assert "professions" not in outfit
    assert "Иванова" not in json.dumps(outfit, ensure_ascii=False)
    assert "Blender" not in json.dumps(outfit, ensure_ascii=False)
    made_outfit = parse_equipment(
        json.dumps(
            {
                "equipment": ["станок", "стол для репетиции", "Blender и 3D-принтер", "зеркало"],
                "consumables": ["ткань для костюма", "пластик для 3D-печати", "булавки"],
                "software": ["редактор нот, установленный в организации, без обязательного интернета"],
                "professions": ["хореограф", "3D-моделлер", "репетитор"],
            },
            ensure_ascii=False,
        ),
        "Современная хореография",
    )
    assert "Blender" not in made_outfit["equipment"]
    assert "стол для репетиции" in made_outfit["equipment"]
    assert "хореограф" in made_outfit["professions"]
    assert "3D-моделлер" not in made_outfit["professions"]
    assert "редактор нот" in made_outfit["software"]
    assert "ткань для костюма" in made_outfit["consumables"]
    assert "3D-печати" not in made_outfit["consumables"]
    assert spoken["modules"][0]["theory_text"].startswith("Теория вводного")
    assert "Теория:" in spoken["modules"][1]["theory_text"] or spoken["modules"][1]["theory_text"].startswith("Теория")
    assert "Практика:" in spoken["modules"][0]["practice_text"] or spoken["modules"][0]["practice_text"].startswith("Практика")
    assert "Форма занятий:" in spoken["modules"][0]["form_text"]
    assert "Навыки:" in spoken["modules"][0]["skills_text"]
    assert "Умения:" in spoken["modules"][0]["abilities_text"]
    dumped = normalize_module_row(
        {
            "theory": "Нумерация чисел от 1 до 100 и состав числа.",
            "practice": "Устный счёт в игровой форме и решение задач.",
            "form": "игра и учебное занятие",
            "tasks": {
                "обязательное задание": "составить простую программу приветствия",
                "задание с усложнением": "создать программу вывода таблицы умножения",
            },
            "skills": "устный счёт в пределах 20, понимание состава числа",
            "abilities": "концентрация внимания, работа в команде",
        }
    )
    assert "приветствия" in dumped["basic"]
    assert "умножения" in dumped["advanced"]
    assert "{" not in dumped["basic"]
    probe.generated = {
        **made,
        "modules": [
            {
                "theory": made["modules"][0]["theory"],
                "practice": made["modules"][0]["practice"],
                "tasks": "{'обязательное задание': 'составить простую программу приветствия', 'задание с усложнением': 'создать программу вывода таблицы умножения'}",
            },
            *made["modules"][1:],
        ],
    }
    repaired = build_context(probe)
    assert "приветствия" in repaired["modules"][0]["basic_text"]
    assert "умножения" in repaired["modules"][0]["advanced_text"]
    assert "{" not in repaired["modules"][0]["text"]
    probe.generated = made
    probe.generated = {}

    openings: list[str] = []
    with tempfile.TemporaryDirectory(prefix="doppro-check-") as folder:
        path = Path(folder)
        for direction in DIRECTIONS:
            program = _sample(direction)
            openings.append(build_context(program)["relevance_paragraphs"][0])
            check_direction(direction, path)
            print("ok", direction)
    assert len(set(openings)) == len(DIRECTIONS), "актуальность не должна совпадать у направленностей"
    print("SELFCHECK OK")


if __name__ == "__main__":
    main()
