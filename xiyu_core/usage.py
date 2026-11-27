"""API 用量本地统计：每次调用成功后把 usage 累加进 Data/usage.json。"""
import json
import os
import threading
import time

from . import paths

def usage_file():
    """用量文件路径（随数据目录切换而变化）。"""
    return os.path.join(paths.DATA_DIR, "usage.json")


_lock = threading.Lock()
_KEEP_DAYS = 120


def _empty_bucket():
    return {"prompt": 0, "completion": 0, "calls": 0}


def _load_raw():
    path = usage_file()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data.setdefault("total", _empty_bucket())
            data.setdefault("days", {})
            data.setdefault("models", {})
            return data
    except Exception:
        pass
    return {"total": _empty_bucket(), "days": {}, "models": {}, "updated": 0}


def _inc(bucket, prompt_tokens, completion_tokens):
    bucket["prompt"] = int(bucket.get("prompt", 0)) + int(prompt_tokens or 0)
    bucket["completion"] = int(bucket.get("completion", 0)) + int(completion_tokens or 0)
    bucket["calls"] = int(bucket.get("calls", 0)) + 1
    return bucket


def record(prompt_tokens, completion_tokens, model=""):
    """记录一次调用。thread-safe。"""
    with _lock:
        data = _load_raw()
        _inc(data["total"], prompt_tokens, completion_tokens)
        day = time.strftime("%Y-%m-%d")
        days = data["days"]
        days[day] = _inc(days.get(day) or _empty_bucket(), prompt_tokens, completion_tokens)
        if model:
            models = data["models"]
            models[model] = _inc(models.get(model) or _empty_bucket(),
                                 prompt_tokens, completion_tokens)
        # 只保留最近 N 天
        if len(days) > _KEEP_DAYS:
            for k in sorted(days.keys())[:-_KEEP_DAYS]:
                days.pop(k, None)
        data["updated"] = int(time.time())
        path = usage_file()
        tmp = path + ".tmp"
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception:
            pass


def summary():
    """返回今日与累计用量。"""
    data = _load_raw()
    today = data["days"].get(time.strftime("%Y-%m-%d")) or _empty_bucket()
    return {
        "today": today,
        "total": data.get("total") or _empty_bucket(),
        "updated": data.get("updated", 0),
        "models": data.get("models", {}),
    }
