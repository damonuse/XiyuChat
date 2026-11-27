"""通用小组件：Canvas 圆角按钮。"""
import tkinter as tk
import tkinter.font as tkfont

from .theme import C_ACCENT, font, round_rect


def _parent_bg(master, fallback="#F5F6FA"):
    try:
        return master.cget("bg")
    except Exception:
        return fallback


class RoundButton(tk.Canvas):
    def __init__(self, master, text, command=None, bg=C_ACCENT, fg="#FFFFFF",
                 hover=None, parent_bg=None, height=34, padx=18, radius=None,
                 font_spec=None, outline=""):
        self._font = tkfont.Font(font=font_spec or font(10, bold=True))
        self._text = text
        self._cmd = command
        self._bg = bg
        self._fg = fg
        self._hover = hover or _shade(bg, -12)
        self._radius = radius if radius is not None else height / 2
        self._outline = outline
        self._enabled = True
        w = self._font.measure(text) + padx * 2
        super().__init__(master, width=w, height=height,
                         bg=parent_bg or _parent_bg(master),
                         highlightthickness=0, bd=0, cursor="hand2")
        self._draw()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    # ---------- 绘制 ----------
    def _draw(self):
        self.delete("all")
        w = int(self["width"])
        h = int(self["height"])
        if not self._enabled:
            fill, fg = "#DCE0E8", "#FFFFFF"
        elif getattr(self, "_pressed", False):
            fill, fg = _shade(self._bg, -18), self._fg
        elif getattr(self, "_active", False):
            fill, fg = self._hover, self._fg
        else:
            fill, fg = self._bg, self._fg
        round_rect(self, 0.5, 0.5, w - 0.5, h - 0.5, r=self._radius,
                   fill=fill, outline=self._outline)
        self.create_text(w / 2, h / 2, text=self._text, fill=fg, font=self._font)

    # ---------- 状态 ----------
    def set_enabled(self, enabled: bool):
        self._enabled = bool(enabled)
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def set_text(self, text):
        self._text = text
        self._draw()

    # ---------- 事件 ----------
    def _on_enter(self, _e):
        self._active = True
        self._draw()

    def _on_leave(self, _e):
        self._active = False
        self._pressed = False
        self._draw()

    def _on_press(self, _e):
        if not self._enabled:
            return
        self._pressed = True
        self._draw()

    def _on_release(self, e):
        if not self._enabled:
            return
        self._pressed = False
        inside = 0 <= e.x <= int(self["width"]) and 0 <= e.y <= int(self["height"])
        self._draw()
        if inside and self._cmd:
            self._cmd()


def _shade(color, delta):
    try:
        color = color.lstrip("#")
        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
        r = max(0, min(255, r + delta))
        g = max(0, min(255, g + delta))
        b = max(0, min(255, b + delta))
        return "#%02X%02X%02X" % (r, g, b)
    except Exception:
        return color
