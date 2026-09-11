import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import telegram_bot as tb
import video_command
from video_job import VideoJob


class TelegramBotTest(unittest.TestCase):
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
        font = "/home/isaac/.local/share/fonts/Barlow-ExtraBoldItalic.ttf"
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
