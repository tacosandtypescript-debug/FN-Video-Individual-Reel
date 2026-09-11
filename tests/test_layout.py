#!/usr/bin/env python3
"""test_layout.py - Bounding box de bloques y anclaje al video."""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import calculate_layout as cl

FONT = "/home/isaac/.local/share/fonts/Barlow-ExtraBoldItalic.ttf"


def make():
    top = cl.parse_text_spec("TRAILER OFICIAL|FFFFFF\nLEGO FORTNITE X BATMAN|FF39D7")
    bot = cl.parse_text_spec("LLEGA EL 3 DE SEPTIEMBRE|42E8FF")
    return cl.Layout(1080, 1920, 1280, 720, top, bot, gap=32, spacing=18,
                     font_path=FONT)


class LayoutTest(unittest.TestCase):
    def test_anchored_to_video(self):
        lay = make()
        v = lay.video
        self.assertEqual(v.top - lay.top_block.bottom, lay.gap)
        self.assertEqual(lay.bot_block.top - v.bottom, lay.gap)

    def test_gaps_equal(self):
        lay = make()
        self.assertEqual(lay.gap_top, lay.gap_bot)

    def test_top_block_is_unit(self):
        lay = make()
        self.assertEqual(len(lay.top_block.lines), 2)
        self.assertGreaterEqual(lay.top_block.height, 2 * cl.glyph_h(60))
        self.assertTrue(lay.top_block.bottom <= lay.video.top - lay.gap)

    def test_text_widths_measured(self):
        lay = make()
        for ln in lay.top_block.lines:
            self.assertGreater(ln.width_px, 0)

    def test_short_title_can_be_larger_than_support_copy(self):
        top = cl.parse_text_spec("NUEVO EVENTO|FFFFFF")
        bottom = cl.parse_text_spec("EN FORTNITE|FFFFFF")
        safe_width = 1080 - int(1080 * 0.056) * 2 - 10
        cl.enlarge_short_lines(top, FONT, safe_width, 60, 84, 0.82)
        cl.enlarge_short_lines(bottom, FONT, safe_width, 60, 68, 0.82)
        self.assertGreater(top[0].size, bottom[0].size)

    def test_render_lines_are_uppercase_without_diacritics(self):
        lines = cl.parse_text_spec("Código: más acción|FFFFFF")
        cl.normalize_copy_lines(lines)
        self.assertEqual(lines[0].text, "CODIGO: MAS ACCION")
        self.assertNotRegex(lines[0].text, r"[áéíóúÁÉÍÓÚüÜ]")

    def test_long_copy_is_wrapped_inside_safe_zone(self):
        safe = {"left_f": 0.056, "right_f": 0.056,
                "top_f": 0.0725, "bottom_f": 0.174}
        top = cl.parse_text_spec(
            "ESTE ES UN TITULO MUY LARGO QUE DEBE QUEDAR DENTRO DEL MARGEN SEGURO "
            "CON DATOS IMPORTANTES|FFFFFF"
        )
        bottom = cl.parse_text_spec(
            "Y ESTE ES EL TEXTO INFERIOR CON MUCHA INFORMACION PARA PROBAR EL AJUSTE "
            "AUTOMATICO|42E8FF"
        )
        top, bottom, lay = cl.fit_text_blocks(
            top, bottom, 1080, 1920, 1920, 1080, FONT,
            gap=32, spacing=18, safe=safe, min_size=30, text_padding=5,
        )
        self.assertGreater(len(top), 1)
        self.assertGreater(len(bottom), 1)
        self.assertGreaterEqual(lay.top_block.top, lay.safe_limits["top"])
        self.assertLessEqual(lay.bot_block.bottom, lay.safe_limits["bottom"])
        safe_width = lay.safe_limits["right"] - lay.safe_limits["left"]
        for block in (lay.top_block, lay.bot_block):
            for line in block.lines:
                self.assertLessEqual(line.width_px, safe_width)

    def test_extreme_copy_is_truncated_within_safe_zone(self):
        safe = {"left_f": 0.056, "right_f": 0.056,
                "top_f": 0.0725, "bottom_f": 0.174}
        repeated = " ".join(["FORTNITE"] * 600)
        top = cl.parse_text_spec(repeated + "|FFFFFF", default_size=84)
        bottom = cl.parse_text_spec("TEMPORADA NUEVA|FFFFFF", default_size=84)
        top, bottom, lay = cl.fit_text_blocks(
            top, bottom, 1080, 1920, 1920, 1080, FONT,
            gap=32, spacing=18, safe=safe, min_size=30, text_padding=5,
        )
        self.assertTrue(any(line.text.endswith("…") for line in top))
        self.assertLessEqual(lay.top_block.bottom, lay.video.top - lay.gap)
        self.assertLessEqual(lay.bot_block.bottom, lay.safe_limits["bottom"])


if __name__ == "__main__":
    unittest.main()
