"""Frozen development ablation: vertical-first whitespace XY-cut.

Only reorders existing body items using their normalized source coordinates.
No recognition, reference text, sample-specific rule, or content rewriting.
Thresholds fixed in P4 geometry-preregistration.json before evaluation.
"""
import math

FURNITURE = {'header', 'footer', 'footnote', 'vision_footnote', 'aside_text',
             'number', 'figure_title', 'table_title'}


def valid_box(item):
    boxes = item.get('boxes', [])
    if len(boxes) != 1 or boxes[0].get('page_no') != 1:
        return None
    box = boxes[0]['bbox']
    if len(box) != 4 or not all(math.isfinite(v) and 0 <= v <= 1 for v in box):
        return None
    return box if box[2] > box[0] and box[3] > box[1] else None


def gaps(items, axis):
    intervals = sorted((item['_box'][axis], item['_box'][axis+2]) for item in items)
    end = intervals[0][1]; result = []
    for start, stop in intervals[1:]:
        if start > end:
            result.append((start-end, (start+end)/2))
        end = max(end, stop)
    return sorted(result, key=lambda p: (-p[0], p[1]))


def recursive_order(items):
    if len(items) < 2:
        return items
    for size, cut in gaps(items, 0):
        if size < .015:
            continue
        left = [i for i in items if i['_box'][2] < cut]
        right = [i for i in items if i['_box'][0] > cut]
        if not left or not right or len(left)+len(right) != len(items):
            continue
        def substantial(group):
            width = max(i['_box'][2] for i in group)-min(i['_box'][0] for i in group)
            characters = sum(len(''.join(i['item']['text'].split())) for i in group)
            return width >= .18 and characters >= 80
        if substantial(left) and substantial(right):
            return recursive_order(left)+recursive_order(right)
    # Peel the top spanning band first; a larger row gap lower in the page
    # must not split aligned columns before their spanning title is removed.
    for size, cut in sorted(gaps(items, 1), key=lambda pair: pair[1]):
        if size < .005:
            continue
        top = [i for i in items if i['_box'][3] < cut]
        bottom = [i for i in items if i['_box'][1] > cut]
        if top and bottom and len(top)+len(bottom) == len(items):
            return recursive_order(top)+recursive_order(bottom)
    return items


def reorder_items(items):
    body = []
    for index, item in enumerate(items):
        if item.get('type') in FURNITURE or item.get('is_picture') or not item.get('text', '').strip():
            continue
        box = valid_box(item)
        if box is not None:
            body.append({'index': index, 'item': item, '_box': box})
    result = list(items)
    for position, reordered in zip([i['index'] for i in body], recursive_order(body)):
        result[position] = reordered['item']
    return result
