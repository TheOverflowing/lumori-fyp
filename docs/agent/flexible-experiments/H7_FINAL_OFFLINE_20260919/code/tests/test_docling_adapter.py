import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec('docling_core'), 'requires isolated Docling environment')
class DoclingAdapterTests(unittest.TestCase):
    def test_headers_and_body_keep_parser_order_without_markdown(self):
        from docling_core.types.doc import DoclingDocument,DocItemLabel,ContentLayer
        from scripts.evaluate_parsing_candidates import docling_content
        doc=DoclingDocument(name='fixture')
        doc.add_text(label=DocItemLabel.PAGE_HEADER,text='Header',content_layer=ContentLayer.FURNITURE)
        doc.add_text(label=DocItemLabel.TITLE,text='正文 Title')
        doc.add_text(label=DocItemLabel.TEXT,text='A **literal** marker')
        doc.add_text(label=DocItemLabel.PAGE_FOOTER,text='Footer',content_layer=ContentLayer.FURNITURE)
        self.assertEqual([i['text'] for i in docling_content(doc)],['Header','正文 Title','A **literal** marker','Footer'])

    def test_bottom_left_picture_box_is_normalized_to_top_left(self):
        from docling_core.types.doc import DoclingDocument,Size,BoundingBox,CoordOrigin,ProvenanceItem
        from scripts.evaluate_parsing_candidates import docling_content
        doc=DoclingDocument(name='fixture');doc.add_page(page_no=1,size=Size(width=100,height=200))
        doc.add_picture(prov=ProvenanceItem(page_no=1,bbox=BoundingBox(l=10,t=180,r=50,b=100,coord_origin=CoordOrigin.BOTTOMLEFT),charspan=(0,0)))
        items=docling_content(doc)
        self.assertEqual(items[0]['boxes'],[{'page_no':1,'bbox':[.1,.1,.5,.5]}])
        self.assertTrue(items[0]['is_picture']);self.assertEqual(items[0]['text'],'')

    def test_table_text_has_no_serialization_markup(self):
        from docling_core.types.doc import DoclingDocument,TableData,TableCell
        from scripts.evaluate_parsing_candidates import docling_content
        doc=DoclingDocument(name='fixture')
        doc.add_table(data=TableData(num_rows=1,num_cols=1,table_cells=[TableCell(text='value 42',start_row_offset_idx=0,end_row_offset_idx=1,start_col_offset_idx=0,end_col_offset_idx=1)]))
        self.assertEqual([i['text'] for i in docling_content(doc)],['value 42'])


if __name__=='__main__':unittest.main()
