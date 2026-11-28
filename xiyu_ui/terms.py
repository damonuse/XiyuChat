"""用户协议：首次启动（或协议版本更新后）强制阅读，同意后才能进入主界面。"""

import json
import os
import sys
import time
import tkinter as tk

from xiyu_core import paths

TERMS_VERSION = "1"

TERMS = """戏语（XiyuChat）用户协议

欢迎使用戏语。请在使用前完整阅读下面的条款；点击「我已阅读并同意」表示你接受全部内容，点击「不同意并退出」则程序不会启动。

一、软件性质
1. 戏语是一个运行在你自己设备上的 AI 角色扮演聊天工具，本身不提供模型服务。
2. 对话内容由你自行配置的第三方大模型接口生成，你需要自备接口地址、模型名称和 API Key，并遵守该服务商的条款。
3. 软件不收集、不上传你的聊天记录、角色设定与密钥；所有数据只保存在本机。

二、内容与使用规范
1. AI 生成的内容由模型产生，可能存在错误、偏见或不准确之处，不代表开发者观点，也不构成任何建议。
2. 你不得利用本软件制作、传播违反法律法规的内容，包括但不限于危害国家安全、暴力恐怖、违法犯罪、色情低俗、侵犯他人隐私与名誉、诈骗与冒充他人等内容。
3. 你不得利用角色扮演功能冒充真实人物骗取信任、实施欺诈，或诱导他人做出财产、人身方面的决定。
4. 你对使用本软件产生的一切行为与后果负责。

三、未成年人
未成年人应在监护人的知情与指导下使用；监护人应妥善保管 API Key 并设置合理的消费额度。

四、免责
1. 软件按「现状」提供，不承诺无错误、不中断或适用于特定目的。
2. 因第三方接口故障、网络问题、模型输出或你的操作造成的任何损失，开发者不承担责任。
3. 你应自行承担使用第三方接口产生的费用。

五、其他
1. 本协议可能随版本更新而调整，更新后会在启动时再次展示。
2. 你若不同意本协议的任何内容，请停止使用并删除本软件。

点击「我已阅读并同意」即表示你已年满 18 周岁，或在监护人陪同下阅读并同意本协议。"""


def _center(win, w, h):
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, (sh - h) // 3))


def ask_agree():
    """弹出协议窗口。返回 True 表示同意；False 表示拒绝（调用方应退出）。"""
    root = tk.Tk()
    root.title("戏语 · 用户协议")
    root.configure(bg="#FFFFFF")
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass

    state = {"ok": False}

    title = tk.Label(root, text="用户协议", bg="#FFFFFF", fg="#1F2330",
                     font=("Microsoft YaHei UI", 15, "bold"), anchor="w")
    title.pack(fill="x", padx=22, pady=(18, 4))
    sub = tk.Label(root, text="首次使用前请阅读并同意以下条款", bg="#FFFFFF",
                   fg="#8B93A3", font=("Microsoft YaHei UI", 9), anchor="w")
    sub.pack(fill="x", padx=22, pady=(0, 10))

    frame = tk.Frame(root, bg="#E3E6EE")
    frame.pack(fill="both", expand=True, padx=22, pady=(0, 12))
    text = tk.Text(frame, wrap="word", bg="#FFFFFF", fg="#2A2F3A", relief="flat",
                   font=("Microsoft YaHei UI", 10), padx=12, pady=10,
                   spacing1=2, spacing3=4)
    sb = tk.Scrollbar(frame, command=text.yview)
    text.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    text.pack(side="left", fill="both", expand=True)
    text.insert("1.0", TERMS)
    text.configure(state="disabled")

    bar = tk.Frame(root, bg="#FFFFFF")
    bar.pack(fill="x", padx=22, pady=(0, 18))

    def agree():
        state["ok"] = True
        root.destroy()

    def refuse():
        state["ok"] = False
        root.destroy()

    no = tk.Button(bar, text="不同意并退出", command=refuse, relief="flat",
                   bg="#EEF1F6", fg="#2A2F3A", font=("Microsoft YaHei UI", 10),
                   activebackground="#E1E5EE", cursor="hand2", padx=16, pady=6)
    no.pack(side="right")
    yes = tk.Button(bar, text="我已阅读并同意", command=agree, relief="flat",
                    bg="#3B6FE0", fg="#FFFFFF", font=("Microsoft YaHei UI", 10, "bold"),
                    activebackground="#2F5ED0", cursor="hand2", padx=20, pady=6)
    yes.pack(side="right", padx=(0, 10))

    _center(root, 760, 620)
    root.protocol("WM_DELETE_WINDOW", refuse)
    root.mainloop()
    return state["ok"]


def _record_file():
    return os.path.join(paths.ROOT_DIR, "terms.json")


def already_agreed():
    """当前版本协议是否已被同意。"""
    try:
        with open(_record_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("version") == TERMS_VERSION
    except Exception:
        return False


def _remember():
    try:
        os.makedirs(paths.ROOT_DIR, exist_ok=True)
        with open(_record_file(), "w", encoding="utf-8") as f:
            json.dump({"version": TERMS_VERSION, "time": time.strftime("%Y-%m-%d %H:%M:%S")},
                      f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def gate():
    """协议闸门：已同意过当前版本直接放行，否则弹出；拒绝则退出进程。"""
    if already_agreed():
        return True
    if ask_agree():
        _remember()
        return True
    print("已拒绝用户协议，程序退出。")
    sys.exit(0)
