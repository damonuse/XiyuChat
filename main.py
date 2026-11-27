"""戏语 · 启动入口。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from xiyu_ui.app import main

if __name__ == "__main__":
    main()
