# -*- coding: utf-8 -*-
"""Короткая подсказка при наведении. Не забирает фокус и не остаётся на экране."""

from __future__ import annotations

import tkinter as tk

from gui.theme import LINE, NAVY


class _Tip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip: tk.Toplevel | None = None
        self._job = None
        self._bind(widget)
        widget.after(0, self._bind_children)

    def _bind(self, node) -> None:
        node.bind("<Enter>", self._schedule, add="+")
        node.bind("<Leave>", self._schedule_hide, add="+")
        node.bind("<ButtonPress>", self._close, add="+")

    def _bind_children(self) -> None:
        try:
            children = self.widget.winfo_children()
        except tk.TclError:
            return
        for child in children:
            self._bind(child)
            self._bind_tree(child)

    def _bind_tree(self, node) -> None:
        try:
            children = node.winfo_children()
        except tk.TclError:
            return
        for child in children:
            self._bind(child)
            self._bind_tree(child)

    def _schedule(self, _event=None):
        self._cancel()
        try:
            self._job = self.widget.after(450, self._show)
        except tk.TclError:
            return None

    def _schedule_hide(self, _event=None):
        self._cancel()
        try:
            self._job = self.widget.after(80, self._close_if_outside)
        except tk.TclError:
            self._close()

    def _cancel(self) -> None:
        if self._job is None:
            return
        try:
            self.widget.after_cancel(self._job)
        except tk.TclError:
            pass
        self._job = None

    def _inside(self) -> bool:
        try:
            x, y = self.widget.winfo_pointerxy()
            target = self.widget.winfo_containing(x, y)
        except tk.TclError:
            return False
        while target is not None:
            if target == self.widget:
                return True
            target = getattr(target, "master", None)
        return False

    def _close_if_outside(self) -> None:
        self._job = None
        if self._inside():
            return
        self._close()

    def _show(self) -> None:
        self._job = None
        if self.tip is not None or not self._inside():
            return
        try:
            x = self.widget.winfo_rootx() + 8
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except tk.TclError:
            return
        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        try:
            tip.transient(self.widget.winfo_toplevel())
        except tk.TclError:
            pass
        tip.attributes("-topmost", True)
        label = tk.Label(
            tip,
            text=self.text,
            justify="left",
            background="white",
            foreground=NAVY,
            font=("Segoe UI", 10),
            wraplength=280,
            padx=10,
            pady=7,
            highlightbackground=LINE,
            highlightthickness=1,
        )
        label.pack()
        tip.update_idletasks()
        width = tip.winfo_reqwidth()
        height = tip.winfo_reqheight()
        screen_w = tip.winfo_screenwidth()
        screen_h = tip.winfo_screenheight()
        x = min(max(8, x), max(8, screen_w - width - 8))
        if y + height > screen_h - 8:
            y = max(8, self.widget.winfo_rooty() - height - 6)
        tip.wm_geometry(f"+{x}+{y}")
        self.tip = tip

    def _close(self, _event=None) -> None:
        self._cancel()
        if self.tip is not None:
            try:
                self.tip.destroy()
            except tk.TclError:
                pass
            self.tip = None


def tooltip(widget, text: str) -> None:
    """Показывает text, когда курсор задерживается на виджете."""
    if widget is None or not str(text).strip():
        return
    _Tip(widget, str(text).strip())
