"""设置窗口（含首次引导）与角色/群聊创建窗口。"""
import os
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from xiyu_core import llm, paths, storage, usage
from .theme import (C_BG, C_CARD, C_TEXT, C_TEXT_SUB, C_ACCENT, C_ACCENT_DARK,
                    C_LINE, C_DANGER, C_ACCENT_SOFT, FONT_FAMILY, font)


def _n(v):
    try:
        return "{:,}".format(int(v))
    except Exception:
        return str(v)


def flat_button(master, text, command=None, kind="primary", width=None, padx=16, pady=6):
    colors = {
        "primary": (C_ACCENT, "#FFFFFF", C_ACCENT_DARK),
        "soft": (C_ACCENT_SOFT, C_ACCENT, "#DCE5FF"),
        "plain": ("#F0F2F6", C_TEXT, "#E4E7EE"),
        "danger": ("#FCEDEC", "#B0413C", "#F8DBD9"),
    }
    bg, fg, active = colors.get(kind, colors["primary"])
    btn = tk.Button(master, text=text, command=command, bg=bg, fg=fg,
                    activebackground=active, activeforeground=fg,
                    relief="flat", bd=0, cursor="hand2", font=font(10, bold=True),
                    padx=padx, pady=pady, highlightthickness=0)
    if width:
        btn.configure(width=width)
    return btn


def _section(parent, title):
    return tk.Label(parent, text=title, bg=C_CARD, fg=C_TEXT,
                    font=font(11, bold=True), anchor="w")


def _hint(parent, text):
    return tk.Label(parent, text=text, bg=C_CARD, fg=C_TEXT_SUB,
                    font=font(9), anchor="w", justify="left", wraplength=520)


def _text_box(parent, height=5, wrap="word"):
    holder = tk.Frame(parent, bg=C_LINE, padx=1, pady=1)
    txt = tk.Text(holder, height=height, wrap=wrap, bd=0, relief="flat",
                  bg="#FCFCFE", fg=C_TEXT, insertbackground=C_TEXT,
                  font=font(10), padx=10, pady=8, undo=True)
    txt.pack(fill="both", expand=True)
    return holder, txt


class SettingsWindow(tk.Toplevel):
    def __init__(self, master, config, api_key, first_run=False, on_saved=None):
        super().__init__(master)
        self.cfg = dict(config)
        self.first_run = first_run
        self.on_saved = on_saved
        self.result = None
        self.new_data_dir = None
        self._migrate_flag = False

        self.title("开始使用戏语" if first_run else "设置 · F2")
        self.configure(bg=C_CARD)
        self.resizable(False, False)
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._build(api_key)
        self._center()
        self.grab_set()
        self.v_preset.set(self.cfg.get("preset", "DeepSeek"))
        self._apply_preset(silent=True)
        self._update_token_label()
        if self.v_auto_balance.get():
            self.after(300, self._refresh_balance)
        self.focus_force()

    # ---------- 余额与用量 ----------
    def _update_token_label(self):
        try:
            s = usage.summary()
            t, tot = s["today"], s["total"]
            self.lbl_tokens.configure(text=(
                "今日：%s tokens（输入 %s / 输出 %s，%d 次调用）\n"
                "累计：%s tokens（输入 %s / 输出 %s，%d 次调用）"
                % (_n(t["prompt"] + t["completion"]), _n(t["prompt"]), _n(t["completion"]), t["calls"],
                   _n(tot["prompt"] + tot["completion"]), _n(tot["prompt"]),
                   _n(tot["completion"]), tot["calls"])))
        except Exception as e:
            self.lbl_tokens.configure(text="用量读取失败：%s" % e)

    def _refresh_balance(self):
        base = self.v_base.get().strip()
        key = self.v_key.get().strip()
        self._update_token_label()
        if not base or not key:
            self.lbl_balance.configure(text="请先填写 Base URL 和 API Key", fg=C_DANGER)
            return
        self.lbl_balance.configure(text="正在查询余额…", fg=C_TEXT_SUB)
        self.lbl_balance_state.configure(text="")

        def work():
            try:
                info, err = llm.query_balance(base, key), ""
            except Exception as e:
                info, err = None, str(e)
            self.after(0, lambda: self._balance_done(info, err))

        threading.Thread(target=work, daemon=True).start()

    def _balance_done(self, info, err):
        try:
            if err:
                self.lbl_balance.configure(text=err, fg=C_DANGER)
                return
            sym = {"CNY": "¥", "USD": "$", "EUR": "€"}
            parts = []
            for i in info.get("infos", []):
                cur = i.get("currency", "")
                s = sym.get(cur, (cur + " ") if cur else "")
                parts.append("%s%s（充值 %s / 赠送 %s）" % (
                    s, i.get("total_balance", "0"),
                    i.get("topped_up_balance", "0"), i.get("granted_balance", "0")))
            state = "可用" if info.get("is_available") else "不可用（余额可能不足）"
            body = "　".join(parts) if parts else "接口未返回余额信息"
            self.lbl_balance.configure(text="%s｜账户状态：%s" % (body, state), fg=C_TEXT)
            self.lbl_balance_state.configure(text="更新于 " + time.strftime("%H:%M:%S"))
            self._update_token_label()
        except Exception:
            pass

    # ---------- 界面 ----------
    def _build(self, api_key):
        pad = 22
        head = tk.Frame(self, bg=C_CARD)
        head.pack(fill="x", padx=pad, pady=(18, 0))
        tk.Label(head, text="欢迎使用 戏 语" if self.first_run else "设置",
                 bg=C_CARD, fg=C_TEXT, font=font(16, bold=True), anchor="w").pack(anchor="w")
        tip = ("先填好 API Key 和接口，就能开始角色扮演。" if self.first_run else
               "修改后点击保存生效，API Key 只保存在本机。")
        tk.Label(head, text=tip, bg=C_CARD, fg=C_TEXT_SUB, font=font(10),
                 anchor="w", justify="left", wraplength=520).pack(anchor="w", pady=(4, 0))

        nb = self.nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=pad, pady=(14, 0))

        # --- 接口页 ---
        p1 = tk.Frame(nb, bg=C_CARD, padx=4, pady=12)
        nb.add(p1, text="  接口连接  ")

        row = tk.Frame(p1, bg=C_CARD)
        row.pack(fill="x", pady=4)
        tk.Label(row, text="接口预设", bg=C_CARD, fg=C_TEXT, font=font(10),
                 width=9, anchor="w").pack(side="left")
        self.v_preset = tk.StringVar()
        self.cb_preset = ttk.Combobox(row, textvariable=self.v_preset,
                                      values=list(storage.PRESETS.keys()),
                                      state="readonly", width=22, font=font(10))
        self.cb_preset.pack(side="left")
        self.cb_preset.bind("<<ComboboxSelected>>", lambda e: self._apply_preset())

        self.v_base = tk.StringVar(value=self.cfg.get("base_url", ""))
        self.v_model = tk.StringVar(value=self.cfg.get("model", ""))
        self.v_key = tk.StringVar(value=api_key or "")

        for label, var, show in (("Base URL", self.v_base, None),
                                 ("模型名称", self.v_model, None),
                                 ("API Key", self.v_key, "•")):
            r = tk.Frame(p1, bg=C_CARD)
            r.pack(fill="x", pady=4)
            tk.Label(r, text=label, bg=C_CARD, fg=C_TEXT, font=font(10),
                     width=9, anchor="w").pack(side="left")
            ent = tk.Entry(r, textvariable=var, font=font(10), relief="flat",
                           bg="#F5F6FA", fg=C_TEXT, insertbackground=C_TEXT,
                           highlightthickness=1, highlightbackground=C_LINE,
                           highlightcolor=C_ACCENT)
            if show:
                ent.configure(show=show)
            ent.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 2))

        p1.pack_propagate(True)
        _hint(p1, "预设会自动填好地址与默认模型；也可选择「自定义」手动填写任意 OpenAI 兼容地址。"
                   "\nAPI Key 使用 Windows 本机加密（DPAPI）保存，不写进代码，也不随聊天记录外传。"
              ).pack(fill="x", pady=(10, 0))

        trow = tk.Frame(p1, bg=C_CARD)
        trow.pack(fill="x", pady=(12, 0))
        flat_button(trow, "测试连接", self._test, kind="plain", padx=12, pady=4).pack(side="left")
        self.lbl_test = tk.Label(trow, text="", bg=C_CARD, fg=C_TEXT_SUB, font=font(9))
        self.lbl_test.pack(side="left", padx=10)

        # --- 设定页 ---
        p2 = tk.Frame(nb, bg=C_CARD, padx=4, pady=12)
        nb.add(p2, text="  角色设定  ")
        _section(p2, "全局系统提示词").pack(fill="x")
        _hint(p2, "对所有角色生效的基础规则，例如语气、语言、禁则。").pack(fill="x", pady=(0, 6))
        h1, self.txt_global = _text_box(p2, height=5)
        h1.pack(fill="x")
        self.txt_global.insert("1.0", self.cfg.get("global_prompt", ""))

        _section(p2, "全局世界背景").pack(fill="x", pady=(14, 0))
        _hint(p2, "公共世界观 / 地点 / 规则。角色自己设置了世界背景时，优先用角色自己的。").pack(fill="x", pady=(0, 6))
        h2, self.txt_world = _text_box(p2, height=5)
        h2.pack(fill="x")
        self.txt_world.insert("1.0", self.cfg.get("global_world", ""))

        # --- 高级页 ---
        p3 = tk.Frame(nb, bg=C_CARD, padx=4, pady=12)
        nb.add(p3, text="  高级参数  ")

        self.v_temp = tk.DoubleVar(value=float(self.cfg.get("temperature", 0.8)))
        self.v_max = tk.IntVar(value=int(self.cfg.get("max_tokens", 800)))
        self.v_ctx = tk.IntVar(value=int(self.cfg.get("context_turns", 20)))

        def spin_row(label, var, frm, to, step, note):
            r = tk.Frame(p3, bg=C_CARD)
            r.pack(fill="x", pady=6)
            tk.Label(r, text=label, bg=C_CARD, fg=C_TEXT, font=font(10),
                     width=10, anchor="w").pack(side="left")
            sp = tk.Spinbox(r, from_=frm, to=to, increment=step, textvariable=var,
                            width=8, font=font(10), relief="flat", bg="#F5F6FA",
                            highlightthickness=1, highlightbackground=C_LINE,
                            buttonbackground="#EEF0F5")
            sp.pack(side="left")
            tk.Label(r, text=note, bg=C_CARD, fg=C_TEXT_SUB, font=font(9),
                     anchor="w").pack(side="left", padx=10)

        spin_row("温度", self.v_temp, 0.0, 2.0, 0.05, "越大越活泼，越小越稳定（建议 0.7–0.9）")
        spin_row("回复长度", self.v_max, 100, 4096, 50, "单条回复的最大 token 数")
        spin_row("上下文条数", self.v_ctx, 4, 100, 2, "每次携带的历史消息条数上限，越大越连贯也越贵")

        self.v_memory = tk.BooleanVar(value=bool(self.cfg.get("memory_enabled", True)))
        tk.Checkbutton(p3, text="启用长期记忆：自动把关键剧情写成 memory 文本，每次对话都带上",
                       variable=self.v_memory, bg=C_CARD, fg=C_TEXT,
                       activebackground=C_CARD, font=font(10), anchor="w",
                       selectcolor="#FFFFFF").pack(fill="x", pady=(10, 2))
        _hint(p3, "记忆文件存在 Data\\memory 下，可随时手动编辑或清空；"
                  "关掉后只带「上下文条数」范围内的原始对话。").pack(fill="x")

        tk.Frame(p3, bg=C_CARD, height=8).pack()
        _hint(p3, "聊天记录与角色资料均为本地 JSON 文件，可随时备份。"
                  "保存位置可在「数据目录」页更改。").pack(fill="x")

        # --- 用量页 ---
        p4 = tk.Frame(nb, bg=C_CARD, padx=4, pady=12)
        nb.add(p4, text="  用量余额  ")

        tk.Label(p4, text="账户余额", bg=C_CARD, fg=C_TEXT, font=font(10, bold=True),
                 anchor="w").pack(fill="x")
        self.lbl_balance = tk.Label(p4, text="点下方「刷新余额」查询（仅 DeepSeek 支持）",
                                    bg=C_CARD, fg=C_TEXT_SUB, font=font(10), anchor="w",
                                    justify="left", wraplength=520)
        self.lbl_balance.pack(fill="x", pady=(4, 0))
        self.lbl_balance_state = tk.Label(p4, text="", bg=C_CARD, fg="#AEB5C2",
                                          font=font(8), anchor="w")
        self.lbl_balance_state.pack(fill="x", pady=(2, 0))

        tk.Label(p4, text="Token 用量（本机统计）", bg=C_CARD, fg=C_TEXT, font=font(10, bold=True),
                 anchor="w").pack(fill="x", pady=(16, 0))
        self.lbl_tokens = tk.Label(p4, text="", bg=C_CARD, fg=C_TEXT_SUB, font=font(9),
                                   anchor="w", justify="left", wraplength=520)
        self.lbl_tokens.pack(fill="x", pady=(4, 0))

        brow = tk.Frame(p4, bg=C_CARD)
        brow.pack(fill="x", pady=(14, 0))
        flat_button(brow, "刷新余额", self._refresh_balance, kind="plain",
                    padx=12, pady=4).pack(side="left")
        self.v_auto_balance = tk.BooleanVar(value=bool(self.cfg.get("balance_auto_refresh", True)))
        tk.Checkbutton(brow, text="打开设置时自动刷新", variable=self.v_auto_balance,
                       bg=C_CARD, fg=C_TEXT, activebackground=C_CARD, font=font(9),
                       selectcolor="#FFFFFF").pack(side="left", padx=8)

        _hint(p4, "余额来自 DeepSeek 的 /user/balance 接口，只读取、不产生费用；"
                  "token 数是本机把每次回复返回的 usage 累加得到，换电脑不会同步。"
              ).pack(fill="x", pady=(10, 0))

        # --- 数据目录页 ---
        p5 = tk.Frame(nb, bg=C_CARD, padx=4, pady=12)
        nb.add(p5, text="  数据目录  ")

        tk.Label(p5, text="当前数据目录", bg=C_CARD, fg=C_TEXT, font=font(10, bold=True),
                 anchor="w").pack(fill="x")
        self.lbl_data_dir = tk.Label(p5, text=paths.DATA_DIR, bg=C_CARD, fg=C_TEXT_SUB,
                                     font=font(9), anchor="w", justify="left",
                                     wraplength=520)
        self.lbl_data_dir.pack(fill="x", pady=(4, 0))
        self.lbl_data_note = tk.Label(p5, text="", bg=C_CARD, fg=C_ACCENT, font=font(9),
                                      anchor="w", justify="left", wraplength=520)
        self.lbl_data_note.pack(fill="x", pady=(4, 0))

        drow = tk.Frame(p5, bg=C_CARD)
        drow.pack(fill="x", pady=(12, 0))
        flat_button(drow, "更改目录…", self._change_data_dir, kind="plain",
                    padx=12, pady=4).pack(side="left")
        flat_button(drow, "打开目录", self._open_data_dir, kind="soft",
                    padx=12, pady=4).pack(side="left", padx=8)

        _hint(p5, "角色、聊天记录、长期记忆和加密保存的 API Key 都在这个目录里，"
                  "备份或换电脑时复制整个目录即可。\n"
                  "换到新目录时可以顺手把现有数据复制过去；API Key 用系统加密绑定本机，"
                  "换机器后需要在「接口连接」页重新填写。"
              ).pack(fill="x", pady=(12, 0))

        # --- 底部 ---
        foot = tk.Frame(self, bg=C_CARD)
        foot.pack(fill="x", padx=pad, pady=(14, 18))
        if not self.first_run:
            flat_button(foot, "取消", self._close, kind="plain").pack(side="right", padx=(8, 0))
        flat_button(foot, "开始使用" if self.first_run else "保存",
                    self._save, kind="primary").pack(side="right")

    def _center(self):
        self.update_idletasks()
        w, h = 600, 620
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, (sh - h) // 3))

    # ---------- 逻辑 ----------
    def _apply_preset(self, silent=False):
        name = self.v_preset.get()
        preset = storage.PRESETS.get(name)
        if not preset:
            return
        if name == "自定义" and silent:
            return
        if preset["base_url"]:
            self.v_base.set(preset["base_url"])
        if preset["model"]:
            self.v_model.set(preset["model"])
        if name == "自定义" and not silent:
            self.v_base.set("")
            self.v_model.set("")

    def _test(self):
        base = self.v_base.get().strip()
        key = self.v_key.get().strip()
        model = self.v_model.get().strip()
        if not (base and key and model):
            messagebox.showwarning("提示", "请先填写 Base URL、模型名称和 API Key", parent=self)
            return
        self.lbl_test.configure(text="正在测试…", fg=C_TEXT_SUB)
        cfg = self.cfg

        def work():
            try:
                reply = llm.chat_completion(
                    base, key, model,
                    [{"role": "user", "content": "只回复两个字：可用"}],
                    temperature=0.3, max_tokens=16, timeout=30)
                msg, ok = "连接成功，模型回复：%s" % reply[:30], True
            except Exception as e:
                msg, ok = str(e)[:120], False
            self.after(0, lambda: self.lbl_test.configure(
                text=msg, fg="#2F7A4F" if ok else C_DANGER))

        threading.Thread(target=work, daemon=True).start()

    # ---------- 数据目录 ----------
    def _open_data_dir(self):
        target = self.new_data_dir or paths.DATA_DIR
        try:
            if os.path.isdir(target):
                os.startfile(target)
            else:
                messagebox.showinfo("提示", "目录还不存在：\n" + target, parent=self)
        except Exception as e:
            messagebox.showinfo("提示", "无法打开目录：%s" % e, parent=self)

    def _change_data_dir(self):
        start = paths.DATA_DIR if os.path.isdir(paths.DATA_DIR) else paths.ROOT_DIR
        chosen = filedialog.askdirectory(parent=self, initialdir=start,
                                         title="选择数据保存目录")
        if not chosen:
            return
        chosen = os.path.abspath(chosen)
        if chosen == paths.DATA_DIR:
            messagebox.showinfo("提示", "这就是当前的数据目录。", parent=self)
            return

        if paths.has_data(chosen):
            ok = messagebox.askyesno(
                "该目录已有数据",
                "这个目录里已经有一份戏语的数据。\n\n"
                "选「是」：改用该目录里现有的角色和聊天记录，"
                "窗口里的接口设置会保存到那里；\n"
                "选「否」：保持现在的目录不动。", parent=self)
            if not ok:
                return
            self.new_data_dir = chosen
            self._migrate_flag = False
            self.lbl_data_dir.configure(text="将切换到：\n" + chosen, fg=C_ACCENT)
            self.lbl_data_note.configure(text="点「保存」后生效：使用该目录已有的数据。")
            return

        try:
            others = os.listdir(chosen) if os.path.isdir(chosen) else []
        except Exception:
            others = []
        if others:
            ok = messagebox.askyesno(
                "目录不是空的",
                "这个目录里还有其它文件。戏语只会把自己的数据文件写进来，"
                "不会改动其它文件。\n\n继续使用这个目录吗？", parent=self)
            if not ok:
                return

        migrate = False
        if paths.has_data(paths.DATA_DIR):
            ans = messagebox.askyesnocancel(
                "迁移现有数据",
                "是否把现在的角色、聊天记录、长期记忆和密钥复制到新目录？\n\n"
                "「是」：复制过去，旧目录的数据保留；\n"
                "「否」：新目录从空白开始，旧数据仍留在原目录。", parent=self)
            if ans is None:
                return
            migrate = bool(ans)

        self.new_data_dir = chosen
        self._migrate_flag = migrate
        self.lbl_data_dir.configure(text="将切换到：\n" + chosen, fg=C_ACCENT)
        self.lbl_data_note.configure(
            text="点「保存」后生效：" + ("现有数据会复制到新目录。" if migrate
                                        else "新目录从空白开始。"))

    def _save(self):
        base = self.v_base.get().strip()
        model = self.v_model.get().strip()
        key = self.v_key.get().strip()
        if not base:
            messagebox.showwarning("提示", "接口地址（Base URL）不能为空", parent=self)
            return
        if not model:
            messagebox.showwarning("提示", "模型名称不能为空", parent=self)
            return
        if not key:
            messagebox.showwarning("提示", "API Key 不能为空", parent=self)
            return
        try:
            temp = round(float(self.v_temp.get()), 2)
            max_tokens = int(self.v_max.get())
            ctx = int(self.v_ctx.get())
        except Exception:
            messagebox.showwarning("提示", "高级参数需要填写数字", parent=self)
            return

        cfg = dict(self.cfg)
        cfg.update({
            "preset": self.v_preset.get(),
            "base_url": base,
            "model": model,
            "global_prompt": self.txt_global.get("1.0", "end").strip(),
            "global_world": self.txt_world.get("1.0", "end").strip(),
            "temperature": max(0.0, min(2.0, temp)),
            "max_tokens": max(60, min(4096, max_tokens)),
            "context_turns": max(2, min(100, ctx)),
            "memory_enabled": bool(self.v_memory.get()),
            "balance_auto_refresh": bool(self.v_auto_balance.get()),
            "onboarded": True,
        })
        # 数据目录有改动时先切换（必要时先把现有数据复制过去），再往新目录写配置
        new_dir = self.new_data_dir
        if new_dir and os.path.abspath(new_dir) != paths.DATA_DIR:
            try:
                if self._migrate_flag and not paths.has_data(new_dir):
                    paths.migrate_data(paths.DATA_DIR, new_dir)
                paths.set_data_dir(new_dir)
                self.new_data_dir = None
            except Exception as e:
                messagebox.showerror("切换数据目录失败", str(e), parent=self)
                return
        try:
            storage.save_api_key(key)
            storage.save_config(cfg)
        except Exception as e:
            messagebox.showerror("保存失败", str(e), parent=self)
            return

        self.result = cfg
        if self.on_saved:
            self.on_saved(cfg)
        self._close(force=True)

    def _close(self, force=False):
        if self.first_run and not force:
            if messagebox.askyesno("退出", "还没有完成初始设置，现在退出戏语吗？", parent=self):
                self.master.destroy()
            return
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


def _wheel_bind(w, canvas):
    """把滚轮事件绑到滚动容器上（输入框保留自身滚动）。"""
    if isinstance(w, (tk.Text, tk.Listbox)):
        return

    def on_wheel(e):
        canvas.yview_scroll(int(-e.delta / 120) * 3, "units")

    w.bind("<MouseWheel>", on_wheel)
    for c in w.winfo_children():
        _wheel_bind(c, canvas)


class MemoryWindow(tk.Toplevel):
    """查看 / 编辑某个会话的长期记忆文本。"""

    def __init__(self, master, title, text, on_save, on_regen):
        super().__init__(master)
        self.on_save = on_save
        self.on_regen = on_regen
        self.title("长期记忆 · %s" % title)
        self.configure(bg=C_CARD)
        self.transient(master)
        self.grab_set()
        self.resizable(True, True)

        pad = 20
        tk.Label(self, text="长期记忆 · %s" % title, bg=C_CARD, fg=C_TEXT,
                 font=font(14, bold=True), anchor="w").pack(fill="x", padx=pad, pady=(16, 2))
        tk.Label(self, text="这份文本会在每次请求时一起发给模型，越准确越省 token。\n"
                            "可以手动编辑，也可以让 AI 按最近的对话重新整理。",
                 bg=C_CARD, fg=C_TEXT_SUB, font=font(9), anchor="w", justify="left"
                 ).pack(fill="x", padx=pad)

        holder = tk.Frame(self, bg=C_LINE, padx=1, pady=1)
        holder.pack(fill="both", expand=True, padx=pad, pady=(10, 0))
        self.txt = tk.Text(holder, wrap="word", bd=0, relief="flat", bg="#FCFCFE",
                           fg=C_TEXT, insertbackground=C_TEXT, font=font(10),
                           padx=12, pady=10, undo=True)
        sb = ttk.Scrollbar(holder, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.txt.pack(side="left", fill="both", expand=True)
        self.txt.insert("1.0", text or "")

        foot = tk.Frame(self, bg=C_CARD)
        foot.pack(fill="x", padx=pad, pady=14)
        flat_button(foot, "关闭", self.destroy, kind="plain").pack(side="right", padx=(8, 0))
        flat_button(foot, "保存", self._save, kind="primary").pack(side="right")
        self.btn_regen = flat_button(foot, "AI 重新整理", self._regen, kind="soft")
        self.btn_regen.pack(side="left")
        flat_button(foot, "清空", self._clear, kind="plain").pack(side="left", padx=(8, 0))

        self.update_idletasks()
        w, h = 620, 540
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, max(20, (sh - h) // 3)))
        self.focus_force()

    def _save(self):
        self.on_save(self.txt.get("1.0", "end").rstrip())
        messagebox.showinfo("已保存", "记忆已写入本地文件，下次回复起生效。", parent=self)

    def _clear(self):
        if messagebox.askyesno("清空记忆", "确定清空这个会话的长期记忆吗？", parent=self):
            self.txt.delete("1.0", "end")

    def _regen(self):
        self.btn_regen.configure(state="disabled", text="整理中…")
        self.on_regen(self._regen_done)

    def _regen_done(self, text, err):
        try:
            self.btn_regen.configure(state="normal", text="AI 重新整理")
        except Exception:
            return
        if err:
            messagebox.showerror("整理失败", err, parent=self)
            return
        if text:
            self.txt.delete("1.0", "end")
            self.txt.insert("1.0", text)
            self.on_save(self.txt.get("1.0", "end").rstrip())


class CharacterDialog(tk.Toplevel):
    """新建角色 / 编辑角色 / 新建群聊。"""

    def __init__(self, master, characters, edit=None, group_mode=False):
        super().__init__(master)
        self.characters = characters
        self.edit = edit
        self.result = None
        self.group_mode = bool(group_mode) or (edit is None and False)
        self.title("编辑角色" if edit else ("新建群聊" if group_mode else "创建角色"))
        self.configure(bg=C_CARD)
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self._build(edit, group_mode)
        self._center()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.focus_force()

    def _build(self, edit, group_mode):
        pad = 20
        head_text = ("编辑角色" if edit else ("新建群聊房间" if group_mode else "创建角色"))
        tk.Label(self, text=head_text, bg=C_CARD, fg=C_TEXT, font=font(15, bold=True),
                 anchor="w").pack(fill="x", padx=pad, pady=(18, 2))
        tk.Label(self, text="角色的话会被严格按人设回复；动作、神态用中文括号（）表达。"
                 if not group_mode else "把多个已创建的角色放进同一个房间，他们会依次各自发言。",
                 bg=C_CARD, fg=C_TEXT_SUB, font=font(9), anchor="w").pack(fill="x", padx=pad)

        holder = tk.Frame(self, bg=C_CARD)
        holder.pack(fill="both", expand=True, padx=pad, pady=(12, 0))
        cvs = tk.Canvas(holder, bg=C_CARD, highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(holder, orient="vertical", command=cvs.yview)
        cvs.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        cvs.pack(side="left", fill="both", expand=True)
        body = tk.Frame(cvs, bg=C_CARD)
        win = cvs.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda e: cvs.configure(scrollregion=cvs.bbox("all")))
        cvs.bind("<Configure>", lambda e: cvs.itemconfigure(win, width=max(200, e.width - 14)))
        self._scroll_canvas = cvs

        # 角色区
        self.f_role = tk.Frame(body, bg=C_CARD)
        self.f_role.pack(fill="both", expand=True)

        self.v_name = tk.StringVar(value=(edit or {}).get("name", ""))
        r1 = tk.Frame(self.f_role, bg=C_CARD)
        r1.pack(fill="x", pady=(0, 8))
        tk.Label(r1, text="角色名字", bg=C_CARD, fg=C_TEXT, font=font(10),
                 width=8, anchor="w").pack(side="left")
        tk.Entry(r1, textvariable=self.v_name, font=font(10), relief="flat", bg="#F5F6FA",
                 highlightthickness=1, highlightbackground=C_LINE,
                 highlightcolor=C_ACCENT).pack(side="left", fill="x", expand=True, ipady=5)

        tk.Label(self.f_role, text="开场白（进入对话时角色说的第一段话）", bg=C_CARD,
                 fg=C_TEXT, font=font(10), anchor="w").pack(fill="x")
        h1, self.txt_greet = _text_box(self.f_role, height=3)
        h1.pack(fill="x", pady=(4, 10))
        self.txt_greet.insert("1.0", (edit or {}).get("greeting", ""))

        tk.Label(self.f_role, text="角色提示词（人设 / 性格 / 说话风格 / 与用户的关系）", bg=C_CARD,
                 fg=C_TEXT, font=font(10), anchor="w").pack(fill="x")
        h2, self.txt_prompt = _text_box(self.f_role, height=8)
        h2.pack(fill="x", pady=(4, 10))
        self.txt_prompt.insert("1.0", (edit or {}).get("prompt", ""))

        self.v_adv = tk.BooleanVar(value=bool((edit or {}).get("advanced")))
        cb_adv = tk.Checkbutton(self.f_role, text="高级权限：为该角色单独设定世界背景",
                                variable=self.v_adv, command=self._toggle_adv,
                                bg=C_CARD, fg=C_TEXT, activebackground=C_CARD,
                                font=font(10), anchor="w", selectcolor="#FFFFFF")
        cb_adv.pack(fill="x")
        self.f_world = tk.Frame(self.f_role, bg=C_CARD)
        tk.Label(self.f_world, text="世界背景（世界观 / 地点 / 规则等公共设定）", bg=C_CARD,
                 fg=C_TEXT_SUB, font=font(9), anchor="w").pack(fill="x", pady=(2, 4))
        h3, self.txt_world = _text_box(self.f_world, height=5)
        h3.pack(fill="x")
        self.txt_world.insert("1.0", (edit or {}).get("world", ""))
        if self.v_adv.get():
            self.f_world.pack(fill="x")

        # 群聊区
        self.f_group = tk.Frame(body, bg=C_CARD)
        self.v_gname = tk.StringVar(value="")
        g1 = tk.Frame(self.f_group, bg=C_CARD)
        g1.pack(fill="x", pady=(0, 8))
        tk.Label(g1, text="房间名字", bg=C_CARD, fg=C_TEXT, font=font(10),
                 width=8, anchor="w").pack(side="left")
        tk.Entry(g1, textvariable=self.v_gname, font=font(10), relief="flat", bg="#F5F6FA",
                 highlightthickness=1, highlightbackground=C_LINE,
                 highlightcolor=C_ACCENT).pack(side="left", fill="x", expand=True, ipady=5)

        tk.Label(self.f_group, text="公共场景说明（可选，所有成员都会读到）", bg=C_CARD,
                 fg=C_TEXT, font=font(10), anchor="w").pack(fill="x")
        h4, self.txt_scene = _text_box(self.f_group, height=4)
        h4.pack(fill="x", pady=(4, 10))

        tk.Label(self.f_group, text="选择成员（按住 Ctrl 点选多个）", bg=C_CARD,
                 fg=C_TEXT, font=font(10), anchor="w").pack(fill="x")
        lw = tk.Frame(self.f_group, bg=C_LINE, padx=1, pady=1)
        lw.pack(fill="both", expand=True, pady=(4, 0))
        self.lb_members = tk.Listbox(lw, selectmode="extended", bd=0, relief="flat",
                                     bg="#FCFCFE", fg=C_TEXT, font=font(10),
                                     activestyle="none", highlightthickness=0,
                                     selectbackground=C_ACCENT_SOFT,
                                     selectforeground=C_TEXT)
        self.lb_members.pack(side="left", fill="both", expand=True, ipady=4)
        sb = ttk.Scrollbar(lw, orient="vertical", command=self.lb_members.yview)
        sb.pack(side="right", fill="y")
        self.lb_members.configure(yscrollcommand=sb.set)
        for c in self.characters:
            self.lb_members.insert("end", "  " + c.get("name", "未命名"))
        if not self.characters:
            tk.Label(self.f_group, text="还没有已创建的角色，请先创建至少两个角色。",
                     bg=C_CARD, fg=C_DANGER, font=font(9), anchor="w").pack(fill="x", pady=(6, 0))

        # 模式开关
        self.f_mode = tk.Frame(body, bg=C_CARD)
        self.f_mode.pack(fill="x", pady=(10, 0))
        self.v_groupmode = tk.BooleanVar(value=bool(group_mode))
        if edit is None:
            tk.Checkbutton(self.f_mode, text="创建群聊房间（把多个已有角色放进同一对话）",
                           variable=self.v_groupmode, command=self._toggle_mode,
                           bg=C_CARD, fg=C_ACCENT, activebackground=C_CARD,
                           font=font(10, bold=True), anchor="w",
                           selectcolor="#FFFFFF").pack(fill="x")

        foot = tk.Frame(self, bg=C_CARD)
        foot.pack(fill="x", padx=pad, pady=(12, 16))
        flat_button(foot, "取消", self._cancel, kind="plain").pack(side="right", padx=(8, 0))
        flat_button(foot, "保存", self._save, kind="primary").pack(side="right")

        self._toggle_mode()
        self._toggle_adv()
        _wheel_bind(body, cvs)

    def _center(self):
        self.update_idletasks()
        w, h = 620, 700
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        h = min(h, int(sh * 0.9))
        self.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, max(20, (sh - h) // 3)))

    def _toggle_adv(self):
        if self.v_adv.get():
            self.f_world.pack(fill="x", pady=(4, 0))
        else:
            self.f_world.pack_forget()

    def _toggle_mode(self):
        if getattr(self, "edit", None) is not None:
            self.f_group.pack_forget()
            self.f_mode.pack_forget()
            self.f_role.pack(fill="both", expand=True)
            return
        if self.v_groupmode.get():
            self.f_role.pack_forget()
            self.f_group.pack(fill="both", expand=True, before=self.f_mode)
        else:
            self.f_group.pack_forget()
            self.f_role.pack(fill="both", expand=True, before=self.f_mode)

    def _cancel(self):
        self.result = None
        self.destroy()

    def _save(self):
        if self.v_groupmode.get() and self.edit is None:
            name = self.v_gname.get().strip()
            idxs = list(self.lb_members.curselection())
            members = [self.characters[i]["id"] for i in idxs if i < len(self.characters)]
            if not name:
                messagebox.showwarning("提示", "请填写房间名字", parent=self)
                return
            if len(members) < 2:
                messagebox.showwarning("提示", "群聊至少需要选择两个角色", parent=self)
                return
            self.result = {
                "kind": "group",
                "name": name,
                "member_ids": members,
                "scene": self.txt_scene.get("1.0", "end").strip(),
            }
            self.destroy()
            return

        name = self.v_name.get().strip()
        prompt = self.txt_prompt.get("1.0", "end").strip()
        if not name:
            messagebox.showwarning("提示", "请填写角色名字", parent=self)
            return
        if not prompt:
            messagebox.showwarning("提示", "请填写角色提示词", parent=self)
            return
        greeting = self.txt_greet.get("1.0", "end").strip()
        if not greeting:
            greeting = "（%s 抬起头看向你，似乎等着你先开口。）" % name
        self.result = {
            "kind": "role",
            "name": name,
            "greeting": greeting,
            "prompt": prompt,
            "advanced": bool(self.v_adv.get()),
            "world": self.txt_world.get("1.0", "end").strip() if self.v_adv.get() else "",
        }
        self.destroy()
