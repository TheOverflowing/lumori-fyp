"""Reproducible text-block extraction; no network access or new dependencies."""
from html.parser import HTMLParser
import re

class ParagraphParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nodes = []
        self.pending = None

    def handle_starttag(self, tag, attrs):
        if tag in ('p', 'h1', 'h2', 'h3', 'h4'):
            if self.pending:
                self.finish()
            self.pending = [tag, []]

    def handle_endtag(self, tag):
        if self.pending and tag == self.pending[0]:
            self.finish()

    def handle_data(self, data):
        if self.pending:
            self.pending[1].append(data)

    def finish(self):
        tag, parts = self.pending
        text = re.sub(r'\s+', ' ', ''.join(parts)).strip()
        self.pending = None
        if text:
            self.nodes.append({'tag': tag, 'text': text})
