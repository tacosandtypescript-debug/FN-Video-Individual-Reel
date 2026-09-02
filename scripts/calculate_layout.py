#!/usr/bin/env python3
"""calculate_layout.py - Geometria relativa (reglas 2-4 y 7).

Video central: contain (sin deformar). Textos anclados al video:
    topTextBlock.bottom = videoTop - gap
    bottomTextBlock.top  = videoBottom + gap   (topGap == bottomGap)
Cada bloque (1+ lineas) se mide como UNIDAD (bbox) antes de posicionarse.
Safe zones se aplican SOLO a texto desplazando el bloque entero lo minimo.
"""
from dataclasses import dataclass
from PIL import ImageFont


def glyph_h(fs):
    return max(1, round(fs * 0.68))


def scale_1080(value, canvas_h):
    return max(1, round(value * canvas_h / 1920))


@dataclass
class VideoBox:
    x: int; y: int; w: int; h: int

    @property
    def top(self):
        return self.y

    @property
    def right(self):
        return self.x + self.w

    @property
    def bottom(self):
        return self.y + self.h


def video_box(canvas_w, canvas_h, content_w, content_h):
    s = min(canvas_w / content_w, canvas_h / content_h)
    w = int(content_w * s)
    h = int(content_h * s)
    if w % 2:
        w -= 1
    if h % 2:
        h -= 1
    return VideoBox((canvas_w - w) // 2, (canvas_h - h) // 2, w, h)


@dataclass
class TextLine:
    text: str
    color: str = "FFFFFF"
    size: int = 60
    y: int = 0
    width_px: int = 0


def measure(font_path, lines):
    for ln in lines:
        ln.width_px = int(round(ImageFont.truetype(font_path, ln.size).getlength(ln.text)))
    return lines


class TextBlock:
    """Unidad de texto (1+ lineas)."""
    def __init__(self, lines, canvas_w, side, anchor_row, spacing):
        self.lines = lines
        self.cw = canvas_w
        self.spacing = spacing
        self._place(side, anchor_row)

    def _place(self, side, anchor_row):
        if side == "bottom":
            y = anchor_row - 1
            for ln in reversed(self.lines):
                ln.y = y
                y -= glyph_h(ln.size) + self.spacing
        else:
            y = anchor_row - glyph_h(self.lines[-1].size)
            for ln in reversed(self.lines):
                ln.y = y
                y -= glyph_h(ln.size) + self.spacing
        self._recompute()

    def _recompute(self):
        self.top = min(ln.y for ln in self.lines) + 1
        self.bottom = max(ln.y + glyph_h(ln.size) for ln in self.lines)
        mw = max(ln.width_px for ln in self.lines)
        self.left = self.cw // 2 - mw // 2
        self.right = self.left + mw
        self.width = mw
        self.height = self.bottom - self.top + 1

    def shift(self, dy):
        for ln in self.lines:
            ln.y += dy
        self._recompute()

    def __repr__(self):
        return (f"bbox top={self.top} bottom={self.bottom} left={self.left} "
                f"right={self.right} w={self.width} h={self.height}")


class Layout:
    def __init__(self, canvas_w, canvas_h, content_w, content_h, top_lines, bot_lines,
                 gap=None, spacing=None, font_path=None, wave=0, safe=None):
        self.cw, self.ch = canvas_w, canvas_h
        self.gap = gap if gap is not None else scale_1080(32, canvas_h)
        self.spacing = spacing if spacing is not None else scale_1080(18, canvas_h)
        self.font = font_path or ""
        self.wave = wave
        if font_path:
            measure(font_path, top_lines)
            measure(font_path, bot_lines)
        s = safe or {"left_f": 0.056, "right_f": 0.056, "top_f": 0.0725, "bottom_f": 0.174}
        self.safe_limits = {"left": int(canvas_w * s["left_f"]),
                            "right": canvas_w - int(canvas_w * s["right_f"]),
                            "top": int(canvas_h * s["top_f"]),
                            "bottom": canvas_h - int(canvas_h * s["bottom_f"])}
        self.video = video_box(canvas_w, canvas_h, content_w, content_h)
        self.top_block = TextBlock(top_lines, canvas_w, "top",
                                   self.video.top - self.gap, self.spacing)
        self.bot_block = TextBlock(bot_lines, canvas_w, "bottom",
                                   self.video.bottom + self.gap, self.spacing)
        self._clamp_safe()

    def _clamp_safe(self):
        sl = self.safe_limits
        if self.top_block.top < sl["top"]:
            self.top_block.shift(sl["top"] - self.top_block.top)
        if self.bot_block.bottom > sl["bottom"]:
            self.bot_block.shift(sl["bottom"] - self.bot_block.bottom)

    @property
    def gap_top(self):
        return self.video.top - self.top_block.bottom

    @property
    def gap_bot(self):
        return self.bot_block.top - self.video.bottom

    def debug(self, src_note=""):
        v = self.video
        L = [f"Canvas: {self.cw}x{self.ch}"]
        if src_note:
            L.append(src_note)
        L += [f"Video rendered: {v.w}x{v.h}", f"Video top: {v.top}",
              f"Video bottom: {v.bottom}"]
        for name, blk in (("Top text", self.top_block), ("Bottom text", self.bot_block)):
            L.append(f"{name} bbox: {blk}")
            L.append(f"{name.split()[0]} lines: " + ", ".join(
                f"'{t.text}' fs{t.size} y{t.y}" for t in blk.lines))
        L += [f"Top gap: {self.gap_top}", f"Bottom gap: {self.gap_bot}",
              f"Gaps equal: {abs(self.gap_top - self.gap_bot) <= 2}"]
        return "\n".join(L)


def parse_text_spec(path_or_str, default_size=60):
    raw = None
    if path_or_str and "\n" not in path_or_str and "|" not in path_or_str:
        try:
            raw = open(path_or_str).read()
        except OSError:
            raw = path_or_str
    else:
        raw = path_or_str
    out = []
    for ln in (raw or "").strip().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        parts = [p.strip() for p in ln.split("|")]
        color = (parts[1] if len(parts) > 1 and parts[1] else "FFFFFF").lstrip("#").upper()
        size = int(parts[2]) if len(parts) > 2 and parts[2] else default_size
        out.append(TextLine(text=parts[0], color=color, size=size))
    return out
