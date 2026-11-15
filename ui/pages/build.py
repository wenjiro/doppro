# -*- coding: utf-8 -*-
"""Шаг 5. Проверка и сборка документа Word."""

from __future__ import annotations

import os
import re
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget

from core.document_builder import build_document
from core.generator import GenerationError, current_credentials, generate_sections
from core.templates_engine import build_context
from ui import prefs
from ui.pages.base import StepPage
from ui.state import STEP_TITLES
from ui.theme import Glyph
from ui.widgets import Banner, Button, Card, GlyphLabel, alert, label, run_async

_PROVIDER_NAMES = {"gemini": "Gemini", "gigachat": "GigaChat", "deepseek": "DeepSeek"}


class BuildPage(StepPage):
    index = 4

    def __init__(self, window):
        super().__init__(
            window,
            "Проверка и сборка",
            "Документ Word собирается и без интернета — из текстов направленности. Нейросеть по желанию уточняет формулировки.",
        )
        self.output_path = ""
        self._waiting = False
        self._building = False

        # Готовность шагов
        self.ready_card = Card("Готовность")
        self.ready_rows: list[tuple[GlyphLabel, object, object, Button]] = []
        for index in range(4):
            row = QHBoxLayout()
            row.setSpacing(10)
            icon = GlyphLabel(Glyph.CHECK, "ok", 16)
            row.addWidget(icon)
            name = label(STEP_TITLES[index], "label")
            name.setFixedWidth(120)
            row.addWidget(name)
            note = label("", "muted", wrap=True)
            row.addWidget(note, 1)
            go = Button("Перейти", "link", on=lambda i=index: self.window_.show_step(i))
            row.addWidget(go)
            self.ready_card.body.addLayout(row)
            self.ready_rows.append((icon, name, note, go))
        self.add(self.ready_card)

        # Нейросеть
        card = Card(
            "Формулировки под эту программу",
            "Нейросеть формулирует цель, задачи, пункт 1.4 (личностные, метапредметные и предметные результаты), "
            "тексты разделов и литературу по ГОСТ. Берётся всё уже введённое, кроме фамилии и организации. "
            "Часы, даты и нормативные пункты подставляет сама программа.",
        )
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.gen_button = Button(
            "Сформулировать под эту программу", "teal", Glyph.SPARK, on=self._start_generation,
            tip="Формулирует тексты по всем уже заполненным шагам, включая пункт 1.4.",
        )
        buttons.addWidget(self.gen_button)
        self.clear_button = Button(
            "Вернуть текст направленности", glyph=Glyph.UNDO, on=self._clear_generation,
            tip="Убирает текст нейросети. В документе снова будут формулировки направленности.",
        )
        buttons.addWidget(self.clear_button)
        buttons.addStretch(1)
        card.body.addLayout(buttons)
        self.gen_status = Banner("info")
        card.body.addWidget(self.gen_status)
        self.add(card)

        # Предпросмотр
        card = Card("Предпросмотр", "Краткая выжимка того, что попадёт в документ.")
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(260)
        self.preview.setProperty("flat", True)
        card.body.addWidget(self.preview)
        self.add(card)

        # Документ
        card = Card("Документ Word")
        line = QHBoxLayout()
        line.setSpacing(10)
        self.build_button = Button(
            "Собрать программу", "primary", Glyph.DOCUMENT, on=self.build,
            tip="Создаёт файл Word. Интернет для сборки не нужен.",
        )
        line.addWidget(self.build_button)
        self.open_file_button = Button("Открыть документ", glyph=Glyph.DOCUMENT, on=self._open_file)
        self.open_folder_button = Button("Открыть папку с файлом", glyph=Glyph.FOLDER, on=self._open_folder)
        line.addWidget(self.open_file_button)
        line.addWidget(self.open_folder_button)
        line.addStretch(1)
        card.body.addLayout(line)
        self.status = Banner("info")
        self.status.hide()
        card.body.addWidget(self.status)
        card.body.addWidget(label(
            "Перед утверждением в организации текст нужно вычитать: сверить часы, даты, локальные акты "
            "и актуальные редакции нормативных документов.", "small", wrap=True))
        self.add(card)
        self.open_file_button.setEnabled(False)
        self.open_folder_button.setEnabled(False)
        self.finish()

    def load(self) -> None:
        self.refresh()

    def commit(self) -> None:
        return None

    def show_errors(self, errors: list[str]) -> None:
        return None

    def refresh(self) -> None:
        self._render_ready()
        self._render_gen_state()
        self._render_preview()

    # ---------- готовность ----------

    def _render_ready(self) -> None:
        for index, (icon, _name, note, go) in enumerate(self.ready_rows):
            errors = self.session.step_errors(index)
            if errors:
                icon.set_glyph(Glyph.WARNING, "warn")
                tail = f" И ещё {len(errors) - 2}." if len(errors) > 2 else ""
                note.setText(" ".join(errors[:2]) + tail)
            else:
                icon.set_glyph(Glyph.CHECK, "ok")
                note.setText("Заполнено")
            go.setVisible(bool(errors))

    def _render_gen_state(self) -> None:
        if self._waiting:
            return
        provider, key = current_credentials()
        name = _PROVIDER_NAMES.get(provider, provider)
        if self.model.generated.get("relevance"):
            self.gen_status.show_message("ok", "Формулировки подобраны под название этой программы.")
        elif len(key) < 10:
            self.gen_status.show_message(
                "info", f"Ключ {name} не задан — документ соберётся из текстов направленности. Ключ задаётся в «Настройках»."
            )
        else:
            self.gen_status.show_message("info", f"Выбран сервис {name}. Сейчас в документе тексты направленности.")
        self.clear_button.setEnabled(bool(self.model.generated))

    def _render_preview(self) -> None:
        errors = self.model.validate()
        if errors:
            self.preview.setPlainText("Перед сборкой нужно исправить:\n\n" + "\n".join(f"• {item}" for item in errors))
            return
        try:
            context = build_context(self.model)
            lines = list(context["preview_lines"])
            if self.model.generated.get("relevance"):
                lines.insert(0, "Формулировки подобраны под название этой программы.")
                lines.insert(1, context["relevance_paragraphs"][0])
            text = "\n".join(lines)
        except Exception as exc:
            text = f"Не удалось собрать предварительный текст:\n{exc}"
        self.preview.setPlainText(text)

    # ---------- сборка ----------

    def build(self) -> None:
        if self._building:
            return
        model = self.model
        errors = model.validate()
        if errors:
            self.session.touched.update(range(4))
            self.window_.refresh_status()
            self.refresh()
            shown = "\n".join(f"• {item}" for item in errors[:6])
            if len(errors) > 6:
                shown += f"\nи ещё {len(errors) - 6}"
            alert(self, "Перед сборкой нужно исправить", shown, "warn")
            return
        folder = str(prefs.get("save_dir") or "")
        if not folder or not Path(folder).is_dir():
            documents = Path.home() / "Documents"
            folder = str(documents if documents.exists() else Path.home())
        initial = str(Path(folder) / (_filename(model.title) + ".docx"))
        path, _filter = QFileDialog.getSaveFileName(self, "Сохранить программу", initial, "Документ Word (*.docx)")
        if not path:
            return
        if not path.lower().endswith(".docx"):
            path += ".docx"
        prefs.put("save_dir", str(Path(path).parent))
        self._building = True
        self.build_button.setEnabled(False)
        self.window_.set_busy(True)
        self.status.show_message("info", "Собираю документ…")
        run_async(self, lambda: build_document(model, path), lambda _r: self._built(path), self._build_failed)

    def _build_done(self) -> None:
        self._building = False
        self.build_button.setEnabled(True)
        self.window_.set_busy(False)

    def _build_failed(self, error) -> None:
        self._build_done()
        if isinstance(error, PermissionError):
            self.status.show_message("error", str(error))
            alert(self, "Файл не записан", str(error), "error")
            return
        self.status.show_message("error", "Документ не собран.")
        alert(self, "Не удалось собрать документ", str(error), "error")

    def _built(self, path: str) -> None:
        self._build_done()
        self.output_path = path
        self.status.show_message("ok", f"Файл сохранён:\n{path}")
        self.open_file_button.setEnabled(True)
        self.open_folder_button.setEnabled(True)
        self.window_.toast("Документ Word собран")
        self.session.touch()

    def _open_folder(self) -> None:
        if not self.output_path:
            return
        try:
            os.startfile(str(Path(self.output_path).parent))
        except OSError as exc:
            alert(self, "Не удалось открыть папку", str(exc), "error")

    def _open_file(self) -> None:
        if not self.output_path:
            return
        try:
            os.startfile(self.output_path)
        except OSError as exc:
            alert(self, "Не удалось открыть документ", str(exc), "error")

    # ---------- нейросеть ----------

    def _start_generation(self) -> None:
        if self._waiting:
            return
        self._waiting = True
        self.gen_button.setEnabled(False)
        self.gen_status.show_message("info", "Формулирую тексты под название… Обычно это занимает до минуты.")
        model = self.model
        run_async(self, lambda: generate_sections(model), self._generated, self._generation_failed)

    def _generation_failed(self, error) -> None:
        self._waiting = False
        self.gen_button.setEnabled(True)
        text = str(error)
        if not isinstance(error, GenerationError):
            text = f"Не удалось получить формулировки.\n\n{text}"
        self.gen_status.show_message("error", text)

    def _generated(self, result) -> None:
        self._waiting = False
        self.gen_button.setEnabled(True)
        self.model.generated = result
        self.session.touch()
        self.refresh()
        self.gen_status.show_message(
            "ok", "Готово. Проверьте абзац в предпросмотре и соберите документ. Нормативные пункты и часы не менялись."
        )

    def _clear_generation(self) -> None:
        self.model.generated = {}
        self.session.touch()
        self.refresh()
        self.gen_status.show_message("info", "Снова используются тексты направленности.")


def _filename(title: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', "", title).strip().rstrip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned or "Программа")[:80]
