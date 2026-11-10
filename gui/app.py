# -*- coding: utf-8 -*-
"""Главное окно мастера: шапка с логотипом, шаги, проверка и сборка."""

from __future__ import annotations

import ctypes
import threading
import webbrowser
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

from core.data_model import ProgramData
from core.paths import icon_path, logo_path
from core.updates import look_for_update
from gui.onboarding import OnboardingDialog, onboarding_seen
from gui.steps import StepBuild, StepConditions, StepLearners, StepPassport, StepPlan
from gui.theme import BG, DANGER, FONT_S, FONT_TITLE, LINE, MUTED, NAVY, TEAL
from gui.tooltip import tooltip
from gui.widgets import primary_button, secondary_button

STEP_NAMES = ["1  Паспорт", "2  Обучающиеся", "3  План", "4  Условия", "5  Сборка"]


class DopProApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        _set_windows_app_id()
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=BG)
        self.title("ДопПро")
        self.minsize(980, 660)
        self._place_on_screen()
        self._apply_icon()

        self.model, self.draft_used = ProgramData.load_draft()
        self.current = 0
        self.step_frames: list = []
        self.step_buttons: list[ctk.CTkButton] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build_header()
        self._build_steps()
        self._build_content()
        self._build_footer()
        self.show_step()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Configure>", self._on_resize)
        self.after(400, self._offer_onboarding)
        self.after(2500, self._check_updates)

    def show_step(self) -> None:
        for index, frame in enumerate(self.step_frames):
            if index == self.current:
                frame.grid(row=0, column=0, sticky="nsew")
                frame.on_show()
            else:
                frame.grid_remove()
        self._paint_steps()
        self._paint_nav()
        self.show_errors([])

    def next_step(self) -> None:
        step = self.step_frames[self.current]
        step.save()
        errors = step.validate()
        if errors:
            self.show_errors(errors)
            return
        self._remember()
        if self.current < len(self.step_frames) - 1:
            self.current += 1
            self.show_step()

    def back_step(self) -> None:
        self.step_frames[self.current].save()
        self._remember()
        if self.current > 0:
            self.current -= 1
            self.show_step()

    def jump(self, index: int) -> None:
        """На пройденный шаг можно вернуться. Вперёд — только кнопкой «Далее»."""
        if index >= self.current:
            return
        self.step_frames[self.current].save()
        self._remember()
        self.current = index
        self.show_step()

    def open_settings(self) -> None:
        from gui.settings_dialog import SettingsDialog

        SettingsDialog(self)

    def open_help(self) -> None:
        OnboardingDialog(self)

    def open_library(self) -> None:
        from gui.library_dialog import LibraryDialog

        self.step_frames[self.current].save()
        LibraryDialog(self)

    def replace_program(self, program) -> None:
        """Подменяет открытую программу и возвращает мастер на первый шаг."""
        self.model = program
        self.current = 0
        self.show_step()
        self._remember()

    def _offer_onboarding(self) -> None:
        if not onboarding_seen():
            self.open_help()

    def _check_updates(self) -> None:
        def work() -> None:
            report = look_for_update()
            if report.newer:
                self.after(0, lambda: self._offer_update(report))

        threading.Thread(target=work, daemon=True).start()

    def _offer_update(self, report) -> None:
        if messagebox.askyesno(
            "ДопПро",
            f"Вышла версия {report.remote}. Открыть страницу загрузки?",
            parent=self,
        ):
            webbrowser.open(report.url)

    def build(self) -> None:
        self.step_frames[self.current].save()
        errors = self.model.validate()
        if errors:
            self.show_errors(errors)
            builder = self.step_frames[-1]
            if isinstance(builder, StepBuild):
                builder._render_preview()
            return
        self.show_errors([])
        self.step_frames[-1].generate()

    def show_errors(self, errors: list[str]) -> None:
        if not errors:
            self.error_label.configure(text="")
            return
        shown = errors[:6]
        text = "\n".join(shown)
        if len(errors) > len(shown):
            text += f"\nи ещё {len(errors) - len(shown)}"
        self.error_label.configure(text=text)

    def _remember(self) -> None:
        try:
            self.model.save_draft()
        except OSError:
            pass

    def _on_close(self) -> None:
        try:
            self.step_frames[self.current].save()
            self._remember()
        except Exception:
            pass
        self.destroy()

    def _on_resize(self, event) -> None:
        if event.widget is self:
            self.error_label.configure(wraplength=max(420, event.width - 48))

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="white", corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        self._logo_image = None
        logo = logo_path()
        if logo.exists():
            self._pil_logo = Image.open(logo)
            self._logo_image = ctk.CTkImage(light_image=self._pil_logo, dark_image=self._pil_logo, size=(52, 52))
            ctk.CTkLabel(header, text="", image=self._logo_image).grid(row=0, column=0, padx=(18, 10), pady=12)
        else:
            ctk.CTkLabel(header, text="", width=18).grid(row=0, column=0)

        titles = ctk.CTkFrame(header, fg_color="white")
        titles.grid(row=0, column=1, sticky="w", pady=12)
        ctk.CTkLabel(titles, text="ДопПро", font=FONT_TITLE, text_color=NAVY, anchor="w").pack(anchor="w")
        ctk.CTkLabel(
            titles,
            text="Конструктор дополнительных общеобразовательных программ",
            font=FONT_S,
            text_color=MUTED,
            anchor="w",
        ).pack(anchor="w")

        help_button = ctk.CTkButton(
            header,
            text="Помощь",
            command=self.open_help,
            height=28,
            width=64,
            font=FONT_S,
            fg_color="transparent",
            hover_color=BG,
            text_color=MUTED,
            corner_radius=6,
        )
        help_button.grid(row=0, column=2, padx=(0, 2), pady=12, sticky="e")
        library_button = secondary_button(header, "Мои программы", self.open_library)
        library_button.grid(row=0, column=3, padx=(0, 8), pady=12, sticky="e")
        settings_button = secondary_button(header, "Настройки", self.open_settings)
        settings_button.grid(row=0, column=4, padx=(0, 8), pady=12, sticky="e")
        offline = ctk.CTkLabel(header, text="Шаблон без интернета", font=FONT_S, text_color=TEAL)
        offline.grid(row=0, column=5, padx=(0, 18), sticky="e")
        ctk.CTkFrame(header, fg_color=LINE, height=1, corner_radius=0).grid(row=1, column=0, columnspan=6, sticky="ew")
        tooltip(help_button, "Коротко о пяти шагах. То же окно, что при первом запуске.")
        tooltip(library_button, "Несколько сохранённых программ. Ключ нейросети в этот список не записывается.")
        tooltip(settings_button, "Ключ нейросети. Хранится только на этом компьютере и в документ не попадает.")
        tooltip(offline, "Документ собирается и без сети. Нейросеть нужна только для формулировок по названию.")

    def _build_steps(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        bar.grid(row=1, column=0, sticky="ew", padx=12, pady=(10, 4))
        step_tips = (
            "Название, организация и педагог. Звёздочка — обязательное поле.",
            "Возраст, часы и размер группы. От них зависят календарь и занятия.",
            "Разделы и часы. Сумма должна совпасть с общим объёмом.",
            "Оборудование, программы, расходные материалы и профессии проб.",
            "Проверка текста и сборка файла Word.",
        )
        for index, name in enumerate(STEP_NAMES):
            bar.grid_columnconfigure(index, weight=1)
            button = ctk.CTkButton(
                bar,
                text=name,
                height=34,
                font=FONT_S,
                corner_radius=8,
                command=lambda i=index: self.jump(i),
            )
            button.grid(row=0, column=index, sticky="ew", padx=4)
            tooltip(button, step_tips[index])
            self.step_buttons.append(button)

    def _build_content(self) -> None:
        self.content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.content.grid(row=2, column=0, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        self.step_frames = [
            StepPassport(self.content, self),
            StepLearners(self.content, self),
            StepPlan(self.content, self),
            StepConditions(self.content, self),
            StepBuild(self.content, self),
        ]

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="white", corner_radius=0)
        footer.grid(row=3, column=0, sticky="ew")
        self.error_label = ctk.CTkLabel(
            footer,
            text="",
            font=FONT_S,
            text_color=DANGER,
            anchor="w",
            justify="left",
            wraplength=900,
        )
        self.error_label.pack(fill="x", padx=20, pady=(8, 0))
        buttons = ctk.CTkFrame(footer, fg_color="white")
        buttons.pack(fill="x", padx=16, pady=(6, 12))
        self.back_button = secondary_button(buttons, "Назад", self.back_step)
        self.back_button.pack(side="left")
        self.step_caption = ctk.CTkLabel(buttons, text="", font=FONT_S, text_color=MUTED)
        self.step_caption.pack(side="left", padx=16)
        self.next_button = primary_button(buttons, "Далее", self.next_step)
        self.next_button.pack(side="right")
        tooltip(self.back_button, "Вернуться на предыдущий шаг. Введённое сохранится в черновик.")
        tooltip(self.next_button, "Проверить этот шаг и перейти дальше. На последнем шаге здесь сборка документа.")

    def _paint_steps(self) -> None:
        for index, button in enumerate(self.step_buttons):
            if index == self.current:
                button.configure(fg_color=NAVY, hover_color=NAVY, text_color="white", state="normal")
            elif index < self.current:
                button.configure(fg_color=TEAL, hover_color="#0B655E", text_color="white", state="normal")
            else:
                button.configure(fg_color="#E2E8F0", hover_color="#E2E8F0", text_color="#64748B", state="disabled")

    def _paint_nav(self) -> None:
        last = self.current == len(self.step_frames) - 1
        self.back_button.configure(state="normal" if self.current else "disabled")
        self.step_caption.configure(text=f"Шаг {self.current + 1} из {len(self.step_frames)}")
        if last:
            self.next_button.configure(text="Собрать программу", command=self.build)
        else:
            self.next_button.configure(text="Далее", command=self.next_step)

    def _place_on_screen(self) -> None:
        width, height = 1100, 760
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _apply_icon(self) -> None:
        icon = icon_path()
        if not icon.exists():
            return
        try:
            self.iconbitmap(str(icon))
        except Exception:
            return


def _set_windows_app_id() -> None:
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DopPro.Desktop.1")
    except Exception:
        return


def run() -> None:
    app = DopProApp()
    app.mainloop()
