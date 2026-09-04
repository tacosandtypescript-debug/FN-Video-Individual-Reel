#!/usr/bin/env python3
"""calculate_layout.py - Geometria relativa (reglas 2-4 y 7).

Video central: contain (sin deformar). Textos anclados al video:
    topTextBlock.bottom = videoTop - gap
    bottomTextBlock.top  = videoBottom + gap   (topGap == bottomGap)
Cada bloque (1+ lineas) se mide como UNIDAD (bbox) antes de posicionarse.

Calibracion empirica drawtext: con y=Y las filas van de Y a Y+H-1, donde H es el
bbox real de la linea medido con PIL (incluye ascendentes/descendentes/italica).
"""
from dataclasses import dataclass, field
import re
from PIL import ImageFont


def glyph_h(fs):
    return max(1, round(fs * 0.68))


def scale_1080(value, canvas_h):
    return max(1, round(value * canvas_h / 1920))


def line_h(font_path, text, fs):
    """Alto real en px de la linea (getbbox de PIL a ese tamano)."""
    try:
        bb = ImageFont.truetype(font_path, fs).getbbox(text)
        return max(1, bb[3] - bb[1])
    except Exception:
        return glyph_h(fs)


def line_width(font_path, text, fs):
    return int(round(ImageFont.truetype(font_path, fs).getlength(text)))


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
    height_px: int = 0
    # Segmentos [(texto, RRGGBB)]. Sin marcado, es una sola entrada.
    segments: list = field(default_factory=list)
    size_explicit: bool = False

    def h(self, font_path):
        return self.height_px or line_h(font_path, self.text, self.size)


def measure(font_path, lines):
    f = None
    for ln in lines:
        if f is None or True:
            f = ImageFont.truetype(font_path, ln.size)
        ln.width_px = int(round(f.getlength(ln.text)))
        bb = f.getbbox(ln.text)
        ln.height_px = max(1, bb[3] - bb[1])
    return lines


class TextBlock:
    """Unidad de texto (1+ lineas). Filas: y .. y+H-1."""
    def __init__(self, lines, canvas_w, font_path, side, anchor_row, spacing):
        self.lines = lines
        self.cw = canvas_w
        self.font = font_path
        self.spacing = spacing
        if lines:
            self._place(side, anchor_row)
            self._recompute()
        else:
            self.top = self.bottom = self.left = self.right = 0
            self.width = self.height = 0

    def _place(self, side, anchor_row):
        if side == "bottom":
            # primera linea: su fila TOP == anchor_row
            y = anchor_row
            for ln in self.lines:
                ln.y = y
                y += ln.h(self.font) + self.spacing
        else:
            # ultima linea: su fila BOTTOM == anchor_row
            y = anchor_row - self.lines[-1].h(self.font) + 1
            for ln in reversed(self.lines):
                ln.y = y
                y -= ln.h(self.font) + self.spacing

    def _recompute(self):
        if not self.lines:
            return
        self.top = min(ln.y for ln in self.lines)
        self.bottom = max(ln.y + ln.h(self.font) - 1 for ln in self.lines)
        mw = max(ln.width_px for ln in self.lines)
        self.left = self.cw // 2 - mw // 2
        self.right = self.left + mw
        self.width = mw
        self.height = self.bottom - self.top + 1

    def shift(self, dy):
        if not self.lines:
            return
        for ln in self.lines:
            ln.y += dy
        self._recompute()

    def __repr__(self):
        if not self.lines:
            return "(vacio)"
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
        if font_path and (top_lines or bot_lines):
            measure(font_path, top_lines)
            measure(font_path, bot_lines)
        s = safe or {"left_f": 0.056, "right_f": 0.056, "top_f": 0.0725, "bottom_f": 0.174}
        self.safe_limits = {"left": int(canvas_w * s["left_f"]),
                            "right": canvas_w - int(canvas_w * s["right_f"]),
                            "top": int(canvas_h * s["top_f"]),
                            "bottom": canvas_h - int(canvas_h * s["bottom_f"])}
        self.video = video_box(canvas_w, canvas_h, content_w, content_h)
        self.top_block = TextBlock(top_lines, canvas_w, font_path or "", "top",
                                   self.video.top - self.gap, self.spacing)
        self.bot_block = TextBlock(bot_lines, canvas_w, font_path or "", "bottom",
                                   self.video.bottom + self.gap, self.spacing)
        # En fuentes verticales, contain puede ocupar casi todo el canvas y no
        # dejar sitio a los dos bloques. Se reduce el video proporcionalmente,
        # conservando AR, hasta que texto + gaps caben en safe zone.
        if top_lines and bot_lines and self.bot_block.bottom > self.safe_limits["bottom"]:
            max_h = (self.safe_limits["bottom"] - self.safe_limits["top"]
                     - self.top_block.height - self.bot_block.height - 2 * self.gap)
            if max_h > 0 and self.video.h > max_h:
                scale = max_h / self.video.h
                nw = max(2, int(self.video.w * scale) // 2 * 2)
                nh = max(2, int(self.video.h * scale) // 2 * 2)
                self.video = VideoBox((canvas_w - nw) // 2,
                                      self.safe_limits["top"] + self.top_block.height + self.gap,
                                      nw, nh)
                self.top_block = TextBlock(top_lines, canvas_w, font_path or "", "top",
                                           self.video.top - self.gap, self.spacing)
                self.bot_block = TextBlock(bot_lines, canvas_w, font_path or "", "bottom",
                                           self.video.bottom + self.gap, self.spacing)
        self._clamp_safe()

    def _clamp_safe(self):
        sl = self.safe_limits
        if self.top_block.top and self.top_block.top < sl["top"]:
            self.top_block.shift(sl["top"] - self.top_block.top)
        if self.bot_block.lines and self.bot_block.bottom > sl["bottom"]:
            self.bot_block.shift(sl["bottom"] - self.bot_block.bottom)

    @property
    def gap_top(self):
        return self.video.top - self.top_block.bottom if self.top_block.lines else None

    @property
    def gap_bot(self):
        return self.bot_block.top - self.video.bottom if self.bot_block.lines else None

    def debug(self, src_note=""):
        v = self.video
        L = [f"Canvas: {self.cw}x{self.ch}"]
        if src_note:
            L.append(src_note)
        L += [f"Video rendered: {v.w}x{v.h}", f"Video top: {v.top}",
              f"Video bottom: {v.bottom}"]
        for name, blk in (("Top text", self.top_block), ("Bottom text", self.bot_block)):
            if blk.lines:
                L.append(f"{name} bbox: {blk}")
                L.append(f"{name.split()[0]} lines: " + ", ".join(
                    f"'{t.text}' fs{t.size} y{t.y} H{t.height_px}" for t in blk.lines))
            else:
                L.append(f"{name}: (vacio)")
        L.append(f"Top gap: {self.gap_top}")
        L.append(f"Bottom gap: {self.gap_bot}")
        if self.gap_top is not None and self.gap_bot is not None:
            L.append(f"Gaps equal: {abs(self.gap_top - self.gap_bot) <= 2}")
        return "\n".join(L)


def _split_top_level(value):
    """Separa | solo fuera de {segmentos|COLOR}."""
    out, cur, depth = [], [], 0
    for ch in value:
        if ch == "{": depth += 1
        elif ch == "}" and depth: depth -= 1
        if ch == "|" and depth == 0:
            out.append("".join(cur)); cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return out


def _segments(markup, default_color):
    """{TEXTO|RRGGBB} colorea solo ese segmento; texto normal usa default."""
    result, pos = [], 0
    for m in re.finditer(r"\{([^{}|]+)\|#?([0-9A-Fa-f]{6})\}", markup):
        if m.start() > pos:
            result.append((markup[pos:m.start()], default_color))
        result.append((m.group(1), m.group(2).upper()))
        pos = m.end()
    if pos < len(markup):
        result.append((markup[pos:], default_color))
    if not result:
        result = [(markup, default_color)]
    return [(t, c) for t, c in result if t]


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
        parts = [p.strip() for p in _split_top_level(ln)]
        color = (parts[1] if len(parts) > 1 and parts[1] else "FFFFFF").lstrip("#").upper()
        size_explicit = len(parts) > 2 and bool(parts[2])
        size = int(parts[2]) if size_explicit else default_size
        segs = _segments(parts[0], color)
        out.append(TextLine(text="".join(t for t, _ in segs), color=color, size=size,
                            segments=segs, size_explicit=size_explicit))
    return out


def enlarge_short_lines(lines, font_path, safe_width, base_size=60, max_size=84,
                        target_fraction=0.82):
    """Aumenta texto corto sin tocar tamaños explícitos ni desbordar safe zone."""
    if not lines or not font_path:
        return lines
    longest = max(line_width(font_path, ln.text, base_size) for ln in lines)
    if longest <= 0 or longest >= safe_width * target_fraction:
        return lines
    target = min(max_size, max(base_size, int(base_size * safe_width * target_fraction / longest)))
    for ln in lines:
        if not ln.size_explicit:
            ln.size = target
    return lines
