#!/usr/bin/env python3
"""test_background.py - El fondo usa cover; prohibido stretch/downscale-extremo."""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import build_background as bb


class BackgroundTest(unittest.TestCase):
    def test_cover_preserves_ar(self):
        sw, sh = bb.cover_dims(1280, 720, 1080, 1920)
        self.assertAlmostEqual(sw / sh, 1280 / 720, delta=0.01)
        self.assertGreaterEqual(sw, 1080)
        self.assertGreaterEqual(sh, 1920)

    def test_chain_has_increase_and_crop(self):
        chain = bb.bg_chain(1080, 1920, 16)
        self.assertIn("force_original_aspect_ratio=increase", chain)
        self.assertIn("crop=1080:1920:(iw-1080)/2:(ih-1920)/2", chain)
        self.assertIn("gblur=sigma=16", chain)

    def test_no_bare_stretch(self):
        chain = bb.bg_chain(1080, 1920, 16)
        self.assertNotRegex(chain, r"scale=1080:1920[,;]")

    def test_no_tiny_downscale(self):
        self.assertNotIn("scale_cuda=96", bb.bg_chain(1080, 1920, 16))

    def test_precrop_cover_avoids_overscale_and_keeps_centered_ar(self):
        chain = bb.bg_chain(
            1080,
            1920,
            16,
            src_w=1920,
            src_h=1080,
            mode="precrop",
        )
        self.assertIn("crop=608:1080:(iw-608)/2:(ih-1080)/2", chain)
        self.assertIn("scale=1080:1920", chain)
        self.assertNotIn("force_original_aspect_ratio=increase", chain)


if __name__ == "__main__":
    unittest.main()
