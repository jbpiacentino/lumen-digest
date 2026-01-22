import os
import sys
import unittest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from app.main import extract_full_text_from_html


class FullTextExtractionTests(unittest.TestCase):
    def _load_fixture(self, name):
        path = os.path.join(os.path.dirname(__file__), "fixtures", name)
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    def test_extracts_main_article_text(self):
        html = self._load_fixture("sample_article_one.html")
        text = extract_full_text_from_html(html)
        self.assertIn("City council approves new waterfront plan.", text)
        self.assertIn("The project will unfold in three phases.", text)

    def test_ignores_nav_and_footer(self):
        html = self._load_fixture("sample_article_two.html")
        text = extract_full_text_from_html(html)
        self.assertIn("Researchers report a new battery chemistry.", text)
        self.assertIn("The team expects pilots within 18 months.", text)


if __name__ == "__main__":
    unittest.main()
