# -*- coding: utf-8 -*-
"""Шаг 1. Паспорт программы: название, организация, педагог, место."""

from __future__ import annotations

import customtkinter as ctk

from core.data_model import DIRECTIONS, LEVELS
from gui.theme import FONT_S, MUTED
from gui.tooltip import tooltip
from core.places import places_for, regions
from gui.widgets import LabeledCombo, LabeledEntry, SearchableCombo, caption, card, hint, parse_int


class StepPassport(ctk.CTkScrollableFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        caption(self, "Паспорт программы")
        hint(self, "Поля со звёздочкой обязательны. Подсказки в полях — пример, они не попадают в документ, пока вы их не впишете.")
        if app.draft_used:
            hint(self, "Открыт прошлый черновик с этого компьютера. Его можно поправить и собрать документ заново.")

        body = card(self)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        self.title = LabeledEntry(
            body,
            "Название программы",
            required=True,
            placeholder="Название объединения",
            tip="Тема всей программы. План, оснащение и формулировки нейросети опираются на это название.",
        )
        self.title.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        self.direction = LabeledCombo(
            body,
            "Направленность",
            DIRECTIONS,
            required=True,
            tip="Одна из шести направленностей. Без нейросети тексты документа берутся из неё.",
        )
        self.direction.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(0, 10))
        self.level = LabeledCombo(body, "Уровень", LEVELS, required=True)
        self.level.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))

        self.organization = LabeledEntry(
            body,
            "Организация",
            required=True,
            placeholder="Полное название организации",
        )
        self.organization.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        self.authority = LabeledEntry(
            body,
            "Учредитель или министерство",
            placeholder="Учредитель",
        )
        self.authority.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.department = LabeledEntry(
            body,
            "Управление образования",
            placeholder="Управление образования",
        )
        self.department.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.org_short = LabeledEntry(
            body,
            "Краткое название организации",
            placeholder="Краткое название",
            tip="Попадает в строку составителя вместо полного названия. Если пусто, останется полное.",
        )
        self.org_short.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        self.teacher = LabeledEntry(body, "ФИО педагога", required=True, placeholder="Фамилия И.О.")
        self.teacher.grid(row=6, column=0, sticky="ew", padx=(0, 8), pady=(0, 10))
        self.position = LabeledEntry(body, "Должность", required=True)
        self.position.grid(row=6, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))

        self.director_position = LabeledEntry(body, "Должность руководителя", placeholder="директор")
        self.director_position.grid(row=7, column=0, sticky="ew", padx=(0, 8), pady=(0, 10))
        self.director_name = LabeledEntry(body, "ФИО руководителя", placeholder="Фамилия И.О.")
        self.director_name.grid(row=7, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))

        self.region = SearchableCombo(
            body,
            "Регион",
            regions(),
            required=True,
            tip="Все регионы России. Введите несколько букв и откройте список стрелкой или клавишей «вниз». Если региона нет, впишите его сами.",
            on_commit=self._region_chosen,
        )
        self.region.grid(row=8, column=0, sticky="ew", padx=(0, 8), pady=(0, 10))
        self.city = SearchableCombo(
            body,
            "Город или населённый пункт",
            [],
            required=True,
            tip="Пункты выбранного региона. Если вашего нет в списке, впишите название сами.",
        )
        self.city.grid(row=8, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))

        ctk.CTkLabel(
            body,
            text="Регион и населённый пункт можно выбрать из списка или вписать свои, если их там нет.",
            font=FONT_S,
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=860,
        ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(0, 10))

        self.year = LabeledEntry(body, "Год начала программы", required=True)
        self.year.grid(row=10, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkLabel(
            body,
            text="Направленность — одна из шести, по которым описывают дополнительные программы.",
            font=FONT_S,
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=420,
        ).grid(row=10, column=1, sticky="w", padx=(8, 0))

    def on_show(self) -> None:
        model = self.app.model
        self.title.set(model.title)
        self.direction.set(model.direction)
        self.level.set(model.level)
        self.organization.set(model.organization)
        self.authority.set(model.authority)
        self.department.set(model.department)
        self.org_short.set(model.org_short)
        self.teacher.set(model.teacher_name)
        self.position.set(model.teacher_position)
        self.director_position.set(model.director_position)
        self.director_name.set(model.director_name)
        self.region.set(model.region)
        self._region_chosen()
        self.city.set(model.city)
        self.year.set(str(model.year) if model.year > 0 else "")

    def _region_chosen(self) -> None:
        current = self.city.get() if hasattr(self, "city") else ""
        self.city.set_choices(places_for(self.region.get()))
        if current:
            self.city.set(current)

    def save(self) -> None:
        model = self.app.model
        model.title = self.title.get()
        model.direction = self.direction.get()
        model.level = self.level.get()
        model.organization = self.organization.get()
        model.authority = self.authority.get()
        model.department = self.department.get()
        model.org_short = self.org_short.get()
        model.teacher_name = self.teacher.get()
        model.teacher_position = self.position.get()
        model.director_position = self.director_position.get()
        model.director_name = self.director_name.get()
        model.region = self.region.get()
        model.city = self.city.get()
        model.year = parse_int(self.year.get())

    def validate(self) -> list[str]:
        return self.app.model.errors_passport()
