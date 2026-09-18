from scripts.evaluate_mineru_regions import iou,match_regions


def test_identical_disjoint_and_partial_regions():
    assert iou([0,0,1,1],[0,0,1,1])==1
    assert iou([0,0,.4,.4],[.5,.5,1,1])==0
    assert iou([0,0,1,1],[0,0,.5,1])==.5


def test_duplicate_predictions_do_not_inflate_recall():
    assert len(match_regions([[0,0,1,1]],[[0,0,1,1],[0,0,1,1]]))==1


def test_one_large_prediction_cannot_match_two_gold_regions():
    assert len(match_regions([[0,0,.5,1],[.5,0,1,1]],[[0,0,1,1]]))==1


def test_augmenting_match_avoids_greedy_under_count():
    gold=[[0,0,.8,1],[.2,0,1,1]]
    predicted=[[.1,0,.9,1],[0,0,.5,1]]
    assert len(match_regions(gold,predicted))==2


def test_empty_predictions_and_empty_gold():
    assert match_regions([[0,0,1,1]],[])==[]
    assert match_regions([],[[0,0,1,1]])==[]
