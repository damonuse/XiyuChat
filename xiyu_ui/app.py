"""戏语 · 主窗口与程序入口。"""
import ctypes
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from xiyu_core import paths, storage, llm, engine, memory
from .chat_view import ChatView
from .dialogs import SettingsWindow, CharacterDialog, MemoryWindow
from .theme import (C_BG, C_CARD, C_TEXT, C_TEXT_SUB, C_LINE, C_ACCENT, C_ACCENT_SOFT,
                    C_DANGER, C_BANNER, C_BANNER_SUB, FONT_FAMILY, font, avatar_color,
                    round_rect)
from .widgets import RoundButton

PLACEHOLDER = "说点什么…   （Enter 发送，Shift+Enter 换行）"


class App:
    def __init__(self, root, scale=1.0):
        self.root = root
        self.scale = scale
        self.cfg = storage.load_config()
        self.api_key = storage.load_api_key()
        self.chars = storage.load_characters()
        self.sessions = storage.load_sessions()
        self.loaded = {}          # session_id -> messages
        self.current = None
        self.rounds = {}          # session_id -> {token, pending, chan}
        self.q = queue.Queue()
        self._gen = 0
        self._placeholder_on = False
        self.memory_cache = {}
        self.marks = {}
        self._summarizing = set()

        self._sanitize()
        self._build()
        self._refresh_sidebar()
        self._update_header()
        self._restore_last()

        self.root.bind("<F2>", lambda e: self._open_settings())
        self.root.after(60, self._poll)
        self.root.after(150, self._first_run_check)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ================= 数据整理 =================
    def _char(self, cid):
        for c in self.chars:
            if c["id"] == cid:
                return c
        return None

    def _session(self, sid):
        for s in self.sessions:
            if s["id"] == sid:
                return s
        return None

    def _sanitize(self):
        valid = {c["id"] for c in self.chars}
        keep = []
        for s in self.sessions:
            if s.get("type") == "group":
                s["member_ids"] = [m for m in s.get("member_ids", []) if m in valid]
                if len(s["member_ids"]) >= 2:
                    keep.append(s)
            elif s.get("single_char_id") in valid:
                keep.append(s)
        self.sessions = keep
        for s in self.chars:
            pass
        storage.save_sessions(self.sessions)

    # ================= 界面 =================
    def _build(self):
        root = self.root
        root.configure(bg=C_BG)

        # 顶部标题栏
        banner = tk.Frame(root, bg=C_BANNER, height=int(64 * self.scale))
        banner.pack(fill="x")
        banner.pack_propagate(False)
        tk.Label(banner, text="戏 语", bg=C_BANNER, fg="#FFFFFF",
                 font=font(20, bold=True)).pack(side="left", padx=(22, 10))
        tk.Label(banner, text="AI 角色扮演 · 多角色群聊",
                 bg=C_BANNER, fg=C_BANNER_SUB, font=font(9)).pack(side="left", pady=(6, 0))
        RoundButton(banner, "设置 (F2)", self._open_settings, bg="#2E3442", hover="#3B4252",
                    parent_bg=C_BANNER, height=30, padx=14).pack(side="right", padx=18)

        # 工具栏
        tool = tk.Frame(root, bg=C_BG)
        tool.pack(fill="x", padx=18, pady=(12, 10))
        RoundButton(tool, "＋ 创建角色", self._create_character, bg=C_ACCENT,
                    height=36, padx=20, parent_bg=C_BG).pack(side="left")
        RoundButton(tool, "新建群聊", self._create_group, bg=C_CARD, fg=C_ACCENT,
                    hover=C_ACCENT_SOFT, outline=C_LINE, height=36, padx=16,
                    parent_bg=C_BG).pack(side="left", padx=(10, 0))
        self.lbl_model = tk.Label(tool, text="", bg=C_BG, fg=C_TEXT_SUB, font=font(9))
        self.lbl_model.pack(side="right")
        self._refresh_model_label()

        # 主体
        body = tk.Frame(root, bg=C_BG)
        body.pack(fill="both", expand=True, padx=18, pady=(0, 14))

        # 左侧
        side = tk.Frame(body, bg=C_CARD, width=int(246 * self.scale),
                        highlightthickness=1, highlightbackground=C_LINE)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        side_head = tk.Frame(side, bg=C_CARD)
        side_head.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(side_head, text="角色 / 会话", bg=C_CARD, fg=C_TEXT_SUB,
                 font=font(9, bold=True)).pack(side="left")
        self.lbl_count = tk.Label(side_head, text="", bg=C_CARD, fg=C_TEXT_SUB, font=font(9))
        self.lbl_count.pack(side="right")

        holder = tk.Frame(side, bg=C_CARD)
        holder.pack(fill="both", expand=True)
        self.side_canvas = tk.Canvas(holder, bg=C_CARD, highlightthickness=0, bd=0)
        self.side_sb = ttk.Scrollbar(holder, orient="vertical", command=self.side_canvas.yview)
        self.side_canvas.configure(yscrollcommand=self.side_sb.set)
        self.side_sb.pack(side="right", fill="y")
        self.side_canvas.pack(side="left", fill="both", expand=True)
        self.side_inner = tk.Frame(self.side_canvas, bg=C_CARD)
        self.side_window = self.side_canvas.create_window(0, 0, window=self.side_inner, anchor="nw")
        self.side_inner.bind("<Configure>", lambda e: self.side_canvas.configure(
            scrollregion=self.side_canvas.bbox("all")))
        self.side_canvas.bind("<Configure>", lambda e: self.side_canvas.itemconfigure(
            self.side_window, width=e.width))
        self.side_canvas.bind("<MouseWheel>", self._on_side_wheel)

        side_foot = tk.Frame(side, bg=C_CARD)
        side_foot.pack(fill="x", padx=10, pady=10)
        self.btn_edit = RoundButton(side_foot, "编辑", self._edit_current, bg="#F0F2F6",
                                    fg=C_TEXT, hover="#E6E9F0", height=30, padx=14,
                                    parent_bg=C_CARD)
        self.btn_edit.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.btn_del = RoundButton(side_foot, "删除", self._delete_current, bg="#FCEDEC",
                                   fg="#B0413C", hover="#F8DBD9", height=30, padx=14,
                                   parent_bg=C_CARD)
        self.btn_del.pack(side="left", expand=True, fill="x", padx=(4, 0))

        # 右侧
        chat = tk.Frame(body, bg=C_CARD, highlightthickness=1, highlightbackground=C_LINE)
        chat.pack(side="left", fill="both", expand=True, padx=(12, 0))

        head = tk.Frame(chat, bg=C_CARD, height=58)
        head.pack(fill="x")
        head.pack_propagate(False)
        hleft = tk.Frame(head, bg=C_CARD)
        hleft.pack(side="left", padx=18, pady=9)
        self.lbl_title = tk.Label(hleft, text="戏 语", bg=C_CARD, fg=C_TEXT,
                                  font=font(13, bold=True), anchor="w")
        self.lbl_title.pack(anchor="w")
        self.lbl_sub = tk.Label(hleft, text="", bg=C_CARD, fg=C_TEXT_SUB,
                                font=font(9), anchor="w")
        self.lbl_sub.pack(anchor="w")
        self.btn_memory = RoundButton(head, "记忆", self._open_memory, bg="#F0F2F6",
                                      fg=C_TEXT, hover="#E6E9F0", height=28, padx=12,
                                      parent_bg=C_CARD)
        self.btn_memory.pack(side="right", padx=(0, 16))
        self.lbl_state = tk.Label(head, text="", bg=C_CARD, fg=C_TEXT_SUB,
                                  font=font(9), anchor="e")
        self.lbl_state.pack(side="right", padx=(0, 10))
        tk.Frame(chat, bg=C_LINE, height=1).pack(fill="x")

        self.chat_view = ChatView(chat)
        self.chat_view.pack(fill="both", expand=True)

        # 输入区
        ia = tk.Frame(chat, bg=C_CARD)
        ia.pack(fill="x", padx=14, pady=(8, 4))
        box = tk.Frame(ia, bg=C_CARD, highlightthickness=1, highlightbackground=C_LINE,
                       highlightcolor="#C7D2EC")
        box.pack(fill="x")
        self.txt_input = tk.Text(box, height=3, wrap="word", bd=0, relief="flat",
                                 bg=C_CARD, fg=C_TEXT, insertbackground=C_TEXT,
                                 font=font(11), padx=12, pady=8, undo=True)
        self.txt_input.pack(side="left", fill="both", expand=True)
        self.btn_send = RoundButton(box, "发送", self._send, bg=C_ACCENT, height=32,
                                    padx=18, parent_bg=C_CARD)
        self.btn_send.pack(side="right", padx=8, pady=10, anchor="s")

        self.txt_input.bind("<FocusIn>", self._on_focus_in)
        self.txt_input.bind("<FocusOut>", self._on_focus_out)
        self.txt_input.bind("<Return>", self._on_return)
        self._set_placeholder()

        hint = tk.Frame(chat, bg=C_CARD)
        hint.pack(fill="x", padx=16, pady=(0, 10))
        tk.Label(hint, text="Enter 发送 · Shift+Enter 换行 · F2 打开设置",
                 bg=C_CARD, fg="#AEB5C2", font=font(8)).pack(side="left")
        self.lbl_input_tip = tk.Label(hint, text="", bg=C_CARD, fg=C_DANGER, font=font(8))
        self.lbl_input_tip.pack(side="right")

    # ================= 输入框 =================
    def _set_placeholder(self):
        self.txt_input.delete("1.0", "end")
        self.txt_input.insert("1.0", PLACEHOLDER)
        self.txt_input.configure(fg="#AEB5C2")
        self._placeholder_on = True

    def _on_focus_in(self, _e):
        if self._placeholder_on:
            self.txt_input.delete("1.0", "end")
            self.txt_input.configure(fg=C_TEXT)
            self._placeholder_on = False

    def _on_focus_out(self, _e):
        if not self.txt_input.get("1.0", "end").strip():
            self._set_placeholder()

    def _on_return(self, event):
        if event.state & 0x0001:      # Shift
            return None
        self._send()
        return "break"

    def _take_input(self):
        if self._placeholder_on:
            return "", True
        return self.txt_input.get("1.0", "end").strip(), False

    # ================= 侧栏 =================
    def _on_side_wheel(self, event):
        self.side_canvas.yview_scroll(int(-event.delta / 120) * 3, "units")

    def _bind_side_wheel(self, w):
        w.bind("<MouseWheel>", self._on_side_wheel)
        for c in w.winfo_children():
            self._bind_side_wheel(c)

    def _refresh_sidebar(self):
        for w in self.side_inner.winfo_children():
            w.destroy()
        self.lbl_count.configure(text=("%d" % len(self.sessions)) if self.sessions else "")
        self.btn_edit.set_enabled(self.current is not None)
        self.btn_del.set_enabled(self.current is not None)

        if not self.sessions:
            box = tk.Frame(self.side_inner, bg=C_CARD)
            box.pack(fill="x", pady=(70, 0), padx=16)
            tk.Label(box, text="还没有角色", bg=C_CARD, fg=C_TEXT,
                     font=font(11, bold=True)).pack()
            tk.Label(box, text="点击上方的「＋ 创建角色」\n填写名字、人设和开场白\n就能开始对话",
                     bg=C_CARD, fg=C_TEXT_SUB, font=font(9), justify="center").pack(pady=(8, 0))
            self._bind_side_wheel(self.side_inner)
            self.side_canvas.yview_moveto(0)
            return

        ordered = sorted(self.sessions, key=lambda s: -s.get("created_at", 0))
        for s in ordered:
            self._make_item(s)
        self._bind_side_wheel(self.side_inner)
        self.side_canvas.yview_moveto(0)

    def _make_item(self, s):
        selected = (s["id"] == self.current)
        bg = C_ACCENT_SOFT if selected else C_CARD
        item = tk.Frame(self.side_inner, bg=bg, cursor="hand2")
        item.pack(fill="x", padx=8, pady=2)

        av = tk.Canvas(item, width=30, height=30, bg=bg, highlightthickness=0, bd=0)
        av.pack(side="left", padx=(6, 8), pady=8)
        color = avatar_color(s.get("name", ""))
        av.create_oval(1, 1, 29, 29, fill=color, outline="")
        av.create_text(15, 15, text=(s.get("name", "")[:1] or "角"), fill="#FFFFFF",
                       font=(FONT_FAMILY, 11, "bold"))

        txt = tk.Frame(item, bg=bg)
        txt.pack(side="left", fill="x", expand=True, pady=8)
        name_lbl = tk.Label(txt, text=s.get("name", "未命名"), bg=bg,
                            fg=C_ACCENT if selected else C_TEXT,
                            font=font(10, bold=selected), anchor="w")
        name_lbl.pack(fill="x", anchor="w")
        if s.get("type") == "group":
            sub = "群聊 · %d 位角色" % len(s.get("member_ids", []))
        else:
            sub = "私聊角色"
        sub_lbl = tk.Label(txt, text=sub, bg=bg, fg=C_TEXT_SUB, font=font(8), anchor="w")
        sub_lbl.pack(fill="x", anchor="w")

        def on_enter(_e, it=item):
            if s["id"] != self.current:
                self._paint_item(it, "#F4F6FB", C_TEXT)

        def on_leave(_e, it=item):
            if s["id"] != self.current:
                self._paint_item(it, C_CARD, None)
            else:
                self._paint_item(it, C_ACCENT_SOFT, C_ACCENT)

        item.bind("<Enter>", on_enter)
        item.bind("<Leave>", on_leave)
        for w in (item, av, txt, name_lbl, sub_lbl):
            w.bind("<Button-1>", lambda e, sid=s["id"]: self.open_session(sid))
        self._bind_side_wheel(item)

    def _paint_item(self, item, bg, name_fg):
        for w in item.winfo_children():
            try:
                w.configure(bg=bg)
            except Exception:
                pass
        for w in item.winfo_children():
            if isinstance(w, tk.Frame) and w.winfo_children():
                for c in w.winfo_children():
                    try:
                        c.configure(bg=bg)
                    except Exception:
                        pass
                if name_fg:
                    w.winfo_children()[0].configure(fg=name_fg)

    # ================= 会话 =================
    def _update_header(self):
        sid = self.current
        if not sid:
            self.lbl_title.configure(text="戏 语")
            self.lbl_sub.configure(text="选择一个角色开始对话，或点击上方「＋ 创建角色」")
            return
        s = self._session(sid)
        if not s:
            return
        self.lbl_title.configure(text=s.get("name", "会话"))
        names = []
        for cid in s.get("member_ids", []):
            c = self._char(cid)
            if c:
                names.append(c.get("name", ""))
        if s.get("type") == "group":
            self.lbl_sub.configure(text="群聊 · " + "、".join(names))
        else:
            self.lbl_sub.configure(text="与 %s 的对话" % (names[0] if names else s.get("name", "")))

    def _restore_last(self):
        last = self.cfg.get("last_session")
        if last and self._session(last):
            self.open_session(last)
            return
        if self.sessions:
            self.open_session(sorted(self.sessions, key=lambda s: -s.get("created_at", 0))[0]["id"])

    def open_session(self, sid):
        s = self._session(sid)
        if not s:
            return
        self.current = sid
        if sid not in self.loaded:
            self.loaded[sid] = storage.load_messages(sid)
        char_map = {c["id"]: c for c in self.chars}
        hint = "群聊开始后，每位角色会依次发言" if s.get("type") == "group" else None
        self.chat_view.set_conversation(s, self.loaded[sid], char_map, empty_hint=hint)
        st = self.rounds.get(sid)
        if st:
            self.chat_view.set_thinking(st.get("chan") or "角色")
        self._update_header()
        self._refresh_sidebar()
        self._sync_input()
        self.cfg["last_session"] = sid
        try:
            storage.save_config(self.cfg)
        except Exception:
            pass

    def _sync_input(self):
        busy = self.current in self.rounds
        self.btn_send.set_enabled(bool(self.current) and not busy)
        self.lbl_state.configure(text="正在生成回复…" if busy else "")
        self.lbl_input_tip.configure(text="")

    # ================= 创建 / 编辑 / 删除 =================
    def _create_character(self):
        dlg = CharacterDialog(self.root, self.chars)
        self.root.wait_window(dlg)
        data = dlg.result
        if not data:
            return
        if data.get("kind") == "group":
            self._do_create_group(data)
            return

        ch = storage.new_character(data["name"], data["greeting"], data["prompt"],
                                   data.get("world", ""), data.get("advanced", False))
        self.chars.append(ch)
        storage.save_characters(self.chars)
        s = storage.new_single_session(ch)
        self.sessions.append(s)
        storage.save_sessions(self.sessions)
        msgs = [storage.make_message("character", ch["greeting"], ch["id"], ch["name"])]
        storage.save_messages(s["id"], msgs)
        self.loaded[s["id"]] = msgs
        self._refresh_sidebar()
        self.open_session(s["id"])
        self.lbl_input_tip.configure(text="已创建「%s」" % ch["name"])

    def _create_group(self):
        if len(self.chars) < 2:
            messagebox.showinfo("提示", "群聊需要至少两个已创建的角色。请先创建角色。",
                                parent=self.root)
            return
        dlg = CharacterDialog(self.root, self.chars, group_mode=True)
        self.root.wait_window(dlg)
        if dlg.result and dlg.result.get("kind") == "group":
            self._do_create_group(dlg.result)

    def _do_create_group(self, data):
        s = storage.new_group_session(data["name"], data["member_ids"])
        s["scene"] = data.get("scene", "")
        self.sessions.append(s)
        storage.save_sessions(self.sessions)
        msgs = []
        if s["scene"]:
            msgs.append({"role": "notice", "content": "场景 · " + s["scene"],
                         "speaker_id": "", "speaker_name": "", "ts": 0})
        for cid in s["member_ids"]:
            c = self._char(cid)
            if c and c.get("greeting"):
                msgs.append(storage.make_message("character", c["greeting"], c["id"], c["name"]))
        storage.save_messages(s["id"], msgs)
        self.loaded[s["id"]] = msgs
        self._refresh_sidebar()
        self.open_session(s["id"])

    def _edit_current(self):
        sid = self.current
        if not sid:
            return
        s = self._session(sid)
        if not s:
            return
        if s.get("type") == "group":
            messagebox.showinfo("提示", "群聊房间暂不支持直接编辑，可删除后在「新建群聊」里重建。",
                                parent=self.root)
            return
        ch = self._char(s.get("single_char_id"))
        if not ch:
            return
        dlg = CharacterDialog(self.root, self.chars, edit=ch)
        self.root.wait_window(dlg)
        data = dlg.result
        if not data:
            return
        ch.update({
            "name": data["name"],
            "greeting": data["greeting"],
            "prompt": data["prompt"],
            "advanced": data.get("advanced", False),
            "world": data.get("world", ""),
        })
        s["name"] = ch["name"]
        storage.save_characters(self.chars)
        storage.save_sessions(self.sessions)
        msgs = self.loaded.get(sid, [])
        if len(msgs) == 1 and msgs[0].get("role") == "character":
            msgs[0]["content"] = ch["greeting"]
            msgs[0]["speaker_name"] = ch["name"]
            storage.save_messages(sid, msgs)
        char_map = {c["id"]: c for c in self.chars}
        self.chat_view.set_conversation(s, msgs, char_map)
        self._update_header()
        self._refresh_sidebar()

    def _delete_current(self):
        sid = self.current
        if not sid:
            return
        s = self._session(sid)
        if not s:
            return
        if s.get("type") == "group":
            if not messagebox.askyesno("删除群聊", "确定删除群聊「%s」及其聊天记录吗？"
                                       % s.get("name", ""), parent=self.root):
                return
            self.sessions = [x for x in self.sessions if x["id"] != sid]
            storage.delete_chat(sid)
            memory.delete(sid)
            self.loaded.pop(sid, None)
        else:
            ch = self._char(s.get("single_char_id"))
            name = ch.get("name", "") if ch else s.get("name", "")
            if not messagebox.askyesno("删除角色",
                                       "确定删除角色「%s」吗？\n它的人设资料和私聊记录都会一起删除。"
                                       % name, parent=self.root):
                return
            if ch:
                self.chars = [c for c in self.chars if c["id"] != ch["id"]]
                storage.save_characters(self.chars)
            for g in list(self.sessions):
                if g.get("type") == "group" and ch and ch["id"] in g.get("member_ids", []):
                    g["member_ids"] = [m for m in g["member_ids"] if m != ch["id"]]
                    if len(g["member_ids"]) < 2:
                        self.sessions = [x for x in self.sessions if x["id"] != g["id"]]
                        storage.delete_chat(g["id"])
                        memory.delete(g["id"])
                        self.loaded.pop(g["id"], None)
                        self.rounds.pop(g["id"], None)
            self.sessions = [x for x in self.sessions if x["id"] != sid]
            storage.delete_chat(sid)
            memory.delete(sid)
            self.loaded.pop(sid, None)

        storage.save_sessions(self.sessions)
        self.rounds.pop(sid, None)
        self.current = None
        self._refresh_sidebar()
        self.chat_view.set_conversation(None, [], {})
        self._update_header()
        self._sync_input()
        if self.sessions:
            self.open_session(sorted(self.sessions, key=lambda s: -s.get("created_at", 0))[0]["id"])

    # ================= 设置 =================
    def _refresh_model_label(self):
        base = (self.cfg.get("base_url") or "").split("//")[-1].split("/")[0]
        self.lbl_model.configure(text="%s · %s" % (self.cfg.get("model", "未配置"), base or "未配置"))

    def _open_settings(self):
        try:
            self.root.grab_release()
        except Exception:
            pass
        self._dir_before_settings = paths.DATA_DIR
        SettingsWindow(self.root, self.cfg, self.api_key, first_run=False,
                       on_saved=self._on_settings_saved)

    def _on_settings_saved(self, cfg):
        old_dir = getattr(self, "_dir_before_settings", paths.DATA_DIR)
        self.cfg = cfg
        self.api_key = storage.load_api_key()
        self._refresh_model_label()
        if old_dir != paths.DATA_DIR:
            self._reload_all()
            self.lbl_input_tip.configure(text="数据目录已切换")
        else:
            self.lbl_input_tip.configure(text="设置已保存")

    def _reload_all(self):
        """数据目录变化后重新读取全部数据并刷新界面。"""
        self.cfg = storage.load_config()
        self.api_key = storage.load_api_key()
        self.chars = storage.load_characters()
        self.sessions = storage.load_sessions()
        self.loaded = {}
        self.memory_cache = {}
        self.marks = {}
        self.rounds = {}
        self.current = None
        self._sanitize()
        self._refresh_sidebar()
        self._refresh_model_label()
        self._update_header()
        self._restore_last()

    def _first_run_check(self):
        if self.cfg.get("onboarded") and self.api_key:
            return
        self._dir_before_settings = paths.DATA_DIR
        SettingsWindow(self.root, self.cfg, self.api_key, first_run=True,
                       on_saved=self._on_settings_saved)

    # ================= 发送与回复 =================
    def _send(self):
        sid = self.current
        if not sid:
            self.lbl_input_tip.configure(text="请先在左侧选择或创建一个角色")
            return
        if sid in self.rounds:
            return
        if not self.api_key:
            self._open_settings()
            return
        text, is_empty = self._take_input()
        if is_empty or not text:
            return
        s = self._session(sid)
        targets = [self._char(s.get("single_char_id"))] if s.get("type") == "single" \
            else [self._char(cid) for cid in s.get("member_ids", [])]
        targets = [c for c in targets if c]
        if not targets:
            self.lbl_input_tip.configure(text="这个会话没有可用角色")
            return

        msg = storage.make_message("user", text)
        self._add_msg(sid, msg)
        self.txt_input.delete("1.0", "end")
        self._placeholder_on = False
        self.txt_input.configure(fg=C_TEXT)
        self._gen += 1
        self.rounds[sid] = {"token": self._gen, "pending": targets, "chan": ""}
        self._sync_input()
        self._next_reply(sid)

    def _build_ctx(self, sid, ch):
        s = self._session(sid)
        history = list(self.loaded.get(sid, []))
        user_text = ""
        if s.get("type") == "single":
            if history and history[-1].get("role") == "user":
                user_text = history[-1].get("content", "")
                history = history[:-1]
        mem = self._get_memory(sid) if self.cfg.get("memory_enabled", True) else ""
        return engine.build_messages(s, ch, history, user_text, self.cfg, self.chars,
                                     memory_text=mem)

    # ---------------- 长期记忆 ----------------
    def _get_memory(self, sid):
        if sid not in self.memory_cache:
            self.memory_cache[sid] = memory.load(sid)
        return self.memory_cache[sid]

    def _save_memory(self, sid, text):
        self.memory_cache[sid] = text
        try:
            memory.save(sid, text)
        except Exception as e:
            messagebox.showerror("保存失败", str(e), parent=self.root)
            return
        self.marks[sid] = len(self.loaded.get(sid, []))

    def _role_names(self, sid):
        s = self._session(sid)
        names = []
        if not s:
            return names
        for cid in s.get("member_ids", []) or [s.get("single_char_id")]:
            c = self._char(cid)
            if c:
                names.append(c.get("name", ""))
        return names

    def _maybe_summarize(self, sid):
        if not self.cfg.get("memory_enabled", True):
            return
        if sid in self._summarizing:
            return
        msgs = self.loaded.get(sid, [])
        every = int(self.cfg.get("memory_every", 12) or 12)
        mark = self.marks.get(sid)
        if mark is None:
            mark = max(0, len(msgs) - 1)
            self.marks[sid] = mark
        if len(msgs) - mark < every:
            return
        self._summarizing.add(sid)
        old = self._get_memory(sid)
        snapshot = list(msgs)
        names = self._role_names(sid)
        upto = len(snapshot)

        def work():
            try:
                text = memory.summarize(self.cfg.get("base_url"), self.api_key,
                                        self.cfg.get("model"), old, snapshot, names)
            except Exception as e:
                self.q.put(("mem", sid, "", upto, str(e)))
                return
            self.q.put(("mem", sid, text, upto, ""))

        threading.Thread(target=work, daemon=True).start()

    def _handle_memory(self, ev):
        _, sid, text, upto, err = ev
        self._summarizing.discard(sid)
        self.marks[sid] = upto
        if err or not text:
            return
        self.memory_cache[sid] = text
        try:
            memory.save(sid, text)
        except Exception:
            return
        if sid == self.current:
            self.lbl_input_tip.configure(text="长期记忆已更新")

    def _open_memory(self):
        sid = self.current
        if not sid:
            messagebox.showinfo("提示", "请先选择一个会话。", parent=self.root)
            return
        s = self._session(sid)
        MemoryWindow(self.root, s.get("name", ""), self._get_memory(sid),
                     on_save=lambda t: self._save_memory(sid, t),
                     on_regen=lambda cb: self._regen_memory(sid, cb))

    def _regen_memory(self, sid, callback):
        s = self._session(sid)
        msgs = list(self.loaded.get(sid, []))
        old = self._get_memory(sid)
        names = self._role_names(sid)

        def work():
            try:
                text = memory.summarize(self.cfg.get("base_url"), self.api_key,
                                        self.cfg.get("model"), old, msgs, names)
                err = ""
            except Exception as e:
                text, err = "", str(e)
            self.root.after(0, lambda: callback(text, err))

        threading.Thread(target=work, daemon=True).start()

    def _next_reply(self, sid):
        st = self.rounds.get(sid)
        if not st:
            return
        if not st["pending"]:
            self.rounds.pop(sid, None)
            if sid == self.current:
                self.chat_view.clear_thinking()
            self._sync_input()
            return
        ch = st["pending"].pop(0)
        st["chan"] = ch["name"]
        msgs = self._build_ctx(sid, ch)
        if sid == self.current:
            self.chat_view.set_thinking(ch["name"])
        threading.Thread(target=self._worker,
                         args=(sid, st["token"], ch["id"], ch["name"], msgs),
                         daemon=True).start()

    def _worker(self, sid, token, cid, cname, msgs):
        try:
            reply = llm.chat_completion(
                self.cfg.get("base_url"), self.api_key, self.cfg.get("model"),
                msgs, self.cfg.get("temperature", 0.8),
                self.cfg.get("max_tokens", 800))
        except Exception as e:
            self.q.put(("err", sid, token, cid, cname, str(e)))
            return
        self.q.put(("ok", sid, token, cid, cname, reply))

    def _poll(self):
        try:
            while True:
                ev = self.q.get_nowait()
                if ev and ev[0] == "mem":
                    self._handle_memory(ev)
                else:
                    self._handle(ev)
        except queue.Empty:
            pass
        self.root.after(60, self._poll)

    def _handle(self, ev):
        kind, sid, token, cid, cname, payload = ev
        st = self.rounds.get(sid)
        if not st or st["token"] != token:
            return
        if kind == "err":
            self._add_msg(sid, {"role": "error", "content": "回复失败：" + payload,
                                "speaker_id": "", "speaker_name": "", "ts": 0})
            self.rounds.pop(sid, None)
            if sid == self.current:
                self.chat_view.clear_thinking()
            self._sync_input()
            return
        ch = self._char(cid)
        msg = storage.make_message("character", payload, cid,
                                   cname or (ch or {}).get("name", "角色"))
        self._add_msg(sid, msg)
        self._maybe_summarize(sid)
        self._next_reply(sid)

    def _add_msg(self, sid, msg):
        msgs = self.loaded.setdefault(sid, [])
        msgs.append(msg)
        try:
            storage.save_messages(sid, msgs)
        except Exception:
            pass
        if sid == self.current:
            self.chat_view.append_message(msg)

    # ================= 关闭 =================
    def _on_close(self):
        try:
            self.cfg["last_session"] = self.current or ""
            storage.save_config(self.cfg)
        except Exception:
            pass
        self.root.destroy()


def _dpi_aware():
    if not hasattr(ctypes, "windll"):
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _setup_style(root):
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except Exception:
        pass
    st.configure("TNotebook", background=C_CARD, borderwidth=0, tabmargins=[0, 0, 0, 0])
    st.configure("TNotebook.Tab", padding=(14, 8), font=font(10),
                 background="#EDEFF4", foreground=C_TEXT_SUB, borderwidth=0)
    st.map("TNotebook.Tab", background=[("selected", C_CARD)],
           foreground=[("selected", C_ACCENT)])
    st.configure("Vertical.TScrollbar", background="#DCE0E9", troughcolor="#F4F5F9",
                 bordercolor="#F4F5F9", arrowcolor="#8B93A3", relief="flat", arrowsize=12)
    st.map("Vertical.TScrollbar", background=[("active", "#C9CFDB")])


def main():
    _dpi_aware()
    paths.ensure_dirs()
    root = tk.Tk()
    root.withdraw()
    try:
        dpi = root.winfo_fpixels("1i") or 96.0
    except Exception:
        dpi = 96.0
    scale = max(1.0, dpi / 96.0)
    try:
        root.tk.call("tk", "scaling", dpi / 72.0)
    except Exception:
        pass
    root.title("戏语 · AI 角色扮演聊天")
    _setup_style(root)
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    w = int(min(1180 * scale, sw * 0.92))
    h = int(min(770 * scale, sh * 0.88))
    root.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, max(0, (sh - h) // 2 - 20)))
    root.minsize(int(900 * scale), int(600 * scale))
    root.deiconify()
    App(root, scale)
    root.mainloop()


if __name__ == "__main__":
    main()
