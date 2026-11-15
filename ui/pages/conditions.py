# -*- coding: utf-8 -*-
"""Шаг 4. Регион, оснащение и форма итоговой аттестации."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout

from core.data_model import ATTESTATION_FORMS
from core.generator import GenerationError, generate_equipment
from core.templates_engine import profile_for
from ui.pages.base import StepPage
from ui.theme import Glyph
from ui.widgets import Banner, Button, Card, Combo, TextArea, alert, ask, run_async


class ConditionsPage(StepPage):
    index = 3
    ERR_MAP = (
        ("аттестаци", "attestation"),
        ("Итоговая форма", "attestation"),
        ("об оборудовании", "equipment"),
        ("программном обеспечении", "software"),
        ("региональных особенностях", "regional"),
        ("о партнёрах", "partners"),
        ("о расходных", "consumables"),
        ("о помещении", "room"),
        ("о межпредметных", "subjects"),
        ("о профессиях", "professions"),
    )

    def __init__(self, window):
        super().__init__(
            window,
            "Условия и оснащение",
            "Пустые поля закроет типовой перечень направленности. Всё можно поправить вручную.",
        )
        self._waiting = False

        card = Card("Оснащение", "Нейросеть может составить эти четыре поля по названию программы. "
                                 "Фамилия и организация в запрос не входят.")
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.equipment_button = Button(
            "Составить оснащение по названию", "teal", Glyph.SPARK, on=self._start_equipment,
            tip="Заполняет оборудование, расходные материалы, программы и профессии по названию. Нужен ключ в «Настройках».",
        )
        buttons.addWidget(self.equipment_button)
        buttons.addWidget(Button("Типовой перечень направленности", glyph=Glyph.LIST, on=self._fill_equipment,
                                 tip="Подставляет оборудование из типового перечня. Программы заполняются, только если поле пустое."))
        buttons.addStretch(1)
        card.body.addLayout(buttons)
        self.equipment_status = Banner("info")
        self.equipment_status.hide()
        card.body.addWidget(self.equipment_status)
        self.equipment = TextArea(120)
        card.body.addWidget(self.field(
            "equipment", "Оборудование и материалы", self.equipment,
            tip="То, что остаётся в кабинете. Пустое поле закроет типовой перечень направленности."))
        self.software = TextArea(84)
        self.consumables = TextArea(84)
        card.row(
            self.field("software", "Программное обеспечение", self.software,
                       tip="Только программы, без которых тему не провести. Каждая строка станет отдельным пунктом."),
            self.field("consumables", "Расходные материалы", self.consumables,
                       tip="То, что тратится на занятии: бумага, краска, ткань. Не дублируйте здесь мебель."),
        )
        self.professions = TextArea(64)
        card.body.addWidget(self.field(
            "professions", "Профессии и роли для проб", self.professions,
            tip="Роли через точку с запятой. В документе это знакомство, а не профессиональное обучение."))
        self.add(card)

        card = Card("Место и связи")
        self.regional = TextArea(90)
        regional_field = self.field("regional", "Региональные особенности", self.regional)
        card.body.addWidget(regional_field)
        line = QHBoxLayout()
        line.addWidget(Button("Подставить типовую формулировку о регионе", "ghost", Glyph.LOCATION,
                              on=self._fill_regional))
        line.addStretch(1)
        card.body.addLayout(line)
        self.room = TextArea(64)
        self.partners = TextArea(64)
        card.row(
            self.field("room", "Помещение", self.room),
            self.field("partners", "Партнёры и экскурсии вне часов программы", self.partners),
        )
        self.subjects = TextArea(64)
        self.upbringing = TextArea(64)
        card.row(
            self.field("subjects", "Межпредметные связи", self.subjects),
            self.field("upbringing", "На что опирается воспитание", self.upbringing),
        )
        self.add(card)

        card = Card("Итоговая аттестация", "Форма должна совпадать с тем, что реально можно провести в организации.")
        self.attestation = Combo(ATTESTATION_FORMS)
        card.body.addWidget(self.field("attestation", "Форма итоговой аттестации", self.attestation, True))
        self.add(card)
        self.finish()

    def load(self) -> None:
        model = self.model
        self.regional.set_value(model.regional_notes)
        self.equipment.set_value(model.equipment)
        self.software.set_value(model.software)
        self.consumables.set_value(model.consumables)
        self.room.set_value(model.room)
        self.partners.set_value(model.partners)
        self.subjects.set_value(model.subjects)
        self.professions.set_value(model.professions)
        self.upbringing.set_value(model.upbringing_base)
        self.attestation.set_value(model.attestation_form)

    def commit(self) -> None:
        model = self.model
        model.regional_notes = self.regional.value()
        model.equipment = self.equipment.value()
        model.software = self.software.value()
        model.consumables = self.consumables.value()
        model.room = self.room.value()
        model.partners = self.partners.value()
        model.subjects = self.subjects.value()
        model.professions = self.professions.value()
        model.upbringing_base = self.upbringing.value()
        model.attestation_form = self.attestation.value()

    def _replace(self, editor: TextArea, text: str, question: str) -> None:
        if editor.value() and not ask(self, question, yes="Заменить"):
            return
        editor.set_value(text)

    def _fill_regional(self) -> None:
        model = self.model
        city = model.city or "своём населённом пункте"
        region = model.region or "своём регионе"
        text = (
            f"Занятия идут в {city} ({region}). "
            "Педагог использует примеры, которые обучающиеся могут узнать рядом: "
            "городские объекты, местные события, материалы и работу людей вокруг."
        )
        self._replace(self.regional, text, "Заменить текст о регионе?")

    def _fill_equipment(self) -> None:
        profile = profile_for(self.model.direction)
        self._replace(self.equipment, profile["equipment"], "Заменить текст об оборудовании?")
        if not self.software.value():
            self.software.set_value(profile["software"])

    def _start_equipment(self) -> None:
        if self._waiting:
            return
        self.commit()
        model = self.model
        if not model.title.strip():
            alert(self, "Сначала укажите название программы", "Оно задаётся на шаге «Паспорт».", "warn")
            return
        if self.equipment.value() or self.consumables.value() or self.software.value() or self.professions.value():
            if not ask(self, "Заменить оснащение текстом по названию?",
                       "Оборудование, расходные материалы, программное обеспечение и профессии будут заменены.",
                       yes="Заменить"):
                return
        self._waiting = True
        self.equipment_button.setEnabled(False)
        self.equipment_status.show_message("info", f"Составляю оснащение по названию «{model.title.strip()}»…")
        run_async(self, lambda: generate_equipment(model), self._equipment_ready, self._equipment_failed)

    def _equipment_failed(self, error) -> None:
        self._waiting = False
        self.equipment_button.setEnabled(True)
        text = str(error)
        if not isinstance(error, GenerationError):
            text = f"Не удалось составить оснащение.\n\n{text}"
        self.equipment_status.show_message("error", text)

    def _equipment_ready(self, ready) -> None:
        self._waiting = False
        self.equipment_button.setEnabled(True)
        self.equipment.set_value(ready["equipment"])
        self.consumables.set_value(ready["consumables"])
        self.software.set_value(ready["software"])
        self.professions.set_value(ready["professions"])
        self.equipment_status.show_message(
            "ok",
            "Оборудование, расходные материалы, программное обеспечение и профессии составлены по названию. "
            "Текст можно поправить.",
        )
