"""Offline structural tests. Fixture identities are fictional test data, not human labels."""
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("build_course_benchmark", Path(__file__).resolve().parents[1] / "scripts/build_course_benchmark.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def annotation():
    corpus = {"schema_version": "course-corpus-v1", "corpus_id": "fictional-test-fixture", "sources": [{"id": "fixture-source"}], "documents": [
        {"id": name, "text": text, "source_id": "fixture-source", "text_sha256": hashlib.sha256(text.encode()).hexdigest()}
        for name, text in [("p1", "Example relevant fact."), ("p2", "Example unrelated fact.")]
    ]}
    provenance = {"reviewer_id": "fictional-test-reviewer", "reviewed_at": "2026-09-12T12:00:00Z", "review_status": "reviewed"}
    queries = [{"query_id": "q1", "query_text": "Example question?", "query_language": "en", "author_id": "fictional-test-author", "authored_at_utc": "2026-09-12T10:00:00Z", "family_id": "family1", "proposed_split": "dev", "category": "semantic", "answerable": "true", "notes": "Fictional test data only", **provenance}]
    judgments = [{"query_id": "q1", "passage_id": passage, "annotator_id": "fictional-test-annotator", "judged_at_utc": "2026-09-12T11:00:00Z", "relevance_grade": grade, "required_evidence_group": group, "rationale": "Fictional structural test rationale", **provenance} for passage, grade, group in [("p1", "2", "g1"), ("p2", "0", "")]]
    return corpus, queries, judgments


def convert(annotation):
    return module.build_dataset(*annotation, dataset_id="fictional-test-output")


def test_complete_review_preserves_raw_judgments_and_evidence(annotation):
    result = convert(annotation)
    assert result["label_status"] == "human_reviewed"
    assert result["queries"][0]["relevance"] == {"p1": 2}
    assert result["queries"][0]["required_evidence_groups"] == [["p1"]]
    assert result["annotation_provenance"]["raw_final_judgments"] == annotation[2]


@pytest.mark.parametrize("which", [1, 2])
def test_empty_tables_cannot_become_human_reviewed(annotation, which):
    values = list(annotation)
    values[which] = []
    with pytest.raises(ValueError, match="Empty human"):
        convert(values)


@pytest.mark.parametrize("table,field,value", [
    (1, "author_id", ""), (1, "reviewer_id", ""), (1, "reviewed_at", ""),
    (2, "annotator_id", ""), (2, "reviewer_id", ""), (2, "reviewed_at", ""),
    (2, "rationale", ""), (2, "review_status", "draft"),
    (1, "review_status", "draft"), (1, "reviewed_at", "2026-09-12"),
    (2, "reviewed_at", "2026-09-11T12:00:00Z"),
    (2, "relevance_grade", "2.0"), (2, "relevance_grade", "true"),
    (2, "relevance_grade", "-1"), (1, "answerable", "yes"),
    (1, "query_language", "fr"), (1, "proposed_split", "train"),
    (2, "passage_id", "unknown"), (2, "query_id", "unknown"),
])
def test_incomplete_or_invalid_review_refused(annotation, table, field, value):
    annotation[table][0][field] = value
    with pytest.raises(ValueError):
        convert(annotation)


def test_missing_zero_label_is_not_silently_assumed(annotation):
    annotation[2].pop()
    with pytest.raises(ValueError, match="Incomplete judgment coverage"):
        convert(annotation)


def test_invalid_source_id_refused(annotation):
    annotation[0]["documents"][0]["source_id"] = "not-in-source-catalog"
    with pytest.raises(ValueError, match="source ID"):
        convert(annotation)


def test_mutated_passage_refused(annotation):
    annotation[0]["documents"][0]["text"] = "modified"
    with pytest.raises(ValueError, match="hash mismatch"):
        convert(annotation)


def test_duplicate_pair_requires_explicit_adjudication(annotation):
    annotation[2].append(deepcopy(annotation[2][0]))
    with pytest.raises(ValueError, match="Duplicate judgment pair"):
        convert(annotation)


def test_evidence_group_is_not_inferred_from_relevant_grade(annotation):
    annotation[2][0]["required_evidence_group"] = ""
    with pytest.raises(ValueError, match="evidence groups"):
        convert(annotation)


def test_semicolon_groups_preserve_distinct_facts(annotation):
    annotation[2][0]["required_evidence_group"] = "g1;g2"
    result = convert(annotation)
    assert result["queries"][0]["required_evidence_groups"] == [["p1"], ["p1"]]
    assert result["queries"][0]["evidence_group_names"] == ["g1", "g2"]


def test_nonrelevant_cannot_enter_evidence_groups(annotation):
    annotation[2][1]["required_evidence_group"] = "g1"
    with pytest.raises(ValueError, match="graded 2"):
        convert(annotation)


def test_unanswerable_requires_explicit_all_zero_judgments(annotation):
    annotation[1][0]["answerable"] = "false"
    annotation[2][0]["relevance_grade"] = "0"
    annotation[2][0]["required_evidence_group"] = ""
    query = convert(annotation)["queries"][0]
    assert query["relevance"] == {}
    assert query["required_evidence_groups"] == []


def test_family_must_not_cross_split(annotation):
    second = deepcopy(annotation[1][0])
    second.update(query_id="q2", proposed_split="test")
    annotation[1].append(second)
    for row in list(annotation[2]):
        row = deepcopy(row)
        row["query_id"] = "q2"
        annotation[2].append(row)
    with pytest.raises(ValueError, match="must not cross"):
        convert(annotation)
