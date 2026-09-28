"""Project TEDS adaptation of IBM PubTabNet (Apache-2.0).

Copyright 2020 IBM. Original author: peter.zhong@au1.ibm.com.
Pinned original and license: docs/parsing/experiments/P4-candidate-expansion-20260918/research/pubtabnet/.
Changes: standalone implementation, pure Python Levenshtein, wrapper normalization,
th->td, strip thead/tbody/tfoot, clamp [0,1], invalid/empty table returns zero.
This is a project diagnostic, not the official OmniDocBench leaderboard metric.
"""
from apted import APTED, Config
from lxml import etree, html


def levenshtein(a, b):
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        new = [i]
        for j, y in enumerate(b, 1):
            new.append(min(new[-1] + 1, row[j] + 1, row[j-1] + (x != y)))
        row = new
    return row[-1]


class Node:
    def __init__(self, tag, colspan=None, rowspan=None, content=None):
        self.tag, self.colspan, self.rowspan, self.content = tag, colspan, rowspan, content
        self.children = []


class Costs(Config):
    def rename(self, a, b):
        if (a.tag, a.colspan, a.rowspan) != (b.tag, b.colspan, b.rowspan):
            return 1.0
        if a.tag == 'td' and (a.content or b.content):
            return levenshtein(a.content, b.content) / max(len(a.content), len(b.content))
        return 0.0


def tokens(node):
    result = [f'<{node.tag}>'] + list(node.text or '')
    for child in node:
        result.extend(tokens(child))
    if node.tag != 'unk':
        result.append(f'</{node.tag}>')
    if node.tag != 'td':
        result.extend(node.tail or '')
    return result


def tree(element, structure_only):
    if element.tag == 'td':
        return Node('td', int(element.get('colspan', 1)), int(element.get('rowspan', 1)),
                    [] if structure_only else tokens(element)[1:-1])
    node = Node(element.tag)
    node.children = [tree(child, structure_only) for child in element]
    return node


def table_element(value):
    root = html.document_fromstring(value, parser=html.HTMLParser(remove_comments=True))
    tables = root.xpath('//table')
    if not tables:
        return None
    table = tables[0]
    for cell in table.xpath('.//th'):
        cell.tag = 'td'
    etree.strip_tags(table, 'thead', 'tbody', 'tfoot')
    return table


def teds(prediction, reference, structure_only=False):
    if not prediction or not reference:
        return 0.0
    try:
        pred, gold = table_element(prediction), table_element(reference)
        if pred is None or gold is None:
            return 0.0
        count = max(len(pred.xpath('.//*')), len(gold.xpath('.//*')))
        if not count:
            return 0.0
        distance = APTED(tree(pred, structure_only), tree(gold, structure_only), Costs()).compute_edit_distance()
        return max(0.0, min(1.0, 1.0 - distance / count))
    except (ValueError, etree.ParserError):
        return 0.0
