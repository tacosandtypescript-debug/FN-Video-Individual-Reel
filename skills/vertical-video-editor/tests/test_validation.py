#!/usr/bin/env python3
"""Pruebas de validación de integridad del render."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import validate_render as vr


class RenderValidationTest(unittest.TestCase):
    @patch("validate_render.validate_output")
    def test_accepts_duration_within_tolerance(self, validate_output):
        validate_output.return_value = {"format": {"duration": "1.050"}}
        result = vr.validate_complete_render("output.mp4", 1080, 1920, 1.0)
        self.assertEqual(result["format"]["duration"], "1.050")

    @patch("validate_render.validate_output")
    def test_rejects_truncated_duration(self, validate_output):
        validate_output.return_value = {"format": {"duration": "0.700"}}
        with self.assertRaisesRegex(RuntimeError, "Render incompleto"):
            vr.validate_complete_render("output.mp4", 1080, 1920, 1.0)


if __name__ == "__main__":
    unittest.main()
