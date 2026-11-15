# -*- coding: utf-8 -*-
"""Главное окно: боковая панель с шагами, экран программ и мастер из пяти шагов."""

from __future__ import annotations

import ctypes
import webbrowser

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QFontMetrics, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.paths import VERSION, icon_path, logo_path
from core.updates import look_for_update
from ui import prefs
from ui.onboarding import OnboardingDialog, onboarding_seen
from ui.pages.build import BuildPage
from ui.pages.conditions import ConditionsPage
from ui.pages.home import HomePage
from ui.pages.learners import LearnersPage
from ui.pages.passport import PassportPage
from ui.pages.plan import PlanPage
from ui.state import STEP_TITLES, Session
from ui.theme import Glyph, glyph_icon, theme
from ui.widgets import Button, Toast, ask, label, run_async, set_prop

_STEP_TIPS = (
    "Название, организация и педагог. Звёздочка — обязательное поле.",
    "Возраст, часы и размер группы. От них зависят календарь и занятия.",
    "Разделы и часы. Сумма должна совпасть с общим объёмом.",
    "Оборудование, программы, расходные материалы и профессии проб.",
    "Проверка текста и сборка файла Word.",
)
_SIDE_ICON = "#C7D3E8"


class StepButton(QPushButton):
    """Строка шага в боковой панели: кружок состояния и название."""

    def __init__(self, index: int, title: str):
        super().__init__()
        self.index = index
        self.setObjectName("step")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(42)
        self.setFocusPolicy(Qt.TabFocus)
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(11)
        self.badge = QLabel(str(index + 1))
        self.badge.setObjectName("badge")
        self.badge.setFixedSize(24, 24)
        self.badge.setAlignment(Qt.AlignCenter)
        self.text = QLabel(title)
        self.text.setObjectName("stepText")
        self.note = QLabel("")
        self.note.setObjectName("stepNote")
        for item in (self.badge, self.text, self.note):
            item.setAttribute(Qt.WA_TransparentForMouseEvents)
        row.addWidget(self.badge)
        row.addWidget(self.text, 1)
        row.addWidget(self.note)

    def set_state(self, state: str, count: int = 0, active: bool = False) -> None:
        self.setChecked(active)
        set_prop(self.text, "active", active)
        if state == "ok":
            self.badge.setText("✓")
        else:
            self.badge.setText(str(self.index + 1))
        self.note.setText(str(count) if state == "warn" and count else "")
        self.note.setToolTip("")
        set_prop(self.badge, "state", "current" if active and state != "warn" and state != "ok" else state)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        _set_windows_app_id()
        self.session = Session()
        self.setWindowTitle("ДопПро")
        self.setMinimumSize(1040, 680)
        self.resize(1240, 820)
        if icon_path().exists():
            self.setWindowIcon(QIcon(str(icon_path())))

        root = QWidget()
        self.setCentralWidget(root)
        line = QHBoxLayout(root)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(0)
        line.addWidget(self._build_sidebar())

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self.stack = QStackedWidget()
        right.addWidget(self.stack, 1)
        right.addWidget(self._build_footer())
        line.addLayout(right, 1)

        self.home = HomePage(self)
        self.steps = [PassportPage(self), LearnersPage(self), PlanPage(self), ConditionsPage(self), BuildPage(self)]
        self.stack.addWidget(self.home)
        for page in self.steps:
            self.stack.addWidget(page)
        self.current = -1  # -1 — экран программ, 0…4 — шаги

        self._toast = Toast(root)
        self.session.changed.connect(self._model_changed)
        self.session.saved.connect(self.save_state.setText)
        self.session.replaced.connect(self._program_replaced)
        QShortcut(QKeySequence.Save, self, activated=self._save_now)

        if self.session.draft_used and (self.session.model.title.strip() or self.session.model.organization.strip()):
            self.show_step(0)
        else:
            self.show_home()
        QTimer.singleShot(400, self._offer_onboarding)
        QTimer.singleShot(2500, self._check_updates)

    # ---------- построение ----------

    def _build_sidebar(self) -> QWidget:
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(256)
        box = QVBoxLayout(side)
        box.setContentsMargins(14, 18, 14, 14)
        box.setSpacing(4)

        brand = QHBoxLayout()
        brand.setSpacing(11)
        if logo_path().exists():
            plate = QLabel()
            plate.setFixedSize(44, 44)
            plate.setStyleSheet("background: #FFFFFF; border-radius: 11px;")
            plate.setAlignment(Qt.AlignCenter)
            pixmap = QPixmap(str(logo_path())).scaled(
                QSize(108, 108), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            pixmap.setDevicePixelRatio(3)
            plate.setPixmap(pixmap)
            brand.addWidget(plate)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        name = QLabel("ДопПро")
        name.setObjectName("brand")
        sub = QLabel("Конструктор программ")
        sub.setObjectName("brandSub")
        titles.addWidget(name)
        titles.addWidget(sub)
        brand.addLayout(titles, 1)
        box.addLayout(brand)
        box.addSpacing(16)

        self.home_button = self._nav("Мои программы", Glyph.HOME, self.show_home,
                                     "Все сохранённые программы. Ключ нейросети в них не записывается.")
        self.home_button.setCheckable(True)
        box.addWidget(self.home_button)
        box.addSpacing(14)

        section = QLabel("ПРОГРАММА")
        section.setObjectName("navSection")
        section.setContentsMargins(12, 0, 0, 0)
        box.addWidget(section)
        self.program_name = QLabel("")
        self.program_name.setObjectName("programName")
        self.program_name.setContentsMargins(12, 0, 0, 0)
        box.addWidget(self.program_name)
        box.addSpacing(6)

        self.step_buttons: list[StepButton] = []
        for index, title in enumerate(STEP_TITLES):
            button = StepButton(index, title)
            button.setToolTip(_STEP_TIPS[index])
            button.clicked.connect(lambda _c=False, i=index: self.show_step(i))
            box.addWidget(button)
            self.step_buttons.append(button)

        box.addStretch(1)
        self.save_state = QLabel("")
        self.save_state.setObjectName("saveState")
        self.save_state.setContentsMargins(12, 0, 0, 0)
        box.addWidget(self.save_state)
        offline = QLabel("Шаблон без интернета")
        offline.setObjectName("offline")
        offline.setContentsMargins(12, 0, 0, 0)
        offline.setToolTip("Документ собирается и без сети. Нейросеть нужна только для формулировок по названию.")
        box.addWidget(offline)
        box.addSpacing(8)
        divider = QFrame()
        divider.setObjectName("sideLine")
        box.addWidget(divider)
        box.addSpacing(6)
        box.addWidget(self._nav("Настройки", Glyph.SETTINGS, self.open_settings,
                                "Ключ нейросети, тема и обновления. Ключ хранится только на этом компьютере."))
        box.addWidget(self._nav("Помощь", Glyph.HELP, self.open_help,
                                "Коротко о пяти шагах. То же окно, что при первом запуске."))
        self.theme_button = self._nav("", Glyph.MOON, self.toggle_theme, "Переключить светлую и тёмную тему.")
        box.addWidget(self.theme_button)
        version = QLabel(f"Версия {VERSION}")
        version.setObjectName("brandSub")
        version.setContentsMargins(12, 4, 0, 0)
        box.addWidget(version)
        self._paint_theme_button()
        return side

    def _nav(self, text: str, glyph: str, on, tip: str = "") -> QPushButton:
        button = QPushButton("  " + text)
        button.setObjectName("nav")
        button.setCursor(Qt.PointingHandCursor)
        button.setIcon(glyph_icon(glyph, _SIDE_ICON, 16))
        button.setIconSize(QSize(16, 16))
        button.setFocusPolicy(Qt.TabFocus)
        button.clicked.connect(lambda _c=False: on())
        if tip:
            button.setToolTip(tip)
        return button

    def _build_footer(self) -> QWidget:
        self.footer = QFrame()
        self.footer.setObjectName("footer")
        row = QHBoxLayout(self.footer)
        row.setContentsMargins(32, 12, 32, 12)
        row.setSpacing(14)
        self.back_button = Button("Назад", glyph=Glyph.LEFT, on=self.back_step,
                                  tip="Вернуться на предыдущий шаг. Введённое уже сохранено.")
        row.addWidget(self.back_button)
        self.step_caption = label("", "muted")
        row.addWidget(self.step_caption)
        row.addStretch(1)
        self.footer_note = label("", "warn")
        row.addWidget(self.footer_note)
        self.next_button = Button("Далее", "primary", on=self.next_step)
        self.next_button.setMinimumWidth(150)
        row.addWidget(self.next_button)
        return self.footer

    # ---------- навигация ----------

    def show_home(self) -> None:
        self._leave_step()
        self.current = -1
        self.stack.setCurrentWidget(self.home)
        self.home.on_show()
        self.footer.hide()
        self.refresh_status()

    def show_step(self, index: int) -> None:
        self._leave_step()
        self.current = max(0, min(len(self.steps) - 1, index))
        page = self.steps[self.current]
        self.stack.setCurrentWidget(page)
        page.on_show()
        page.scroll.verticalScrollBar().setValue(0)
        self.footer.show()
        self.refresh_status()

    def _leave_step(self) -> None:
        if 0 <= self.current < 4:
            self.session.touched.add(self.current)

    def next_step(self) -> None:
        if self.current == len(self.steps) - 1:
            self.steps[-1].build()
            return
        self.show_step(self.current + 1)

    def back_step(self) -> None:
        if self.current > 0:
            self.show_step(self.current - 1)
        else:
            self.show_home()

    # ---------- состояние ----------

    def refresh_status(self) -> None:
        model = self.session.model
        title = model.title.strip() or "Новая программа"
        metrics = QFontMetrics(self.program_name.font())
        self.program_name.setText(metrics.elidedText(title, Qt.ElideRight, 210))
        self.program_name.setToolTip(title)
        self.home_button.setChecked(self.current == -1)
        total_errors = 0
        for index, button in enumerate(self.step_buttons):
            active = index == self.current
            if index == 4:
                button.set_state("idle", active=active)
                continue
            errors = self.session.step_errors(index)
            total_errors += len(errors)
            if index in self.session.touched:
                button.set_state("warn" if errors else "ok", len(errors), active)
            else:
                button.set_state("idle", active=active)
        if 0 <= self.current < 4:
            page = self.steps[self.current]
            errors = self.session.step_errors(self.current) if self.current in self.session.touched else []
            page.show_errors(errors)
        if self.current >= 0:
            last = self.current == len(self.steps) - 1
            self.step_caption.setText(f"Шаг {self.current + 1} из {len(self.steps)}")
            self.back_button.setText("К программам" if self.current == 0 else "Назад")
            self.next_button.setText("Собрать программу" if last else "Далее")
            self.next_button.setToolTip(
                "Создаёт файл Word. Интернет для сборки не нужен." if last else "Перейти к следующему шагу."
            )
            self.footer_note.setText(f"Осталось поправить: {total_errors}" if last and total_errors else "")

    def _model_changed(self) -> None:
        self.save_state.setText("Сохраняю…")
        self.refresh_status()

    def _program_replaced(self) -> None:
        self.refresh_status()

    def _save_now(self) -> None:
        self.session.touch()
        self.session.flush()
        self.toast("Сохранено")

    def set_busy(self, busy: bool) -> None:
        if busy:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()

    def toast(self, text: str) -> None:
        self._toast.show_text(text)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._toast.isVisible():
            self._toast.place()

    def closeEvent(self, event) -> None:
        try:
            self.session.flush()
        except Exception:
            pass
        geometry = self.normalGeometry()
        prefs.put("window", [geometry.width(), geometry.height(), self.isMaximized()])
        super().closeEvent(event)

    # ---------- окна ----------

    def open_settings(self) -> None:
        from ui.settings_dialog import SettingsDialog

        SettingsDialog(self).exec()
        self._paint_theme_button()
        if self.current == 4:
            self.steps[4].refresh()

    def open_help(self) -> None:
        OnboardingDialog(self).exec()

    def toggle_theme(self) -> None:
        prefs.put("theme", theme.toggle())
        self._paint_theme_button()

    def _paint_theme_button(self) -> None:
        dark = theme.dark
        self.theme_button.setText("  Светлая тема" if dark else "  Тёмная тема")
        self.theme_button.setIcon(glyph_icon(Glyph.SUN if dark else Glyph.MOON, _SIDE_ICON, 16))

    def _offer_onboarding(self) -> None:
        if not onboarding_seen():
            self.open_help()

    def _check_updates(self) -> None:
        run_async(self, look_for_update, self._update_checked)

    def _update_checked(self, report) -> None:
        if report.newer and ask(
            self, f"Вышла версия {report.remote}", "Открыть страницу загрузки?", yes="Открыть", no="Позже"
        ):
            webbrowser.open(report.url)


def _set_windows_app_id() -> None:
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DopPro.Desktop.2")
    except Exception:
        return
