import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import editorial_proposal as ep
from editorial_proposal import EditorialProposal, EditorialProposalSet


class EditorialProposalTest(unittest.TestCase):
    def test_requires_approval_before_specs(self):
        p = EditorialProposal("https://x.com/post", top=["NUEVO EVENTO|00E5FF"],
                              bottom=["LLEGA MAÑANA|FFFFFF"])
        with self.assertRaises(PermissionError):
            p.to_specs()
        p.approve()
        top, bottom = p.to_specs()
        self.assertEqual(top, "NUEVO EVENTO|00E5FF")
        self.assertEqual(bottom, "LLEGA MANANA|FFFFFF")

    def test_rejects_invalid_color(self):
        p = EditorialProposal("https://x.com/post", top=["HOLA|NOPE"],
                              bottom=["MUNDO|FFFFFF"])
        with self.assertRaises(ValueError):
            p.validate()

    def test_three_options_selects_only_one(self):
        opts = [EditorialProposal("https://x.com/post", top=[f"OPCION {i}|FFFFFF"],
                                  bottom=["CONTEXTO|FFFFFF"]) for i in range(3)]
        choices = EditorialProposalSet("job.json", opts)
        picked = choices.choose(1)
        self.assertEqual(picked.status, "approved")
        self.assertEqual(choices.selected, 1)
        self.assertEqual([x.status for x in choices.options],
                         ["proposed", "approved", "proposed"])

    def test_colored_word_markup_is_preserved(self):
        p = EditorialProposal("https://x.com/post",
                              top=["REGRESA LA {TEMPORADA|B84DFF}|FFFFFF"],
                              bottom=["MAÑANA EN FORTNITE|FFFFFF"], status="approved")
        top, _ = p.to_specs()
        self.assertEqual(top, "REGRESA LA {TEMPORADA|B84DFF}|FFFFFF")

    def test_rejects_multiword_accent(self):
        p = EditorialProposal("https://x.com/post",
                              top=["{DOS PALABRAS|B84DFF}|FFFFFF"],
                              bottom=["CONTEXTO|FFFFFF"])
        with self.assertRaises(ValueError):
            p.validate()

    def test_limits_accent_colors(self):
        p = EditorialProposal(
            "https://x.com/post",
            top=["{ALFA|B84DFF} {BETA|42E8FF} {GAMMA|FFDD00}|FFFFFF"],
            bottom=["{DELTA|FF39D7} {EPSILON|00FF00}|FFFFFF"],
        )
        with self.assertRaises(ValueError):
            p.validate()

    def test_semantic_colorizer_skips_stopwords_and_spreads_accents(self):
        top, bottom, colors = ep.semantic_colorize_blocks(
            ["LA NUEVA TEMPORADA LLEGA EN FORTNITE|FFFFFF"],
            ["CON MÁS XP PARA LOS JUGADORES|FFFFFF"],
        )
        rendered = " ".join(top + bottom)
        self.assertIn("{NUEVA|", rendered)
        self.assertIn("{TEMPORADA|", rendered)
        self.assertIn("{FORTNITE|", rendered)
        self.assertIn("{XP|", rendered)
        for stopword in ("LA", "EN", "CON", "MÁS", "PARA", "LOS"):
            self.assertNotIn("{" + stopword + "|", rendered)
        self.assertLessEqual(len(colors), ep.MAX_ACCENT_COLORS)
        self.assertGreaterEqual(len(colors), 3)
        self.assertNotIn("{MAS|", " ".join(top + bottom))

    def test_overlay_copy_is_uppercase_without_diacritics(self):
        top, bottom, _ = ep.semantic_colorize_blocks(
            ["Código de creador|FFFFFF"],
            ["Más acción mañana|FFFFFF"],
        )
        rendered = " ".join(ep._plain_line(line) for line in top + bottom)
        self.assertIn("CODIGO DE CREADOR", rendered)
        self.assertIn("MAS ACCION MANANA", rendered)
        self.assertNotRegex(rendered, r"[áéíóúÁÉÍÓÚüÜ]")

    def test_rejects_explicit_stopword_accent(self):
        p = EditorialProposal(
            "https://x.com/post",
            top=["{DE|B84DFF} FORTNITE|FFFFFF"],
            bottom=["NUEVA TEMPORADA|FFFFFF"],
        )
        with self.assertRaisesRegex(ValueError, "relleno"):
            p.validate()

    def test_rejects_generic_hook(self):
        p = EditorialProposal("https://x.com/post", top=["MIRA EL GLITCH|FFFFFF"],
                              bottom=["EN FORTNITE|FFFFFF"])
        with self.assertRaises(ValueError):
            p.validate()

    def test_rejects_hashtag_or_url_in_title(self):
        p = EditorialProposal("https://x.com/post", top=["NUEVO GLITCH|FFFFFF"],
                              bottom=["#FORTNITE https://example.com|FFFFFF"])
        with self.assertRaises(ValueError):
            p.validate()

    def test_set_rejects_duplicate_proposals(self):
        opts = [EditorialProposal("https://x.com/post", top=["MISMO HECHO|FFFFFF"],
                                  bottom=["MISMO DATO|FFFFFF"]) for _ in range(3)]
        with self.assertRaises(ValueError):
            EditorialProposalSet("job.json", opts).validate()

    def test_round_trip(self):
        p = EditorialProposal("https://x.com/post", original_title="Original",
                              top=["TEXTO ARRIBA|FFFFFF"],
                              bottom=["TEXTO ABAJO|FFDD00"], status="approved")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "proposal.json")
            p.save(path)
            got = EditorialProposal.load(path)
            self.assertEqual(got.to_specs(), ("TEXTO ARRIBA|FFFFFF", "TEXTO ABAJO|FFDD00"))


if __name__ == "__main__":
    unittest.main()
