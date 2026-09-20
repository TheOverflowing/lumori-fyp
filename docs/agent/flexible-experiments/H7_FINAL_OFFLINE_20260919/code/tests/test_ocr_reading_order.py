"""Geometry and text preservation checks independent of benchmark references."""
from collections import Counter
from copy import deepcopy
import json

import pytest

from scripts.reorder_ocr_blocks import DEFAULT_CONFIG, reorder_page


@pytest.fixture
def config():
    return json.loads(DEFAULT_CONFIG.read_text())


def page_with(lines, *, prefix='', separator='\n', suffix=''):
    text = prefix + separator.join(line[0] for line in lines) + suffix
    blocks, offset = [], len(prefix)
    for value, bbox in lines:
        blocks.append({'kind': 'ocr_line', 'text': value, 'bbox': bbox,
                       'coordinate_system': 'image_pixels_top_left',
                       'char_start': offset, 'char_end': offset + len(value)})
        offset += len(value) + len(separator)
    return {'text': text, 'blocks': blocks,
            'metrics': {'ocr_image_width': 1000, 'ocr_image_height': 1200}}


def two_columns(rows=5):
    return [(f'{side}{index} 字符，{index}!', [x, 200 + index * 45, 330, 20])
            for index in range(rows) for side, x in [('L', 80), ('R', 580)]]


def values_in_result(page, result):
    return [page['blocks'][index]['text'] for index in result['trace']['order_indices']]


def test_two_columns_read_complete_left_then_right(config):
    page = page_with(two_columns())
    result = reorder_page(page, config)
    assert result['trace']['two_column_gate_passed'] is True
    assert result['trace']['changed'] is True
    assert result['trace']['order_indices'] == [0, 2, 4, 6, 8, 1, 3, 5, 7, 9]
    assert result['trace']['selected_cut_fraction'] == .5
    assert Counter(page['text']) == Counter(result['text'])
    assert result == reorder_page(page, config)


def test_missing_blocks_and_dimensions_preserve_original(config):
    page = page_with(two_columns())
    page['metrics'] = {}
    result = reorder_page(page, config)
    assert result['text'] == page['text']
    assert result['trace']['reason'] == 'missing_or_invalid_raster_dimensions'
    assert reorder_page({'text': 'source only'}, config)['text'] == 'source only'


@pytest.mark.parametrize('lines', [
    [(str(i), [100, 100 + 35 * i, 780, 20]) for i in range(12)],
    two_columns(rows=3),
    [(str(i), [100, 100 + 35 * i, 100, 20]) for i in range(8)]
       + [(str(i), [600, 100 + 35 * i, 100, 20]) for i in range(8)],
    [(str(i), [100, 100 + 35 * i, 350, 20]) for i in range(5)]
       + [(str(i), [600, 650 + 35 * i, 350, 20]) for i in range(5)],
    [(str(i), [100, 100 + 35 * i, 350, 20]) for i in range(4)]
       + [(str(i), [600, 100 + 35 * i, 350, 20]) for i in range(15)],
])
def test_single_column_sparse_narrow_nonoverlap_or_imbalanced_falls_back(config, lines):
    page = page_with(lines)
    result = reorder_page(page, config)
    assert result['text'] == page['text']
    assert result['trace']['two_column_gate_passed'] is False
    assert result['trace']['reason'] == 'no_confident_two_column_gutter'


def test_cross_gutter_header_footer_and_same_row_number_are_anchors(config):
    lines = [('TITLE', [200, 50, 650, 20]), ('page 1', [900, 50, 60, 20])]
    lines += two_columns()
    lines += [('FOOTER', [150, 1100, 700, 20])]
    page = page_with(lines)
    result = reorder_page(page, config)
    ordered = values_in_result(page, result)
    assert ordered[:2] == ['TITLE', 'page 1']
    assert ordered[-1] == 'FOOTER'
    assert [line[:2] for line in ordered[2:-1]] == ['L0', 'L1', 'L2', 'L3', 'L4', 'R0', 'R1', 'R2', 'R3', 'R4']
    assert len(result['trace']['anchor_bands']) == 2


def test_middle_crossing_anchor_splits_two_column_sections(config):
    lines = two_columns(rows=4) + [('SECTION', [150, 400, 700, 20])]
    lines += [(value.replace('L', 'A').replace('R', 'B'), [bbox[0], bbox[1] + 300, bbox[2], bbox[3]])
              for value, bbox in two_columns(rows=4)]
    page = page_with(lines)
    result = reorder_page(page, config)
    ordered = values_in_result(page, result)
    assert [line[:2] for line in ordered[:8]] == ['L0', 'L1', 'L2', 'L3', 'R0', 'R1', 'R2', 'R3']
    assert ordered[8] == 'SECTION'
    assert [line[:2] for line in ordered[9:]] == ['A0', 'A1', 'A2', 'A3', 'B0', 'B1', 'B2', 'B3']


def test_overlapping_anchor_bands_merge(config):
    lines = [('header 1', [120, 60, 760, 20]), ('header 2', [120, 90, 760, 20])] + two_columns(rows=6)
    page = page_with(lines)
    result = reorder_page(page, config)
    assert len(result['trace']['anchor_bands']) == 1
    assert values_in_result(page, result)[:2] == ['header 1', 'header 2']


def test_text_content_does_not_affect_geometry(config):
    first = page_with(two_columns())
    second = page_with([('arbitrary ' + str(i), line[1]) for i, line in enumerate(two_columns())])
    result1, result2 = reorder_page(first, config), reorder_page(second, config)
    assert result1['trace']['order_indices'] == result2['trace']['order_indices']
    assert result1['trace']['candidate_diagnostics'] == result2['trace']['candidate_diagnostics']
    assert result1['trace']['selected_cut_fraction'] == result2['trace']['selected_cut_fraction']


def test_exact_whitespace_and_duplicate_content_inventory_preserved(config):
    lines = [('重复 SAME!', bbox) for _, bbox in two_columns()]
    page = page_with(lines, prefix='\n\t', separator=' \n\n\t', suffix='\n ')
    original = deepcopy(page)
    result = reorder_page(page, config)
    assert result['trace']['changed']
    assert Counter(page['text']) == Counter(result['text'])
    assert page == original
    assert result['text'] == page['text']  # Distinct boxes may have identical text.


@pytest.mark.parametrize('mutation,reason', [
    (lambda p: p['blocks'][0].update(bbox=[float('nan'), 0, 30, 20]), 'invalid_bbox'),
    (lambda p: p['blocks'][0].update(bbox=[900, 0, 200, 20]), 'bbox_outside_raster'),
    (lambda p: p['blocks'][0].update(coordinate_system='normalized'), 'unsupported_block_geometry'),
    (lambda p: p['blocks'][0].update(text='incorrect text'), 'invalid_or_mismatched_text_spans'),
    (lambda p: p['blocks'][1].update(char_start=0), 'invalid_or_mismatched_text_spans'),
    (lambda p: p.update(text=p['text'] + 'Untracked source'), 'untracked_nonwhitespace_text'),
])
def test_invalid_geometry_or_untracked_text_never_drops_content(config, mutation, reason):
    page = page_with(two_columns())
    mutation(page)
    result = reorder_page(page, config)
    assert result['text'] == page['text']
    assert result['trace']['reason'] == reason
    assert result['trace']['characters_unchanged'] is True


def test_mostly_crossing_uncertainty_preserves_original(config):
    lines = two_columns() + [(str(i), [50, 600 + i * 40, 900, 20]) for i in range(10)]
    page = page_with(lines)
    result = reorder_page(page, config)
    assert result['text'] == page['text']
    assert result['trace']['two_column_gate_passed'] is False


def test_pixel_dimensions_define_geometry_not_ground_truth_dimensions(config):
    first = page_with(two_columns())
    doubled = deepcopy(first)
    doubled['metrics'] = {'ocr_image_width': 2000, 'ocr_image_height': 2400}
    for block in doubled['blocks']:
        block['bbox'] = [2 * number for number in block['bbox']]
    result1, result2 = reorder_page(first, config), reorder_page(doubled, config)
    assert result1['trace'] == result2['trace']
