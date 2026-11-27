"""对话区：Canvas 自绘消息气泡，支持滚动、自动宽度、群聊区分说话人。"""
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from .theme import (C_BG, C_TEXT, C_TEXT_SUB, C_USER_BUBBLE, C_CHAR_BUBBLE,
                    C_LINE, C_CARD, FONT_FAMILY, avatar_color, font, round_rect)


class ChatView(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C_BG)
        self.canvas = tk.Canvas(self, bg=C_BG, highlightthickness=0, bd=0)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.vbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.f_body = tkfont.Font(family=FONT_FAMILY, size=11)
        self.f_name = tkfont.Font(family=FONT_FAMILY, size=10, weight="bold")
        self.f_meta = tkfont.Font(family=FONT_FAMILY, size=9)
        self.f_big = tkfont.Font(family=FONT_FAMILY, size=13)

        self.messages = []
        self.char_map = {}
        self.session = None
        self.thinking_name = None
        self.empty_hint = "在左侧选择一个角色开始对话"
        self._resize_job = None

        self.canvas.bind("<Configure>", self._on_configure)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-3, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(3, "units"))

    # ---------- 外部接口 ----------
    def set_conversation(self, session, messages, char_map, empty_hint=None):
        self.session = session
        self.messages = list(messages or [])
        self.char_map = char_map or {}
        self.thinking_name = None
        if empty_hint:
            self.empty_hint = empty_hint
        self.render()

    def append_message(self, msg):
        self.messages.append(msg)
        self.render(scroll=True)

    def set_thinking(self, name):
        self.thinking_name = name
        self.render(scroll=True)

    def clear_thinking(self):
        self.thinking_name = None
        self.render(scroll=True)

    # ---------- 事件 ----------
    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120) * 3, "units")

    def _on_configure(self, _e):
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(80, self.render)

    # ---------- 绘制 ----------
    def render(self, scroll=False):
        c = self.canvas
        c.delete("all")
        self._resize_job = None
        width = c.winfo_width()
        if width <= 20:
            width = 900
        pad_left = 26
        pad_right = 26
        avail = width - pad_left - pad_right

        if not self.session:
            self._draw_empty(width)
            c.configure(scrollregion=(0, 0, width, c.winfo_height() or 400))
            return

        y = 22
        # 群聊抬头
        if self.session.get("type") == "group":
            members = [self.char_map.get(i, {}).get("name", "") for i in
                       self.session.get("member_ids", [])]
            names = "、".join(n for n in members if n)
            y = self._draw_notice(
                "群聊房间 · %d 位角色：%s" % (len([n for n in members if n]), names),
                width, y) + 18

        if not self.messages:
            hint = self.session.get("empty_hint") or "还没有对话，说点什么吧"
            y = self._draw_notice(hint, width, y)

        for m in self.messages:
            role = m.get("role")
            if role == "user":
                y = self._draw_user(m, width, pad_right, avail, y)
            elif role == "error":
                y = self._draw_error(m.get("content", ""), width, y)
            elif role == "notice":
                y = self._draw_notice(m.get("content", ""), width, y + 4) + 10
            else:
                y = self._draw_character(m, width, pad_left, pad_right, avail, y)

        if self.thinking_name:
            y = self._draw_thinking(self.thinking_name, width, pad_left, pad_right, avail, y)

        c.configure(scrollregion=(0, 0, width, y + 10))
        if scroll:
            c.yview_moveto(1.0)

    def _draw_empty(self, width):
        c = self.canvas
        cx = width // 2
        h = c.winfo_height()
        if h < 120:
            h = 520
        c.create_text(cx, h // 2 - 24, text="戏 语", font=(FONT_FAMILY, 22, "bold"),
                      fill="#C8CEDA")
        c.create_text(cx, h // 2 + 16, text=self.empty_hint, font=self.f_body,
                      fill="#AAB2C0")

    def _draw_notice(self, text, width, y):
        c = self.canvas
        tid = c.create_text(width // 2, y, text=text, font=self.f_meta,
                            fill=C_TEXT_SUB, anchor="n", width=max(200, width - 180),
                            justify="center")
        bbox = c.bbox(tid)
        return bbox[3] + 6

    def _draw_error(self, text, width, y):
        c = self.canvas
        maxw = int(min(width - 160, 620))
        tid = c.create_text(width // 2, y + 11, text=text, font=self.f_meta,
                            fill="#A2443F", anchor="nw", width=maxw - 28, justify="left")
        bbox = c.bbox(tid)
        wpx, hpx = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x1 = (width - (wpx + 28)) // 2
        round_rect(c, x1, y, x1 + wpx + 28, y + hpx + 22, r=10,
                   fill="#FDECEA", outline="#F7D5D1")
        c.coords(tid, x1 + 14, y + 11)
        c.tag_raise(tid)
        return y + hpx + 22 + 16

    def _draw_user(self, msg, width, pad_right, avail, y):
        c = self.canvas
        maxw = int(min(avail * 0.72, 640))
        text = msg.get("content", "")
        tid = c.create_text(width - pad_right - 16, y + 12, text=text, font=self.f_body,
                            fill="#FFFFFF", anchor="nw", width=maxw, justify="left")
        bbox = c.bbox(tid)
        wpx, hpx = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x2 = width - pad_right
        x1 = x2 - (wpx + 28)
        round_rect(c, x1, y, x2, y + hpx + 24, r=14, fill=C_USER_BUBBLE, outline="")
        c.coords(tid, x1 + 14, y + 12)
        c.tag_raise(tid)
        return y + hpx + 24 + 14

    def _draw_character(self, msg, width, pad_left, pad_right, avail, y):
        c = self.canvas
        name = msg.get("speaker_name") or ""
        char = self.char_map.get(msg.get("speaker_id"), {})
        name = name or char.get("name") or "角色"
        color = avatar_color(name)

        # 头像 + 名字
        c.create_oval(pad_left, y, pad_left + 36, y + 36, fill=color, outline="")
        c.create_text(pad_left + 18, y + 18, text=(name[:1] or "角"), fill="#FFFFFF",
                      font=(FONT_FAMILY, 13, "bold"))
        c.create_text(pad_left + 46, y + 1, text=name, font=self.f_name,
                      fill="#59627A", anchor="nw")
        ts = msg.get("ts")
        if ts:
            c.create_text(pad_left + 46, y + 18, text=time.strftime("%H:%M", time.localtime(ts)),
                          font=self.f_meta, fill="#A6AEBE", anchor="nw")

        maxw = int(min(avail - 80, 660))
        text = msg.get("content", "")
        tx = pad_left + 46
        tid = c.create_text(tx + 14, y + 46, text=text, font=self.f_body,
                            fill=C_TEXT, anchor="nw", width=maxw - 28, justify="left")
        bbox = c.bbox(tid)
        wpx, hpx = bbox[2] - bbox[0], bbox[3] - bbox[1]
        round_rect(c, tx, y + 38, tx + wpx + 28, y + 38 + hpx + 24, r=12,
                   fill=C_CHAR_BUBBLE, outline=C_LINE)
        c.coords(tid, tx + 14, y + 50)
        c.tag_raise(tid)
        return y + 38 + hpx + 24 + 16

    def _draw_thinking(self, name, width, pad_left, pad_right, avail, y):
        c = self.canvas
        color = avatar_color(name)
        c.create_oval(pad_left, y, pad_left + 36, y + 36, fill=color, outline="")
        c.create_text(pad_left + 18, y + 18, text=(name[:1] or "角"), fill="#FFFFFF",
                      font=(FONT_FAMILY, 13, "bold"))
        c.create_text(pad_left + 46, y + 1, text=name, font=self.f_name,
                      fill="#59627A", anchor="nw")
        tx = pad_left + 46
        round_rect(c, tx, y + 38, tx + 120, y + 72, r=12, fill=C_CARD, outline=C_LINE)
        c.create_text(tx + 16, y + 55, text="正在回应…", font=self.f_meta,
                      fill=C_TEXT_SUB, anchor="w")
        return y + 72 + 16
