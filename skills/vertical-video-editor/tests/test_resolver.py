#!/usr/bin/env python3
"""Pruebas de normalización de URL y argumentos del resolvedor."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import video_resolver as vr


class ResolverTest(unittest.TestCase):
    def test_detect_platform_uses_hostname(self):
        self.assertEqual(vr.detect_platform("https://x.com/user/status/1"), "x")
        self.assertEqual(vr.detect_platform("https://x.com.evil.test/post"), "unknown")
        self.assertEqual(vr.detect_platform("https://cdn.test/video.mp4?token=1"), "direct")
        self.assertEqual(vr.detect_platform("ftp://x.com/video"), "invalid")
        self.assertEqual(vr.detect_platform("http://127.0.0.1/video.mp4"), "invalid")

    def test_validate_url_rejects_local_hosts(self):
        with self.assertRaises(vr.ResolverError) as context:
            vr.validate_url("http://10.0.0.5/video.mp4")
        self.assertEqual(context.exception.kind, "unsafe_url")

    def test_formats_download_size_for_ytdlp(self):
        self.assertEqual(vr._format_max_filesize(500 * 1024 * 1024), "500M")
        self.assertEqual(vr._format_max_filesize(512 * 1024), "0.5M")

    @patch("video_resolver._ytdlp")
    def test_download_passes_max_filesize_to_ytdlp(self, ytdlp):
        with tempfile.TemporaryDirectory() as directory:
            def fake_ytdlp(args):
                Path(directory, "original.mp4").write_bytes(b"fixture")
                return SimpleNamespace(returncode=0, stderr="")

            ytdlp.side_effect = fake_ytdlp
            path, _ = vr.download(
                "https://x.com/user/status/1",
                dest_dir=directory,
                max_bytes=500 * 1024 * 1024,
            )
            args = ytdlp.call_args.args[0]
            self.assertEqual(args[args.index("--max-filesize") + 1], "500M")
            self.assertTrue(path.endswith("original.mp4"))

    @patch("video_resolver._ytdlp")
    def test_probe_disables_playlists(self, ytdlp):
        ytdlp.return_value.returncode = 0
        ytdlp.return_value.stdout = '{"title":"demo"}'
        ytdlp.return_value.stderr = ""
        meta, browser, reason = vr.probe_remote("https://x.com/user/status/1")
        args = ytdlp.call_args.args[0]
        self.assertIn("--no-playlist", args)
        self.assertFalse(browser)
        self.assertEqual(reason, "")
        self.assertEqual(meta["title"], "demo")


if __name__ == "__main__":
    unittest.main()
