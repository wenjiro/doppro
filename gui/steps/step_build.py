# -*- coding: utf-8 -*-
"""Шаг 5. Проверка и сборка документа Word."""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core.document_builder import build_document
from core.generator import GenerationError, generate_sections
from core.templates_engine import build_context
from gui.theme import DANGER, FONT, FONT_B, FONT_S, LINE, MUTED, NAVY, OK
from gui.tooltip import tooltip
from gui.widgets import caption, card, hint, primary_button, secondary_button


class StepBuild(ctk.CTkScrollableFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.output_path = ""

        caption(self, "Проверка и сборка")
        hint(
            self,
            "Без ключа документ собирается из текстов направленности. "
            "Цель, адресат, предметные, метапредметные и личностные задачи, а также список литературы по ГОСТ "
            "появляются после кнопки ниже. Ключ задаётся в «Настройках». "
            "Фамилия и организация в запрос не входят. Часы и нормативные пункты модель не переписывает.",
        )

        ask = card(self)
        ask.grid_columnconfigure(0, weight=1)
        buttons = ctk.CTkFrame(ask, fg_color="white")
        buttons.grid(row=0, column=0, sticky="w")
        self.gen_button = secondary_button(buttons, "Сформулировать под эту программу", self._start_generation)
        self.gen_button.pack(side="left", padx=(0, 8))
        self.clear_button = secondary_button(buttons, "Вернуть текст направленности", self._clear_generation)
        self.clear_button.pack(side="left")
        tooltip(self.gen_button, "Просит цель, адресат, задачи и литературу по ГОСТ. Фамилия и организация не отправляются.")
        tooltip(self.clear_button, "Убирает текст нейросети. В документе снова будут формулировки направленности.")
        self.gen_status = ctk.CTkLabel(ask, text="", font=FONT_S, text_color=MUTED, anchor="w", justify="left", wraplength=860)
        self.gen_status.grid(row=1, column=0, sticky="w", pady=(8, 0))
        self._waiting = False
        self._gen_result = None
        self._gen_error = None

        body = card(self)
        body.grid_columnconfigure(0, weight=1)
        self.preview = ctk.CTkTextbox(
            body,
            height=280,
            font=FONT,
            fg_color="#F8FAFC",
            border_width=1,
            border_color=LINE,
            text_color="#1A1A1A",
            wrap="word",
        )
        self.preview.grid(row=0, column=0, sticky="ew")
        self.preview.configure(state="disabled")

        build_button = primary_button(body, "Собрать программу", self.app.build)
        build_button.grid(row=1, column=0, sticky="w", pady=(12, 0))
        tooltip(build_button, "Создаёт файл Word и открывает его папку. Интернет для сборки не нужен.")

        self.status = ctk.CTkLabel(body, text="", font=FONT_S, text_color=MUTED, anchor="w", justify="left", wraplength=860)
        self.status.grid(row=2, column=0, sticky="w", pady=(10, 0))

        actions = ctk.CTkFrame(body, fg_color="white")
        actions.grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.open_folder_button = secondary_button(actions, "Открыть папку с файлом", self._open_folder)
        self.open_folder_button.pack(side="left", padx=(0, 8))
        self.open_file_button = secondary_button(actions, "Открыть документ", self._open_file)
        self.open_file_button.pack(side="left")
        self.open_folder_button.configure(state="disabled")
        self.open_file_button.configure(state="disabled")

    def on_show(self) -> None:
        self._render_preview()

    def save(self) -> None:
        return None

    def validate(self) -> list[str]:
        return self.app.model.validate()

    def generate(self) -> None:
        model = self.app.model
        initial = _filename(model.title) + ".docx"
        documents = Path.home() / "Documents"
        if not documents.exists():
            documents = Path.home()
        path = filedialog.asksaveasfilename(
            parent=self.app,
            title="Сохранить программу",
            defaultextension=".docx",
            initialfile=initial,
            initialdir=str(documents),
            filetypes=[("Документ Word", "*.docx")],
        )
        if not path:
            return
        if not path.lower().endswith(".docx"):
            path += ".docx"
        self.app.configure(cursor="watch")
        self.status.configure(text="Собираю документ…", text_color=NAVY)
        self.app.update_idletasks()
        try:
            build_document(model, path)
        except PermissionError as exc:
            self.status.configure(text=str(exc), text_color=DANGER)
            messagebox.showerror("ДопПро", str(exc), parent=self.app)
            return
        except Exception as exc:  # показываем педагогу причину, а не пустое окно
            self.status.configure(text="Документ не собран.", text_color=DANGER)
            messagebox.showerror("ДопПро", f"Не удалось собрать документ.\n\n{exc}", parent=self.app)
            return
        finally:
            self.app.configure(cursor="")
        self.output_path = path
        self.status.configure(text=f"Файл сохранён:\n{path}", text_color=OK)
        self.open_folder_button.configure(state="normal")
        self.open_file_button.configure(state="normal")
        model.save_draft()

    def _render_preview(self) -> None:
        errors = self.app.model.validate()
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        if errors:
            self.preview.insert("1.0", "Перед сборкой нужно исправить:\n\n" + "\n".join(f"• {item}" for item in errors))
            self.preview.configure(state="disabled")
            return
        try:
            context = build_context(self.app.model)
            lines = list(context["preview_lines"])
            if self.app.model.generated.get("relevance"):
                lines.insert(0, "Формулировки подобраны под название этой программы.")
                lines.insert(1, context["relevance_paragraphs"][0])
            text = "\n".join(lines)
        except Exception as exc:
            text = f"Не удалось собрать предварительный текст:\n{exc}"
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def _open_folder(self) -> None:
        if not self.output_path:
            return
        folder = str(Path(self.output_path).parent)
        try:
            os.startfile(folder)
        except OSError as exc:
            messagebox.showerror("ДопПро", f"Не удалось открыть папку.\n\n{exc}", parent=self.app)

    def _open_file(self) -> None:
        if not self.output_path:
            return
        try:
            os.startfile(self.output_path)
        except OSError as exc:
            messagebox.showerror("ДопПро", f"Не удалось открыть документ.\n\n{exc}", parent=self.app)


    def _start_generation(self) -> None:
        if self._waiting:
            return
        self._waiting = True
        self._gen_result = None
        self._gen_error = None
        self.gen_button.configure(state="disabled")
        self.gen_status.configure(text="Формулирую тексты под название…", text_color=NAVY)
        model = self.app.model

        def work() -> None:
            try:
                self._gen_result = generate_sections(model)
            except Exception as exc:
                self._gen_error = exc

        threading.Thread(target=work, daemon=True).start()
        self.after(200, self._poll_generation)

    def _poll_generation(self) -> None:
        if self._gen_result is None and self._gen_error is None:
            self.after(200, self._poll_generation)
            return
        self._waiting = False
        self.gen_button.configure(state="normal")
        if self._gen_error is not None:
            text = str(self._gen_error)
            if not isinstance(self._gen_error, GenerationError):
                text = f"Не удалось получить формулировки.\n\n{text}"
            self.gen_status.configure(text=text, text_color=DANGER)
            messagebox.showerror("ДопПро", text, parent=self.app)
            return
        self.app.model.generated = self._gen_result
        try:
            self.app.model.save_draft()
        except OSError:
            pass
        self.gen_status.configure(
            text="Готово. Проверьте абзац ниже и соберите документ. Нормативные пункты и часы не менялись.",
            text_color=OK,
        )
        self._render_preview()

    def _clear_generation(self) -> None:
        self.app.model.generated = {}
        try:
            self.app.model.save_draft()
        except OSError:
            pass
        self.gen_status.configure(text="Снова используются тексты направленности.", text_color=MUTED)
        self._render_preview()


def _filename(title: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', "", title).strip().rstrip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned or "Программа")[:80]
