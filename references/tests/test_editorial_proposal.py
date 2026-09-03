import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
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
        self.assertEqual(bottom, "LLEGA MAÑANA|FFFFFF")

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
                              top=["REGRESA LA {TEMPORADA X|B84DFF}|FFFFFF"],
                              bottom=["MAÑANA EN FORTNITE|FFFFFF"], status="approved")
        top, _ = p.to_specs()
        self.assertEqual(top, "REGRESA LA {TEMPORADA X|B84DFF}|FFFFFF")

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
