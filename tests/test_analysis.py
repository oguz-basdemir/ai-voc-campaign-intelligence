import pytest

from voc.analysis import analyze, clusters, match_themes, opportunity_score, sentiment


@pytest.mark.parametrize(
    "text,label",
    [
        ("The service is excellent and helpful", "positive"),
        ("The setup is difficult and confusing", "negative"),
        ("We use it on Tuesdays", "neutral"),
        ("The interface is not easy", "negative"),
        ("The pricing is not expensive", "positive"),
        ("Not difficult but slow", "neutral"),
    ],
)
def test_sentiment_and_negation(text, label):
    assert sentiment(text)[0] == label


def test_theme_word_boundaries_and_overlap():
    assert match_themes("We like spicy foods and agentless scripts") == []
    assert set(match_themes("Expensive CRM integration")) == {"price", "integrations"}


def test_results_are_reproducible_and_evidence_is_grounded(frame):
    first = analyze(frame)
    assert first == analyze(frame)
    ledger = {r["record_id"]: r for r in first["records"]}
    assert sum(first["summary"]["sentiment"].values()) == len(frame)
    for collection in ["themes", "pain_points", "objections", "opportunities"]:
        for item in first[collection]:
            assert item["frequency"] == len(set(item["evidence_ids"]))
            assert all(item["theme"] in ledger[i]["themes"] for i in item["evidence_ids"])
            for e in item["evidence"]:
                assert e["text"] == ledger[e["record_id"]]["text"]
    for item in first["language_library"]:
        assert item["frequency"] >= 2
        assert all(item["phrase"] in e["text"].lower() for e in item["evidence"])
    assert all("hypothesis" in s["status"] for s in first["segments"])
    assert sum(c["frequency"] for c in first["clusters"]) == len(frame)


def test_priority_formula_and_bounds():
    score, parts = opportunity_score(50, 100, 3, 1, 50, 100)
    assert parts == {"frequency": 50, "severity": 100, "commercial_relevance": 100, "segment_size": 50}
    assert score == 75
    assert opportunity_score(100, 100, 3, 1, 100, 100)[0] == 100


def test_representative_quote_prefers_theme_specific_signal(frame):
    sample = frame.iloc[:2].copy()
    sample["text"] = [
        "An outage blocked our reporting during a critical deadline.",
        "We spend hours on manual reporting. It is frustrating.",
    ]
    result = analyze(sample)
    value = next(o for o in result["opportunities"] if o["theme"] == "value")
    assert "manual reporting" in value["evidence"][0]["text"]


def test_empty_scope(frame):
    result = analyze(frame.iloc[:0])
    assert result["summary"]["records"] == 0
    assert not result["opportunities"]
    assert not result["clusters"]
    assert not result["segments"]


def test_sparse_identical_and_unmatched_text(frame):
    assert clusters(frame.iloc[:1], 6) == []
    same = frame.iloc[:3].copy()
    same["text"] = "the and of"
    assert clusters(same, 6) == []
    same["text"] = "banana orchard harvest"
    assert clusters(same, 6) == []
    result = analyze(same)
    assert result["summary"]["unclassified_records"] == 3
    assert not result["opportunities"]


def test_no_campaign_without_negative_or_objection_signal(frame):
    clean = frame.iloc[:1].copy()
    clean["text"] = "The interface is easy and intuitive."
    result = analyze(clean)
    assert result["themes"][0]["theme"] == "ease of use"
    assert not result["pain_points"]
    assert not result["opportunities"]


def test_objection_and_severity_are_separate_signals(frame):
    sample = frame.iloc[:1].copy()
    sample["text"] = "Implementation seems difficult. A critical rollout was blocked."
    result = analyze(sample)
    assert result["summary"]["objection_records"] == 1
    assert result["pain_points"][0]["severity"] == 3
    assert result["objections"][0]["recommended_response"]
