# -*- coding: utf-8 -*-
"""Стартовый экран: все программы педагога карточками."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QFrame, QGridLayout, QHBoxLayout, QMenu, QVBoxLayout, QWidget

from core.data_model import ProgramData
from core.library import (
    LibraryError,
    delete_program,
    duplicate_program,
    export_program,
    import_program,
    list_programs,
    load_program,
)
from core.places import fold_search
from ui import prefs
from ui.theme import Glyph
from ui.widgets import Banner, Button, GlyphLabel, LineEdit, Page, alert, ask, label


class ProgramCard(QFrame):
    opened = Signal(str)
    action = Signal(str, str)

    def __init__(self, entry, current: bool):
        super().__init__()
        self.entry = entry
        self.setObjectName("programCard")
        self.setProperty("current", current)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(168)
        box = QVBoxLayout(self)
        box.setContentsMargins(18, 16, 14, 14)
        box.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(label(entry.direction or "направленность не указана", "chip"))
        if current:
            top.addWidget(label("открыта сейчас", "chipTeal"))
        top.addStretch(1)
        more = Button("", "icon", Glyph.MORE, on=self._menu, tip="Копия, экспорт, удаление")
        top.addWidget(more)
        self._more = more
        box.addLayout(top)

        title = label(entry.title, "h2", wrap=True)
        title.setMaximumHeight(66)
        title.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        box.addWidget(title, 1)

        bottom = QHBoxLayout()
        bottom.addWidget(label(f"Изменена {entry.updated_text}" if entry.updated_text else "", "small"))
        bottom.addStretch(1)
        bottom.addWidget(Button("Открыть", "link", on=lambda: self.opened.emit(self.entry.id)))
        box.addLayout(bottom)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.opened.emit(self.entry.id)
        super().mouseReleaseEvent(event)

    def _menu(self) -> None:
        menu = QMenu(self)
        menu.addAction("Открыть", lambda: self.opened.emit(self.entry.id))
        menu.addAction("Сделать копию", lambda: self.action.emit("copy", self.entry.id))
        menu.addAction("Экспорт в файл…", lambda: self.action.emit("export", self.entry.id))
        menu.addSeparator()
        menu.addAction("Удалить", lambda: self.action.emit("delete", self.entry.id))
        menu.exec(self._more.mapToGlobal(self._more.rect().bottomLeft()))


class HomePage(Page):
    def __init__(self, window):
        super().__init__(
            "Мои программы",
            "Программы хранятся на этом компьютере и сохраняются сами. Ключ нейросети в них не записывается.",
            max_width=1100,
        )
        self.window_ = window
        self.session = window.session
        self._cards: list[ProgramCard] = []
        self._columns = 0

        self.header.addWidget(Button("Импорт из файла…", glyph=Glyph.IMPORT, on=self._import,
                                     tip="Открыть программу, которую экспортировали на другом компьютере."), 0, Qt.AlignTop)
        self.header.addWidget(Button("Новая программа", "primary", Glyph.ADD, on=self._new), 0, Qt.AlignTop)

        self.search = LineEdit("Поиск по названию или направленности")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self.refresh())
        self.add(self.search)

        self.draft = Banner("info")
        self.draft_button = Button("Продолжить", "link", on=lambda: self.window_.show_step(0))
        self.draft.actions.addWidget(self.draft_button)
        self.draft.hide()
        self.add(self.draft)

        self.grid_holder = QWidget()
        self.grid = QGridLayout(self.grid_holder)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(14)
        self.add(self.grid_holder)

        self.empty = QFrame()
        self.empty.setObjectName("card")
        empty = QVBoxLayout(self.empty)
        empty.setContentsMargins(24, 40, 24, 40)
        empty.setSpacing(10)
        empty.addWidget(GlyphLabel(Glyph.DOCUMENT, "teal", 36), 0, Qt.AlignHCenter)
        self.empty_title = label("Пока нет ни одной программы", "h2")
        empty.addWidget(self.empty_title, 0, Qt.AlignHCenter)
        self.empty_text = label("Нажмите «Новая программа» — пять шагов, и файл Word готов.", "muted")
        empty.addWidget(self.empty_text, 0, Qt.AlignHCenter)
        self.empty_button = Button("Новая программа", "primary", Glyph.ADD, on=self._new)
        empty.addWidget(self.empty_button, 0, Qt.AlignHCenter)
        self.add(self.empty)
        self.finish()

    def on_show(self) -> None:
        self.session.flush()
        self.refresh()

    def refresh(self) -> None:
        entries = list_programs()
        needle = fold_search(self.search.text())
        shown = [e for e in entries if not needle or needle in fold_search(e.title + " " + e.direction)]
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards = []
        current = self.session.model.library_id
        for entry in shown:
            card = ProgramCard(entry, entry.id == current)
            card.opened.connect(self._open)
            card.action.connect(self._action)
            self._cards.append(card)
        self._columns = 0
        self._layout_cards()
        self.search.setVisible(len(entries) > 3 or bool(needle))
        self.grid_holder.setVisible(bool(shown))
        self.empty.setVisible(not shown)
        if entries and not shown:
            self.empty_title.setText("Ничего не нашлось")
            self.empty_text.setText("Попробуйте другое слово или очистите поиск.")
            self.empty_button.hide()
        else:
            self.empty_title.setText("Пока нет ни одной программы")
            self.empty_text.setText("Нажмите «Новая программа» — пять шагов, и файл Word готов.")
            self.empty_button.show()
        model = self.session.model
        if not model.library_id:
            self.draft.show_message(
                "info", "Открыт черновик без названия. Он попадёт в этот список, когда вы впишете название программы."
            )
        else:
            self.draft.hide()

    def _layout_cards(self) -> None:
        width = self.grid_holder.width() or self.width()
        columns = max(1, min(3, width // 320))
        if columns == self._columns:
            return
        self._columns = columns
        for card in self._cards:
            self.grid.removeWidget(card)
        for index, card in enumerate(self._cards):
            self.grid.addWidget(card, index // columns, index % columns)
        for column in range(3):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_cards()

    # ---------- действия ----------

    def _open(self, program_id: str) -> None:
        if program_id == self.session.model.library_id:
            self.window_.show_step(0)
            return
        try:
            program = load_program(program_id)
        except LibraryError as exc:
            alert(self, "Программа не открылась", str(exc), "error")
            self.refresh()
            return
        self.session.replace(program)
        self.window_.show_step(0)

    def _new(self) -> None:
        self.session.replace(ProgramData())
        self.window_.show_step(0)

    def _action(self, name: str, program_id: str) -> None:
        if name == "copy":
            try:
                duplicate_program(program_id)
            except (LibraryError, OSError) as exc:
                alert(self, "Не удалось сделать копию", str(exc), "error")
                return
            self.window_.toast("Копия добавлена в список")
            self.refresh()
        elif name == "export":
            self._export(program_id)
        elif name == "delete":
            self._delete(program_id)

    def _delete(self, program_id: str) -> None:
        title = next((item.title for item in list_programs() if item.id == program_id), "эту программу")
        if not ask(self, f"Удалить «{title}»?", "Программа пропадёт из списка. Уже собранный файл Word останется на диске.",
                   yes="Удалить", danger=True):
            return
        try:
            delete_program(program_id)
        except LibraryError as exc:
            alert(self, "Не удалось удалить", str(exc), "error")
            return
        if self.session.model.library_id == program_id:
            self.session.replace(ProgramData(), keep_current=False)
        self.window_.toast("Программа удалена")
        self.window_.refresh_status()
        self.refresh()

    def _export(self, program_id: str) -> None:
        try:
            program = self.session.model if program_id == self.session.model.library_id else load_program(program_id)
        except LibraryError as exc:
            alert(self, "Программа не открылась", str(exc), "error")
            return
        name = program.title.strip() or "программа"
        folder = str(prefs.get("export_dir") or Path.home())
        path, _filter = QFileDialog.getSaveFileName(
            self, "Экспорт программы", str(Path(folder) / f"{name}.doppro.json"),
            "Программа ДопПро (*.json);;Все файлы (*.*)",
        )
        if not path:
            return
        try:
            export_program(program, Path(path))
        except OSError as exc:
            alert(self, "Не удалось записать файл", str(exc), "error")
            return
        prefs.put("export_dir", str(Path(path).parent))
        self.window_.toast("Файл записан. Ключ нейросети в него не входит")

    def _import(self) -> None:
        folder = str(prefs.get("export_dir") or Path.home())
        path, _filter = QFileDialog.getOpenFileName(
            self, "Импорт программы", folder, "Программа ДопПро (*.json);;Все файлы (*.*)"
        )
        if not path:
            return
        try:
            program = import_program(Path(path))
        except (LibraryError, OSError) as exc:
            alert(self, "Файл не подошёл", str(exc), "error")
            return
        self.refresh()
        if ask(self, f"Открыть «{program.title or 'программу'}»?", "Программа добавлена в список.", yes="Открыть", no="Позже"):
            self.session.replace(program)
            self.window_.show_step(0)
