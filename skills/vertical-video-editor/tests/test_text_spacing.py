#!/usr/bin/env python3
"""test_text_spacing.py - Simetria de gaps y clamp de safe zone."""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import calculate_layout as cl
import render_video

FONT = render_video.resolve_font("Barlow:style=ExtraBold Italic")


def layout_for(src_w, src_h, canvas=(1080, 1920)):
    fs = cl.scale_1080(60, canvas[1])
    gap = cl.scale_1080(32, canvas[1])
    top = cl.parse_text_spec("LINEA UNO|FFFFFF\nLINEA DOS|FF39D7", default_size=fs)
    bot = cl.parse_text_spec("TEXTO BAJO|42E8FF", default_size=fs)
    return cl.Layout(canvas[0], canvas[1], src_w, src_h, top, bot, gap=gap,
                     spacing=cl.scale_1080(18, canvas[1]), font_path=FONT)


class SpacingTest(unittest.TestCase):
    def test_equal_16_9(self):
        lay = layout_for(1920, 1080)
        self.assertEqual(lay.gap_top, lay.gap_bot)
        self.assertEqual(lay.gap_top, 32)
    def test_equal_4_3(self):
        lay = layout_for(960, 720)
        self.assertEqual(lay.gap_top, lay.gap_bot)

    def test_equal_square(self):
        lay = layout_for(720, 720)
        self.assertEqual(lay.gap_top, lay.gap_bot)

    def test_equal_1_1_at_720(self):
        lay = layout_for(720, 720, canvas=(720, 1280))
        self.assertEqual(lay.gap_top, lay.gap_bot)
        self.assertGreaterEqual(lay.top_block.top, lay.safe_limits["top"])
        self.assertLessEqual(lay.bot_block.bottom, lay.safe_limits["bottom"])


if __name__ == "__main__":
    unittest.main()
