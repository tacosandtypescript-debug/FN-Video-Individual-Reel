#!/usr/bin/env python3
"""test_layout.py - Bounding box de bloques y anclaje al video."""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
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


if __name__ == "__main__":
    unittest.main()
