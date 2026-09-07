#!/usr/bin/env python3
"""Pruebas de contrato del comando FFmpeg y de la salida."""
import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import build_ffmpeg_filter as bff
import calculate_layout as cl


FONT = "/home/isaac/.local/share/fonts/Barlow-ExtraBoldItalic.ttf"


class EncodingTest(unittest.TestCase):
    def make_layout(self):
        top = cl.parse_text_spec("TITULO|FFFFFF")
        bottom = cl.parse_text_spec("CONTEXTO|42E8FF")
        return cl.Layout(1080, 1920, 1920, 1080, top, bottom,
                         gap=32, spacing=18, font_path=FONT)

    def test_cpu_fallback_does_not_require_cuda(self):
        cmd, tmpdir, _ = bff.build(
            "input.mp4",
            {"width": 1920, "height": 1080},
            {"x": 0, "y": 0, "w": 1920, "h": 1080},
            self.make_layout(),
            "output.mp4",
            encode={"vcodec": "h264_nvenc", "cpu_vcodec": "libx264",
                    "cpu_preset": "fast", "pix_fmt": "yuv420p"},
            use_cuda=False,
        )
        try:
            self.assertNotIn("-hwaccel", cmd)
            self.assertIn("libx264", cmd)
            self.assertIn("-crf", cmd)
            self.assertTrue(any("setsar=1[out]" in item for item in cmd))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_nvenc_uses_preset_values(self):
        cmd, tmpdir, _ = bff.build(
            "input.mp4",
            {"width": 1920, "height": 1080},
            {"x": 0, "y": 0, "w": 1920, "h": 1080},
            self.make_layout(),
            "output.mp4",
            cq=19,
            encode={"vcodec": "h264_nvenc", "preset": "p4",
                    "pix_fmt": "yuv420p", "acodec": "aac",
                    "audio_bitrate": "128k"},
            use_cuda=True,
        )
        try:
            self.assertEqual(cmd[cmd.index("-preset") + 1], "p4")
            self.assertEqual(cmd[cmd.index("-cq") + 1], "19")
            self.assertEqual(cmd[cmd.index("-b:a") + 1], "128k")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_rounded_mask_uses_luminance_plane(self):
        cmd, tmpdir, _ = bff.build(
            "input.mp4",
            {"width": 1920, "height": 1080},
            {"x": 0, "y": 0, "w": 1920, "h": 1080},
            self.make_layout(),
            "output.mp4",
            encode={"vcodec": "libx264", "pix_fmt": "yuv420p"},
            use_cuda=False,
        )
        try:
            graph = cmd[cmd.index("-filter_complex") + 1]
            self.assertIn("color=c=black:s=1080x608", graph)
            self.assertIn("geq=lum='if(", graph)
            self.assertNotIn("geq=lum='255':a=", graph)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_text_watermark_is_centered_in_the_filter(self):
        cmd, tmpdir, _ = bff.build(
            "input.mp4",
            {"width": 1920, "height": 1080},
            {"x": 0, "y": 0, "w": 1920, "h": 1080},
            self.make_layout(),
            "output.mp4",
            watermark={"enabled": True, "text": "Código: khetzalgg", "font_size": 28},
            encode={"vcodec": "libx264", "pix_fmt": "yuv420p"},
            use_cuda=False,
        )
        try:
            graph = cmd[cmd.index("-filter_complex") + 1]
            self.assertNotIn("-loop", cmd)
            self.assertIn("watermark.txt", graph)
            self.assertIn("x='(w-text_w)/2'", graph)
            self.assertIn("fontcolor=0xFFFFFF@0.82", graph)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
