# -*- coding: utf-8 -*-
"""Шаг 3. Разделы, часы и опции: пробы, мини-проект, итоговая работа."""

from __future__ import annotations

import threading
from tkinter import messagebox

import customtkinter as ctk

from core.data_model import ModuleItem
from core.generator import GenerationError, generate_plan
from core.planning import default_modules, scale_modules
from gui.theme import DANGER, FONT, FONT_B, FONT_S, LINE, MUTED, NAVY, OK
from gui.tooltip import tooltip
from gui.widgets import bind_text_shortcuts, caption, card, checkbox, hint, parse_int, secondary_button, set_checkbox


def _lines(widget) -> list[str]:
    raw = widget.get("1.0", "end").strip()
    return [line.strip() for line in raw.splitlines() if line.strip()][:24]


class StepPlan(ctk.CTkScrollableFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._rows: list[dict] = []

        caption(self, "Учебный план")
        hint(
            self,
            "Часы всех разделов должны сойтись с общим объёмом. "
            "Каждый учебный день в календарно-тематическом плане получает тему лекции и тему практики. "
            "Списки ниже — по одной теме на строку. Если список пуст, программа составит темы сама. "
            "«Составить план по названию» берёт тему, возраст и часы из предыдущих шагов. "
            "Ключ задаётся в «Настройках». Фамилия и организация в запрос не входят.",
        )

        tools = card(self)
        tools.grid_columnconfigure((0, 1, 2), weight=1)
        add_button = secondary_button(tools, "Добавить раздел", self._add)
        add_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        defaults_button = secondary_button(tools, "Типовые разделы", self._load_defaults)
        defaults_button.grid(row=0, column=1, sticky="ew", padx=6)
        scale_button = secondary_button(tools, "Распределить часы", self._scale)
        scale_button.grid(row=0, column=2, sticky="ew", padx=(6, 0))
        tooltip(add_button, "Пустой раздел в конец списка. Часы потом нужно свести с общим объёмом.")
        tooltip(defaults_button, "Заменяет разделы типовым набором выбранной направленности, не вашей темой.")
        tooltip(scale_button, "Раскладывает уже указанные часы так, чтобы сумма совпала с общим объёмом.")
        self.plan_button = secondary_button(tools, "Составить план по названию", self._start_plan)
        self.plan_button.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        tooltip(self.plan_button, "Просит разделы, темы лекций и практик по названию. Нужен ключ в «Настройках».")
        self.plan_status = ctk.CTkLabel(tools, text="", font=FONT_S, text_color=MUTED, anchor="w", justify="left", wraplength=860)
        self.plan_status.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self._waiting = False
        self._plan_result = None
        self._plan_error = None

        self.sum_label = ctk.CTkLabel(tools, text="", font=FONT_B, anchor="w", justify="left")
        self.sum_label.grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 0))

        self.list_card = card(self)
        self.list_card.grid_columnconfigure(0, weight=1)

        options = card(self)
        options.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(options, text="Что включить в программу", font=FONT_B, text_color=NAVY, anchor="w").grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        self.trials = checkbox(options, "Профессиональные пробы")
        self.regional = checkbox(options, "Региональный мини-проект")
        self.final = checkbox(options, "Итоговый проект или итоговый продукт")
        self.interim = checkbox(options, "Промежуточная аттестация по разделам")
        self.excursions = checkbox(options, "Экскурсии или выездные занятия")
        for row, box in enumerate((self.trials, self.regional, self.final, self.interim, self.excursions), start=1):
            box.grid(row=row, column=0, sticky="w", pady=3)
        tooltip(self.trials, "Добавляет знакомство с ролью специалиста. Отдельные часы под это не выделяются.")
        tooltip(self.regional, "Связывает один раздел с городом из паспорта.")
        tooltip(self.final, "Нужно включить, если итоговая аттестация — защита проекта.")
        tooltip(self.interim, "В середине срока появится промежуточная проверка по разделам.")
        tooltip(self.excursions, "Отметьте, если выезды есть. Их часы входят в практические разделы.")
        ctk.CTkLabel(
            options,
            text=(
                "Если на предыдущем шаге несколько возрастных промежутков, проба для младших из них остаётся коротким шагом, "
                "а для старшего — ближе к роли. Отдельные часы под опции не добавляются — они входят в практические и проектные разделы."
            ),
            font=FONT_S,
            text_color=MUTED,
            wraplength=860,
            justify="left",
            anchor="w",
        ).grid(row=6, column=0, sticky="w", pady=(8, 0))

    def on_show(self) -> None:
        model = self.app.model
        if not model.modules:
            hours = model.total_hours if model.total_hours > 0 else 144
            model.modules = default_modules(model.direction, hours)
        self._draw()
        set_checkbox(self.trials, model.professional_trials)
        set_checkbox(self.regional, model.regional_project)
        set_checkbox(self.final, model.final_project)
        set_checkbox(self.interim, model.interim_attestation)
        set_checkbox(self.excursions, model.excursions)
        self._refresh_sum()

    def save(self) -> None:
        self._read()
        model = self.app.model
        model.professional_trials = bool(self.trials.get())
        model.regional_project = bool(self.regional.get())
        model.final_project = bool(self.final.get())
        model.interim_attestation = bool(self.interim.get())
        model.excursions = bool(self.excursions.get())

    def validate(self) -> list[str]:
        return self.app.model.errors_plan()

    def _read(self) -> None:
        modules: list[ModuleItem] = []
        for row in self._rows:
            name = row["name"].get().strip()
            theory_raw = row["theory"].get().strip()
            practice_raw = row["practice"].get().strip()
            theory = parse_int(theory_raw) if theory_raw else 0
            practice = parse_int(practice_raw) if practice_raw else 0
            modules.append(
                ModuleItem(
                    name=name,
                    theory=theory,
                    practice=practice,
                    lectures=_lines(row["lectures"]),
                    practices=_lines(row["practices"]),
                )
            )
        self.app.model.modules = modules

    def _draw(self) -> None:
        for child in self.list_card.winfo_children():
            child.destroy()
        self._rows = []
        for index, module in enumerate(self.app.model.modules):
            self._add_row(index, module)
        if not self.app.model.modules:
            ctk.CTkLabel(
                self.list_card,
                text="Разделов пока нет. Добавьте раздел или подставьте типовой набор.",
                font=FONT,
                text_color=MUTED,
                anchor="w",
            ).grid(row=0, column=0, sticky="w")

    def _add_row(self, index: int, module: ModuleItem) -> None:
        row = ctk.CTkFrame(self.list_card, fg_color="#F8FAFC", corner_radius=8, border_width=1, border_color=LINE)
        row.grid(row=index, column=0, sticky="ew", pady=4)
        row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(row, text=f"{index + 1}.", font=FONT_B, text_color=NAVY, width=28).grid(
            row=0, column=0, padx=(8, 4), pady=8
        )
        name = ctk.CTkEntry(row, height=34, font=FONT, border_color=LINE, fg_color="white")
        name.insert(0, module.name)
        name.grid(row=0, column=1, columnspan=6, sticky="ew", padx=(0, 8), pady=(8, 4))
        bind_text_shortcuts(name)

        ctk.CTkLabel(row, text="Теория", font=FONT_S, text_color=MUTED).grid(row=1, column=1, sticky="w", padx=(0, 4))
        theory = ctk.CTkEntry(row, width=70, height=32, font=FONT, border_color=LINE, fg_color="white")
        theory.insert(0, str(module.theory))
        theory.grid(row=1, column=2, sticky="w", pady=(0, 8))
        bind_text_shortcuts(theory)

        ctk.CTkLabel(row, text="Практика", font=FONT_S, text_color=MUTED).grid(row=1, column=3, sticky="w", padx=(12, 4))
        practice = ctk.CTkEntry(row, width=70, height=32, font=FONT, border_color=LINE, fg_color="white")
        practice.insert(0, str(module.practice))
        practice.grid(row=1, column=4, sticky="w", pady=(0, 8))
        bind_text_shortcuts(practice)

        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.grid(row=1, column=5, columnspan=2, sticky="e", padx=(8, 8), pady=(0, 8))
        secondary_button(actions, "Выше", lambda i=index: self._move(i, -1)).pack(side="left", padx=2)
        secondary_button(actions, "Ниже", lambda i=index: self._move(i, 1)).pack(side="left", padx=2)
        secondary_button(actions, "Удалить", lambda i=index: self._delete(i)).pack(side="left", padx=2)

        ctk.CTkLabel(row, text="Темы лекций", font=FONT_S, text_color=MUTED, anchor="w").grid(
            row=2, column=1, columnspan=6, sticky="w", padx=(0, 8)
        )
        lectures = ctk.CTkTextbox(row, height=64, font=FONT_S, border_width=1, border_color=LINE, fg_color="white")
        lectures.grid(row=3, column=1, columnspan=6, sticky="ew", padx=(0, 8), pady=(2, 6))
        if module.lectures:
            lectures.insert("1.0", "\n".join(module.lectures))
        bind_text_shortcuts(lectures)

        ctk.CTkLabel(row, text="Темы практик", font=FONT_S, text_color=MUTED, anchor="w").grid(
            row=4, column=1, columnspan=6, sticky="w", padx=(0, 8)
        )
        practices = ctk.CTkTextbox(row, height=64, font=FONT_S, border_width=1, border_color=LINE, fg_color="white")
        practices.grid(row=5, column=1, columnspan=6, sticky="ew", padx=(0, 8), pady=(2, 8))
        if module.practices:
            practices.insert("1.0", "\n".join(module.practices))
        bind_text_shortcuts(practices)

        theory.bind("<KeyRelease>", lambda _event: self._refresh_sum())
        practice.bind("<KeyRelease>", lambda _event: self._refresh_sum())
        self._rows.append({"name": name, "theory": theory, "practice": practice, "lectures": lectures, "practices": practices})

    def _refresh_sum(self) -> None:
        total = 0
        broken = False
        for row in self._rows:
            theory_raw = row["theory"].get().strip()
            practice_raw = row["practice"].get().strip()
            theory = parse_int(theory_raw) if theory_raw else 0
            practice = parse_int(practice_raw) if practice_raw else 0
            if theory < 0 or practice < 0:
                broken = True
                continue
            total += theory + practice
        target = self.app.model.total_hours
        if broken:
            self.sum_label.configure(text="В часах раздела должны быть целые числа.", text_color=DANGER)
            return
        if target > 0 and total == target:
            self.sum_label.configure(text=f"Часов в разделах: {total} из {target}. Сходится.", text_color=OK)
        else:
            self.sum_label.configure(
                text=f"Часов в разделах: {total} из {target}. Пока не сходится.",
                text_color=DANGER,
            )

    def _add(self) -> None:
        self._read()
        self.app.model.modules.append(ModuleItem("Новый раздел", 0, 2))
        self._draw()
        self._refresh_sum()

    def _delete(self, index: int) -> None:
        self._read()
        if len(self.app.model.modules) <= 1:
            messagebox.showwarning("ДопПро", "В программе нужен хотя бы один раздел.", parent=self.app)
            return
        del self.app.model.modules[index]
        self._draw()
        self._refresh_sum()

    def _move(self, index: int, shift: int) -> None:
        self._read()
        target = index + shift
        modules = self.app.model.modules
        if target < 0 or target >= len(modules):
            return
        modules[index], modules[target] = modules[target], modules[index]
        self._draw()
        self._refresh_sum()

    def _load_defaults(self) -> None:
        self._read()
        if any(item.name.strip() for item in self.app.model.modules):
            agreed = messagebox.askyesno(
                "ДопПро",
                "Заменить текущие разделы типовым набором выбранной направленности?",
                parent=self.app,
            )
            if not agreed:
                return
        hours = self.app.model.total_hours if self.app.model.total_hours > 0 else 144
        self.app.model.modules = default_modules(self.app.model.direction, hours)
        self._draw()
        self._refresh_sum()

    def _start_plan(self) -> None:
        if self._waiting:
            return
        self.save()
        if not self.app.model.title.strip():
            messagebox.showwarning("ДопПро", "Сначала укажите название программы на шаге «Паспорт».", parent=self.app)
            return
        if any(item.name.strip() for item in self.app.model.modules):
            agreed = messagebox.askyesno(
                "ДопПро",
                "Заменить текущие разделы планом по названию программы? Часы будут сведены с общим объёмом.",
                parent=self.app,
            )
            if not agreed:
                return
        self._waiting = True
        self._plan_result = None
        self._plan_error = None
        self.plan_button.configure(state="disabled")
        model = self.app.model
        self.plan_status.configure(
            text=f"Составляю разделы по названию «{model.title.strip()}»…",
            text_color=NAVY,
        )

        def work() -> None:
            try:
                self._plan_result = generate_plan(model)
            except Exception as exc:
                self._plan_error = exc

        threading.Thread(target=work, daemon=True).start()
        self.after(200, self._poll_plan)

    def _poll_plan(self) -> None:
        if self._plan_result is None and self._plan_error is None:
            self.after(200, self._poll_plan)
            return
        self._waiting = False
        self.plan_button.configure(state="normal")
        if self._plan_error is not None:
            text = str(self._plan_error)
            if not isinstance(self._plan_error, GenerationError):
                text = f"Не удалось составить план.\n\n{text}"
            self.plan_status.configure(text=text, text_color=DANGER)
            messagebox.showerror("ДопПро", text, parent=self.app)
            return
        self.app.model.modules = self._plan_result
        self.app.model.generated = {}
        try:
            self.app.model.save_draft()
        except OSError:
            pass
        self.plan_status.configure(
            text="Разделы составлены по названию, часы сведены с объёмом. Тексты разделов на шаге сборки нужно сформулировать заново.",
            text_color=OK,
        )
        self._draw()
        self._refresh_sum()

    def _scale(self) -> None:
        self._read()
        hours = self.app.model.total_hours
        if hours <= 0:
            messagebox.showwarning("ДопПро", "Сначала укажите общий объём часов на предыдущем шаге.", parent=self.app)
            return
        if not self.app.model.modules:
            return
        self.app.model.modules = scale_modules(self.app.model.modules, hours)
        self._draw()
        self._refresh_sum()
