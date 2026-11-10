# -*- coding: utf-8 -*-
"""Список сохранённых программ: открыть, копировать, перенести файлом."""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core.data_model import ProgramData
from core.library import (
    LibraryError,
    delete_program,
    duplicate_program,
    export_program,
    import_program,
    list_programs,
    load_program,
    save_program,
)
from gui.theme import BG, FONT, FONT_B, FONT_H, FONT_S, LINE, MUTED, NAVY
from gui.widgets import primary_button, secondary_button


class LibraryDialog(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.selected = ""
        self._rows: dict[str, ctk.CTkFrame] = {}
        self.title("Мои программы")
        self.resizable(True, True)
        self.minsize(640, 460)
        self.configure(fg_color="white")
        self.geometry("760x540")
        self.transient(app)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(self, text="Мои программы", font=FONT_H, text_color=NAVY, anchor="w").grid(
            row=0, column=0, sticky="ew", padx=22, pady=(18, 2)
        )
        ctk.CTkLabel(
            self,
            text="Здесь можно держать несколько программ. Ключ нейросети в них не записывается. "
            "Файл экспорта можно открыть на другом компьютере.",
            font=FONT_S,
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=700,
        ).grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 8))

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=8)
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=22, pady=(0, 8))
        self.list_frame.grid_columnconfigure(0, weight=1)

        self.status = ctk.CTkLabel(self, text="", font=FONT_S, text_color=MUTED, anchor="w", justify="left")
        self.status.grid(row=3, column=0, sticky="ew", padx=22)

        buttons = ctk.CTkFrame(self, fg_color="white")
        buttons.grid(row=4, column=0, sticky="ew", padx=16, pady=(6, 16))
        for column in range(4):
            buttons.grid_columnconfigure(column, weight=1)
        primary_button(buttons, "Сохранить текущую", self._save_current).grid(
            row=0, column=0, sticky="ew", padx=4, pady=4
        )
        secondary_button(buttons, "Открыть", self._open_selected).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        secondary_button(buttons, "Копия", self._duplicate).grid(row=0, column=2, sticky="ew", padx=4, pady=4)
        secondary_button(buttons, "Удалить", self._delete).grid(row=0, column=3, sticky="ew", padx=4, pady=4)
        secondary_button(buttons, "Новая программа", self._new_program).grid(
            row=1, column=0, sticky="ew", padx=4, pady=4
        )
        secondary_button(buttons, "Экспорт в файл…", self._export).grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        secondary_button(buttons, "Импорт из файла…", self._import).grid(
            row=1, column=2, columnspan=2, sticky="ew", padx=4, pady=4
        )

        self._reload()
        self.grab_set()
        self.focus()

    def _reload(self, prefer: str = "") -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()
        self._rows.clear()
        entries = list_programs()
        if prefer:
            self.selected = prefer
        elif self.selected not in {item.id for item in entries}:
            self.selected = self.app.model.library_id if any(item.id == self.app.model.library_id for item in entries) else ""
        if not entries:
            ctk.CTkLabel(
                self.list_frame,
                text="Пока пусто. Нажмите «Сохранить текущую», чтобы программа осталась в списке.",
                font=FONT,
                text_color=MUTED,
                anchor="w",
                justify="left",
                wraplength=640,
            ).grid(row=0, column=0, sticky="ew", padx=12, pady=16)
            return
        for row, item in enumerate(entries):
            selected = item.id == self.selected
            frame = ctk.CTkFrame(
                self.list_frame,
                fg_color="#E8EEF5" if selected else "white",
                corner_radius=8,
                border_width=1,
                border_color=NAVY if selected else LINE,
            )
            frame.grid(row=row, column=0, sticky="ew", pady=4)
            frame.grid_columnconfigure(0, weight=1)
            title = ctk.CTkLabel(frame, text=item.title, font=FONT_B, text_color=NAVY, anchor="w")
            title.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 0))
            details = item.direction or "направленность не указана"
            if item.updated_text:
                details = f"{details} · {item.updated_text}"
            if item.id == self.app.model.library_id:
                details = f"{details} · открыта сейчас"
            meta = ctk.CTkLabel(frame, text=details, font=FONT_S, text_color=MUTED, anchor="w")
            meta.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
            for widget in (frame, title, meta):
                widget.bind("<Button-1>", lambda _event, program_id=item.id: self._select(program_id))
            self._rows[item.id] = frame

    def _select(self, program_id: str) -> None:
        self.selected = program_id
        self._reload(prefer=program_id)

    def _save_current(self) -> None:
        self.app.step_frames[self.app.current].save()
        try:
            save_program(self.app.model)
            self.app.model.save_draft()
        except OSError as exc:
            messagebox.showerror("ДопПро", f"Не удалось сохранить программу.\n\n{exc}", parent=self)
            return
        self.status.configure(text="Программа записана в список.")
        self._reload(prefer=self.app.model.library_id)

    def _open_selected(self) -> None:
        if not self.selected:
            messagebox.showwarning("ДопПро", "Сначала выберите программу в списке.", parent=self)
            return
        if not messagebox.askyesno(
            "ДопПро",
            "Открыть выбранную программу? Правки текущей, которые не нажимали «Сохранить текущую», в список не попадут.",
            parent=self,
        ):
            return
        try:
            program = load_program(self.selected)
        except LibraryError as exc:
            messagebox.showerror("ДопПро", str(exc), parent=self)
            self._reload()
            return
        self.app.replace_program(program)
        self.destroy()

    def _duplicate(self) -> None:
        if not self.selected:
            messagebox.showwarning("ДопПро", "Сначала выберите программу, которую нужно скопировать.", parent=self)
            return
        try:
            copy_id = duplicate_program(self.selected)
        except (LibraryError, OSError) as exc:
            messagebox.showerror("ДопПро", f"Не удалось сделать копию.\n\n{exc}", parent=self)
            return
        self.status.configure(text="Копия добавлена в список.")
        self._reload(prefer=copy_id)

    def _delete(self) -> None:
        if not self.selected:
            messagebox.showwarning("ДопПро", "Сначала выберите программу, которую нужно убрать из списка.", parent=self)
            return
        title = "эту программу"
        for item in list_programs():
            if item.id == self.selected:
                title = f"«{item.title}»"
                break
        if not messagebox.askyesno(
            "ДопПро",
            f"Удалить {title} из списка? Уже собранный файл Word останется на диске.",
            parent=self,
        ):
            return
        removed = self.selected
        try:
            delete_program(removed)
        except LibraryError as exc:
            messagebox.showerror("ДопПро", str(exc), parent=self)
            return
        if self.app.model.library_id == removed:
            self.app.model.library_id = ""
            try:
                self.app.model.save_draft()
            except OSError:
                pass
        self.selected = ""
        self.status.configure(text="Программа удалена из списка.")
        self._reload()

    def _new_program(self) -> None:
        if self.app.model.title.strip() or self.app.model.organization.strip():
            agreed = messagebox.askyesno(
                "ДопПро",
                "Начать новую программу? Текущую сначала сохраните, если она нужна в списке.",
                parent=self,
            )
            if not agreed:
                return
        self.app.replace_program(ProgramData())
        self.destroy()

    def _export(self) -> None:
        self.app.step_frames[self.app.current].save()
        if self.selected and self.selected != self.app.model.library_id:
            try:
                program = load_program(self.selected)
            except LibraryError as exc:
                messagebox.showerror("ДопПро", str(exc), parent=self)
                return
        else:
            program = self.app.model
        name = program.title.strip() or "программа"
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Экспорт программы",
            initialfile=f"{name}.doppro.json",
            defaultextension=".json",
            filetypes=[("Программа ДопПро", "*.json"), ("Все файлы", "*.*")],
        )
        if not path:
            return
        try:
            export_program(program, Path(path))
        except OSError as exc:
            messagebox.showerror("ДопПро", f"Не удалось записать файл.\n\n{exc}", parent=self)
            return
        self.status.configure(text="Файл записан. Ключ нейросети в него не входит.")

    def _import(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Импорт программы",
            filetypes=[("Программа ДопПро", "*.json"), ("Все файлы", "*.*")],
        )
        if not path:
            return
        try:
            program = import_program(Path(path))
        except (LibraryError, OSError) as exc:
            messagebox.showerror("ДопПро", f"Файл не подошёл.\n\n{exc}", parent=self)
            return
        self._reload(prefer=program.library_id)
        if messagebox.askyesno("ДопПро", f"Открыть «{program.title or 'программу'}»?", parent=self):
            self.app.replace_program(program)
            self.destroy()
