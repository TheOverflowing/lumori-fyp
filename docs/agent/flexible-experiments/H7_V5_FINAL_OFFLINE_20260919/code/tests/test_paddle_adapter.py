import unittest
from scripts.evaluate_paddle_parsing import items_from_result


class PaddleAdapterTests(unittest.TestCase):
    def test_furniture_and_reading_order_are_retained(self):
        blocks = [{'block_id': i, 'block_label': label, 'block_content': text,
                   'block_bbox': [10, 20, 50, 80]}
                  for i, (label, text) in enumerate([('header', 'Header'), ('text', 'First body'),
                                                    ('text', 'Second body'), ('footer', 'Footer')])]
        items = items_from_result({'width': 100, 'height': 200, 'parsing_res_list': blocks})
        self.assertEqual([i['text'] for i in items], ['Header', 'First body', 'Second body', 'Footer'])
        self.assertEqual(items[0]['boxes'][0]['bbox'], [.1, .1, .5, .4])

    def test_figure_markup_does_not_become_prose(self):
        item = items_from_result({'width': 100, 'height': 200, 'parsing_res_list': [
            {'block_id': 0, 'block_label': 'image', 'block_content': '![](img.png)', 'block_bbox': [0, 0, 100, 200]}]})[0]
        self.assertTrue(item['is_picture'])
        self.assertEqual(item['text'], '')
