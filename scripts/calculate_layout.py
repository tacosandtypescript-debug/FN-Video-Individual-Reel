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
from copy import deepcopy
import re
import unicodedata
from PIL import ImageFont

HEX = set("0123456789ABCDEF")

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


def _even_nearest(value, minimum=2):
    """Redondea a una dimensión par sin introducir un sesgo sistemático."""
    return max(minimum, int(round(value / 2.0)) * 2)


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
    if min(canvas_w, canvas_h, content_w, content_h) <= 0:
        raise ValueError("Las dimensiones del canvas y del video deben ser positivas")
    max_w = max(2, (canvas_w // 2) * 2)
    max_h = max(2, (canvas_h // 2) * 2)
    s = min(max_w / content_w, max_h / content_h)
    # Redondear al entero par más cercano evita que un 16:9 de 1080x607.5
    # termine innecesariamente en 1080x606 y pierda más proporción de la debida.
    w = _even_nearest(content_w * s)
    h = _even_nearest(content_h * s)
    while w > max_w:
        w -= 2
    while h > max_h:
        h -= 2
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
        if f is None or getattr(f, "size", None) != ln.size:
            f = ImageFont.truetype(font_path, ln.size)
        # Segmented drawtext is positioned as the sum of its segment widths;
        # measure the same geometry instead of relying on whole-string kerning.
        if ln.segments:
            ln.width_px = sum(int(round(f.getlength(text)))
                              for text, _ in ln.segments)
        else:
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
                 gap=None, spacing=None, font_path=None, wave=0, safe=None,
                 text_padding=0):
        self.cw, self.ch = canvas_w, canvas_h
        self.gap = gap if gap is not None else scale_1080(32, canvas_h)
        self.spacing = spacing if spacing is not None else scale_1080(18, canvas_h)
        self.font = font_path or ""
        self.wave = wave
        if font_path and (top_lines or bot_lines):
            measure(font_path, top_lines)
            measure(font_path, bot_lines)
        s = safe or {"left_f": 0.056, "right_f": 0.056, "top_f": 0.0725, "bottom_f": 0.174}
        padding = max(0, int(text_padding))
        self.safe_limits = {
            "left": int(canvas_w * s["left_f"]) + padding,
            "right": canvas_w - int(canvas_w * s["right_f"]) - padding,
            "top": int(canvas_h * s["top_f"]) + padding,
            "bottom": canvas_h - int(canvas_h * s["bottom_f"]) - padding,
        }
        self.video = video_box(canvas_w, canvas_h, content_w, content_h)
        self.top_block = TextBlock(top_lines, canvas_w, font_path or "", "top",
                                   self.video.top - self.gap, self.spacing)
        self.bot_block = TextBlock(bot_lines, canvas_w, font_path or "", "bottom",
                                   self.video.bottom + self.gap, self.spacing)
        self._fit_video_to_text(top_lines, bot_lines, font_path or "")
        self._clamp_safe()
        self._validate_text_geometry()

    def _fit_video_to_text(self, top_lines, bot_lines, font_path):
        """Fit the foreground in the vertical corridor left by the text.

        The old implementation only reduced a vertical source when *both* text
        blocks existed.  A source with just a top or bottom caption therefore
        kept a full-height foreground and the safe-zone clamp moved the caption
        on top of it.  Treating each block independently keeps the text anchored
        to the video for every valid combination of top/bottom text.
        """
        top_h = self.top_block.height if top_lines else 0
        bot_h = self.bot_block.height if bot_lines else 0
        min_video_top = (self.safe_limits["top"] + top_h + self.gap
                         if top_lines else 0)
        max_video_bottom = (self.safe_limits["bottom"] - bot_h - self.gap
                            if bot_lines else self.ch)
        max_video_h = max_video_bottom - min_video_top
        if (top_lines or bot_lines) and max_video_h < 2:
            raise ValueError("No queda altura suficiente para colocar el video y los textos")

        old = self.video
        if top_lines or bot_lines:
            if old.h > max_video_h:
                scale = max_video_h / old.h
                nh = _even_nearest(old.h * scale)
                nw = _even_nearest(old.w * scale)
                # The even-pixel rounding must not cross the text corridor.
                while nh > max_video_h:
                    nh -= 2
                while nw > self.cw:
                    nw -= 2
                if nh < 2 or nw < 2:
                    raise ValueError("No queda altura suficiente para el video")
                y = min_video_top
            else:
                nw, nh = old.w, old.h
                y = min(max(old.y, min_video_top), max_video_bottom - nh)
            self.video = VideoBox((self.cw - nw) // 2, y, nw, nh)

        # Re-anchor both blocks after any size/position change.  In particular,
        # this restores the exact configured gap after a constrained fit.
        self.top_block = TextBlock(top_lines, self.cw, font_path, "top",
                                   self.video.top - self.gap, self.spacing)
        self.bot_block = TextBlock(bot_lines, self.cw, font_path, "bottom",
                                   self.video.bottom + self.gap, self.spacing)

    def _clamp_safe(self):
        sl = self.safe_limits
        if self.top_block.lines and self.top_block.top < sl["top"]:
            self.top_block.shift(sl["top"] - self.top_block.top)
        if self.bot_block.lines and self.bot_block.bottom > sl["bottom"]:
            self.bot_block.shift(sl["bottom"] - self.bot_block.bottom)

    def _validate_text_geometry(self):
        """Falla de forma explícita cuando el texto no puede caber en el canvas."""
        safe_width = self.safe_limits["right"] - self.safe_limits["left"]
        for name, block in (("superior", self.top_block), ("inferior", self.bot_block)):
            for line in block.lines:
                if line.width_px > safe_width:
                    raise ValueError(
                        f"La línea {name} '{line.text}' supera el ancho seguro "
                        f"({line.width_px}px > {safe_width}px); reduce su tamaño"
                    )
        if self.top_block.lines and self.bot_block.lines:
            if self.top_block.bottom >= self.bot_block.top:
                raise ValueError(
                    "Los bloques de texto se solapan; reduce el tamaño o usa menos líneas"
                )
        sl = self.safe_limits
        if self.top_block.lines and self.top_block.top < sl["top"]:
            raise ValueError("El bloque superior no cabe en la zona segura")
        if self.bot_block.lines and self.bot_block.bottom > sl["bottom"]:
            raise ValueError("El bloque inferior no cabe en la zona segura")

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
            with open(path_or_str, encoding="utf-8") as fh:
                raw = fh.read()
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
        if len(parts) > 3:
            raise ValueError("Formato de texto inválido; usa TEXTO|COLOR|TAMAÑO")
        color = (parts[1] if len(parts) > 1 and parts[1] else "FFFFFF").lstrip("#").upper()
        if len(color) != 6 or any(c not in HEX for c in color):
            raise ValueError(f"Color inválido: {color}; usa RRGGBB")
        size_explicit = len(parts) > 2 and bool(parts[2])
        size = int(parts[2]) if size_explicit else default_size
        if size <= 0:
            raise ValueError("El tamaño de texto debe ser mayor que cero")
        segs = _segments(parts[0], color)
        out.append(TextLine(text="".join(t for t, _ in segs), color=color, size=size,
                            segments=segs, size_explicit=size_explicit))
    return out


def normalize_copy_lines(lines):
    """Normalize renderable lines to uppercase without accents/diacritics."""
    for line in lines or []:
        line.segments = [
            ("".join(
                ch for ch in unicodedata.normalize("NFKD", text or "")
                if not unicodedata.combining(ch)
            ).upper(), color)
            for text, color in (line.segments or [(line.text, line.color)])
            if text
        ]
        line.text = "".join(text for text, _ in line.segments)
        line.color = line.color.upper()
    return lines


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


def _segments_for_slice(segments, start, end):
    """Keep the original word colors for a substring of a TextLine."""
    if not segments:
        return []
    result = []
    cursor = 0
    for text, color in segments:
        segment_start = max(start, cursor)
        segment_end = min(end, cursor + len(text))
        if segment_end > segment_start:
            piece = text[segment_start - cursor:segment_end - cursor]
            if piece:
                if result and result[-1][1] == color:
                    result[-1] = (result[-1][0] + piece, color)
                else:
                    result.append((piece, color))
        cursor += len(text)
    return result


def _wrapped_ranges(text, font_path, size, max_width, segments=None):
    """Return character ranges whose rendered widths never exceed max_width."""
    if max_width <= 0:
        raise ValueError("El ancho seguro debe ser mayor que cero")
    visible = text.strip()
    if not visible:
        return []
    left = text.find(visible)
    right = left + len(visible)
    font = ImageFont.truetype(font_path, size)

    def width(value, start=None, end=None):
        if segments is not None and start is not None and end is not None:
            pieces = _segments_for_slice(segments, start, end)
            return int(round(sum(font.getlength(piece) for piece, _ in pieces)))
        return int(round(font.getlength(value)))

    ranges = []
    current_start = current_end = None
    for match in re.finditer(r"\S+", text[left:right]):
        token_start = left + match.start()
        token_end = left + match.end()
        token = text[token_start:token_end]
        if width(token, token_start, token_end) > max_width:
            if current_start is not None:
                ranges.append((current_start, current_end))
                current_start = current_end = None
            # A single unbreakable token still cannot be allowed to overflow.
            # Split it at a character boundary only as the last resort.
            cursor = token_start
            while cursor < token_end:
                end = cursor + 1
                while (end < token_end and
                       width(text[cursor:end + 1], cursor, end + 1) <= max_width):
                    end += 1
                ranges.append((cursor, end))
                cursor = end
            continue
        if current_start is None:
            current_start, current_end = token_start, token_end
        elif width(text[current_start:token_end], current_start, token_end) <= max_width:
            current_end = token_end
        else:
            ranges.append((current_start, current_end))
            current_start, current_end = token_start, token_end
    if current_start is not None:
        ranges.append((current_start, current_end))
    return ranges


def _line_slice(line, start, end):
    """Create a TextLine for a range produced by _wrapped_ranges."""
    raw = line.text[start:end]
    text = raw.strip()
    if not text:
        return None
    leading = len(raw) - len(raw.lstrip())
    trailing = len(raw.rstrip())
    actual_start = start + leading
    actual_end = start + trailing
    segments = _segments_for_slice(line.segments, actual_start, actual_end)
    return TextLine(
        text=text,
        color=line.color,
        size=line.size,
        segments=segments,
        size_explicit=line.size_explicit,
    )


def wrap_text_lines(lines, font_path, max_width):
    """Wrap every logical line to the safe width, preserving color segments."""
    result = []
    for line in lines or []:
        measure(font_path, [line])
        width = line.width_px
        if width <= max_width:
            result.append(line)
            continue
        for start, end in _wrapped_ranges(
                line.text, font_path, line.size, max_width, line.segments):
            sliced = _line_slice(line, start, end)
            if sliced:
                result.append(sliced)
    return measure(font_path, result)


def _ellipsis_line(line, font_path, max_width):
    """Trim one line and append an ellipsis without crossing max_width."""
    suffix = " …"
    text = line.text.strip()
    font = ImageFont.truetype(font_path, line.size)
    while text and int(round(font.getlength(text + suffix))) > max_width:
        text = text[:-1].rstrip()
    if not text:
        text = "…"
        suffix = ""
    visible = text + suffix
    segments = _segments_for_slice(line.segments, 0, len(text))
    if segments:
        segments.append((suffix, line.color))
    else:
        segments = [(visible, line.color)]
    return TextLine(
        text=visible,
        color=line.color,
        size=line.size,
        segments=[(piece, color) for piece, color in segments if piece],
        size_explicit=line.size_explicit,
    )


def truncate_text_lines(lines, max_lines, font_path, max_width):
    """Keep a block inside a line budget and make truncation explicit."""
    if max_lines <= 0:
        return []
    if len(lines) <= max_lines:
        return list(lines)
    kept = list(lines[:max_lines])
    kept[-1] = _ellipsis_line(kept[-1], font_path, max_width)
    return measure(font_path, kept)


def fit_text_blocks(top_lines, bot_lines, canvas_w, canvas_h, content_w, content_h,
                    font_path, gap, spacing, safe, min_size=28, text_padding=0):
    """Fit both text blocks to safe zones before creating the final Layout.

    The function first wraps long lines, then progressively reduces the
    requested sizes only if the two blocks leave no vertical corridor for the
    video. As a final guard it truncates with an ellipsis. This makes the safe
    zone a hard invariant for long user/provider copy instead of an exception
    that can reach FFmpeg or a caption drawn outside the canvas.
    """
    raw_top = deepcopy(top_lines or [])
    raw_bot = deepcopy(bot_lines or [])
    padding = max(0, int(text_padding))
    max_width = (
        canvas_w - int(canvas_w * safe["left_f"])
        - int(canvas_w * safe["right_f"]) - 2 * padding
    )
    if max_width <= 0:
        raise ValueError("La zona segura no deja ancho para el texto")
    min_size = max(1, int(min_size))
    all_sizes = [line.size for line in raw_top + raw_bot]
    largest = max(all_sizes or [min_size])
    min_ratio = min(1.0, min_size / max(1, largest))
    ratios = [1.0 - (0.05 * index) for index in range(13)]
    if min_ratio not in ratios:
        ratios.append(min_ratio)
    ratios = sorted({max(min_ratio, ratio) for ratio in ratios}, reverse=True)

    def scaled(lines, ratio):
        result = deepcopy(lines)
        for line in result:
            line.size = max(min_size, int(round(line.size * ratio)))
        return result

    def attempt(ratio, top_limit=None, bot_limit=None):
        top = wrap_text_lines(scaled(raw_top, ratio), font_path, max_width)
        bot = wrap_text_lines(scaled(raw_bot, ratio), font_path, max_width)
        if top_limit is not None:
            top = truncate_text_lines(top, top_limit, font_path, max_width)
        if bot_limit is not None:
            bot = truncate_text_lines(bot, bot_limit, font_path, max_width)
        return make_layout(top, bot)

    def make_layout(top, bot):
        try:
            layout = Layout(
                canvas_w, canvas_h, content_w, content_h, top, bot,
                gap=gap, spacing=spacing, font_path=font_path,
                safe=safe, text_padding=padding,
            )
        except ValueError:
            return None
        return top, bot, layout

    for ratio in ratios:
        result = attempt(ratio)
        if result is not None:
            return result

    # If both blocks are still too tall, preserve as many wrapped lines as the
    # safe corridor can hold and mark the cut. Prefer keeping both blocks.
    minimum_total = (1 if raw_top else 0) + (1 if raw_bot else 0)
    min_top_lines = wrap_text_lines(scaled(raw_top, min_ratio), font_path, max_width)
    min_bot_lines = wrap_text_lines(scaled(raw_bot, min_ratio), font_path, max_width)
    widest_top = len(min_top_lines)
    widest_bot = len(min_bot_lines)
    min_font = ImageFont.truetype(font_path, min_size)
    min_line_height = max(1, min_font.getbbox("Ag")[3] - min_font.getbbox("Ag")[1])
    safe_height = (canvas_h - int(canvas_h * safe["bottom_f"])
                   - padding - (int(canvas_h * safe["top_f"]) + padding))
    # Conservative maximum number of visual rows available when the video has
    # already reached its smallest useful size. This prevents a huge paragraph
    # from making the fallback loop quadratic.
    max_total = max(
        minimum_total,
        (max(1, safe_height - 2 * gap - 2 + 2 * spacing)
         // max(1, min_line_height + spacing)),
    )
    for total in range(min(widest_top + widest_bot, max_total), minimum_total - 1, -1):
        top_min = 1 if raw_top else 0
        bot_min = 1 if raw_bot else 0
        for top_limit in range(min(widest_top, total), top_min - 1, -1):
            bot_limit = total - top_limit
            if bot_limit < bot_min or bot_limit > widest_bot:
                continue
            top = truncate_text_lines(min_top_lines, top_limit, font_path, max_width)
            bot = truncate_text_lines(min_bot_lines, bot_limit, font_path, max_width)
            result = make_layout(top, bot)
            if result is not None:
                return result
    raise ValueError("El texto no cabe en la zona segura ni con ajuste automático")
