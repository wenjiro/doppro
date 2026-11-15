# -*- coding: utf-8 -*-
"""Светлая и тёмная темы. Цвета взяты из знака «ДопПро»: синий и бирюзовый."""

from __future__ import annotations

from PySide6.QtCore import QObject, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication

from core.paths import user_data_dir

LIGHT = {
    "name": "light",
    "bg": "#F2F5FA",
    "surface": "#FFFFFF",
    "field": "#F8FAFC",
    "line": "#DAE2ED",
    "line_strong": "#B9C5D6",
    "text": "#16202E",
    "muted": "#5F6E80",
    "heading": "#1B3A6F",
    "primary": "#1B3A6F",
    "primary_hover": "#254A8A",
    "primary_pressed": "#142C56",
    "on_primary": "#FFFFFF",
    "soft": "#E8EEF6",
    "soft_hover": "#D8E2F0",
    "teal": "#0E7C74",
    "teal_hover": "#0B655E",
    "teal_soft": "#D7F0EC",
    "danger": "#B42318",
    "danger_soft": "#FDECEA",
    "warn": "#A15C00",
    "warn_soft": "#FDF1DC",
    "ok": "#067647",
    "ok_soft": "#DDF3E7",
    "sidebar": "#152B52",
    "sidebar_text": "#C7D3E8",
    "sidebar_muted": "#8496B8",
    "sidebar_hover": "#1E3A6B",
    "sidebar_active": "#2A4C88",
    "sidebar_line": "#24406F",
    "today": "#E8F0FE",
    "weekend": "#F7F8FA",
    "class_day": "#F1FAF9",
    "class_week": "#D7F0EC",
    "grid": "#E6EAF0",
    "holiday_bg": "#FDE7C7",
    "holiday_text": "#7A4E00",
    "shift": "#B86E00",
    "tooltip_bg": "#16202E",
    "tooltip_text": "#FFFFFF",
}

DARK = {
    "name": "dark",
    "bg": "#0F1622",
    "surface": "#172131",
    "field": "#111A28",
    "line": "#2A384F",
    "line_strong": "#3D4F6B",
    "text": "#E6ECF5",
    "muted": "#93A1B5",
    "heading": "#E6ECF5",
    "primary": "#3B6FCC",
    "primary_hover": "#4C80DD",
    "primary_pressed": "#325FB0",
    "on_primary": "#FFFFFF",
    "soft": "#22304A",
    "soft_hover": "#2C3D5C",
    "teal": "#2CB5AA",
    "teal_hover": "#35C7BB",
    "teal_soft": "#123B38",
    "danger": "#F0776C",
    "danger_soft": "#3A1E1C",
    "warn": "#E3A548",
    "warn_soft": "#3A2D14",
    "ok": "#4CC38A",
    "ok_soft": "#143326",
    "sidebar": "#0A101A",
    "sidebar_text": "#B7C3D8",
    "sidebar_muted": "#6F7E96",
    "sidebar_hover": "#162235",
    "sidebar_active": "#22365A",
    "sidebar_line": "#1B2740",
    "today": "#1B2B4A",
    "weekend": "#131C2A",
    "class_day": "#132A2B",
    "class_week": "#154640",
    "grid": "#243247",
    "holiday_bg": "#4A3610",
    "holiday_text": "#F3CF8E",
    "shift": "#C98A2B",
    "tooltip_bg": "#E6ECF5",
    "tooltip_text": "#0F1622",
}

LESSON_COLORS = ("#1B3A6F", "#0E7C74", "#3D5A80", "#1B6CA8", "#0B655E", "#2457A6")
LESSON_COLORS_DARK = ("#3B6FCC", "#1E9C92", "#5578A6", "#2C86C9", "#17877E", "#4573C4")

ICON_FONTS = ["Segoe Fluent Icons", "Segoe MDL2 Assets"]


class Glyph:
    """Значки из системного шрифта Windows."""

    HOME = ""
    SETTINGS = ""
    HELP = ""
    ADD = ""
    DELETE = ""
    UP = ""
    DOWN = ""
    LEFT = ""
    RIGHT = ""
    COPY = ""
    FOLDER = ""
    DOCUMENT = ""
    CALENDAR = ""
    CHECK = ""
    WARNING = ""
    INFO = ""
    SEARCH = ""
    IMPORT = ""
    EXPORT = ""
    MORE = ""
    SUN = ""
    MOON = ""
    SPARK = ""
    REFRESH = ""
    EYE = ""
    LINK = ""
    LIST = ""
    UNDO = ""
    CLOSE = ""
    BALANCE = ""
    PLAY = ""
    LOCATION = ""


class ThemeManager(QObject):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.p = dict(LIGHT)

    @property
    def dark(self) -> bool:
        return self.p["name"] == "dark"

    def color(self, key: str) -> QColor:
        return QColor(self.p[key])

    def lesson_colors(self) -> tuple[str, ...]:
        return LESSON_COLORS_DARK if self.dark else LESSON_COLORS

    def apply(self, name: str) -> None:
        self.p = dict(DARK if name == "dark" else LIGHT)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(_qss(self.p, _write_marks(self.p)))
        self.changed.emit()

    def toggle(self) -> str:
        name = "light" if self.dark else "dark"
        self.apply(name)
        return name


theme = ThemeManager()


def base_font() -> QFont:
    font = QFont("Segoe UI")
    font.setPixelSize(14)
    return font


def icon_font(px: int) -> QFont:
    font = QFont()
    font.setFamilies(ICON_FONTS)
    font.setPixelSize(px)
    return font


def glyph_icon(char: str, color: str, px: int = 16) -> QIcon:
    """Значок нужного цвета. Рисуется с запасом, чтобы не мылился на крупном масштабе."""
    scale = 3
    pixmap = QPixmap(px * scale, px * scale)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.TextAntialiasing)
    painter.setFont(icon_font(px * scale))
    painter.setPen(QColor(color))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, char)
    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return QIcon(pixmap)


def _write_marks(p: dict) -> dict:
    """Стрелка списка и галочка: Qt берёт их в стилях только из файлов."""
    folder = user_data_dir() / "ui_cache"
    folder.mkdir(parents=True, exist_ok=True)
    found = {}
    for key, color, kind in (
        ("chevron", p["muted"], "chevron"),
        ("check", "#FFFFFF", "check"),
    ):
        size = 36
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(color), 4.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        if kind == "chevron":
            painter.drawPolyline([QPointF(8, 13), QPointF(18, 23), QPointF(28, 13)])
        else:
            painter.drawPolyline([QPointF(7, 19), QPointF(15, 26), QPointF(29, 10)])
        painter.end()
        path = folder / f"{key}_{p['name']}.png"
        pixmap.save(str(path), "PNG")
        found[key] = str(path).replace("\\", "/")
    return found


def _qss(p: dict, marks: dict) -> str:
    return f"""
* {{ outline: 0; }}
QWidget {{ color: {p['text']}; font-family: 'Segoe UI'; font-size: 14px; }}
QMainWindow, QDialog {{ background: {p['bg']}; }}
#page, #pageBody {{ background: {p['bg']}; }}
#dialogSurface {{ background: {p['surface']}; }}
QToolTip {{ background: {p['tooltip_bg']}; color: {p['tooltip_text']}; border: 0; padding: 6px 9px; font-size: 13px; }}

/* Боковая панель */
#sidebar {{ background: {p['sidebar']}; }}
#sidebar QLabel {{ color: {p['sidebar_text']}; background: transparent; }}
#sidebar QLabel#brand {{ color: #FFFFFF; font-size: 21px; font-weight: 700; }}
#sidebar QLabel#brandSub {{ color: {p['sidebar_muted']}; font-size: 12px; }}
#sidebar QLabel#navSection {{ color: {p['sidebar_muted']}; font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
#sidebar QLabel#programName {{ color: #FFFFFF; font-size: 13px; font-weight: 600; }}
#sidebar QLabel#saveState {{ color: {p['sidebar_muted']}; font-size: 12px; }}
#sidebar QFrame#sideLine {{ background: {p['sidebar_line']}; max-height: 1px; min-height: 1px; border: 0; }}
QPushButton#nav {{ text-align: left; padding: 9px 12px; border-radius: 8px; border: 0;
    background: transparent; color: {p['sidebar_text']}; font-weight: 500; }}
QPushButton#nav:hover {{ background: {p['sidebar_hover']}; color: #FFFFFF; }}
QPushButton#nav:checked {{ background: {p['sidebar_active']}; color: #FFFFFF; font-weight: 600; }}
QPushButton#step {{ border-radius: 8px; border: 0; background: transparent; }}
QPushButton#step:hover {{ background: {p['sidebar_hover']}; }}
QPushButton#step:checked {{ background: {p['sidebar_active']}; }}
#sidebar QLabel#stepText {{ color: {p['sidebar_text']}; font-size: 14px; }}
#sidebar QLabel#stepText[active="true"] {{ color: #FFFFFF; font-weight: 600; }}
#sidebar QLabel#stepNote {{ color: {p['sidebar_muted']}; font-size: 12px; }}
#sidebar QLabel#badge {{ border-radius: 12px; font-size: 12px; font-weight: 700;
    background: transparent; border: 1px solid {p['sidebar_muted']}; color: {p['sidebar_text']}; }}
#sidebar QLabel#badge[state="ok"] {{ background: #12998F; border: 1px solid #12998F; color: #FFFFFF; }}
#sidebar QLabel#badge[state="warn"] {{ background: #E3A548; border: 1px solid #E3A548; color: #2A1B00; }}
#sidebar QLabel#badge[state="current"] {{ background: #FFFFFF; border: 1px solid #FFFFFF; color: #152B52; }}
#sidebar QLabel#offline {{ color: #7FD6CD; font-size: 12px; }}

/* Заголовки и подписи */
QLabel {{ background: transparent; }}
QLabel[role="h1"] {{ font-size: 24px; font-weight: 700; color: {p['heading']}; }}
QLabel[role="h2"] {{ font-size: 16px; font-weight: 700; color: {p['heading']}; }}
QLabel[role="h3"] {{ font-size: 14px; font-weight: 700; color: {p['heading']}; }}
QLabel[role="label"] {{ font-size: 13px; font-weight: 600; color: {p['text']}; }}
QLabel[role="muted"] {{ color: {p['muted']}; font-size: 13px; }}
QLabel[role="small"] {{ color: {p['muted']}; font-size: 12px; }}
QLabel[role="error"] {{ color: {p['danger']}; font-size: 12px; }}
QLabel[role="ok"] {{ color: {p['ok']}; font-size: 13px; }}
QLabel[role="warn"] {{ color: {p['warn']}; font-size: 13px; }}
QLabel[role="danger"] {{ color: {p['danger']}; font-size: 13px; }}
QLabel[role="accent"] {{ color: {p['primary'] if p['name'] == 'light' else p['primary_hover']}; font-size: 13px; }}
QLabel[role="chip"] {{ background: {p['soft']}; color: {p['heading']}; border-radius: 10px; padding: 2px 9px; font-size: 12px; font-weight: 600; }}
QLabel[role="chipTeal"] {{ background: {p['teal_soft']}; color: {p['teal']}; border-radius: 10px; padding: 2px 9px; font-size: 12px; font-weight: 600; }}
QLabel[role="index"] {{ background: {p['soft']}; color: {p['heading']}; border-radius: 14px; font-weight: 700; font-size: 13px; }}

/* Карточки */
QFrame#card {{ background: {p['surface']}; border: 1px solid {p['line']}; border-radius: 12px; }}
QFrame#card[selected="true"] {{ border: 1px solid {p['primary']}; }}
QFrame#programCard {{ background: {p['surface']}; border: 1px solid {p['line']}; border-radius: 12px; }}
QFrame#programCard:hover {{ border: 1px solid {p['primary_hover']}; }}
QFrame#programCard[current="true"] {{ border: 1px solid {p['teal']}; }}
QFrame#subcard {{ background: {p['field']}; border: 1px solid {p['line']}; border-radius: 10px; }}
QFrame#footer {{ background: {p['surface']}; border: 0; border-top: 1px solid {p['line']}; }}
QFrame#banner {{ border-radius: 10px; border: 0; background: {p['soft']}; }}
QFrame#banner[kind="error"] {{ background: {p['danger_soft']}; }}
QFrame#banner[kind="warn"] {{ background: {p['warn_soft']}; }}
QFrame#banner[kind="ok"] {{ background: {p['ok_soft']}; }}
QFrame#banner[kind="info"] {{ background: {p['soft']}; }}
QFrame#hline {{ background: {p['line']}; max-height: 1px; min-height: 1px; border: 0; }}
QLabel#toast {{ background: {p['tooltip_bg']}; color: {p['tooltip_text']}; border-radius: 10px; padding: 10px 16px; font-size: 13px; }}

/* Кнопки */
QPushButton {{ border-radius: 8px; padding: 8px 14px; font-weight: 600; border: 0;
    background: {p['soft']}; color: {p['heading']}; }}
QPushButton:hover {{ background: {p['soft_hover']}; }}
QPushButton:disabled {{ color: {p['muted']}; background: {p['soft']}; }}
QPushButton[kind="primary"] {{ background: {p['primary']}; color: {p['on_primary']}; padding: 10px 18px; }}
QPushButton[kind="primary"]:hover {{ background: {p['primary_hover']}; }}
QPushButton[kind="primary"]:pressed {{ background: {p['primary_pressed']}; }}
QPushButton[kind="primary"]:disabled {{ background: {p['line_strong']}; color: {p['surface']}; }}
QPushButton[kind="teal"] {{ background: {p['teal']}; color: #FFFFFF; padding: 10px 18px; }}
QPushButton[kind="teal"]:hover {{ background: {p['teal_hover']}; }}
QPushButton[kind="teal"]:disabled {{ background: {p['line_strong']}; color: {p['surface']}; }}
QPushButton[kind="ghost"] {{ background: transparent; color: {p['muted']}; font-weight: 500; }}
QPushButton[kind="ghost"]:hover {{ background: {p['soft']}; color: {p['text']}; }}
QPushButton[kind="link"] {{ background: transparent; color: {p['teal']}; padding: 2px 0; font-weight: 600; text-align: left; }}
QPushButton[kind="link"]:hover {{ color: {p['teal_hover']}; }}
QPushButton[kind="danger"] {{ background: {p['danger_soft']}; color: {p['danger']}; }}
QPushButton[kind="danger"]:hover {{ background: {p['danger']}; color: #FFFFFF; }}
QPushButton[kind="icon"] {{ background: transparent; padding: 6px; border-radius: 8px; }}
QPushButton[kind="icon"]:hover {{ background: {p['soft']}; }}
QPushButton[kind="chip"] {{ background: {p['field']}; border: 1px solid {p['line']}; color: {p['text']};
    padding: 7px 0; min-width: 46px; font-weight: 600; }}
QPushButton[kind="chip"]:hover {{ border: 1px solid {p['primary_hover']}; }}
QPushButton[kind="chip"]:checked {{ background: {p['primary']}; border: 1px solid {p['primary']}; color: #FFFFFF; }}
QPushButton[kind="seg"] {{ background: {p['field']}; border: 1px solid {p['line']}; color: {p['text']}; padding: 8px 16px; }}
QPushButton[kind="seg"]:checked {{ background: {p['primary']}; border: 1px solid {p['primary']}; color: #FFFFFF; }}

/* Поля */
QLineEdit, QPlainTextEdit, QTextEdit, QTextBrowser, QComboBox {{
    background: {p['field']}; border: 1px solid {p['line']}; border-radius: 8px; padding: 7px 10px;
    selection-background-color: {p['primary']}; selection-color: #FFFFFF; color: {p['text']}; }}
QLineEdit:hover, QPlainTextEdit:hover, QComboBox:hover {{ border: 1px solid {p['line_strong']}; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{ border: 1px solid {p['primary_hover']}; background: {p['surface']}; }}
QLineEdit[invalid="true"], QPlainTextEdit[invalid="true"], QComboBox[invalid="true"] {{ border: 1px solid {p['danger']}; }}
QLineEdit:disabled, QPlainTextEdit:disabled {{ color: {p['muted']}; }}
QPlainTextEdit[flat="true"], QTextBrowser[flat="true"] {{ background: {p['field']}; }}
QComboBox {{ padding-right: 28px; min-height: 20px; }}
QComboBox::drop-down {{ border: 0; width: 30px; subcontrol-origin: padding; subcontrol-position: center right; }}
QComboBox::down-arrow {{ image: url({marks['chevron']}); width: 12px; height: 12px; }}
QComboBox QAbstractItemView, QListView#completer {{ background: {p['surface']}; border: 1px solid {p['line_strong']};
    border-radius: 8px; padding: 4px; selection-background-color: {p['soft']}; selection-color: {p['text']}; color: {p['text']}; }}
QComboBox QAbstractItemView::item, QListView#completer::item {{ padding: 6px 8px; border-radius: 6px; min-height: 22px; }}
QComboBox QAbstractItemView::item:hover, QListView#completer::item:hover {{ background: {p['soft']}; }}
QListView#completer::item:selected {{ background: {p['soft']}; color: {p['text']}; }}

QCheckBox {{ spacing: 9px; background: transparent; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid {p['line_strong']}; background: {p['field']}; }}
QCheckBox::indicator:hover {{ border: 1px solid {p['primary_hover']}; }}
QCheckBox::indicator:checked {{ background: {p['primary']}; border: 1px solid {p['primary']}; image: url({marks['check']}); }}

QProgressBar {{ background: {p['soft']}; border: 0; border-radius: 4px; max-height: 8px; min-height: 8px; }}
QProgressBar::chunk {{ background: {p['warn']}; border-radius: 4px; }}
QProgressBar[state="ok"]::chunk {{ background: {p['ok']}; }}
QProgressBar[state="over"]::chunk {{ background: {p['danger']}; }}

/* Прокрутка */
QScrollArea {{ border: 0; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p['line_strong']}; border-radius: 4px; min-height: 36px; }}
QScrollBar::handle:vertical:hover {{ background: {p['muted']}; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p['line_strong']}; border-radius: 4px; min-width: 36px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QMenu {{ background: {p['surface']}; border: 1px solid {p['line_strong']}; border-radius: 8px; padding: 5px; }}
QMenu::item {{ padding: 7px 22px 7px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {p['soft']}; color: {p['text']}; }}
QMenu::separator {{ height: 1px; background: {p['line']}; margin: 4px 6px; }}
"""
