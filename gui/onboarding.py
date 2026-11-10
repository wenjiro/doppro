# -*- coding: utf-8 -*-
"""Короткое знакомство при первом запуске. Потом его открывает кнопка «Помощь»."""

from __future__ import annotations

import json

import customtkinter as ctk

from core.paths import onboarding_path
from gui.theme import FONT, FONT_H, FONT_S, MUTED, NAVY
from gui.widgets import primary_button, secondary_button

PAGES = (
    (
        "С чего начать",
        "ДопПро собирает дополнительную общеобразовательную программу в файл Word.\n\n"
        "Впереди пять шагов. Поля со звёздочкой обязательны. Серый текст внутри поля — пример: "
        "в документ он не попадёт, пока вы его не впишете.\n\n"
        "Черновик сохраняется на этом компьютере, когда вы нажимаете «Далее» или закрываете окно. "
        "Несколько разных программ хранит кнопка «Мои программы».",
    ),
    (
        "Паспорт",
        "Укажите название, направленность, свою организацию и свои данные. "
        "Краткое название организации попадает в строку составителя.\n\n"
        "Серый текст в пустом поле — только подсказка. В документ он не попадает.",
    ),
    (
        "Обучающиеся и план",
        "На втором шаге задаются возраст, часы и размер группы. От них зависят календарь и занятия. "
        "Галочка дифференциации берёт ваши промежутки возраста, а не готовые 11–13 и 14–17.\n\n"
        "На третьем шаге сумма часов разделов должна совпасть с общим объёмом. "
        "«Распределить часы» делает это само. «Составить план по названию» пишет разделы по вашей теме, "
        "если в настройках указан ключ. Фамилия и организация в запрос не отправляются.",
    ),
    (
        "Условия и сборка",
        "На четвёртом шаге по названию можно составить оборудование, расходные материалы, "
        "программы и профессии проб. Пустые поля закроет типовой перечень направленности.\n\n"
        "«Собрать программу» создаёт Word и без интернета. "
        "«Сформулировать под эту программу» просит у нейросети цель, адресат, задачи и литературу по ГОСТ. "
        "Без ключа эти места остаются напоминанием, остальной текст берётся из направленности.",
    ),
    (
        "Где это найти потом",
        "Ключ нейросети хранится в «Настройках» и остаётся только на этом компьютере.\n\n"
        "Это окно можно открыть снова кнопкой «Помощь» рядом с настройками. "
        "Подсказка к кнопке или полю появляется, если задержать на нём курсор.",
    ),
)


def onboarding_seen() -> bool:
    path = onboarding_path()
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(data.get("seen"))


def mark_onboarding_seen() -> None:
    try:
        onboarding_path().write_text(
            json.dumps({"seen": True}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        return


class OnboardingDialog(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.page = 0
        self.title("ДопПро")
        self.resizable(False, False)
        self.configure(fg_color="white")
        self.geometry("640x460")
        self.transient(app)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.heading = ctk.CTkLabel(self, text="", font=FONT_H, text_color=NAVY, anchor="w")
        self.heading.grid(row=0, column=0, sticky="ew", padx=28, pady=(22, 8))
        self.body = ctk.CTkLabel(
            self,
            text="",
            font=FONT,
            text_color="#1A1A1A",
            anchor="nw",
            justify="left",
            wraplength=580,
        )
        self.body.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 8))
        self.counter = ctk.CTkLabel(self, text="", font=FONT_S, text_color=MUTED, anchor="w")
        self.counter.grid(row=2, column=0, sticky="w", padx=28)

        buttons = ctk.CTkFrame(self, fg_color="white")
        buttons.grid(row=3, column=0, sticky="ew", padx=22, pady=(8, 18))
        self.back = secondary_button(buttons, "Назад", self._back)
        self.back.pack(side="left")
        self.next = primary_button(buttons, "Далее", self._next)
        self.next.pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._finish)
        self._show()
        self.update_idletasks()
        self._place()
        self.grab_set()
        self.focus()

    def _place(self) -> None:
        parent = self.app
        parent.update_idletasks()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - 640) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - 460) // 2)
        self.geometry(f"640x460+{x}+{y}")

    def _show(self) -> None:
        title, text = PAGES[self.page]
        self.heading.configure(text=title)
        self.body.configure(text=text)
        self.counter.configure(text=f"{self.page + 1} из {len(PAGES)}")
        self.back.configure(state="normal" if self.page else "disabled")
        self.next.configure(text="Понятно" if self.page == len(PAGES) - 1 else "Далее")

    def _back(self) -> None:
        if self.page:
            self.page -= 1
            self._show()

    def _next(self) -> None:
        if self.page < len(PAGES) - 1:
            self.page += 1
            self._show()
            return
        self._finish()

    def _finish(self) -> None:
        mark_onboarding_seen()
        self.destroy()
