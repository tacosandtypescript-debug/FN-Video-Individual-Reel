import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import telegram_bot as tb
import video_command
import render_video
import prepare_telegram
from video_job import VideoJob
from PIL import Image


class TelegramBotTest(unittest.TestCase):
    def test_editorial_style_reads_preset_from_project_root(self):
        with tempfile.TemporaryDirectory() as directory:
            preset = Path(directory) / "references" / "presets"
            preset.mkdir(parents=True)
            (preset / "custom.json").write_text(
                json.dumps({
                    "editorial_colors": {
                        "palette": ["123456"],
                        "max_highlights": 1,
                    }
                }),
                encoding="utf-8",
            )
            with patch.object(tb, "ROOT", Path(directory)):
                self.assertEqual(tb._editorial_style("custom"), (("123456",), 1))

    def test_caption_contains_hashtag(self):
        proposal = tb.EditorialProposal(
            "https://x.com/post/1",
            top=["NUEVO EVENTO|FFFFFF"],
            bottom=["EN FORTNITE|FFFFFF"],
        )
        self.assertIn("#Fortnite", tb._caption(proposal))

    def test_thumbnail_is_jpeg_and_within_telegram_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            source = os.path.join(directory, "frame.png")
            target = os.path.join(directory, "thumbnail.jpg")
            Image.new("RGB", (1080, 1920), (24, 42, 80)).save(source)
            prepare_telegram.prepare_thumbnail(source, target)
            with Image.open(target) as thumbnail:
                self.assertEqual(thumbnail.format, "JPEG")
                self.assertLessEqual(max(thumbnail.size), 320)
            self.assertLess(os.path.getsize(target), 200_000)

    def test_store_isolates_and_reloads_job(self):
        with tempfile.TemporaryDirectory() as directory:
            store = tb.JobStore(directory)
            job = store.create(100, 200, "url")
            loaded = store.load(job.job_id)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.job_id, job.job_id)
            self.assertEqual(os.path.dirname(loaded.job_path), loaded.workdir)
            self.assertNotEqual(loaded.workdir, directory)

    def test_provider_returns_three_grounded_distinct_options(self):
        job = VideoJob(
            job_id="a" * 32,
            source_url="https://x.com/post/1",
            title="MIRA una jugada | Fortnite",
            description="El jugador consigue una victoria. #fortnite",
            author="Isaac",
            platform="x",
            date="20260906",
            workdir="/tmp/job-a",
        )
        proposals = tb.MetadataProposalProvider().build(job)
        self.assertEqual(len(proposals.options), 3)
        self.assertIsNone(proposals.selected)
        self.assertEqual({option.source_url for option in proposals.options}, {job.source_url})
        self.assertEqual(len({" ".join(option.top + option.bottom) for option in proposals.options}), 3)
        self.assertTrue(all(option.status == "proposed" for option in proposals.options))

    def test_callback_data_stays_within_telegram_limit(self):
        value = f"vve:{'a' * 32}:2"
        self.assertLessEqual(len(value.encode("utf-8")), 64)
        self.assertRegex(value, tb.CALLBACK_RE)

    def test_display_keeps_text_after_colored_segment(self):
        proposal = tb.EditorialProposal(
            source_url="https://x.com/post/1",
            top=["NUEVO {EVENTO|42E8FF} HOY|FFFFFF"],
            bottom=["EN FORTNITE|FFFFFF"],
        )
        rendered = tb.ep.display(proposal)
        self.assertIn("NUEVO EVENTO HOY", rendered)

    def test_auto_title_sanitizes_spec_delimiters_and_keeps_safe_lines(self):
        font = render_video.resolve_font("Barlow:style=ExtraBold Italic")
        lines = video_command.auto_split_title(
            font,
            "Fortnite | una temporada con un título demasiado largo para una sola pantalla",
            1080,
            60,
        )
        self.assertLessEqual(len(lines), 8)
        self.assertTrue(all("|" not in line and "{" not in line for line in lines))


if __name__ == "__main__":
    unittest.main()
