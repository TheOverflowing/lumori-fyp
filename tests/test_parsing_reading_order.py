import unittest
from scripts.parsing_reading_order import reorder_items


def item(name, box, kind='text', text=None):
    return {'id': name, 'type': kind, 'text': text if text is not None else name*100,
            'is_picture': False, 'boxes': [{'page_no': 1, 'bbox': box}] if box else []}


class ReadingOrderTests(unittest.TestCase):
    def columns(self):
        return [item('A', [.05,.1,.45,.2]), item('B', [.55,.1,.95,.2]),
                item('C', [.05,.3,.45,.4]), item('D', [.55,.3,.95,.4])]

    def test_aligned_columns_not_row_major(self):
        data = self.columns(); result = reorder_items(data)
        self.assertEqual([x['id'] for x in result], ['A','C','B','D'])
        self.assertEqual(sorted(map(str, data)), sorted(map(str, result)))

    def test_spanning_title_and_furniture(self):
        data = [item('header', [.1,.01,.9,.02], 'header'), item('title', [.05,.03,.95,.07], 'paragraph_title')]+self.columns()+[item('footer', [.1,.9,.9,.95], 'footer')]
        self.assertEqual([i['id'] for i in reorder_items(data)], ['header','title','A','C','B','D','footer'])

    def test_invalid_geometry_retained_in_place(self):
        data = self.columns(); data.insert(2, item('unknown', None))
        self.assertEqual([i['id'] for i in reorder_items(data)], ['A','C','unknown','B','D'])

    def test_small_side_note_does_not_create_column(self):
        data = [item('note', [.01,.1,.04,.2], text='1'), item('body', [.1,.1,.95,.9])]
        self.assertEqual(reorder_items(data), data)

    def test_empty_or_overlapping_boxes_keep_input_order(self):
        self.assertEqual(reorder_items([]), [])
        data = [item('A', [.1,.1,.9,.8]), item('B', [.2,.2,.8,.7])]
        self.assertEqual(reorder_items(data), data)
