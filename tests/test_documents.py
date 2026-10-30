import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import pymupdf

from bok_documents import load_pdf_pages, search_documents

ROOT = Path(__file__).resolve().parents[1]


def write_pdf(path, texts):
    with pymupdf.open() as document:
        for text in texts:
            page = document.new_page()
            page.insert_text((72, 72), text)
        document.save(path)


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)

    def cli(self, *arguments, cwd=ROOT):
        return subprocess.run([sys.executable, str(ROOT / "bok_cli.py"), *arguments],
                              cwd=cwd, text=True, capture_output=True, timeout=20)

    def test_real_pdf_cli_preserves_filename_page_and_text(self):
        write_pdf(self.folder / "policy.pdf", ["unrelated page", "Rate policy has changed."])
        result = self.cli("search", "RATE policy", "--data-dir", str(self.folder), "--limit", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["method"], "text")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(len(payload["results"]), 1)
        hit = payload["results"][0]
        self.assertEqual(hit["source"], "policy.pdf")
        self.assertEqual(hit["page"], 2)
        self.assertIn("Rate policy has changed.", hit["text"])
        self.assertIsNone(hit["published_at"])

    def test_empty_corpus_and_no_matches_are_distinct(self):
        empty = self.cli("search", "policy", "--data-dir", str(self.folder))
        self.assertEqual(empty.returncode, 0)
        self.assertEqual(json.loads(empty.stdout)["status"], "empty_corpus")
        write_pdf(self.folder / "other.pdf", ["unrelated"])
        absent = self.cli("search", "policy", "--data-dir", str(self.folder))
        self.assertEqual(absent.returncode, 0)
        payload = json.loads(absent.stdout)
        self.assertEqual(payload["status"], "no_matches")
        self.assertEqual(payload["results"], [])

    def test_ranking_is_by_distinct_terms_then_filename_and_page(self):
        write_pdf(self.folder / "b.PDF", ["rate rate", "rate policy"])
        write_pdf(self.folder / "a.pdf", ["policy rate", "policy rate"])
        result = search_documents("rate policy rate", self.folder, 3)
        self.assertEqual([(hit.source, hit.page) for hit in result.results],
                         [("a.pdf", 1), ("a.pdf", 2), ("b.PDF", 2)])

    def test_bad_inputs_use_json_stderr_and_no_stdout(self):
        for args in ([], ["search"], ["search", "   "], ["search", "rate", "--limit", "0"],
                     ["search", "rate", "--limit", "x"], ["search", "rate", "--unknown"],
                     ["search", "rate", "--data-dir", str(self.folder / "missing")]):
            with self.subTest(args=args):
                result = self.cli(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                payload = json.loads(result.stderr)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["error"]["code"], "invalid_input")

    def test_broken_pdf_fails_without_partial_results(self):
        write_pdf(self.folder / "a.pdf", ["rate policy"])
        (self.folder / "broken.pdf").write_bytes(b"not a PDF")
        result = self.cli("search", "rate", "--data-dir", str(self.folder))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("broken.pdf", json.loads(result.stderr)["error"]["message"])

    def test_repaired_pdf_diagnostics_do_not_pollute_json(self):
        path = self.folder / "repaired.pdf"
        write_pdf(path, ["rate policy"])
        original = path.read_bytes()
        path.write_bytes(original[:original.rfind(b"startxref")] + b"startxref\n0\n%%EOF\n")
        result = self.cli("search", "rate", "--data-dir", str(self.folder))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(json.loads(result.stdout)["results"][0]["source"], "repaired.pdf")

    def test_default_corpus_is_independent_of_working_directory(self):
        result = self.cli("search", "생산성", "--limit", "1", cwd=self.folder)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "ok")

    def test_loader_preserves_blank_pages_and_ignores_non_pdfs(self):
        write_pdf(self.folder / "a.pdf", ["", "rate policy"])
        (self.folder / "note.txt").write_text("rate policy")
        pages = load_pdf_pages(self.folder)
        self.assertEqual([page.page for page in pages], [1, 2])
        self.assertEqual(pages[0].text, "")


if __name__ == "__main__":
    unittest.main()
