# -*- coding: utf-8 -*-
"""Шаг 1. Паспорт программы: название, организация, педагог, место."""

from __future__ import annotations

from core.data_model import DIRECTIONS, LEVELS
from core.places import places_for, regions
from ui.pages.base import StepPage
from ui.widgets import Banner, Card, Combo, IntEdit, LineEdit, SearchEdit


class PassportPage(StepPage):
    index = 0
    ERR_MAP = (
        ("азвание программы", "title"),
        ("направленность", "direction"),
        ("уровень", "level"),
        ("организации", "organization"),
        ("ФИО педагога", "teacher"),
        ("должность педагога", "position"),
        ("регион", "region"),
        ("населённый пункт", "city"),
        ("Год программы", "year"),
    )

    def __init__(self, window):
        super().__init__(
            window,
            "Паспорт программы",
            "Поля со звёздочкой обязательны. Серый текст в поле — пример, в документ он не попадает.",
        )
        self.draft_note = Banner("info", "Открыт прошлый черновик с этого компьютера. Его можно поправить и собрать документ заново.")
        self.draft_note.setVisible(self.session.draft_used)
        self.add(self.draft_note)

        card = Card("Программа", "От названия зависят план, оснащение и формулировки нейросети.")
        self.title = LineEdit("Название объединения", 220)
        card.body.addWidget(
            self.field("title", "Название программы", self.title, True,
                       "Тема всей программы. План, оснащение и формулировки нейросети опираются на это название.")
        )
        self.direction = Combo(DIRECTIONS)
        self.level = Combo(LEVELS)
        self.year = IntEdit(4)
        card.row(
            self.field("direction", "Направленность", self.direction, True,
                       "Одна из шести направленностей. Без нейросети тексты документа берутся из неё."),
            self.field("level", "Уровень", self.level, True),
            self.field("year", "Год начала", self.year, True),
            stretch=(3, 2, 1),
        )
        self.add(card)

        card = Card("Организация", "Эти строки идут в шапку титульного листа и в гриф утверждения.")
        self.organization = LineEdit("Полное название организации", 320)
        card.body.addWidget(self.field("organization", "Организация", self.organization, True))
        self.org_short = LineEdit("Краткое название")
        card.body.addWidget(
            self.field("org_short", "Краткое название организации", self.org_short,
                       tip="Попадает в строку составителя вместо полного названия. Если пусто, останется полное.")
        )
        self.authority = LineEdit("Учредитель")
        self.department = LineEdit("Управление образования")
        card.row(
            self.field("authority", "Учредитель или министерство", self.authority),
            self.field("department", "Управление образования", self.department),
        )
        self.director_position = LineEdit("директор")
        self.director_name = LineEdit("Фамилия И.О.")
        card.row(
            self.field("director_position", "Должность руководителя", self.director_position),
            self.field("director_name", "ФИО руководителя", self.director_name),
        )
        self.add(card)

        card = Card("Педагог", "Фамилия педагога и название организации в нейросеть не отправляются.")
        self.teacher = LineEdit("Фамилия И.О.")
        self.position = LineEdit()
        card.row(
            self.field("teacher", "ФИО педагога", self.teacher, True),
            self.field("position", "Должность", self.position, True),
        )
        self.add(card)

        card = Card("Место", "Выберите из списка или впишите свои, если их там нет.")
        self.region = SearchEdit(regions(), "Начните вводить название региона")
        self.city = SearchEdit([], "Начните вводить название")
        self.region.textChanged.connect(self._region_changed)
        card.row(
            self.field("region", "Регион", self.region, True,
                       "Все регионы России. Введите несколько букв или нажмите клавишу «вниз». Если региона нет, впишите его сами."),
            self.field("city", "Город или населённый пункт", self.city, True,
                       "Пункты выбранного региона. Если вашего нет в списке, впишите название сами."),
        )
        # Выбор из списка-подсказки не считается ручным вводом, поэтому слушаем его отдельно.
        self.region.textChanged.connect(self._edited)
        self.city.textChanged.connect(self._edited)
        self.add(card)
        self.finish()

    def _region_changed(self, text: str) -> None:
        self.city.set_choices(places_for(text))

    def load(self) -> None:
        model = self.model
        self.draft_note.setVisible(self.session.draft_used)
        self.title.set_value(model.title)
        self.direction.set_value(model.direction)
        self.level.set_value(model.level)
        self.year.set_value(model.year)
        self.organization.set_value(model.organization)
        self.org_short.set_value(model.org_short)
        self.authority.set_value(model.authority)
        self.department.set_value(model.department)
        self.director_position.set_value(model.director_position)
        self.director_name.set_value(model.director_name)
        self.teacher.set_value(model.teacher_name)
        self.position.set_value(model.teacher_position)
        self.region.set_value(model.region)
        self.city.set_choices(places_for(model.region))
        self.city.set_value(model.city)

    def commit(self) -> None:
        model = self.model
        model.title = self.title.value()
        model.direction = self.direction.value()
        model.level = self.level.value()
        model.year = self.year.value()
        model.organization = self.organization.value()
        model.org_short = self.org_short.value()
        model.authority = self.authority.value()
        model.department = self.department.value()
        model.director_position = self.director_position.value()
        model.director_name = self.director_name.value()
        model.teacher_name = self.teacher.value()
        model.teacher_position = self.position.value()
        model.region = self.region.value()
        model.city = self.city.value()
