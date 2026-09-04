#!/usr/bin/env python3
"""test_aspect_ratio.py - El layout funciona para multiples AR sin hardcode."""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import calculate_layout as cl

FONT = "/home/isaac/.local/share/fonts/Barlow-ExtraBoldItalic.ttf"


def make_layout(cw, ch, src_w, src_h):
    top = cl.parse_text_spec("LINEA UNO|FFFFFF\nLINEA DOS|FF39D7", default_size=60)
    bot = cl.parse_text_spec("TEXTO BAJO|42E8FF", default_size=60)
    return cl.Layout(cw, ch, src_w, src_h, top, bot, gap=cl.scale_1080(32, ch),
                     spacing=cl.scale_1080(18, ch), font_path=FONT, safe={
                         "left_f": 0.056, "right_f": 0.056, "top_f": 0.0725, "bottom_f": 0.174})


class AspectRatioTest(unittest.TestCase):
    def test_wide_full_width(self):
        lay = make_layout(1080, 1920, 1920, 1080)
        self.assertEqual(lay.video.w, 1080)
        self.assertEqual(lay.video.h, 608)
        self.assertEqual(lay.video.x, 0)

    def test_four_three_full_width(self):
        lay = make_layout(1080, 1920, 960, 720)
        self.assertEqual(lay.video.w, 1080)
        self.assertAlmostEqual(lay.video.h, 810, delta=2)

    def test_square_contains(self):
        lay = make_layout(1080, 1920, 720, 720)
        self.assertEqual(lay.video.w, 1080)
        self.assertEqual(lay.video.h, 1080)
        self.assertTrue(lay.video.y > 0)

    def test_scaled_canvas_proportional(self):
        lay = make_layout(720, 1280, 1920, 1080)
        self.assertEqual(lay.video.w, 720)
        self.assertEqual(lay.gap, cl.scale_1080(32, 1280))

    def test_rejects_text_that_cannot_fit(self):
        top = cl.parse_text_spec("LINEA|FFFFFF|1600")
        bot = cl.parse_text_spec("CONTEXTO|FFFFFF")
        with self.assertRaises(ValueError):
            cl.Layout(1080, 1920, 1080, 1920, top, bot,
                      gap=32, spacing=18, font_path=FONT)

    def test_rejects_invalid_text_color(self):
        with self.assertRaises(ValueError):
            cl.parse_text_spec("LINEA|NOPE")


if __name__ == "__main__":
    unittest.main()
