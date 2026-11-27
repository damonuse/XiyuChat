"""本地 JSON 存储：配置、角色、会话、聊天记录。写入均为原子替换。"""
import json
import os
import time
import uuid

from . import paths
from . import secure

DEFAULT_CONFIG = {
    "preset": "DeepSeek",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "global_prompt": "你是一个沉浸式角色扮演引擎。始终以角色身份说话，不要提及自己是 AI，不要跳出设定。",
    "global_world": "",
    "temperature": 0.8,
    "max_tokens": 800,
    "context_turns": 20,
    "memory_enabled": True,
    "memory_every": 12,
    "onboarded": False,
    "last_session": "",
}

PRESETS = {
    "DeepSeek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "OpenAI 兼容": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "自定义": {
        "base_url": "",
        "model": "",
    },
}


def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception:
        # 文件损坏时备份，避免直接覆盖用户数据
        try:
            os.replace(path, path + ".broken-%d" % int(time.time()))
        except Exception:
            pass
        return default


def _write_json(path, data):
    paths.ensure_dirs()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ---------------- 配置 ----------------
def load_config():
    cfg = dict(DEFAULT_CONFIG)
    data = _read_json(paths.CONFIG_FILE, {})
    if isinstance(data, dict):
        for k in DEFAULT_CONFIG:
            if k in data:
                cfg[k] = data[k]
    return cfg


def save_config(cfg):
    _write_json(paths.CONFIG_FILE, cfg)


def load_api_key():
    return secure.load_api_key(paths.KEY_FILE)


def save_api_key(key):
    paths.ensure_dirs()
    secure.save_api_key(paths.KEY_FILE, key)


# ---------------- 角色 ----------------
def load_characters():
    data = _read_json(paths.CHAR_FILE, {"characters": []})
    items = data.get("characters", []) if isinstance(data, dict) else []
    return [c for c in items if isinstance(c, dict) and c.get("id")]


def save_characters(items):
    _write_json(paths.CHAR_FILE, {"characters": items})


def new_character(name, greeting, prompt, world="", advanced=False):
    return {
        "id": "c_" + uuid.uuid4().hex[:12],
        "name": name,
        "greeting": greeting,
        "prompt": prompt,
        "world": world,
        "advanced": advanced,
        "created_at": int(time.time()),
    }


# ---------------- 会话 ----------------
def load_sessions():
    data = _read_json(paths.SESSION_FILE, {"sessions": []})
    items = data.get("sessions", []) if isinstance(data, dict) else []
    return [s for s in items if isinstance(s, dict) and s.get("id")]


def save_sessions(items):
    _write_json(paths.SESSION_FILE, {"sessions": items})


def new_single_session(character):
    return {
        "id": "s_" + uuid.uuid4().hex[:12],
        "type": "single",
        "name": character["name"],
        "single_char_id": character["id"],
        "member_ids": [character["id"]],
        "created_at": int(time.time()),
    }


def new_group_session(name, member_ids):
    return {
        "id": "s_" + uuid.uuid4().hex[:12],
        "type": "group",
        "name": name,
        "single_char_id": "",
        "member_ids": list(member_ids),
        "created_at": int(time.time()),
    }


# ---------------- 聊天记录 ----------------
def load_messages(session_id):
    data = _read_json(paths.chat_file(session_id), {"messages": []})
    msgs = data.get("messages", []) if isinstance(data, dict) else []
    return [m for m in msgs if isinstance(m, dict)]


def save_messages(session_id, messages):
    _write_json(paths.chat_file(session_id), {
        "messages": messages,
        "updated": int(time.time()),
    })


def delete_chat(session_id):
    try:
        os.remove(paths.chat_file(session_id))
    except FileNotFoundError:
        pass
    except Exception:
        pass


def make_message(role, content, speaker_id="", speaker_name=""):
    return {
        "role": role,                   # user / character
        "content": content,
        "speaker_id": speaker_id,
        "speaker_name": speaker_name,
        "ts": int(time.time()),
    }
