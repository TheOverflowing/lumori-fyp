"""Benchmark adapter invariants; no MinerU weights or network required."""
import pytest
from scripts.evaluate_mineru_parsing import content_text, extract_pages, isolated_environment


def document(blocks):
    return {'schema':'docvortex.middle','schema_version':'2.0',
            'pages':[{'page_idx':0,'blocks':blocks}]}


def test_text_spans_preserve_literals_and_original_parser_order():
    payload=document([
        {'type':'header','content':[{'type':'text','content':'Title 2026'}]},
        {'type':'text','content':[{'type':'text','content':'Use *ptr and A_B: '},
                                 {'type':'text','content':'中English.'}]},
        {'type':'footer','content':[{'type':'text','content':'12'}]},
    ])
    assert extract_pages(payload)==['Title 2026\nUse *ptr and A_B: 中English.\n12']


def test_visual_asset_paths_are_not_fabricated_text():
    payload=document([{'type':'image','bbox':[0,0,10,10],'content':[
        {'type':'image_body','image_path':'images/fake-answer.png'},
        {'type':'image_caption','content':[{'type':'text','content':'Figure 1: tree'}]},
    ]}])
    assert extract_pages(payload)==['Figure 1: tree']


def test_table_markup_is_not_counted_as_recognized_words():
    assert content_text({'type':'table_body','content':'<table><tr><td>A &amp; B</td><td>2</td></tr></table>'})=='A & B 2'


@pytest.mark.parametrize('schema,version',[('docvortex.model','2.0'),('docvortex.middle','3.0'),(None,None)])
def test_schema_changes_fail_explicitly(schema,version):
    with pytest.raises(ValueError,match='schema'):
        extract_pages({'schema':schema,'schema_version':version,'pages':[]})


def test_empty_and_missing_pages_are_not_conflated():
    assert extract_pages(document([]))==['']
    with pytest.raises(ValueError,match='pages'):
        extract_pages({'schema':'docvortex.middle','schema_version':'2.0'})


def test_experiment_worker_does_not_inherit_provider_credentials(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-not-real')
    monkeypatch.setenv('MINERU_MODEL_VLM_SERVER_URL','https://test.invalid')
    monkeypatch.setenv('MINERU_API_KEY','test-not-real')
    env=isolated_environment()
    assert not any('KEY' in key or 'SERVER_URL' in key for key in env)
    assert env['MINERU_MODEL_SOURCE']=='local'
    assert env['MINERU_MODEL_SMALL_BACKEND']=='onnx'
