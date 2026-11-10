# -*- coding: utf-8 -*-
"""Шаг 4. Регион, оснащение и форма итоговой аттестации."""

from __future__ import annotations

import threading
from tkinter import messagebox

import customtkinter as ctk

from core.data_model import ATTESTATION_FORMS
from core.generator import GenerationError, generate_equipment
from core.templates_engine import profile_for
from gui.theme import DANGER, FONT_S, MUTED, NAVY, OK
from gui.tooltip import tooltip
from gui.widgets import LabeledCombo, LabeledText, caption, card, hint, secondary_button


class StepConditions(ctk.CTkScrollableFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        caption(self, "Условия и оснащение")
        hint(
            self,
            "«Составить оснащение по названию» заполняет оборудование, расходные материалы, "
            "программное обеспечение и профессии проб по названию программы. Ключ задаётся в «Настройках». "
            "Фамилия и организация в запрос не входят. "
            "Пустые поля можно также закрыть типовым перечнем направленности.",
        )
        self._waiting = False
        self._equipment_result = None
        self._equipment_error = None

        body = card(self)
        body.grid_columnconfigure(0, weight=1)

        self.regional = LabeledText(body, "Региональные особенности", height=90)
        self.regional.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        secondary_button(body, "Подставить типовую формулировку о регионе", self._fill_regional).grid(
            row=1, column=0, sticky="w", pady=(0, 12)
        )

        self.equipment = LabeledText(
            body,
            "Оборудование и материалы",
            height=110,
            tip="То, что остаётся в кабинете. Пустое поле закроет типовой перечень направленности.",
        )
        self.equipment.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.software = LabeledText(
            body,
            "Программное обеспечение",
            height=80,
            tip="Только программы, без которых тему не провести. Каждая строка станет отдельным пунктом.",
        )
        self.software.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self.consumables = LabeledText(
            body,
            "Расходные материалы",
            height=60,
            tip="То, что тратится на занятии: бумага, краска, ткань. Не дублируйте здесь мебель.",
        )
        self.consumables.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        self.room = LabeledText(body, "Помещение", height=60)
        self.room.grid(row=5, column=0, sticky="ew", pady=(0, 8))
        self.partners = LabeledText(body, "Партнёры и экскурсии вне часов программы", height=70)
        self.partners.grid(row=6, column=0, sticky="ew", pady=(0, 8))
        self.subjects = LabeledText(body, "Межпредметные связи", height=60)
        self.subjects.grid(row=7, column=0, sticky="ew", pady=(0, 8))
        self.professions = LabeledText(
            body,
            "Профессии и роли для проб",
            height=60,
            tip="Роли через точку с запятой. В документе это знакомство, а не профессиональное обучение.",
        )
        self.professions.grid(row=8, column=0, sticky="ew", pady=(0, 8))
        self.equipment_button = secondary_button(body, "Составить оснащение по названию", self._start_equipment)
        self.equipment_button.grid(row=9, column=0, sticky="ew", pady=(0, 4))
        tooltip(
            self.equipment_button,
            "Заполняет оборудование, расходные материалы, программы и профессии по названию. Нужен ключ.",
        )
        self.equipment_status = ctk.CTkLabel(
            body, text="", font=FONT_S, text_color=MUTED, anchor="w", justify="left", wraplength=860
        )
        self.equipment_status.grid(row=10, column=0, sticky="w", pady=(0, 8))
        self.upbringing = LabeledText(body, "На что опирается воспитание", height=50)
        self.upbringing.grid(row=11, column=0, sticky="ew", pady=(0, 8))
        secondary_button(body, "Подставить типовой перечень направленности", self._fill_equipment).grid(
            row=12, column=0, sticky="w", pady=(0, 12)
        )

        self.attestation = LabeledCombo(body, "Итоговая аттестация", ATTESTATION_FORMS, required=True)
        self.attestation.grid(row=13, column=0, sticky="ew")
        ctk.CTkLabel(
            body,
            text="Форма должна совпадать с тем, что реально можно провести в организации.",
            font=FONT_S,
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=860,
        ).grid(row=14, column=0, sticky="w", pady=(6, 0))

    def on_show(self) -> None:
        model = self.app.model
        self.regional.set(model.regional_notes)
        self.equipment.set(model.equipment)
        self.software.set(model.software)
        self.consumables.set(model.consumables)
        self.room.set(model.room)
        self.partners.set(model.partners)
        self.subjects.set(model.subjects)
        self.professions.set(model.professions)
        self.upbringing.set(model.upbringing_base)
        self.attestation.set(model.attestation_form)

    def save(self) -> None:
        model = self.app.model
        model.regional_notes = self.regional.get()
        model.equipment = self.equipment.get()
        model.software = self.software.get()
        model.consumables = self.consumables.get()
        model.room = self.room.get()
        model.partners = self.partners.get()
        model.subjects = self.subjects.get()
        model.professions = self.professions.get()
        model.upbringing_base = self.upbringing.get()
        model.attestation_form = self.attestation.get()

    def validate(self) -> list[str]:
        return self.app.model.errors_conditions()

    def _fill_regional(self) -> None:
        model = self.app.model
        city = self.app.model.city or "своём населённом пункте"
        region = self.app.model.region or "своём регионе"
        # Берём город и регион уже из модели: их сохранили на прошлом шаге.
        text = (
            f"Занятия идут в {model.city or city} ({model.region or region}). "
            "Педагог использует примеры, которые обучающиеся могут узнать рядом: "
            "городские объекты, местные события, материалы и работу людей вокруг."
        )
        self._replace(self.regional, text, "Заменить текст о регионе?")

    def _fill_equipment(self) -> None:
        profile = profile_for(self.app.model.direction)
        self._replace(self.equipment, profile["equipment"], "Заменить текст об оборудовании?")
        # Программы заполняем только если поле пустое, чтобы не стереть уже написанное вместе с оборудованием.
        if not self.software.get():
            self.software.set(profile["software"])

    def _start_equipment(self) -> None:
        if self._waiting:
            return
        self.save()
        if not self.app.model.title.strip():
            messagebox.showwarning("ДопПро", "Сначала укажите название программы на шаге «Паспорт».", parent=self.app)
            return
        if self.equipment.get() or self.consumables.get() or self.software.get() or self.professions.get():
            agreed = messagebox.askyesno(
                "ДопПро",
                "Заменить оборудование, расходные материалы, программное обеспечение и профессии текстом по названию программы?",
                parent=self.app,
            )
            if not agreed:
                return
        self._waiting = True
        self._equipment_result = None
        self._equipment_error = None
        self.equipment_button.configure(state="disabled")
        model = self.app.model
        self.equipment_status.configure(
            text=f"Составляю оснащение по названию «{model.title.strip()}»…",
            text_color=NAVY,
        )

        def work() -> None:
            try:
                self._equipment_result = generate_equipment(model)
            except Exception as exc:
                self._equipment_error = exc

        threading.Thread(target=work, daemon=True).start()
        self.after(200, self._poll_equipment)

    def _poll_equipment(self) -> None:
        if self._equipment_result is None and self._equipment_error is None:
            self.after(200, self._poll_equipment)
            return
        self._waiting = False
        self.equipment_button.configure(state="normal")
        if self._equipment_error is not None:
            text = str(self._equipment_error)
            if not isinstance(self._equipment_error, GenerationError):
                text = f"Не удалось составить оснащение.\n\n{text}"
            self.equipment_status.configure(text=text, text_color=DANGER)
            messagebox.showerror("ДопПро", text, parent=self.app)
            return
        ready = self._equipment_result
        self.equipment.set(ready["equipment"])
        self.consumables.set(ready["consumables"])
        self.software.set(ready["software"])
        self.professions.set(ready["professions"])
        self.save()
        try:
            self.app.model.save_draft()
        except OSError:
            pass
        self.equipment_status.configure(
            text="Оборудование, расходные материалы, программное обеспечение и профессии составлены по названию. Текст можно поправить.",
            text_color=OK,
        )

    def _replace(self, field: LabeledText, text: str, question: str) -> None:
        if field.get():
            agreed = messagebox.askyesno("ДопПро", question, parent=self.app)
            if not agreed:
                return
        field.set(text)
