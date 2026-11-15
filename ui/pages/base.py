# -*- coding: utf-8 -*-
"""Общая основа шагов мастера: загрузка из модели, запись в модель, показ ошибок у полей."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QPlainTextEdit

from ui.widgets import Banner, Field, Page


class StepPage(Page):
    index = 0
    # Пары «кусок текста ошибки → имя поля». Что не нашлось, уходит в плашку над карточками.
    ERR_MAP: tuple[tuple[str, str], ...] = ()

    def __init__(self, window, title: str, subtitle: str = ""):
        super().__init__(title, subtitle)
        self.window_ = window
        self.session = window.session
        self.fields: dict[str, Field] = {}
        self._loading = False
        self.banner = Banner("error")
        self.banner.hide()
        self.add(self.banner)

    @property
    def model(self):
        return self.session.model

    def field(self, key: str, caption: str, editor, required: bool = False, tip: str = "", note: str = "") -> Field:
        item = Field(caption, editor, required, tip, note)
        self.fields[key] = item
        self.watch(editor)
        return item

    def watch(self, editor) -> None:
        """Любая правка в поле сразу попадает в модель и в черновик."""
        if isinstance(editor, QLineEdit):
            editor.textEdited.connect(self._edited)
        elif isinstance(editor, QPlainTextEdit):
            editor.textChanged.connect(self._edited)
        elif isinstance(editor, QComboBox):
            editor.activated.connect(self._edited)
        elif isinstance(editor, QCheckBox):
            editor.clicked.connect(self._edited)

    def _edited(self, *_args) -> None:
        if self._loading:
            return
        self.commit()
        self.session.touch()

    def reload(self) -> None:
        self._loading = True
        try:
            self.load()
        finally:
            self._loading = False

    def load(self) -> None:  # модель → поля
        raise NotImplementedError

    def commit(self) -> None:  # поля → модель
        raise NotImplementedError

    def on_show(self) -> None:
        self.reload()

    def show_errors(self, errors: list[str]) -> None:
        placed: dict[str, list[str]] = {}
        rest: list[str] = []
        for text in errors:
            for needle, key in self.ERR_MAP:
                if needle in text and key in self.fields:
                    placed.setdefault(key, []).append(text)
                    break
            else:
                rest.append(text)
        for key, item in self.fields.items():
            item.set_error("\n".join(placed.get(key, [])))
        self.banner.show_message("error", "\n".join(rest))
