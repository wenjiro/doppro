# -*- coding: utf-8 -*-
"""Повторяющиеся элементы форм: подпись, поле, карточка, подсказка."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from core.places import fold_search
from gui.theme import BG, FONT, FONT_B, FONT_H, FONT_S, LINE, MUTED, NAVY
from gui.tooltip import tooltip


class LabeledEntry(ctk.CTkFrame):
    """Подпись над однострочным полем."""

    def __init__(self, master, label: str, required: bool = False, placeholder: str = "", tip: str = ""):
        super().__init__(master, fg_color="transparent")
        caption = label + (" *" if required else "")
        ctk.CTkLabel(self, text=caption, anchor="w", font=FONT, text_color=NAVY).pack(fill="x")
        self.entry = ctk.CTkEntry(
            self,
            height=36,
            font=FONT,
            placeholder_text=placeholder,
            border_color=LINE,
            fg_color="white",
            text_color="#1A1A1A",
        )
        self.entry.pack(fill="x", pady=(4, 0))
        bind_text_shortcuts(self.entry)
        tooltip(self, tip)

    def get(self) -> str:
        return self.entry.get().strip()

    def set(self, value: str) -> None:
        self.entry.delete(0, "end")
        if value:
            self.entry.insert(0, value)


class SearchableCombo(ctk.CTkFrame):
    """Список с поиском. Если нужного пункта нет, в поле остаётся свой текст."""

    def __init__(self, master, label: str, values: list[str], required: bool = False, tip: str = "", on_commit=None):
        super().__init__(master, fg_color="transparent")
        caption = label + (" *" if required else "")
        ctk.CTkLabel(self, text=caption, anchor="w", font=FONT, text_color=NAVY).pack(fill="x")
        self._all = list(values)
        self._on_commit = on_commit
        self.combo = ctk.CTkComboBox(
            self,
            values=self._matches(""),
            height=36,
            font=FONT,
            dropdown_font=FONT,
            state="normal",
            border_color=LINE,
            fg_color="white",
            button_color=NAVY,
            button_hover_color=TEAL_SAFE,
            text_color="#1A1A1A",
            command=self._picked,
        )
        self.combo.pack(fill="x", pady=(4, 0))
        self.combo.set("")
        bind_text_shortcuts(self.combo)
        self.combo.bind("<KeyRelease>", self._typed)
        self.combo.bind("<FocusOut>", self._leave)
        tooltip(self, tip)

    def get(self) -> str:
        return self.combo.get().strip()

    def set(self, value: str) -> None:
        self.combo.set(value or "")
        self.combo.configure(values=self._matches(value or ""))

    def set_choices(self, values: list[str]) -> None:
        self._all = list(values)
        self.combo.configure(values=self._matches(self.get()))

    def _matches(self, text: str) -> list[str]:
        needle = fold_search(text)
        if not needle:
            return self._all[:100]
        starts: list[str] = []
        contains: list[str] = []
        for item in self._all:
            folded = fold_search(item)
            if folded.startswith(needle):
                starts.append(item)
            elif needle in folded:
                contains.append(item)
            if len(starts) >= 40:
                break
        shown = starts[:40]
        if len(shown) < 40:
            shown.extend(contains[: 40 - len(shown)])
        return shown

    def _typed(self, event) -> None:
        if event.keysym in {"Up", "Return", "Escape", "Tab", "Left", "Right"}:
            return
        self.combo.configure(values=self._matches(self.combo.get()))
        if event.keysym == "Down":
            try:
                self.combo._open_dropdown_menu()
            except Exception:
                return
            return "break"

    def _picked(self, _value: str) -> None:
        if self._on_commit is not None:
            self._on_commit()

    def _leave(self, _event=None) -> None:
        if self._on_commit is not None:
            self._on_commit()


class LabeledCombo(ctk.CTkFrame):
    """Подпись над выпадающим списком. Педагог выбирает только готовые значения."""

    def __init__(self, master, label: str, values: list[str], required: bool = False, tip: str = ""):
        super().__init__(master, fg_color="transparent")
        caption = label + (" *" if required else "")
        ctk.CTkLabel(self, text=caption, anchor="w", font=FONT, text_color=NAVY).pack(fill="x")
        self.values = list(values)
        self.combo = ctk.CTkComboBox(
            self,
            values=self.values,
            height=36,
            font=FONT,
            dropdown_font=FONT,
            state="readonly",
            border_color=LINE,
            fg_color="white",
            button_color=NAVY,
            button_hover_color=TEAL_SAFE,
            text_color="#1A1A1A",
        )
        self.combo.pack(fill="x", pady=(4, 0))
        if self.values:
            self.combo.set(self.values[0])
        tooltip(self, tip)

    def get(self) -> str:
        return self.combo.get().strip()

    def set(self, value: str) -> None:
        if value in self.values:
            self.combo.set(value)
        elif self.values:
            self.combo.set(self.values[0])


class LabeledText(ctk.CTkFrame):
    """Многострочное поле."""

    def __init__(self, master, label: str, height: int = 90, tip: str = ""):
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text=label, anchor="w", font=FONT, text_color=NAVY).pack(fill="x")
        self.box = ctk.CTkTextbox(
            self,
            height=height,
            font=FONT,
            border_width=1,
            border_color=LINE,
            fg_color="white",
            text_color="#1A1A1A",
        )
        self.box.pack(fill="x", pady=(4, 0))
        bind_text_shortcuts(self.box)
        tooltip(self, tip)

    def get(self) -> str:
        return self.box.get("1.0", "end").strip()

    def set(self, value: str) -> None:
        self.box.delete("1.0", "end")
        if value:
            self.box.insert("1.0", value)


# Цвет наведения вынесен отдельно, чтобы не создавать цикл импорта темы в рантайме виджета.
TEAL_SAFE = "#0B655E"


def bind_text_shortcuts(widget) -> None:
    """Вставка и копирование работают и в русской раскладке.

    Windows при русской раскладке отдаёт Ctrl+М вместо Ctrl+V, и стандартная
    вставка Tk это сочетание не узнаёт. Код клавиши от раскладки не зависит.
    """
    target = getattr(widget, "_entry", None) or getattr(widget, "_textbox", None) or widget

    def paste(_event=None):
        try:
            text = target.clipboard_get()
        except tk.TclError:
            return "break"
        try:
            target.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        target.insert("insert", text)
        return "break"

    def copy(_event=None):
        try:
            text = target.selection_get()
        except tk.TclError:
            return "break"
        target.clipboard_clear()
        target.clipboard_append(text)
        return "break"

    def cut(_event=None):
        copy()
        try:
            target.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        return "break"

    def select_all(_event=None):
        if target.winfo_class() == "Text":
            target.tag_add("sel", "1.0", "end")
            target.mark_set("insert", "end")
        else:
            target.select_range(0, "end")
            target.icursor("end")
        return "break"

    def on_control(event):
        action = {86: paste, 67: copy, 88: cut, 65: select_all}.get(event.keycode)
        if action is None:
            return None
        return action()

    target.bind("<Control-KeyPress>", on_control, add="+")
    target.bind("<Shift-Insert>", paste, add="+")

    menu = tk.Menu(target, tearoff=0)
    menu.add_command(label="Вставить", command=paste)
    menu.add_command(label="Копировать", command=copy)
    menu.add_command(label="Вырезать", command=cut)
    menu.add_separator()
    menu.add_command(label="Выделить всё", command=select_all)

    def popup(event):
        target.focus_set()
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    target.bind("<Button-3>", popup, add="+")


def card(parent) -> ctk.CTkFrame:
    """Белая карточка. Возвращает внутренний отступ, куда кладут поля."""
    shell = ctk.CTkFrame(parent, fg_color="white", corner_radius=12, border_width=1, border_color=LINE)
    shell.pack(fill="x", padx=20, pady=(4, 10))
    inner = ctk.CTkFrame(shell, fg_color="white")
    inner.pack(fill="x", padx=16, pady=14)
    return inner


def caption(parent, text: str) -> None:
    ctk.CTkLabel(parent, text=text, font=FONT_H, text_color=NAVY, anchor="w", justify="left").pack(
        fill="x", padx=22, pady=(14, 0)
    )


def hint(parent, text: str) -> ctk.CTkLabel:
    label = ctk.CTkLabel(
        parent,
        text=text,
        font=FONT_S,
        text_color=MUTED,
        anchor="w",
        justify="left",
        wraplength=860,
    )
    label.pack(fill="x", padx=22, pady=(4, 6))
    return label


def primary_button(parent, text: str, command) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent,
        text=text,
        command=command,
        height=40,
        font=FONT_B,
        fg_color=NAVY,
        hover_color="#16315F",
        text_color="white",
        corner_radius=8,
    )


def secondary_button(parent, text: str, command) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent,
        text=text,
        command=command,
        height=36,
        font=FONT,
        fg_color="#E8EEF5",
        hover_color="#D5DEEA",
        text_color=NAVY,
        corner_radius=8,
    )


def checkbox(parent, text: str) -> ctk.CTkCheckBox:
    return ctk.CTkCheckBox(
        parent,
        text=text,
        font=FONT,
        text_color="#1A1A1A",
        fg_color=NAVY,
        hover_color=TEAL_SAFE,
        border_color=LINE,
        checkmark_color="white",
    )


def parse_int(text: str) -> int:
    """Пустая строка и любой нецелый ввод дают -1. Это ловит проверка шага."""
    raw = text.strip().replace(" ", "")
    if not raw.isdigit():
        return -1
    return int(raw)


def set_checkbox(box: ctk.CTkCheckBox, value: bool) -> None:
    if value:
        box.select()
    else:
        box.deselect()


# Фон нужен импортирующим модулям как напоминание о цвете окна.
WINDOW_BG = BG
