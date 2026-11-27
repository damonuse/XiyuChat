"""戏语安装向导：选择安装位置与数据目录，创建快捷方式。"""
import json
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

APP_NAMES = {"zh": "戏语", "en": "XiyuChat"}
VERSION = "1.0.0"
DESKTOP_NAME = "戏语"
MENU_NAME = "戏语"
EXE_NAME = "Xiyu.exe"

BG = "#FFFFFF"
CARD = "#FFFFFF"
TEXT = "#1D2330"
SUB = "#6B7280"
ACCENT = "#3B6CF6"
ACCENT_DARK = "#2D55C8"
LINE = "#E4E7EE"

FONT = "Microsoft YaHei UI"


def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def default_install_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Programs", "XiyuChat")


def default_data_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "XiyuChat", "Data")


def location_file():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "XiyuChat", "location.json")


class Wizard(tk.Tk):
    def __init__(self, app_src=None):
        super().__init__()
        self.app_src = app_src or resource("app")
        self.title("戏语 · 安装向导")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.install_dir = tk.StringVar(value=default_install_dir())
        self.data_dir = tk.StringVar(value=default_data_dir())
        self.desktop_sc = tk.BooleanVar(value=True)
        self.menu_sc = tk.BooleanVar(value=True)
        self.run_after = tk.BooleanVar(value=True)
        self.page = 0
        self._center()
        try:
            icon = resource("icon.ico")
            if os.path.exists(icon):
                self.iconbitmap(icon)
        except Exception:
            pass
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill="both", expand=True, padx=34, pady=(26, 0))
        self.foot = tk.Frame(self, bg=BG)
        self.foot.pack(fill="x", padx=34, pady=(0, 24))
        self.back_btn = self._button(self.foot, "上一步", self._back, kind="plain", width=10)
        self.next_btn = self._button(self.foot, "下一步", self._next, kind="primary", width=10)
        self.next_btn.pack(side="right")
        self.back_btn.pack(side="right", padx=(0, 10))
        self._render()

    # ---------- 基础 ----------
    def _center(self):
        w, h = 640, 480
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, (sh - h) // 3))

    def _button(self, master, text, command, kind="primary", width=None):
        bg = ACCENT if kind == "primary" else "#F0F2F6"
        fg = "#FFFFFF" if kind == "primary" else TEXT
        hover = ACCENT_DARK if kind == "primary" else "#E4E7EE"
        btn = tk.Button(master, text=text, command=command, bg=bg, fg=fg,
                        activebackground=hover, activeforeground=fg, relief="flat",
                        bd=0, cursor="hand2", font=(FONT, 10, "bold"),
                        padx=18, pady=7, highlightthickness=0)
        if width:
            btn.configure(width=width)
        return btn

    def _clear(self):
        for w in self.body.winfo_children():
            w.destroy()

    def _title(self, text, sub=None):
        tk.Label(self.body, text=text, bg=BG, fg=TEXT, font=(FONT, 16, "bold"),
                 anchor="w").pack(fill="x")
        if sub:
            tk.Label(self.body, text=sub, bg=BG, fg=SUB, font=(FONT, 10),
                     anchor="w", justify="left", wraplength=560).pack(fill="x", pady=(6, 0))

    def _path_row(self, var, caption):
        tk.Label(self.body, text=caption, bg=BG, fg=TEXT, font=(FONT, 10, "bold"),
                 anchor="w").pack(fill="x", pady=(18, 6))
        row = tk.Frame(self.body, bg=BG)
        row.pack(fill="x")
        entry = tk.Entry(row, textvariable=var, font=(FONT, 10), relief="flat",
                         bg="#F7F8FB", fg=TEXT, insertbackground=TEXT,
                         highlightthickness=1, highlightbackground=LINE,
                         highlightcolor=ACCENT)
        entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self._button(row, "浏览…", lambda: self._browse(var), kind="plain").pack(side="left")

    def _browse(self, var):
        cur = var.get()
        d = filedialog.askdirectory(parent=self, initialdir=cur if os.path.isdir(cur) else os.path.dirname(cur))
        if d:
            var.set(os.path.abspath(d))

    # ---------- 页面 ----------
    def _render(self):
        self._clear()
        pages = [self._page_welcome, self._page_install_dir, self._page_data_dir, self._page_options]
        pages[self.page]()
        self.back_btn.configure(state="normal" if self.page > 0 else "disabled")
        last = self.page == len(pages) - 1
        self.next_btn.configure(text="安装" if last else "下一步",
                                command=self._do_install if last else self._next)

    def _page_welcome(self):
        tk.Label(self.body, text="戏 语", bg=BG, fg=ACCENT, font=(FONT, 26, "bold"),
                 anchor="w").pack(fill="x", pady=(18, 0))
        tk.Label(self.body, text="AI 角色扮演聊天 · 版本 %s" % VERSION, bg=BG, fg=SUB,
                 font=(FONT, 10), anchor="w").pack(fill="x", pady=(2, 0))
        tk.Frame(self.body, bg=LINE, height=1).pack(fill="x", pady=(18, 16))
        tips = [
            "创建你自己的 AI 角色，单聊或拉进群聊演一场戏。",
            "支持 DeepSeek、OpenAI 兼容接口，API Key 用系统加密保存在本机。",
            "角色、聊天记录和长期记忆都在本地，可随时备份或更换目录。",
        ]
        for t in tips:
            tk.Label(self.body, text="·  " + t, bg=BG, fg=TEXT, font=(FONT, 10),
                     anchor="w", justify="left", wraplength=560).pack(fill="x", pady=(0, 8))
        tk.Label(self.body, text="点「下一步」选择安装位置。", bg=BG, fg=SUB,
                 font=(FONT, 9), anchor="w").pack(fill="x", pady=(14, 0))

    def _page_install_dir(self):
        self._title("选择安装位置", "程序文件会装到这里，大约占用 30 MB。卸载时删除该目录即可。")
        self._path_row(self.install_dir, "安装目录")

    def _page_data_dir(self):
        self._title("选择数据目录", "角色、聊天记录、长期记忆和加密的 API Key 都保存在这里。\n"
                                     "之后也可以在软件里按 F2 →「数据目录」随时更改，并带走现有数据。")
        self._path_row(self.data_dir, "数据目录")

    def _page_options(self):
        self._title("准备安装", "选择附加选项，然后开始安装。")
        box = tk.Frame(self.body, bg="#F7F8FB", highlightthickness=1,
                       highlightbackground=LINE)
        box.pack(fill="x", pady=(20, 0), ipady=10, ipadx=14)
        for var, text in ((self.desktop_sc, "创建桌面快捷方式"),
                          (self.menu_sc, "创建开始菜单快捷方式"),
                          (self.run_after, "安装完成后启动戏语")):
            tk.Checkbutton(box, text=text, variable=var, bg="#F7F8FB", fg=TEXT,
                           activebackground="#F7F8FB", font=(FONT, 10),
                           selectcolor="#FFFFFF", anchor="w").pack(fill="x", pady=3)
        self.lbl_status = tk.Label(self.body, text="", bg=BG, fg=SUB, font=(FONT, 9),
                                   anchor="w", justify="left", wraplength=570)
        self.lbl_status.pack(fill="x", pady=(14, 0))

    # ---------- 流程 ----------
    def _next(self):
        if self.page == 1 and not self.install_dir.get().strip():
            messagebox.showwarning("提示", "请填写安装目录", parent=self)
            return
        if self.page == 2 and not self.data_dir.get().strip():
            messagebox.showwarning("提示", "请填写数据目录", parent=self)
            return
        self.page += 1
        self._render()

    def _back(self):
        self.page = max(0, self.page - 1)
        self._render()

    def _do_install(self):
        target = os.path.abspath(self.install_dir.get().strip())
        data = os.path.abspath(self.data_dir.get().strip())
        if os.path.exists(os.path.join(target, EXE_NAME)):
            if not messagebox.askyesno("已存在", "该目录里已经有戏语，覆盖安装吗？\n\n"
                                                 "角色和聊天记录保存在数据目录里，不会被删除。",
                                       parent=self):
                return
        self.next_btn.configure(state="disabled", text="正在安装…")
        self.back_btn.configure(state="disabled")
        self.lbl_status.configure(text="正在复制程序文件…")
        threading.Thread(target=self._install_worker, args=(target, data), daemon=True).start()

    def _install_worker(self, target, data):
        try:
            if not os.path.isdir(self.app_src):
                raise RuntimeError("安装包缺少程序文件，请重新下载安装包")
            os.makedirs(target, exist_ok=True)
            for name in os.listdir(self.app_src):
                s = os.path.join(self.app_src, name)
                d = os.path.join(target, name)
                if os.path.isdir(s):
                    if os.path.isdir(d):
                        shutil.rmtree(d, ignore_errors=True)
                    shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)

            os.makedirs(data, exist_ok=True)
            loc = location_file()
            os.makedirs(os.path.dirname(loc), exist_ok=True)
            tmp = loc + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"data_dir": data}, f, ensure_ascii=False, indent=2)
            os.replace(tmp, loc)

            self._write_uninstaller(target, data)
            exe = os.path.join(target, EXE_NAME)
            if self.desktop_sc.get():
                self._shortcut(os.path.join(self._desktop(), DESKTOP_NAME + ".lnk"), exe, target, "桌面")
            if self.menu_sc.get():
                self._shortcut(os.path.join(self._start_menu(), MENU_NAME + ".lnk"), exe, target, "开始菜单")
            self.after(0, lambda: self._done(exe))
        except Exception as e:
            self.after(0, lambda: self._failed(str(e)))

    def _desktop(self):
        p = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
        return p if os.path.isdir(p) else os.path.expanduser("~/Desktop")

    def _start_menu(self):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "Microsoft", "Windows", "Start Menu", "Programs")

    def _shortcut(self, lnk, exe, workdir, label):
        ps = (
            "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s');"
            "$s.TargetPath='%s';$s.WorkingDirectory='%s';$s.IconLocation='%s,0';"
            "$s.Description='戏语 · AI 角色扮演聊天';$s.Save()"
        ) % (lnk.replace("'", "''"), exe.replace("'", "''"),
             workdir.replace("'", "''"), exe.replace("'", "''"))
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                           capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if not os.path.exists(lnk):
            raise RuntimeError("创建%s快捷方式失败：%s" % (label, (r.stderr or "").strip()[:160]))

    def _write_uninstaller(self, target, data):
        content = (
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            "echo 即将卸载戏语（数据目录会保留：%s）\r\n"
            "pause\r\n"
            "del /f /q \"%%APPDATA%%\\Microsoft\\Windows\\Start Menu\\Programs\\戏语.lnk\" 2>nul\r\n"
            "del /f /q \"%%USERPROFILE%%\\Desktop\\戏语.lnk\" 2>nul\r\n"
            "start \"\" cmd /c \"timeout 2 >nul & rmdir /s /q \"%s\"\"\r\n"
        ) % (data, target)
        try:
            with open(os.path.join(target, "卸载戏语.bat"), "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass

    def _done(self, exe):
        self.next_btn.configure(state="normal", text="完成", command=self._finish)
        self.back_btn.pack_forget()
        self.lbl_status.configure(text="安装完成：\n" + os.path.abspath(self.install_dir.get()),
                                  fg="#2F7A4F")
        if self.run_after.get():
            try:
                subprocess.Popen([exe], cwd=os.path.dirname(exe))
            except Exception:
                pass

    def _failed(self, msg):
        self.next_btn.configure(state="normal", text="安装", command=self._do_install)
        self.back_btn.configure(state="normal")
        self.lbl_status.configure(text="安装失败：" + msg, fg="#B0413C")
        messagebox.showerror("安装失败", msg, parent=self)

    def _finish(self):
        self.destroy()


if __name__ == "__main__":
    app_src = None
    args = sys.argv[1:]
    if "--app-src" in args:
        app_src = args[args.index("--app-src") + 1]
    Wizard(app_src).mainloop()
