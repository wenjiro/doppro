# -*- coding: utf-8 -*-
"""Окно настроек: сервис, версия Gemini, ключ и инструкция, где его взять.

Ключ не попадает ни в документ, ни в черновик программы.
"""

from __future__ import annotations

import threading
import webbrowser
from tkinter import messagebox

import customtkinter as ctk

from core.generator import GEMINI_MODELS, load_settings, save_settings
from core.updates import look_for_update
from gui.theme import FIELD, FONT, FONT_H, FONT_S, LINE, MUTED, NAVY, TEAL
from gui.widgets import bind_text_shortcuts, primary_button, secondary_button

_CHOICES = (
    ("gemini", "Gemini"),
    ("gigachat", "GigaChat"),
    ("deepseek", "DeepSeek"),
)
_KEY_PAGES = {
    "gemini": "https://aistudio.google.com/app/apikey",
    "gigachat": "https://developers.sber.ru/studio",
    "deepseek": "https://platform.deepseek.com/api_keys",
}
_GUIDES = {
    "gemini": (
        "Один ключ Google подходит ко всем версиям. Сейчас в списке выбрана {version}.\n\n"
        "1. Откройте aistudio.google.com и войдите в аккаунт Google. Если сайт просит принять условия, примите их. "
        "Новому пользователю проект создаётся сам.\n"
        "2. Слева откройте Dashboard и страницу API Keys. Кнопка справа открывает её сразу.\n"
        "3. Нажмите Create API key. Банковская карта не нужна: для ДопПро хватает бесплатного уровня. "
        "С мая 2026 года новые ключи в AI Studio создаются как ключи авторизации.\n"
        "4. Скопируйте ключ целиком и вставьте его в поле «Ключ». Храните его как пароль и никому не отправляйте.\n"
        "5. Версию выберите в списке выше и нажмите «Сохранить».\n"
        "   • Gemini 3.8 Flash — основная версия.\n"
        "   • Gemini 3.6 Flash — предыдущая полноценная версия.\n"
        "   • Gemini 3.5 Flash-Lite и Gemini 3.1 Flash-Lite — более лёгкие. "
        "Их стоит выбрать, если программа пишет, что версия перегружена.\n"
        "6. Запрос уходит на сервер Google за пределами России. Если программа сообщит, что Google не ответил, "
        "ключ может быть верным, а сайт с этой сети недоступен. Тогда выберите сервис GigaChat."
    ),
    "gigachat": (
        "В поле «Ключ» вставляется ключ авторизации, Authorization Key. Короткий токен доступа копировать не нужно: "
        "программа получает его сама.\n\n"
        "1. Откройте кабинет developers.sber.ru и войдите через Сбер ID.\n"
        "2. Нажмите «Создать проект». В разделе AI-модели выберите GigaChat API, задайте название и примите соглашение. "
        "Физическому лицу обычно подключается тариф Freemium. Справа в поле Scope должно быть GIGACHAT_API_PERS.\n"
        "3. Откройте проект, слева выберите «Настройки API» и нажмите «Получить ключ». "
        "Кнопку видят владелец и администратор проекта.\n"
        "4. В окне «Сохраните ваш Authorization Key» скопируйте строку Authorization Key. "
        "Client ID и Client Secret в ДопПро не вставляются. Строка показывается один раз. "
        "Если закрыли окно, не сохранив её, нажмите «Получить новый ключ».\n"
        "5. Вставьте ключ авторизации в поле «Ключ» и нажмите «Сохранить».\n"
        "6. Сертификаты Минцифры уже встроены в ДопПро, отдельно устанавливать их не нужно.\n"
        "Платные пакеты новым клиентам с сентября 2026 года Сбер предлагает на cloud.ru. "
        "Для ДопПро нужен ключ из кабинета developers.sber.ru."
    ),
    "deepseek": (
        "Ключ создаётся в кабинете API, а не в обычном чате DeepSeek.\n\n"
        "1. Откройте platform.deepseek.com и зарегистрируйтесь по почте или телефону.\n"
        "2. Слева откройте API keys и нажмите Create new API key. Имя ключа может быть любым.\n"
        "3. Скопируйте ключ сразу: сайт показывает его один раз. Если потеряете, создайте новый.\n"
        "4. Вставьте ключ в поле «Ключ» и нажмите «Сохранить».\n"
        "5. Чат на chat.deepseek.com бесплатный, а запросы из программы списывают баланс API. "
        "После регистрации иногда есть небольшой пробный баланс — его размер смотрите в кабинете. "
        "Когда он кончится, пополните счёт на странице Top up. "
        "Если баланс нулевой, программа сообщит, что оплата не прошла.\n"
        "Отдельного постоянного бесплатного пакета API у DeepSeek нет."
    ),
}


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Настройки")
        self.resizable(False, True)
        self.minsize(680, 560)
        self.configure(fg_color="white")
        self.geometry("700x720")
        self.transient(app)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(9, weight=1)

        stored = load_settings()
        self._keys = {key: stored[key] for _code, key in ((item[0], f"{item[0]}_api_key") for item in _CHOICES)}

        ctk.CTkLabel(self, text="Настройки", font=FONT_H, text_color=NAVY, anchor="w").grid(
            row=0, column=0, sticky="ew", padx=22, pady=(18, 4)
        )
        ctk.CTkLabel(
            self,
            text="Ключ хранится только на этом компьютере. Фамилия педагога и название организации в запрос не отправляются.",
            font=FONT_S,
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=650,
        ).grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 12))

        ctk.CTkLabel(self, text="Сервис", font=FONT, text_color=NAVY, anchor="w").grid(
            row=2, column=0, sticky="w", padx=22
        )
        self.provider = ctk.CTkComboBox(
            self,
            values=[label for _code, label in _CHOICES],
            height=36,
            font=FONT,
            dropdown_font=FONT,
            state="readonly",
            border_color=LINE,
            fg_color="white",
            button_color=NAVY,
            button_hover_color="#0B655E",
            text_color="#1A1A1A",
        )
        self.provider.grid(row=3, column=0, sticky="ew", padx=22, pady=(4, 10))
        current = next(label for code, label in _CHOICES if code == stored["provider"])
        self._current_code = stored["provider"]
        self.provider.set(current)

        self.model_label = ctk.CTkLabel(self, text="Версия Gemini", font=FONT, text_color=NAVY, anchor="w")
        self.model_box = ctk.CTkComboBox(
            self,
            values=[label for _code, label in GEMINI_MODELS],
            height=36,
            font=FONT,
            dropdown_font=FONT,
            state="readonly",
            border_color=LINE,
            fg_color="white",
            button_color=NAVY,
            button_hover_color="#0B655E",
            text_color="#1A1A1A",
        )
        stored_model = next(label for code, label in GEMINI_MODELS if code == stored["gemini_model"])
        self.model_box.set(stored_model)

        ctk.CTkLabel(self, text="Ключ", font=FONT, text_color=NAVY, anchor="w").grid(
            row=6, column=0, sticky="w", padx=22
        )
        self.key_entry = ctk.CTkEntry(self, height=36, font=FONT, show="*", fg_color="white", border_color=LINE)
        self.key_entry.grid(row=7, column=0, sticky="ew", padx=22, pady=(4, 8))
        bind_text_shortcuts(self.key_entry)
        self._show_key(stored["provider"])
        self._show_model_row(stored["provider"])

        head = ctk.CTkFrame(self, fg_color="white")
        head.grid(row=8, column=0, sticky="ew", padx=22, pady=(8, 0))
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text="Как получить ключ", font=FONT, text_color=NAVY, anchor="w").grid(
            row=0, column=0, sticky="w"
        )
        secondary_button(head, "Открыть страницу ключа", self._open_key_page).grid(row=0, column=1, sticky="e")

        self.guide = ctk.CTkTextbox(
            self,
            height=220,
            font=FONT_S,
            fg_color=FIELD,
            border_color=LINE,
            border_width=1,
            text_color="#1A1A1A",
            wrap="word",
            activate_scrollbars=True,
        )
        self.guide.grid(row=9, column=0, sticky="nsew", padx=22, pady=(6, 8))
        self.guide.bind("<Key>", self._keep_guide)
        self._show_guide(stored["provider"])
        self.provider.configure(command=self._on_provider)
        self.model_box.configure(command=self._on_model)

        primary_button(self, "Сохранить", self._save).grid(row=10, column=0, sticky="w", padx=22, pady=(4, 8))
        foot = ctk.CTkFrame(self, fg_color="white")
        foot.grid(row=11, column=0, sticky="ew", padx=22, pady=(0, 16))
        author = ctk.CTkLabel(
            foot,
            text="github.com/wenjiro",
            font=FONT_S,
            text_color=TEAL,
            anchor="w",
            cursor="hand2",
        )
        author.pack(side="left")
        author.bind("<Button-1>", lambda _event: webbrowser.open("https://github.com/wenjiro/doppro"))
        check = ctk.CTkButton(
            foot,
            text="Проверить обновления",
            command=self._check_updates,
            height=26,
            font=FONT_S,
            fg_color="transparent",
            hover_color=FIELD,
            text_color=MUTED,
            corner_radius=6,
        )
        check.pack(side="left", padx=(16, 0))
        self.update_status = ctk.CTkLabel(foot, text="", font=FONT_S, text_color=MUTED, anchor="w")
        self.update_status.pack(side="left", padx=(8, 0))
        self.grab_set()
        self.focus()

    def _check_updates(self) -> None:
        self.update_status.configure(text="Проверяю…")

        def work() -> None:
            report = look_for_update()
            self.after(0, lambda: self._show_update(report))

        threading.Thread(target=work, daemon=True).start()

    def _show_update(self, report) -> None:
        if report.state == "newer":
            self.update_status.configure(text=f"Есть версия {report.remote}")
            if messagebox.askyesno(
                "ДопПро",
                f"Вышла версия {report.remote}. Открыть страницу загрузки?",
                parent=self,
            ):
                webbrowser.open(report.url)
            return
        if report.state == "current":
            self.update_status.configure(text=f"Установлена последняя версия {report.local}")
            return
        if report.state == "missing":
            self.update_status.configure(text="На GitHub пока нет выпуска")
            return
        self.update_status.configure(text="Не удалось проверить")

    def _code(self) -> str:
        label = self.provider.get()
        return next(code for code, item in _CHOICES if item == label)

    def _remember_visible_key(self) -> None:
        self._keys[f"{self._code()}_api_key"] = self.key_entry.get().strip()

    def _show_key(self, code: str) -> None:
        self.key_entry.delete(0, "end")
        value = self._keys.get(f"{code}_api_key", "")
        if value:
            self.key_entry.insert(0, value)

    def _model_code(self) -> str:
        label = self.model_box.get()
        return next(code for code, item in GEMINI_MODELS if item == label)

    def _show_model_row(self, code: str) -> None:
        if code == "gemini":
            self.model_label.grid(row=4, column=0, sticky="w", padx=22)
            self.model_box.grid(row=5, column=0, sticky="ew", padx=22, pady=(4, 10))
            return
        self.model_label.grid_remove()
        self.model_box.grid_remove()

    def _show_guide(self, code: str) -> None:
        text = _GUIDES[code]
        if code == "gemini":
            text = text.format(version=self.model_box.get())
        self.guide.delete("1.0", "end")
        self.guide.insert("1.0", text)
        self.guide.see("1.0")

    def _keep_guide(self, event) -> str | None:
        # Текст инструкции только для чтения, но его можно выделить и скопировать.
        ctrl = bool(event.state & 0x4)
        if ctrl and event.keycode in (67, 65):
            return None
        if ctrl and event.keysym == "Insert":
            return None
        if event.keysym in {
            "Left",
            "Right",
            "Up",
            "Down",
            "Home",
            "End",
            "Prior",
            "Next",
            "Shift_L",
            "Shift_R",
            "Control_L",
            "Control_R",
        }:
            return None
        return "break"

    def _open_key_page(self) -> None:
        webbrowser.open(_KEY_PAGES[self._code()])

    def _on_model(self, _label: str) -> None:
        if self._code() == "gemini":
            self._show_guide("gemini")

    def _on_provider(self, _label: str) -> None:
        self._keys[f"{self._current_code}_api_key"] = self.key_entry.get().strip()
        self._current_code = self._code()
        self._show_key(self._current_code)
        self._show_model_row(self._current_code)
        self._show_guide(self._current_code)

    def _save(self) -> None:
        self._remember_visible_key()
        code = self._code()
        payload = {"provider": code, "gemini_model": self._model_code()}
        payload.update(self._keys)
        try:
            save_settings(payload)
        except OSError as exc:
            messagebox.showerror("ДопПро", f"Не удалось сохранить настройки.\n\n{exc}", parent=self)
            return
        self.destroy()
