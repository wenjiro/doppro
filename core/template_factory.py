# -*- coding: utf-8 -*-
"""Собирает program_template.docx с метками docxtpl.

Файл — каркас официального документа. Тексты в него не зашиты:
их подставляет templates_engine из JSON-формулировок.
Метки {%p %} и {%tr %} должны лежать цельным фрагментом, иначе docxtpl их не увидит.
"""

from __future__ import annotations

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt, RGBColor

def create_template(path: str) -> str:
    """Пишет каркас программы и возвращает путь."""
    document = Document()
    _configure_styles(document)
    _configure_page(document)
    _add_title_page(document)
    document.add_page_break()
    _add_contents(document)
    _add_complex_main(document)
    _add_complex_conditions(document)
    _add_closing(document)
    _add_appendices(document)
    _add_literature(document)
    _enable_field_update(document)
    document.save(path)
    return path


def _configure_styles(document: Document) -> None:
    style = document.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)
    style.font.color.rgb = RGBColor(0x00, 0x00, 0x00)
    style.paragraph_format.line_spacing = 1.0
    style.paragraph_format.space_after = Pt(0)
    style.paragraph_format.space_before = Pt(0)
    for style_name, size in (("Heading 1", 12), ("Heading 2", 12)):
        heading = document.styles[style_name]
        heading.font.name = "Times New Roman"
        heading.font.size = Pt(size)
        heading.font.bold = True
        heading.font.color.rgb = RGBColor(0x00, 0x00, 0x00)
        heading.font.italic = False
        heading.paragraph_format.line_spacing = 1.0
        heading.paragraph_format.space_before = Pt(0)
        heading.paragraph_format.space_after = Pt(6)
        heading_fonts = heading.element.get_or_add_rPr().find(qn("w:rFonts"))
        if heading_fonts is None:
            heading_fonts = OxmlElement("w:rFonts")
            heading.element.get_or_add_rPr().append(heading_fonts)
        for attribute in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            heading_fonts.set(qn(attribute), "Times New Roman")
    properties = style.element.get_or_add_rPr()
    fonts = properties.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        properties.append(fonts)
    for attribute in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(attribute), "Times New Roman")


def _configure_page(document: Document) -> None:
    section = document.sections[0]
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.left_margin = Mm(30)
    section.right_margin = Mm(15)
    section.top_margin = Mm(20)
    section.bottom_margin = Mm(20)
    section.header_distance = Mm(8)
    section.footer_distance = Mm(8)
    section.different_first_page_header_footer = True

    _write(
        section.header.paragraphs[0],
        "ДопПро  ·  {{ header_short }}",
        align="right",
        size=12,
        color="000000",
        before=0,
        after=0,
        line=1.0,
    )
    _write(section.first_page_header.paragraphs[0], "", size=12, before=0, after=0, line=1.0)
    _add_page_number(section.footer.paragraphs[0])
    _write(
        section.first_page_footer.paragraphs[0],
        "{{ city }}",
        align="center",
        size=12,
        bold=True,
        color="000000",
        before=0,
        after=0,
        line=1.0,
    )
    year_line = section.first_page_footer.add_paragraph()
    _write(year_line, "{{ year }}", align="center", size=12, bold=True, color="000000", before=0, after=0, line=1.0)


def _add_title_page(document: Document) -> None:
    _tag(document, "{%p if authority %}")
    _write(document.add_paragraph(), "{{ authority }}", align="center", size=12, bold=True, before=0, after=0, line=1.0)
    _tag(document, "{%p endif %}")
    _tag(document, "{%p if department %}")
    _write(document.add_paragraph(), "{{ department }}", align="center", size=12, before=0, after=0, line=1.0)
    _tag(document, "{%p endif %}")
    _write(document.add_paragraph(), "{{ organization }}", align="center", size=12, bold=True, before=0, after=8, line=1.0)

    table = document.add_table(rows=1, cols=2)
    _set_widths(table, [8.0, 8.5])
    left, right = table.rows[0].cells
    _no_borders(left)
    _no_borders(right)
    _fill_lines(
        left,
        [
            ("{{ logo }}", 12, False),
            ("", 6, False),
            ("Рассмотрена на заседании", 11, False),
            ("педагогического совета", 11, False),
            ("протокол № ______", 11, False),
            ("от «___» __________ {{ year }} г.", 11, False),
        ],
        align="center",
    )
    _fill_lines(
        right,
        [
            ("УТВЕРЖДАЮ", 12, True),
            ("{{ director_position }}", 12, False),
            ("____________ / {{ director_name }}", 12, False),
            ("«___» __________ {{ year }} г.", 12, False),
            ("М.П.", 12, False),
        ],
        align="right",
    )

    _write(document.add_paragraph(), "", size=12, before=0, after=10, line=1.0)
    _write(
        document.add_paragraph(),
        "ДОПОЛНИТЕЛЬНАЯ ОБЩЕОБРАЗОВАТЕЛЬНАЯ",
        align="center",
        size=12,
        bold=True,
        color="000000",
        before=12,
        after=0,
        line=1.0,
    )
    _write(
        document.add_paragraph(),
        "ОБЩЕРАЗВИВАЮЩАЯ ПРОГРАММА {{ direction_gen }} направленности",
        align="center",
        size=12,
        bold=True,
        color="000000",
        before=0,
        after=10,
        line=1.0,
    )
    _write(
        document.add_paragraph(),
        "«{{ title }}»",
        align="center",
        size=12,
        bold=True,
        color="000000",
        before=8,
        after=12,
        line=1.0,
    )
    for line in (
        "Направленность: {{ direction }}",
        "Уровень: {{ level_full }}",
        "Возраст обучающихся: {{ age_text }}",
        "Срок реализации: {{ years_text }}",
        "Год реализации: {{ academic_year }}",
        "Объём: {{ total_hours }} {{ hours_word }}",
    ):
        _write(document.add_paragraph(), line, align="center", size=12, color="000000", before=1, after=1, line=1.0)
    _write(document.add_paragraph(), "Автор-составитель:", align="right", size=12, color="000000", before=12, after=0, line=1.0)
    _write(document.add_paragraph(), "{{ teacher_name }}", align="right", size=12, bold=True, color="000000", before=0, after=0, line=1.0)
    _write(document.add_paragraph(), "{{ teacher_position }}", align="right", size=12, color="000000", before=0, after=0, line=1.0)
    _write(document.add_paragraph(), "{{ org_short }}", align="right", size=12, color="000000", before=0, after=0, line=1.0)


def _add_contents(document: Document) -> None:
    _write(
        document.add_paragraph(),
        "Содержание",
        align="center",
        size=12,
        bold=True,
        color="000000",
        before=0,
        after=12,
        line=1.0,
    )
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.line_spacing = 1.0
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    _add_toc_field(paragraph)


def _add_complex_main(document: Document) -> None:
    _heading1(document, "1. Комплекс основных характеристик программы")
    _heading2(document, "1.1. Пояснительная записка", new_page=False)
    _label(document, "Нормативно-правовая база")
    _loop(document, "normative_items")
    _label(document, "Общая характеристика")
    _loop(document, "overview_paragraphs")
    _label(document, "Актуальность программы")
    _loop(document, "relevance_paragraphs")
    _label(document, "Новизна")
    _loop(document, "novelty_paragraphs")
    _label(document, "Отличительные особенности")
    _loop(document, "distinctive_items")
    _label(document, "Педагогическая целесообразность")
    _loop(document, "expediency_paragraphs")
    _label(document, "Направленность")
    _loop(document, "direction_paragraphs")
    _label(document, "Уровень программы")
    _loop(document, "level_paragraphs")
    _label(document, "Адресат программы")
    _loop(document, "addressee_paragraphs")
    _label(document, "Объём, срок и режим занятий")
    _loop(document, "volume_paragraphs")
    _label(document, "Особенности организации")
    _loop(document, "features_paragraphs")

    _heading2(document, "1.2. Цель и задачи")
    _tag(document, "{%p if goal_manual %}")
    _write(
        document.add_paragraph(),
        "Цель формулирует нейросеть. Откройте «Настройки», вставьте ключ и на шаге сборки нажмите «Сформулировать под эту программу».",
        align="left",
        size=12,
        color="B42318",
        first_indent=1.25,
        before=0,
        after=0,
        line=1.0,
    )
    _tag(document, "{%p endif %}")
    _tag(document, "{%p if goal_ready %}")
    _loop(document, "goal_paragraphs")
    _tag(document, "{%p endif %}")
    _label(document, "Предметные задачи")
    _loop(document, "tasks_teaching")
    _label(document, "Метапредметные задачи")
    _loop(document, "tasks_developing")
    _label(document, "Личностные задачи")
    _loop(document, "tasks_educating")

    _heading2(document, "1.3. Содержание программы")
    _table(
        document,
        headers=["№", "Раздел / тема", "Всего", "Теория", "Практика", "Форма контроля"],
        widths=[1.0, 6.0, 1.5, 1.6, 1.8, 4.6],
        loop="m in modules",
        cells=["{{ m.num }}", "{{ m.name }}", "{{ m.hours }}", "{{ m.theory }}", "{{ m.practice }}", "{{ m.control }}"],
        centers={0, 2, 3, 4},
        total=["", "Итого", "{{ modules_total_hours }}", "{{ modules_total_theory }}", "{{ modules_total_practice }}", ""],
    )
    _body_small(document, "{{ curriculum_note }}")
    _tag(document, "{%p for m in modules %}")
    module_heading = document.add_paragraph()
    _write(
        module_heading,
        "{{ m.heading }}",
        align="left",
        size=12,
        bold=True,
        color="000000",
        before=0,
        after=6,
        line=1.0,
    )
    module_heading.paragraph_format.page_break_before = True
    _body(document, "{{ m.theory_text }}")
    _body(document, "{{ m.practice_text }}")
    _body(document, "{{ m.tasks_text }}")
    _body(document, "{{ m.control_text }}")
    _body_small(document, "{{ m.topics_line }}")
    _tag(document, "{%p endfor %}")

    _heading2(document, "1.4. Планируемые результаты")
    _loop(document, "result_paragraphs")
    _label(document, "Соответствие задач, результатов и оценки")
    _table(
        document,
        headers=["Задача", "Как проявляется результат", "Как проверяется"],
        widths=[5.5, 5.5, 5.5],
        loop="link in link_rows",
        cells=["{{ link.task }}", "{{ link.result }}", "{{ link.tool }}"],
        centers=set(),
    )
    _label(document, "Различия по возрасту при одних результатах")
    _table(
        document,
        headers=["Параметр", "11–13 лет", "14–17 лет"],
        widths=[4.0, 6.2, 6.3],
        loop="age in age_rows",
        cells=["{{ age.parameter }}", "{{ age.junior }}", "{{ age.senior }}"],
        centers=set(),
    )


def _add_complex_conditions(document: Document) -> None:
    _heading1(document, "2. Комплекс организационно-педагогических условий")
    _heading2(document, "2.1. Календарный учебный график", new_page=False)
    _loop(document, "volume_paragraphs")
    _table(
        document,
        headers=["Период", "Часы", "Как проходят занятия"],
        widths=[4.5, 2.2, 9.8],
        loop="cal in calendar_rows",
        cells=["{{ cal.period }}", "{{ cal.hours }}", "{{ cal.note }}"],
        centers={1},
        total=["Итого", "{{ total_hours }}", "сумма равна объёму программы"],
    )
    _body_small(document, "{{ kug_note }}")

    _heading2(document, "2.2. Условия реализации")
    _label(document, "Кадровое обеспечение")
    _loop(document, "staffing_paragraphs")
    _body(document, "{{ staff_extra }}")
    _label(document, "Материально-техническое обеспечение")
    _loop(document, "material_paragraphs")
    _loop(document, "room_paragraphs")
    _label(document, "Программное обеспечение")
    _loop(document, "software_items")
    _loop(document, "information_paragraphs")
    _label(document, "Расходные материалы")
    _loop(document, "consumable_paragraphs")
    _label(document, "Санитарно-гигиенические условия")
    _loop(document, "sanitary_paragraphs")

    _heading2(document, "2.3. Формы аттестации")
    _loop(document, "assessment_paragraphs")
    _body(
        document,
        "Входная диагностика — стартовое задание на первых занятиях. Текущий контроль — на каждом разделе. "
        "Промежуточная аттестация — в середине срока, если она включена. Итоговая аттестация — {{ attestation_form }}. "
        "Высокий уровень: 5 баллов или 4,5–5,0. Средний: 3–4 балла или 2,5–4,4. Низкий: 1–2 балла или ниже 2,5. "
        "Итоговый продукт, если он предусмотрен, оценивается до 50 баллов: высокий 40–50, средний 25–39, не зачтено ниже 25. "
        "Зачёт — не ниже 50 % от максимума.",
    )

    _heading2(document, "2.4. Оценочные материалы")
    _table(
        document,
        headers=["Критерий", "Низкий уровень", "Средний уровень", "Высокий уровень"],
        widths=[3.9, 4.2, 4.2, 4.2],
        loop="cr in criteria",
        cells=["{{ cr.name }}", "{{ cr.low }}", "{{ cr.mid }}", "{{ cr.high }}"],
        centers=set(),
    )
    _body_small(document, "Пустые бланки для группы и для одного обучающегося — в приложении 1. ФИО педагог вписывает сам.")

    _heading2(document, "2.5. Методические материалы")
    _loop(document, "methodical_paragraphs")
    _label(document, "Межпредметные связи")
    _loop(document, "subjects_paragraphs")
    _label(document, "Профессиональные пробы")
    _loop(document, "professions_paragraphs")
    _body(
        document,
        "Профессиональная проба, если она есть в программе, делится примерно так: 15–20 % времени — вводный рассказ о роли, "
        "55–60 % — практическое действие, 15–20 % — разбор: что получилось и какие умения понадобились.",
    )

    _heading2(document, "2.6. Рабочая программа воспитания")
    _body(document, "Воспитательная работа опирается на {{ upbringing_base }} и на Указ Президента Российской Федерации от 09.11.2022 № 809.")
    _loop(document, "upbringing_goal_paragraphs")
    _loop(document, "upbringing_tasks")
    _loop(document, "upbringing_forms_paragraphs")
    _table(
        document,
        headers=["Срок", "Воспитательное событие", "Форма"],
        widths=[3.0, 8.5, 5.0],
        loop="ev in events",
        cells=["{{ ev.when }}", "{{ ev.name }}", "{{ ev.form }}"],
        centers={0},
    )
    _loop(document, "upbringing_results")


def _add_appendices(document: Document) -> None:
    _heading1(document, "Приложения")
    _heading2(document, "Приложение 1. Бланки оценивания", new_page=False)
    _blank_sheet(document, "Бланк 1. Входная диагностика группы", "Стартовый балл")
    _blank_sheet(document, "Бланк 2. Текущий контроль группы", "Балл раздела")
    _blank_sheet(document, "Бланк 3. Промежуточная аттестация группы", "Балл")
    _blank_sheet(document, "Бланк 4. Итоговая аттестация группы", "Балл")
    _heading2(document, "Бланк 5. Индивидуальная карта", new_page=False)
    _table(
        document,
        headers=["ФИО", "Входная", "Текущая", "Промежуточная", "Итоговая", "Комментарий"],
        widths=[4.0, 2.0, 2.0, 2.5, 2.0, 4.0],
        loop="row in blank_rows",
        cells=["", "", "", "", "", ""],
        centers=set(),
    )
    _heading2(document, "Бланк 6. Личностные и метапредметные результаты", new_page=False)
    _body_small(
        document,
        "Л1–Л5 — личностные проявления, М1–М5 — метапредметные. Педагог ставит отметку по наблюдению, без отдельного экзамена.",
    )
    _table(
        document,
        headers=["ФИО", "Л1", "Л2", "Л3", "Л4", "Л5", "М1", "М2", "М3", "М4", "М5"],
        widths=[4.5, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2],
        loop="row in blank_rows",
        cells=["", "", "", "", "", "", "", "", "", "", ""],
        centers=set(),
    )

    _heading2(document, "Приложение 2. Календарный учебный график")
    _table(
        document,
        headers=["№ гр.", "Год", "Начало", "Окончание", "Недели", "Дни", "Часы", "Режим"],
        widths=[1.2, 2.4, 1.8, 1.8, 1.4, 1.2, 1.3, 5.4],
        loop="sch in schedule_rows",
        cells=[
            "{{ sch.group }}",
            "{{ sch.study_year }}",
            "{{ sch.start }}",
            "{{ sch.finish }}",
            "{{ sch.weeks }}",
            "{{ sch.days }}",
            "{{ sch.hours }}",
            "{{ sch.mode }}",
        ],
        centers={0, 2, 3, 4, 5, 6},
    )

    _heading2(document, "Приложение 3. Календарно-тематический план")
    _body_small(document, "{{ ktp_note }} Даты в столбце «предполагаемая» рассчитаны по режиму. Фактическую дату педагог вписывает сам.")
    _table(
        document,
        headers=["№", "Дата предпол.", "Дата факт.", "Часы", "Тема лекции", "Тема практики", "Форма контроля"],
        widths=[0.7, 1.7, 1.5, 0.9, 4.3, 4.4, 3.0],
        loop="ktp in ktp_rows",
        cells=[
            "{{ ktp.num }}",
            "{{ ktp.date }}",
            "________",
            "{{ ktp.hours }}",
            "{{ ktp.lecture }}",
            "{{ ktp.practice }}",
            "{{ ktp.control }}",
        ],
        centers={0, 1, 2, 3},
        total=["", "", "", "{{ ktp_hours }}", "", "Итого", ""],
    )


def _blank_sheet(document: Document, title: str, score: str) -> None:
    _heading2(document, title, new_page=False)
    _table(
        document,
        headers=["№", "ФИО", score, "Комментарий"],
        widths=[1.2, 6.0, 2.8, 6.5],
        loop="row in blank_rows",
        cells=["{{ row.num }}", "", "", ""],
        centers={0},
    )


def _label(document: Document, text: str) -> None:
    _write(
        document.add_paragraph(),
        text,
        align="left",
        size=12,
        bold=True,
        color="000000",
        before=8,
        after=2,
        line=1.0,
    )


def _add_closing(document: Document) -> None:
    _write(
        document.add_paragraph(),
        "Текст собран в программе «ДопПро» из методических шаблонов по сведениям, которые внёс педагог. "
        "Перед утверждением нужно проверить фактические данные, часы, соответствие локальным актам организации "
        "и актуальные редакции нормативных документов.",
        align="left",
        size=12,
        italic=True,
        color="000000",
        before=12,
        after=0,
        line=1.0,
    )


def _add_literature(document: Document) -> None:
    _heading1(document, "Список литературы")
    _tag(document, "{%p if literature_manual %}")
    _write(
        document.add_paragraph(),
        "Укажите литературу вручную, либо подключите нейросеть в настройках ДопПро",
        align="left",
        size=12,
        color="B42318",
        first_indent=1.25,
        before=0,
        after=0,
        line=1.0,
    )
    _tag(document, "{%p endif %}")
    _tag(document, "{%p if literature_ready %}")
    _body_small(document, "Список оформлен по ГОСТ Р 7.0.100-2018.")
    _loop(document, "literature")
    _tag(document, "{%p endif %}")


def _loop(document: Document, name: str) -> None:
    _tag(document, "{%p for item in " + name + " %}")
    _body(document, "{{ item }}")
    _tag(document, "{%p endfor %}")


def _table(
    document: Document,
    *,
    headers: list[str],
    widths: list[float],
    loop: str,
    cells: list[str],
    centers: set[int],
    total: list[str] | None = None,
) -> None:
    row_count = 5 if total else 4
    table = document.add_table(rows=row_count, cols=len(headers))
    table.style = "Table Grid"
    _set_widths(table, widths)
    for index, header in enumerate(headers):
        _cell(table.rows[0].cells[index], header, header=True, center=True)
    _mark_header(table.rows[0])
    table.rows[1].cells[0].text = "{%tr for " + loop + " %}"
    for index, template in enumerate(cells):
        _cell(table.rows[2].cells[index], template, center=index in centers)
    table.rows[3].cells[0].text = "{%tr endfor %}"
    if total:
        for index, template in enumerate(total):
            _cell(table.rows[4].cells[index], template, bold=True, center=index in centers)
    for row in table.rows:
        _cant_split(row)
    _write(document.add_paragraph(), "", size=6, before=0, after=4, line=1.0)


def _heading1(document: Document, text: str) -> None:
    paragraph = document.add_paragraph()
    paragraph.style = document.styles["Heading 1"]
    _write(paragraph, text, align="left", size=12, bold=True, color="000000", before=0, after=6, line=1.0)
    paragraph.paragraph_format.page_break_before = True


def _heading2(document: Document, text: str, new_page: bool = True) -> None:
    paragraph = document.add_paragraph()
    paragraph.style = document.styles["Heading 2"]
    _write(paragraph, text, align="left", size=12, bold=True, color="000000", before=0, after=4, line=1.0)
    if new_page:
        paragraph.paragraph_format.page_break_before = True


def _body(document: Document, text: str) -> None:
    _write(
        document.add_paragraph(),
        text,
        align="justify",
        size=12,
        color="000000",
        first_indent=1.25,
        before=0,
        after=0,
        line=1.0,
    )


def _body_small(document: Document, text: str) -> None:
    _write(
        document.add_paragraph(),
        text,
        align="justify",
        size=12,
        color="000000",
        first_indent=1.25,
        before=2,
        after=0,
        line=1.0,
    )


def _tag(document: Document, text: str) -> None:
    _write(document.add_paragraph(), text, align="left", size=10, before=0, after=0, line=1.0)


def _fill_lines(cell, lines: list[tuple[str, int, bool]], *, align: str) -> None:
    paragraphs = [cell.paragraphs[0]]
    for _ in lines[1:]:
        paragraphs.append(cell.add_paragraph())
    for paragraph, (text, size, bold) in zip(paragraphs, lines):
        _write(paragraph, text, align=align, size=size, bold=bold, before=0, after=2, line=1.0)


def _cell(cell, text: str, *, header: bool = False, bold: bool = False, center: bool = False) -> None:
    paragraph = cell.paragraphs[0]
    # У ячейки уже есть пустой абзац. Пишем в него, чтобы не появился лишний.
    for extra in cell.paragraphs[1:]:
        extra._element.getparent().remove(extra._element)
    _write(
        paragraph,
        text,
        align="center" if center or header else "left",
        size=12,
        bold=bold or header,
        color="000000",
        before=1,
        after=1,
        line=1.0,
    )
    _borders(cell, "000000")
    _valign(cell)
    _shade(cell, "FFFFFF")


def _write(
    paragraph,
    text: str,
    *,
    align: str = "left",
    size: int = 14,
    bold: bool = False,
    italic: bool = False,
    color: str = "000000",
    before: float = 0,
    after: float = 0,
    line: float = 1.0,
    first_indent: float = 0,
) -> None:
    alignment = {
        "left": WD_ALIGN_PARAGRAPH.LEFT,
        "center": WD_ALIGN_PARAGRAPH.CENTER,
        "right": WD_ALIGN_PARAGRAPH.RIGHT,
        "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
    }[align]
    paragraph.alignment = alignment
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(before)
    fmt.space_after = Pt(after)
    fmt.line_spacing = line
    fmt.first_line_indent = Cm(first_indent)
    for run in list(paragraph.runs):
        run._element.getparent().remove(run._element)
    run = paragraph.add_run(text)
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(size)
    run.font.color.rgb = _rgb(color)
    run.font.name = "Times New Roman"
    properties = run._element.get_or_add_rPr()
    fonts = properties.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        properties.append(fonts)
    for attribute in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(attribute), "Times New Roman")


def _add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.first_line_indent = Cm(0)
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    lead = paragraph.add_run("")
    lead.font.size = Pt(12)
    lead.font.color.rgb = _rgb("000000")
    lead.font.name = "Times New Roman"
    field = paragraph.add_run()
    field.font.size = Pt(12)
    field.font.color.rgb = _rgb("000000")
    field.font.name = "Times New Roman"
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = " PAGE "
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    field._r.append(begin)
    field._r.append(instruction)
    field._r.append(end)


def _add_toc_field(paragraph) -> None:
    """Поле автособираемого оглавления Word. Номера страниц появляются при открытии файла."""
    begin_run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    begin_run._r.append(begin)

    instruction_run = paragraph.add_run()
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = ' TOC \\o "1-2" \\h \\z \\u '
    instruction_run._r.append(instruction)

    separate_run = paragraph.add_run()
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    separate_run._r.append(separate)

    hint = paragraph.add_run("Оглавление соберётся по заголовкам при открытии документа в Word.")
    hint.font.name = "Times New Roman"
    hint.font.size = Pt(12)
    hint.font.color.rgb = _rgb("000000")

    end_run = paragraph.add_run()
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    end_run._r.append(end)


def _enable_field_update(document: Document) -> None:
    settings = document.settings.element
    node = OxmlElement("w:updateFields")
    node.set(qn("w:val"), "true")
    settings.append(node)


def _set_widths(table, widths: list[float]) -> None:
    table.autofit = False
    table.allow_autofit = False
    table_element = table._tbl
    properties = table_element.tblPr
    total = int(sum(widths) * 567)
    width_node = properties.find(qn("w:tblW"))
    if width_node is None:
        width_node = OxmlElement("w:tblW")
        properties.append(width_node)
    width_node.set(qn("w:w"), str(total))
    width_node.set(qn("w:type"), "dxa")
    layout = properties.find(qn("w:tblLayout"))
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        properties.append(layout)
    layout.set(qn("w:type"), "fixed")
    grid = table_element.find(qn("w:tblGrid"))
    if grid is None:
        grid = OxmlElement("w:tblGrid")
        properties.addnext(grid)
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        column = OxmlElement("w:gridCol")
        column.set(qn("w:w"), str(int(width * 567)))
        grid.append(column)
    for row in table.rows:
        for cell, width in zip(row.cells, widths):
            cell.width = Cm(width)


def _borders(cell, color: str) -> None:
    properties = cell._tc.get_or_add_tcPr()
    existing = properties.find(qn("w:tcBorders"))
    if existing is not None:
        properties.remove(existing)
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        node = OxmlElement(f"w:{edge}")
        node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), "6")
        node.set(qn("w:space"), "0")
        node.set(qn("w:color"), color)
        borders.append(node)
    properties.append(borders)


def _no_borders(cell) -> None:
    properties = cell._tc.get_or_add_tcPr()
    existing = properties.find(qn("w:tcBorders"))
    if existing is not None:
        properties.remove(existing)
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        node = OxmlElement(f"w:{edge}")
        node.set(qn("w:val"), "nil")
        borders.append(node)
    properties.append(borders)


def _shade(cell, fill: str) -> None:
    properties = cell._tc.get_or_add_tcPr()
    existing = properties.find(qn("w:shd"))
    if existing is not None:
        properties.remove(existing)
    shade = OxmlElement("w:shd")
    shade.set(qn("w:val"), "clear")
    shade.set(qn("w:color"), "auto")
    shade.set(qn("w:fill"), fill)
    properties.append(shade)


def _valign(cell) -> None:
    properties = cell._tc.get_or_add_tcPr()
    align = properties.find(qn("w:vAlign"))
    if align is None:
        align = OxmlElement("w:vAlign")
        properties.append(align)
    align.set(qn("w:val"), "center")


def _mark_header(row) -> None:
    properties = row._tr.get_or_add_trPr()
    marker = OxmlElement("w:tblHeader")
    properties.append(marker)


def _cant_split(row) -> None:
    properties = row._tr.get_or_add_trPr()
    node = OxmlElement("w:cantSplit")
    properties.append(node)


def _rgb(value: str) -> RGBColor:
    value = value.lstrip("#")
    return RGBColor(int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
