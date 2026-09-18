"""Protect the source-cluster interpretation of paired experiment intervals."""
import pytest
from scripts.r5_report import interval


def rows():
    result=[]
    for query,family,gain in [('q1','a',1),('q2','a',1),('q3','a',1),('q4','b',0)]:
        for arm,value in [('original',0),('dual',gain)]:
            result.append({'query_id':query,'family_id':family,'arm':arm,'mode':'cross',
                'language':'en','budget_hit':value})
    return result


def test_component_bootstrap_keeps_query_weighted_effect():
    result=interval(rows(),{'a':'source-a','b':'source-b'},'dual','budget_hit')
    assert result['difference']==pytest.approx(.75)
    assert result['clusters']==2
    assert result['ci95']==[0,1]


def test_duplicating_paired_scenarios_does_not_invent_independent_sources():
    base=rows();paired=base+[dict(r,mode='mixed') for r in base]
    mapping={'a':'source-a','b':'source-b'}
    assert interval(base,mapping,'dual','budget_hit')==interval(paired,mapping,'dual','budget_hit')
