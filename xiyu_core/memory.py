"""长期记忆：把会话的关键上下文写成可读的文本文件，每次请求时注入提示词。

文件位置：Data/memory/<会话id>.md
内容既可由程序自动摘要，也可以由用户手动编辑。
"""
import os
import re

from . import paths, llm

HEADER = "# 长期记忆（可手动编辑，改完请保存）\n\n"


def memory_dir():
    """记忆文件目录（随数据目录切换而变化）。"""
    return os.path.join(paths.DATA_DIR, "memory")


def ensure_dir():
    os.makedirs(memory_dir(), exist_ok=True)


def memory_path(session_id):
    return os.path.join(memory_dir(), session_id + ".md")


def load(session_id):
    try:
        with open(memory_path(session_id), "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""
    except Exception:
        return ""


def save(session_id, text):
    ensure_dir()
    path = memory_path(session_id)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text or "")
    os.replace(tmp, path)


def delete(session_id):
    try:
        os.remove(memory_path(session_id))
    except Exception:
        pass


def _transcript(messages, limit=40):
    lines = []
    for m in messages[-limit:]:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            lines.append("用户：" + content)
        elif role == "character":
            lines.append("%s：%s" % (m.get("speaker_name") or "角色", content))
    return "\n".join(lines)


SUMMARIZE_PROMPT = (
    "你是一个对话记忆整理器。请把「旧记忆」与「新的对话片段」合并，"
    "输出一份简洁的长期记忆，供角色在后续对话中保持连贯。\n"
    "要求：\n"
    "1. 用要点列表，每条一行，以“- ”开头，最多 10 条，总字数不超过 400 字。\n"
    "2. 只保留稳定事实：人物关系与称呼、重要事件、承诺与约定、地点与时间线、"
    "用户的偏好与禁忌、尚未解决的悬念。\n"
    "3. 不要复述台词，不要写动作描写，不要编造未出现的信息。\n"
    "4. 直接输出要点列表，不要写标题、不要解释你在做什么。\n"
    "5. 若旧记忆里的条目已被新对话推翻，直接改写它。"
)


def build_summary_messages(old_memory, messages, role_names):
    body = []
    if (old_memory or "").strip():
        body.append("【旧记忆】\n" + old_memory.strip())
    body.append("【新的对话片段】\n" + _transcript(messages))
    body.append("【当前出场角色】" + "、".join(n for n in role_names if n))
    return [{"role": "system", "content": SUMMARIZE_PROMPT},
            {"role": "user", "content": "\n\n".join(body)}]


def summarize(base_url, api_key, model, old_memory, messages, role_names,
              temperature=0.4, timeout=120):
    msgs = build_summary_messages(old_memory, messages, role_names)
    text = llm.chat_completion(base_url, api_key, model, msgs,
                               temperature=temperature, max_tokens=600, timeout=timeout)
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text).strip()
    if text and not text.startswith("#"):
        text = HEADER + text
    return text
