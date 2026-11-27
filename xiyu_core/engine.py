"""提示词构建：把角色设定、世界背景、历史消息组装成 chat 消息数组。"""
import time

FORMAT_RULE = (
    "【输出格式规范（必须严格遵守）】\n"
    "1. 角色说出口的台词就是正文，直接写，不加引号、不加“旁白：”之类的前缀、不加自己的名字。\n"
    "2. 一切与对话无关的内容——动作、表情、神态、心理活动、场景描写、旁白、环境变化等——"
    "一律用中文全角括号（）包起来，放在对应台词的前面或后面。\n"
    "3. 不使用 Markdown、列表、标题、代码块；不解释你在扮演；不跳出角色；不提“我是 AI”或“作为语言模型”。\n"
    "4. 只输出你这一条回复的内容，不要替用户或其他角色写台词。\n"
    "示例：（端起杯子抿了一口，眼神瞥向门口）这事儿你最好别再提了。"
)


def _clip(text, n=80):
    text = (text or "").replace("\n", " ").strip()
    return text[:n] + ("…" if len(text) > n else "")


def _clean_memory(text):
    lines = [l for l in (text or "").splitlines() if not l.strip().startswith("#")]
    return "\n".join(lines).strip()


def build_system(character, config, others=None, is_group=False, memory_text=""):
    parts = []
    gp = (config.get("global_prompt") or "").strip()
    if gp:
        parts.append("【全局规则】\n" + gp)

    world = (character.get("world") or "").strip() or (config.get("global_world") or "").strip()
    if world:
        parts.append("【世界背景】\n" + world)

    parts.append("【你的身份】\n你叫「%s」。你的角色设定：\n%s"
                 % (character.get("name", ""), (character.get("prompt") or "").strip()))

    if is_group:
        names = "、".join(o.get("name", "") for o in (others or []))
        lines = ["【同场角色】这轮对话里还有：%s。" % (names or "无")]
        for o in (others or []):
            lines.append("- %s：%s" % (o.get("name", ""), _clip(o.get("prompt", ""), 60)))
        lines.append("你要始终清楚自己是谁，只以「%s」的身份说话和行动，"
                     "绝不代替其他角色发言，也不要合并多个角色的话。" % character.get("name", ""))
        parts.append("\n".join(lines))

    mem = _clean_memory(memory_text)
    if mem:
        parts.append("【长期记忆】以下是此前对话中已经确定的事，必须与之一致，不要自相矛盾：\n" + mem)

    parts.append(FORMAT_RULE)
    return "\n\n".join(parts)


def build_messages(session, character, history, user_text, config, all_chars, memory_text=""):
    """history: 本会话已有消息列表（不含最新的用户输入）；user_text: 本次用户输入。"""
    is_group = session.get("type") == "group"
    char_map = {c["id"]: c for c in all_chars}
    others = []
    if is_group:
        for cid in session.get("member_ids", []):
            c = char_map.get(cid)
            if c and c["id"] != character["id"]:
                others.append(c)

    messages = [{"role": "system",
                 "content": build_system(character, config, others, is_group, memory_text)}]
    scene = (session.get("scene") or "").strip()
    if scene:
        messages[0]["content"] = "【场景设定】\n" + scene + "\n\n" + messages[0]["content"]

    limit = max(2, int(config.get("context_turns", 20) or 20)) * 2
    trimmed = history[-limit:] if limit > 0 else history

    for m in trimmed:
        role = m.get("role")
        if role not in ("user", "character"):
            continue
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            messages.append({"role": "user",
                             "content": ("用户：" + content) if is_group else content})
        else:
            speaker = m.get("speaker_name") or character.get("name", "")
            messages.append({"role": "assistant",
                             "content": ("%s：%s" % (speaker, content)) if is_group else content})

    if is_group:
        tail = (user_text or "").strip()
        tip = ("【现在轮到你（%s）回应刚才的对话。只写你自己的一条回复：台词用正文，"
               "动作/神态/心理/场景一律用（）包住。不要写其他角色的台词，不要写用户的话。】"
               % character.get("name", ""))
        content = (tail + "\n\n" + tip) if tail else tip
    else:
        content = user_text or "（继续）"
    messages.append({"role": "user", "content": content})
    return messages


def now_ts():
    return int(time.time())
