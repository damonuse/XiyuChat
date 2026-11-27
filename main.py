"""戏语 · 启动入口。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _enable_x11_threads():
    """Linux 下先初始化 X11 线程，避免 Tk 在部分桌面环境里多线程崩溃。"""
    if not sys.platform.startswith("linux"):
        return
    try:
        import ctypes
        ctypes.CDLL("libX11.so.6").XInitThreads()
    except Exception:
        pass


_enable_x11_threads()

from xiyu_ui.app import main

if __name__ == "__main__":
    main()
