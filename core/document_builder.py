# -*- coding: utf-8 -*-
"""Сборка готового .docx.

Каркас пишет python-docx (template_factory), текст в каркас подставляет docxtpl.
Так таблицы переменной длины и абзацы из шаблонов остаются обычным документом Word.
"""

from __future__ import annotations

import os
import re
import tempfile

from docx import Document
from docx.shared import Mm
from docxtpl import DocxTemplate, InlineImage
from jinja2 import Environment, StrictUndefined
from jinja2.exceptions import TemplateError

from core.data_model import ProgramData
from core.paths import logo_path
from core.template_factory import create_template
from core.templates_engine import build_context

_ILLEGAL_XML = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")


def build_document(program: ProgramData, output_path: str) -> str:
    """Проверяет данные, собирает документ и возвращает путь к файлу."""
    errors = program.validate()
    if errors:
        raise ValueError("\n".join(errors))

    output_parent = os.path.dirname(os.path.abspath(output_path))
    if output_parent and not os.path.isdir(output_parent):
        raise OSError(f"Папка для сохранения не найдена: {output_parent}")

    context = _escape(build_context(program))
    temporary = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
    temporary.close()
    try:
        create_template(temporary.name)
        template = DocxTemplate(temporary.name)
        context["logo"] = InlineImage(template, str(_logo_file()), width=Mm(28))
        environment = Environment(undefined=StrictUndefined, autoescape=False)
        template.render(context, jinja_env=environment)
        template.save(output_path)
    except TemplateError as exc:
        details = ""
        context_lines = getattr(exc, "docx_context", None)
        if context_lines:
            details = "\n".join(context_lines)
        raise RuntimeError(f"Не удалось собрать документ по шаблону: {exc}\n{details}") from exc
    except PermissionError as exc:
        raise PermissionError(
            "Не удалось записать файл. Закройте его в Word, если он уже открыт, и повторите сохранение."
        ) from exc
    finally:
        try:
            os.remove(temporary.name)
        except OSError:
            pass

    _stamp(output_path, program)
    return output_path


def _logo_file() -> str:
    path = logo_path()
    if path.exists():
        return str(path)
    # Запасной знак, если png ещё не подготовили. В обычной сборке файл есть.
    from PIL import Image, ImageDraw

    folder = tempfile.mkdtemp(prefix="doppro-logo-")
    target = os.path.join(folder, "logo.png")
    image = Image.new("RGBA", (256, 256), (232, 240, 248, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((48, 48, 120, 160), fill=(27, 58, 111, 255))
    draw.rectangle((136, 48, 208, 160), fill=(14, 124, 116, 255))
    image.save(target, "PNG")
    return target


def _escape(value):
    """Готовит строки к вставке в XML. Картинка подставляется отдельно и сюда не попадает."""
    if isinstance(value, str):
        cleaned = _ILLEGAL_XML.sub("", value).replace("\r\n", "\n").replace("\r", "\n")
        return cleaned.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    if isinstance(value, list):
        return [_escape(item) for item in value]
    if isinstance(value, dict):
        return {key: _escape(item) for key, item in value.items()}
    return value


def _stamp(path: str, program: ProgramData) -> None:
    """Свойства файла проставляет уже python-docx, после подстановки текста."""
    document = Document(path)
    props = document.core_properties
    props.title = program.title.strip()
    props.author = program.teacher_name.strip()
    props.subject = "Дополнительная общеобразовательная общеразвивающая программа"
    props.category = "ДопПро"
    props.language = "ru-RU"
    props.comments = (
        "Собрано локально в программе ДопПро из методических шаблонов. "
        "Перед утверждением текст проверяет педагог."
    )
    document.save(path)
