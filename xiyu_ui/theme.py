"""界面主题常量与小工具。"""
import tkinter as tk
import tkinter.font as tkfont

FONT_FAMILY = "Microsoft YaHei UI"

C_BG = "#F5F6FA"
C_CARD = "#FFFFFF"
C_LINE = "#E4E7EE"
C_TEXT = "#22262E"
C_TEXT_SUB = "#7B8494"
C_ACCENT = "#3B6CF6"
C_ACCENT_DARK = "#3059D6"
C_ACCENT_SOFT = "#E8EEFF"
C_BANNER = "#20242E"
C_BANNER_SUB = "#9AA3B5"
C_USER_BUBBLE = "#3B6CF6"
C_CHAR_BUBBLE = "#FFFFFF"
C_DANGER = "#E05450"

AVATAR_COLORS = ["#5B8DEF", "#8E7CF0", "#4CAF9D", "#E08A4E",
                 "#D9699B", "#5AA9D6", "#7C9A55", "#C4825B"]


def font(size=11, bold=False, family=FONT_FAMILY):
    return (family, size, "bold") if bold else (family, size)


def avatar_color(seed_text: str) -> str:
    return AVATAR_COLORS[sum(map(ord, seed_text or "x")) % len(AVATAR_COLORS)]


def round_rect(canvas, x1, y1, x2, y2, r=10, **kw):
    """在 Canvas 上画圆角矩形（用平滑多边形近似）。"""
    r = min(r, abs(x2 - x1) / 2, abs(y2 - y1) / 2)
    pts = [
        x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1,
        x2, y1, x2, y1 + r, x2, y1 + r, x2, y2 - r, x2, y2 - r,
        x2, y2, x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r,
        x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


def measure_lines(text, fnt, max_px):
    """粗略估算换行后的行数（用于 Text 高度）。"""
    total = 0
    for para in (text or "").split("\n"):
        if not para:
            total += 1
            continue
        w, lines = 0, 1
        for ch in para:
            cw = fnt.measure(ch)
            if w + cw > max_px:
                lines += 1
                w = cw
            else:
                w += cw
        total += lines
    return max(1, total)
