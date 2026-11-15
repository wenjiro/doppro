# -*- coding: utf-8 -*-
"""Окно настроек: сервис, версия Gemini, ключ с проверкой, тема и обновления.

Ключ не попадает ни в документ, ни в черновик программы.
"""

from __future__ import annotations

import webbrowser

from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLineEdit, QTextBrowser, QVBoxLayout

from core.generator import GEMINI_MODELS, GenerationError, check_connection, load_settings, save_settings
from core.paths import VERSION
from core.updates import look_for_update
from ui import prefs
from ui.theme import Glyph, theme
from ui.widgets import Banner, Button, Combo, alert, ask, hline, label, run_async

_CHOICES = (("gemini", "Gemini"), ("gigachat", "GigaChat"), ("deepseek", "DeepSeek"))
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
        "2. Слева откройте Dashboard и страницу API Keys. Кнопка «Открыть страницу ключа» открывает её сразу.\n"
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


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.setMinimumSize(720, 640)
        self.resize(760, 800)
        stored = load_settings()
        self._stored = stored
        self._keys = {f"{code}_api_key": stored[f"{code}_api_key"] for code, _name in _CHOICES}
        self._code = stored["provider"]
        self._checking = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QFrame()
        surface.setObjectName("dialogSurface")
        outer.addWidget(surface)
        box = QVBoxLayout(surface)
        box.setContentsMargins(26, 22, 26, 18)
        box.setSpacing(10)

        box.addWidget(label("Настройки", "h1"))
        box.addWidget(label(
            "Ключ хранится только на этом компьютере. Фамилия педагога и название организации в запрос не отправляются. "
            "Без ключа программа тоже работает: документ собирается из текстов направленности.", "muted", wrap=True))

        box.addWidget(label("Сервис нейросети", "label"))
        services = QHBoxLayout()
        services.setSpacing(8)
        self.provider_buttons: dict[str, Button] = {}
        for code, name in _CHOICES:
            button = Button(name, "seg", on=lambda c=code: self._on_provider(c))
            button.setCheckable(True)
            self.provider_buttons[code] = button
            services.addWidget(button)
        services.addStretch(1)
        self.model_label = label("Версия", "muted")
        services.addWidget(self.model_label)
        self.model_box = Combo([name for _code, name in GEMINI_MODELS])
        self.model_box.set_value(next(name for code, name in GEMINI_MODELS if code == stored["gemini_model"]))
        self.model_box.setMinimumWidth(210)
        self.model_box.activated.connect(lambda _i: self._show_guide())
        services.addWidget(self.model_box)
        box.addLayout(services)

        box.addWidget(label("Ключ", "label"))
        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        self.key_entry = QLineEdit()
        self.key_entry.setEchoMode(QLineEdit.Password)
        self.key_entry.setPlaceholderText("Вставьте ключ выбранного сервиса")
        key_row.addWidget(self.key_entry, 1)
        self.eye = Button("", glyph=Glyph.EYE, on=self._toggle_eye, tip="Показать или скрыть ключ")
        key_row.addWidget(self.eye)
        self.check_button = Button("Проверить ключ", "teal", Glyph.CHECK, on=self._check_key,
                                   tip="Отправляет короткий пробный запрос без данных программы и показывает, отвечает ли сервис.")
        key_row.addWidget(self.check_button)
        box.addLayout(key_row)
        self.check_status = Banner("info")
        self.check_status.hide()
        box.addWidget(self.check_status)

        head = QHBoxLayout()
        head.addWidget(label("Как получить ключ", "label"), 1)
        head.addWidget(Button("Открыть страницу ключа", "link", Glyph.LINK, on=self._open_key_page))
        box.addLayout(head)
        self.guide = QTextBrowser()
        self.guide.setProperty("flat", True)
        self.guide.setOpenLinks(False)
        box.addWidget(self.guide, 1)

        box.addWidget(hline())
        look = QHBoxLayout()
        look.setSpacing(8)
        look.addWidget(label("Тема", "label"))
        self.theme_buttons: dict[str, Button] = {}
        for code, name in (("light", "Светлая"), ("dark", "Тёмная")):
            button = Button(name, "seg", on=lambda c=code: self._set_theme(c))
            button.setCheckable(True)
            button.setChecked((code == "dark") == theme.dark)
            self.theme_buttons[code] = button
            look.addWidget(button)
        look.addStretch(1)
        look.addWidget(label(f"Версия {VERSION}", "small"))
        look.addWidget(Button("Проверить обновления", "ghost", Glyph.REFRESH, on=self._check_updates))
        box.addLayout(look)
        self.update_status = label("", "small")
        box.addWidget(self.update_status)

        foot = QHBoxLayout()
        foot.addWidget(Button("github.com/wenjiro/doppro", "link",
                              on=lambda: webbrowser.open("https://github.com/wenjiro/doppro")))
        foot.addStretch(1)
        foot.addWidget(Button("Отмена", on=self.reject))
        save = Button("Сохранить", "primary", on=self._save)
        save.setDefault(True)
        foot.addWidget(save)
        box.addLayout(foot)

        self._show_provider()

    # ---------- сервис и ключ ----------

    def _model_code(self) -> str:
        name = self.model_box.value()
        return next(code for code, item in GEMINI_MODELS if item == name)

    def _show_provider(self) -> None:
        for code, button in self.provider_buttons.items():
            button.setChecked(code == self._code)
        self.key_entry.setText(self._keys.get(f"{self._code}_api_key", ""))
        gemini = self._code == "gemini"
        self.model_label.setVisible(gemini)
        self.model_box.setVisible(gemini)
        self._show_guide()

    def _show_guide(self) -> None:
        text = _GUIDES[self._code]
        if self._code == "gemini":
            text = text.format(version=self.model_box.value())
        self.guide.setPlainText(text)

    def _on_provider(self, code: str) -> None:
        self._keys[f"{self._code}_api_key"] = self.key_entry.text().strip()
        self._code = code
        self.check_status.hide()
        self._show_provider()

    def _toggle_eye(self) -> None:
        hidden = self.key_entry.echoMode() == QLineEdit.Password
        self.key_entry.setEchoMode(QLineEdit.Normal if hidden else QLineEdit.Password)

    def _open_key_page(self) -> None:
        webbrowser.open(_KEY_PAGES[self._code])

    def _payload(self) -> dict:
        self._keys[f"{self._code}_api_key"] = self.key_entry.text().strip()
        payload = {"provider": self._code, "gemini_model": self._model_code()}
        payload.update(self._keys)
        return payload

    def _write(self) -> bool:
        try:
            save_settings(self._payload())
        except OSError as exc:
            alert(self, "Не удалось сохранить настройки", str(exc), "error")
            return False
        return True

    def _check_key(self) -> None:
        if self._checking:
            return
        if len(self.key_entry.text().strip()) < 10:
            self.check_status.show_message("warn", "Сначала вставьте ключ в поле выше.")
            return
        # Проверяется ровно то, что в окне: выбранный сервис, версия и ключ. Для этого настройки записываются.
        if not self._write():
            return
        self._checking = True
        self.check_button.setEnabled(False)
        name = dict(_CHOICES)[self._code]
        self.check_status.show_message("info", f"Отправляю пробный запрос в {name}… Настройки при этом сохранены.")
        run_async(self, check_connection, lambda _text: self._checked(name, None), lambda error: self._checked(name, error))

    def _checked(self, name: str, error) -> None:
        self._checking = False
        self.check_button.setEnabled(True)
        if error is None:
            self.check_status.show_message("ok", f"Ключ работает: {name} ответил на пробный запрос.")
            return
        text = str(error)
        if not isinstance(error, GenerationError):
            text = f"Проверка не прошла: {text}"
        self.check_status.show_message("error", text)

    def _save(self) -> None:
        if self._write():
            self.accept()

    def reject(self) -> None:
        changed = self._payload() != {key: self._stored[key] for key in self._payload()}
        on_disk = load_settings()
        unsaved = self._payload() != {key: on_disk[key] for key in self._payload()}
        if changed and unsaved and not ask(self, "Закрыть без сохранения?", "Изменения ключа или сервиса не сохранятся.",
                                           yes="Закрыть", no="Вернуться"):
            return
        super().reject()

    # ---------- тема и обновления ----------

    def _set_theme(self, code: str) -> None:
        for name, button in self.theme_buttons.items():
            button.setChecked(name == code)
        if (code == "dark") != theme.dark:
            theme.apply(code)
            prefs.put("theme", code)

    def _check_updates(self) -> None:
        self.update_status.setText("Проверяю…")
        run_async(self, look_for_update, self._show_update)

    def _show_update(self, report) -> None:
        if report.state == "newer":
            self.update_status.setText(f"Есть версия {report.remote}")
            if ask(self, f"Вышла версия {report.remote}", "Открыть страницу загрузки?", yes="Открыть", no="Позже"):
                webbrowser.open(report.url)
        elif report.state == "current":
            self.update_status.setText(f"Установлена последняя версия {report.local}")
        elif report.state == "missing":
            self.update_status.setText("На GitHub пока нет выпуска")
        else:
            self.update_status.setText("Не удалось проверить обновления")
