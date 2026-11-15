# -*- coding: utf-8 -*-
"""Повторяющиеся элементы: карточка, поле с подписью, кнопки, окна вопросов, фоновые задачи."""

from __future__ import annotations

from PySide6.QtCore import QObject, QRegularExpression, QSize, QRunnable, QStringListModel, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.places import fold_search
from ui.theme import Glyph, glyph_icon, icon_font, theme


def set_prop(widget: QWidget, name: str, value) -> None:
    """Меняет свойство, от которого зависит стиль, и перерисовывает элемент."""
    if widget.property(name) == value:
        return
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def label(text: str = "", role: str = "", wrap: bool = False) -> QLabel:
    item = QLabel(text)
    if role:
        item.setProperty("role", role)
    if wrap:
        item.setWordWrap(True)
    return item


def hline() -> QFrame:
    line = QFrame()
    line.setObjectName("hline")
    return line


class Button(QPushButton):
    """Кнопка с необязательным значком. Значок перекрашивается при смене темы."""

    _COLORS = {
        "primary": "on_primary",
        "teal": "on_primary",
        "ghost": "muted",
        "link": "teal",
        "danger": "danger",
        "icon": "muted",
    }

    def __init__(self, text: str = "", kind: str = "", glyph: str = "", on=None, tip: str = "", icon_px: int = 15):
        super().__init__((" " + text) if glyph and text else text)
        self._glyph = glyph
        self._kind = kind
        self._icon_px = icon_px
        if kind:
            self.setProperty("kind", kind)
        if tip:
            self.setToolTip(tip)
        if on is not None:
            self.clicked.connect(lambda _checked=False: on())
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        if glyph:
            self._paint_icon()
            theme.changed.connect(self._paint_icon)

    def _paint_icon(self) -> None:
        key = self._COLORS.get(self._kind, "heading")
        try:
            self.setIcon(glyph_icon(self._glyph, theme.p[key], self._icon_px))
            self.setIconSize(QSize(self._icon_px, self._icon_px))
        except RuntimeError:  # кнопку уже убрали с экрана
            return


class GlyphLabel(QLabel):
    """Значок-надпись. Цвет берётся из темы по ключу."""

    def __init__(self, glyph: str, color_key: str = "muted", px: int = 16):
        super().__init__(glyph)
        self._key = color_key
        self._px = px
        self.setFont(icon_font(px))
        self.setFixedWidth(px + 6)
        self.setAlignment(Qt.AlignCenter)
        self._paint()
        theme.changed.connect(self._paint)

    def set_glyph(self, glyph: str, color_key: str) -> None:
        self.setText(glyph)
        self._key = color_key
        self._paint()

    def _paint(self) -> None:
        try:
            self.setStyleSheet(
                f"color: {theme.p[self._key]}; background: transparent; "
                f"font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets'; font-size: {self._px}px;"
            )
        except RuntimeError:  # значок уже убрали с экрана
            return


class Card(QFrame):
    """Белая карточка с заголовком. Поля кладут в self.body."""

    def __init__(self, title: str = "", subtitle: str = ""):
        super().__init__()
        self.setObjectName("card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 20)
        outer.setSpacing(12)
        self.head = QHBoxLayout()
        self.head.setSpacing(10)
        if title:
            titles = QVBoxLayout()
            titles.setSpacing(2)
            titles.addWidget(label(title, "h2"))
            if subtitle:
                titles.addWidget(label(subtitle, "muted", wrap=True))
            self.head.addLayout(titles, 1)
            outer.addLayout(self.head)
        self.body = QVBoxLayout()
        self.body.setSpacing(14)
        outer.addLayout(self.body)

    def row(self, *widgets, stretch: tuple = ()) -> QHBoxLayout:
        line = QHBoxLayout()
        line.setSpacing(14)
        for index, widget in enumerate(widgets):
            factor = stretch[index] if index < len(stretch) else 1
            if isinstance(widget, QWidget):
                line.addWidget(widget, factor, Qt.AlignTop)
            else:
                line.addLayout(widget, factor)
        self.body.addLayout(line)
        return line


class Field(QWidget):
    """Подпись, само поле и строка ошибки под ним."""

    def __init__(self, caption: str, editor: QWidget, required: bool = False, tip: str = "", note: str = ""):
        super().__init__()
        self.editor = editor
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(5)
        text = caption + (' <span style="color:#D0483C">*</span>' if required else "")
        self.caption = label(text, "label")
        self.caption.setTextFormat(Qt.RichText)
        box.addWidget(self.caption)
        box.addWidget(editor)
        self.error = label("", "error", wrap=True)
        self.error.hide()
        box.addWidget(self.error)
        if note:
            box.addWidget(label(note, "small", wrap=True))
        if tip:
            self.setToolTip(tip)

    def set_error(self, text: str = "") -> None:
        self.error.setText(text)
        self.error.setVisible(bool(text))
        set_prop(self.editor, "invalid", bool(text))


class LineEdit(QLineEdit):
    def __init__(self, placeholder: str = "", max_length: int = 0):
        super().__init__()
        if placeholder:
            self.setPlaceholderText(placeholder)
        if max_length:
            self.setMaxLength(max_length)

    def value(self) -> str:
        return self.text().strip()

    def set_value(self, text: str) -> None:
        if self.text() != (text or ""):
            self.setText(text or "")


class IntEdit(QLineEdit):
    """Поле для целого числа. Пусто или не число — значение -1, это ловит проверка шага."""

    def __init__(self, digits: int = 4, width: int = 0):
        super().__init__()
        self.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,%d}" % digits)))
        if width:
            self.setFixedWidth(width)

    def value(self) -> int:
        raw = self.text().strip()
        return int(raw) if raw.isdigit() else -1

    def set_value(self, number: int, blank_below: int = 1) -> None:
        text = "" if number < blank_below else str(number)
        if self.text() != text:
            self.setText(text)


class Combo(QComboBox):
    """Список готовых значений. Колесо мыши не меняет выбор, пока список не открыт."""

    def __init__(self, values: list[str]):
        super().__init__()
        self.addItems(list(values))
        self.setFocusPolicy(Qt.StrongFocus)
        self.setView(QListView())
        self.setCursor(Qt.PointingHandCursor)

    def wheelEvent(self, event) -> None:
        event.ignore()

    def value(self) -> str:
        return self.currentText().strip()

    def set_value(self, text: str) -> None:
        index = self.findText(str(text))
        self.setCurrentIndex(index if index >= 0 else 0)


class _FoldCompleter(QCompleter):
    """Поиск без регистра и буквы «ё»: сначала совпадения с начала, потом внутри названия."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all: list[str] = []
        self._model = QStringListModel(self)
        self.setModel(self._model)
        self.setCompletionMode(QCompleter.PopupCompletion)
        self.setCaseSensitivity(Qt.CaseInsensitive)
        self.setMaxVisibleItems(9)
        view = QListView()
        view.setObjectName("completer")
        self.setPopup(view)

    def set_values(self, values: list[str]) -> None:
        self._all = list(values)

    def matches(self, text: str) -> list[str]:
        needle = fold_search(text)
        if not needle:
            return self._all[:100]
        starts: list[str] = []
        contains: list[str] = []
        for item in self._all:
            folded = fold_search(item)
            if folded.startswith(needle):
                starts.append(item)
                if len(starts) >= 40:
                    break
            elif needle in folded and len(contains) < 40:
                contains.append(item)
        return (starts + contains)[:40]

    def splitPath(self, path: str) -> list[str]:
        self._model.setStringList(self.matches(path))
        return [""]


class SearchEdit(QLineEdit):
    """Поле со списком-подсказкой. Если нужного пункта нет, остаётся свой текст."""

    def __init__(self, values: list[str], placeholder: str = ""):
        super().__init__()
        self.setPlaceholderText(placeholder)
        self._completer = _FoldCompleter(self)
        self._completer.set_values(values)
        self.setCompleter(self._completer)

    def set_choices(self, values: list[str]) -> None:
        self._completer.set_values(values)

    def value(self) -> str:
        return self.text().strip()

    def set_value(self, text: str) -> None:
        if self.text() != (text or ""):
            self.setText(text or "")

    def _open(self) -> None:
        self._completer.setCompletionPrefix(self.text())
        self._completer.complete()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Down and not self._completer.popup().isVisible():
            self._open()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        if not self.text().strip():
            QTimer.singleShot(0, self._open)


class TextArea(QPlainTextEdit):
    """Многострочное поле. Tab переходит к следующему полю, колесо листает страницу, если текст короткий."""

    def __init__(self, height: int = 90, placeholder: str = ""):
        super().__init__()
        self.setMinimumHeight(height)
        self.setMaximumHeight(height + 60)
        self.setTabChangesFocus(True)
        if placeholder:
            self.setPlaceholderText(placeholder)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(height)

    def wheelEvent(self, event) -> None:
        bar = self.verticalScrollBar()
        if bar.maximum() == 0 or not self.hasFocus():
            event.ignore()
            return
        super().wheelEvent(event)

    def value(self) -> str:
        return self.toPlainText().strip()

    def set_value(self, text: str) -> None:
        if self.toPlainText() != (text or ""):
            self.setPlainText(text or "")

    def lines(self, limit: int = 24) -> list[str]:
        return [line.strip() for line in self.toPlainText().splitlines() if line.strip()][:limit]


def checkbox(text: str, tip: str = "") -> QCheckBox:
    box = QCheckBox(text)
    box.setCursor(Qt.PointingHandCursor)
    if tip:
        box.setToolTip(tip)
    return box


class Banner(QFrame):
    """Цветная плашка с сообщением: ошибка, предупреждение, успех или справка."""

    _GLYPHS = {
        "error": (Glyph.WARNING, "danger"),
        "warn": (Glyph.WARNING, "warn"),
        "ok": (Glyph.CHECK, "ok"),
        "info": (Glyph.INFO, "heading"),
    }

    def __init__(self, kind: str = "info", text: str = ""):
        super().__init__()
        self.setObjectName("banner")
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 11, 14, 11)
        row.setSpacing(10)
        self.icon = GlyphLabel(Glyph.INFO, "heading", 16)
        row.addWidget(self.icon, 0, Qt.AlignTop)
        self.text = label(text, wrap=True)
        self.text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(self.text, 1)
        self.actions = QHBoxLayout()
        row.addLayout(self.actions)
        self.set_kind(kind)

    def set_kind(self, kind: str) -> None:
        glyph, color = self._GLYPHS.get(kind, self._GLYPHS["info"])
        self.icon.set_glyph(glyph, color)
        set_prop(self, "kind", kind)

    def show_message(self, kind: str, text: str) -> None:
        self.set_kind(kind)
        self.text.setText(text)
        self.setVisible(bool(text))


class Page(QWidget):
    """Экран с заголовком и прокручиваемой колонкой карточек."""

    def __init__(self, title: str, subtitle: str = "", max_width: int = 940):
        super().__init__()
        self.setObjectName("page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(self.scroll)
        body = QWidget()
        body.setObjectName("pageBody")
        self.scroll.setWidget(body)
        center = QHBoxLayout(body)
        center.setContentsMargins(32, 26, 32, 28)
        column = QWidget()
        column.setMaximumWidth(max_width)
        center.addStretch(1)
        center.addWidget(column, 100)
        center.addStretch(1)
        self.column = QVBoxLayout(column)
        self.column.setContentsMargins(0, 0, 0, 0)
        self.column.setSpacing(16)
        self.header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        self.title_label = label(title, "h1")
        titles.addWidget(self.title_label)
        if subtitle:
            titles.addWidget(label(subtitle, "muted", wrap=True))
        self.header.addLayout(titles, 1)
        self.column.addLayout(self.header)

    def add(self, widget: QWidget) -> QWidget:
        self.column.addWidget(widget)
        return widget

    def finish(self) -> None:
        self.column.addStretch(1)


class Toast(QLabel):
    """Короткое сообщение внизу окна. Само исчезает."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("toast")
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_text(self, text: str, msec: int = 3200) -> None:
        self.setText(text)
        self.adjustSize()
        self.place()
        self.show()
        self.raise_()
        self._timer.start(msec)

    def place(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.move((parent.width() - self.width()) // 2 + 120, parent.height() - self.height() - 86)


class MessageDialog(QDialog):
    """Окно с вопросом или сообщением в стиле программы."""

    def __init__(self, parent, title: str, text: str, kind: str = "info", yes: str = "Понятно", no: str = ""):
        super().__init__(parent)
        self.setWindowTitle("ДопПро")
        self.setModal(True)
        self.setMinimumWidth(440)
        self.setMaximumWidth(560)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QFrame()
        surface.setObjectName("dialogSurface")
        outer.addWidget(surface)
        box = QVBoxLayout(surface)
        box.setContentsMargins(24, 22, 24, 20)
        box.setSpacing(12)
        head = QHBoxLayout()
        head.setSpacing(10)
        glyph, color = {
            "error": (Glyph.WARNING, "danger"),
            "warn": (Glyph.WARNING, "warn"),
            "ask": (Glyph.HELP, "heading"),
            "ok": (Glyph.CHECK, "ok"),
        }.get(kind, (Glyph.INFO, "heading"))
        head.addWidget(GlyphLabel(glyph, color, 20))
        head.addWidget(label(title, "h2", wrap=True), 1)
        box.addLayout(head)
        body = label(text, wrap=True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        box.addWidget(body)
        box.addSpacing(6)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        if no:
            buttons.addWidget(Button(no, on=self.reject))
        accept = Button(yes, "danger" if kind == "danger" else "primary", on=self.accept)
        accept.setDefault(True)
        buttons.addWidget(accept)
        box.addLayout(buttons)


def ask(parent, title: str, text: str = "", yes: str = "Да", no: str = "Отмена", danger: bool = False) -> bool:
    dialog = MessageDialog(parent, title, text, "danger" if danger else "ask", yes, no)
    return dialog.exec() == QDialog.Accepted


def alert(parent, title: str, text: str = "", kind: str = "info") -> None:
    MessageDialog(parent, title, text, kind).exec()


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(object)


class _Job(QRunnable):
    def __init__(self, work, signals: _Signals):
        super().__init__()
        self.work = work
        self.signals = signals

    def run(self) -> None:
        try:
            result = self.work()
        except Exception as exc:  # причину показывает вызывающий экран
            try:
                self.signals.failed.emit(exc)
            except RuntimeError:
                pass
            return
        try:
            self.signals.done.emit(result)
        except RuntimeError:
            pass


def run_async(owner: QObject, work, on_done, on_error=None) -> None:
    """Выполняет work в фоне. Ответ приходит в окно, пока оно живо."""
    signals = _Signals(owner)
    signals.done.connect(on_done)
    if on_error is not None:
        signals.failed.connect(on_error)
    signals.done.connect(signals.deleteLater)
    signals.failed.connect(signals.deleteLater)
    QThreadPool.globalInstance().start(_Job(work, signals))


def parse_int(text: str) -> int:
    raw = str(text).strip().replace(" ", "")
    return int(raw) if raw.isdigit() else -1
