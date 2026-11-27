"""路径与常量定义。

数据目录不再绑定固定盘符：默认放在 %APPDATA%\\XiyuChat\\Data，
用户可以在设置里改到任意可写目录，实际位置记录在 %APPDATA%\\XiyuChat\\location.json。
"""
import json
import os
import shutil

APP_NAME = "戏语"
APP_EN = "XiyuChat"
VERSION = "1.2.0"


def _home_root() -> str:
    env = os.environ.get("XIYU_HOME")
    if env:
        return os.path.abspath(env)
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_EN)


ROOT_DIR = _home_root()
LOCATION_FILE = os.path.join(ROOT_DIR, "location.json")
DEFAULT_DATA_DIR = os.path.join(ROOT_DIR, "Data")

# 以下路径由 _apply() 填充，切换数据目录后会同步更新
DATA_DIR = DEFAULT_DATA_DIR
CHAT_DIR = ""
CONFIG_FILE = ""
CHAR_FILE = ""
SESSION_FILE = ""
KEY_FILE = ""
LOG_FILE = ""


def _normalize(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def _apply(data_dir: str) -> None:
    global DATA_DIR, CHAT_DIR, CONFIG_FILE, CHAR_FILE, SESSION_FILE, KEY_FILE, LOG_FILE
    DATA_DIR = _normalize(data_dir)
    CHAT_DIR = os.path.join(DATA_DIR, "chats")
    CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
    CHAR_FILE = os.path.join(DATA_DIR, "characters.json")
    SESSION_FILE = os.path.join(DATA_DIR, "sessions.json")
    KEY_FILE = os.path.join(DATA_DIR, "secret.bin")
    LOG_FILE = os.path.join(DATA_DIR, "app.log")


def configured_data_dir() -> str:
    """读取用户设置的数据目录；没有设置时用默认目录。"""
    try:
        with open(LOCATION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        path = data.get("data_dir")
        if isinstance(path, str) and path.strip():
            path = path.strip()
            if os.path.isabs(path):
                return _normalize(path)
    except Exception:
        pass
    return DEFAULT_DATA_DIR


def save_location(data_dir: str) -> None:
    os.makedirs(ROOT_DIR, exist_ok=True)
    data = {"data_dir": _normalize(data_dir)}
    tmp = LOCATION_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, LOCATION_FILE)


def set_data_dir(data_dir: str) -> None:
    """切换数据目录：写指针文件并刷新本模块的路径常量。"""
    save_location(data_dir)
    _apply(data_dir)
    ensure_dirs()


def ensure_dirs() -> None:
    for d in (DATA_DIR, CHAT_DIR, os.path.join(DATA_DIR, "memory")):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass


def chat_file(session_id: str) -> str:
    return os.path.join(CHAT_DIR, session_id + ".json")


def has_data(path: str) -> bool:
    """判断某个目录里是否已有戏语的数据文件。"""
    path = _normalize(path)
    for name in ("config.json", "characters.json", "sessions.json"):
        if os.path.isfile(os.path.join(path, name)):
            return True
    return False


def migrate_data(src: str, dst: str) -> int:
    """把 src 里的数据复制到 dst，返回复制的文件数；不删除源目录的数据。"""
    src, dst = _normalize(src), _normalize(dst)
    if src == dst:
        return 0
    os.makedirs(dst, exist_ok=True)
    count = 0
    for name in ("config.json", "characters.json", "sessions.json",
                 "secret.bin", "usage.json"):
        s = os.path.join(src, name)
        if os.path.isfile(s):
            try:
                shutil.copy2(s, os.path.join(dst, name))
                count += 1
            except Exception:
                pass
    for sub in ("chats", "memory"):
        sdir = os.path.join(src, sub)
        if not os.path.isdir(sdir):
            continue
        for root, _dirs, files in os.walk(sdir):
            for fn in files:
                s = os.path.join(root, fn)
                rel = os.path.relpath(root, src)
                target_dir = os.path.join(dst, rel)
                try:
                    os.makedirs(target_dir, exist_ok=True)
                    shutil.copy2(s, os.path.join(target_dir, fn))
                    count += 1
                except Exception:
                    pass
    return count


_apply(configured_data_dir())
ensure_dirs()
