#!/usr/bin/env python3
"""Pruebas de validación de la copia de entrega para Telegram."""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import prepare_telegram as pt


def _probe(duration):
    return {
        "streams": [
            {
                "codec_type": "video",
                "width": 1080,
                "height": 1920,
                "sample_aspect_ratio": "1:1",
                "codec_name": "h264",
            },
            {"codec_type": "audio", "codec_name": "aac"},
        ],
        "format": {"duration": str(duration)},
    }


class TelegramPreparationTest(unittest.TestCase):
    def test_rejects_delivery_copy_that_loses_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            source = os.path.join(directory, "source.mp4")
            target = os.path.join(directory, "telegram.mp4")
            with open(source, "wb") as handle:
                handle.write(b"valid fixture")
            with patch.object(pt, "probe", side_effect=[_probe(2.0), _probe(1.0)]):
                with self.assertRaisesRegex(RuntimeError, "perdió duración"):
                    pt.prepare_file(source, target)

    def test_accepts_delivery_copy_with_matching_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            source = os.path.join(directory, "source.mp4")
            target = os.path.join(directory, "telegram.mp4")
            with open(source, "wb") as handle:
                handle.write(b"valid fixture")
            with patch.object(pt, "probe", side_effect=[_probe(2.0), _probe(2.05)]):
                report = pt.prepare_file(source, target)
            self.assertEqual(report["mode"], "copied")
            self.assertEqual(report["duration"], "2.05")


if __name__ == "__main__":
    unittest.main()
