import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec('apted'), 'isolated parsing metric dependency')
class TedsTests(unittest.TestCase):
    def setUp(self):
        from scripts.parsing_teds import teds
        self.score = teds
        self.table = '<table><tr><td>A</td><td>B</td></tr></table>'

    def test_identical_and_wrapper_normalization(self):
        self.assertEqual(self.score(self.table, self.table), 1)
        equivalent = '<html><body><table><thead><tr><th>A</th><th>B</th></tr></thead></table></body></html>'
        self.assertEqual(self.score(equivalent, self.table), 1)

    def test_content_vs_structure(self):
        changed = self.table.replace('A', 'C')
        self.assertLess(self.score(changed, self.table), 1)
        self.assertEqual(self.score(changed, self.table, True), 1)

    def test_span_and_missing(self):
        self.assertLess(self.score(self.table.replace('<td>A', '<td colspan="2">A'), self.table, True), 1)
        self.assertEqual(self.score('', self.table), 0)
        self.assertEqual(self.score('plain text', self.table), 0)
        self.assertEqual(self.score('<table></table>', '<table></table>'), 0)
