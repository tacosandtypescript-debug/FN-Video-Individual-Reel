#!/usr/bin/env python3
"""Pruebas de normalización de URL y argumentos del resolvedor."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import video_resolver as vr


class ResolverTest(unittest.TestCase):
    def test_detect_platform_uses_hostname(self):
        self.assertEqual(vr.detect_platform("https://x.com/user/status/1"), "x")
        self.assertEqual(vr.detect_platform("https://x.com.evil.test/post"), "unknown")
        self.assertEqual(vr.detect_platform("https://cdn.test/video.mp4?token=1"), "direct")
        self.assertEqual(vr.detect_platform("ftp://x.com/video"), "invalid")

    @patch("video_resolver.subprocess.run")
    def test_probe_disables_playlists(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = '{"title":"demo"}'
        run.return_value.stderr = ""
        meta, browser, reason = vr.probe_remote("https://x.com/user/status/1")
        args = run.call_args.args[0]
        self.assertIn("--no-playlist", args)
        self.assertFalse(browser)
        self.assertEqual(reason, "")
        self.assertEqual(meta["title"], "demo")


if __name__ == "__main__":
    unittest.main()
