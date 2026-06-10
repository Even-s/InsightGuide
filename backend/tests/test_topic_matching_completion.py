"""Tests for topic-card completion state semantics."""

from types import SimpleNamespace

from app.services.scoring_service import scoring_service
from app.services.topic_matching_engine import TopicMatchingEngine


class FakeDb:
    pass


def make_card_state(status="pending", confidence=0.0, covered_at=None, evidence=None):
    return SimpleNamespace(
        status=status,
        confidence=confidence,
        covered_at=covered_at,
        evidence=evidence,
        updated_at=None,
    )


def make_card(coverage_rule=None):
    return SimpleNamespace(
        id="card_market",
        title="熱門股票期貨速覽",
        importance="must",
        coverage_rule=coverage_rule or {},
    )


def make_judgment(
    new_status,
    final_score,
    covered_aspect_ids=None,
    missing_aspect_ids=None,
):
    return {
        "new_status": new_status,
        "final_score": final_score,
        "semantic_score": final_score,
        "keyword_score": final_score,
        "fact_score": final_score,
        "gpt_judgment": {
            "confidence": final_score,
            "reasoning": "test judgment",
            "mentioned_keywords": ["交易量"],
            "missing_aspects": [],
            "covered_aspect_ids": covered_aspect_ids or [],
            "missing_aspect_ids": missing_aspect_ids or [],
        },
    }


def test_probably_covered_does_not_set_covered_at():
    engine = TopicMatchingEngine()
    card_state = make_card_state()

    update = engine._update_card_state(
        db=FakeDb(),
        card_state=card_state,
        card=make_card(),
        utterance_id="utt_1",
        utterance_text="先提到熱門股票期貨的交易量排名。",
        judgment=make_judgment("probably_covered", 0.72),
    )

    assert update is not None
    assert update["new_status"] == "probably_covered"
    assert card_state.status == "probably_covered"
    assert card_state.covered_at is None


def test_covered_sets_covered_at():
    engine = TopicMatchingEngine()
    card_state = make_card_state(status="probably_covered", confidence=0.72)

    update = engine._update_card_state(
        db=FakeDb(),
        card_state=card_state,
        card=make_card(),
        utterance_id="utt_2",
        utterance_text="完整講到交易量、漲跌幅和市場熱度。",
        judgment=make_judgment("covered", 0.9),
    )

    assert update is not None
    assert update["new_status"] == "covered"
    assert update["confidence"] == 1.0
    assert card_state.status == "covered"
    assert card_state.confidence == 1.0
    assert card_state.evidence["completionPercentage"] == 100
    assert card_state.covered_at is not None


def test_completion_state_does_not_regress_when_confidence_improves():
    engine = TopicMatchingEngine()
    card_state = make_card_state(status="probably_covered", confidence=0.5)

    update = engine._update_card_state(
        db=FakeDb(),
        card_state=card_state,
        card=make_card(),
        utterance_id="utt_3",
        utterance_text="補充一點相關但還不完整的內容。",
        judgment=make_judgment("listening", 0.6),
    )

    assert update is not None
    assert update["new_status"] == "probably_covered"
    assert card_state.status == "probably_covered"
    assert card_state.confidence == 0.6
    assert card_state.covered_at is None


def test_bullet_progress_updates_without_confidence_regression():
    engine = TopicMatchingEngine()
    card_state = make_card_state(
        status="listening",
        confidence=0.7,
        evidence={"coveredAspectIds": ["anchor_0"]},
    )

    update = engine._update_card_state(
        db=FakeDb(),
        card_state=card_state,
        card=make_card(),
        utterance_id="utt_4",
        utterance_text="接著補充漲跌幅與市場熱度。",
        judgment=make_judgment(
            "listening",
            0.6,
            covered_aspect_ids=["anchor_1"],
            missing_aspect_ids=["anchor_0", "anchor_2"],
        ),
    )

    assert update is not None
    assert update["new_status"] == "listening"
    assert update["confidence"] == 0.7
    assert card_state.confidence == 0.7
    assert card_state.evidence["coveredAspectIds"] == ["anchor_0", "anchor_1"]
    assert card_state.evidence["missingAspectIds"] == ["anchor_2"]


def test_no_update_when_score_and_bullet_progress_do_not_change():
    engine = TopicMatchingEngine()
    card_state = make_card_state(
        status="listening",
        confidence=0.7,
        evidence={"coveredAspectIds": ["anchor_0"]},
    )

    update = engine._update_card_state(
        db=FakeDb(),
        card_state=card_state,
        card=make_card(),
        utterance_id="utt_5",
        utterance_text="重複講同一個交易量重點。",
        judgment=make_judgment(
            "listening",
            0.6,
            covered_aspect_ids=["anchor_0"],
        ),
    )

    assert update is None
    assert card_state.confidence == 0.7


def test_all_talking_points_must_complete_before_card_is_covered():
    engine = TopicMatchingEngine()
    card_state = make_card_state(
        status="listening",
        confidence=0.7,
        evidence={"coveredAspectIds": ["anchor_0"]},
    )
    card = make_card(
        coverage_rule={
            "semanticAnchors": ["交易量重點", "漲跌幅重點", "資金熱度重點"],
            "mustMentionFacts": [],
        }
    )

    update = engine._update_card_state(
        db=FakeDb(),
        card_state=card_state,
        card=card,
        utterance_id="utt_6",
        utterance_text="接著講完漲跌幅重點。",
        judgment=make_judgment(
            "listening",
            0.6,
            covered_aspect_ids=["anchor_1"],
            missing_aspect_ids=["anchor_2"],
        ),
    )

    assert update is not None
    assert update["new_status"] == "probably_covered"
    assert update["confidence"] == 2 / 3
    assert card_state.status == "probably_covered"
    assert card_state.confidence == 2 / 3
    assert card_state.evidence["completionPercentage"] == 67
    assert card_state.evidence["coveredAspectIds"] == ["fact_0", "fact_1"]
    assert card_state.evidence["missingAspectIds"] == ["fact_2"]
    assert card_state.covered_at is None


def test_all_talking_points_complete_marks_card_covered():
    engine = TopicMatchingEngine()
    card_state = make_card_state(
        status="listening",
        confidence=0.7,
        evidence={"coveredAspectIds": ["anchor_0", "anchor_1"]},
    )
    card = make_card(
        coverage_rule={
            "semanticAnchors": ["交易量重點", "漲跌幅重點", "資金熱度重點"],
            "mustMentionFacts": [],
        }
    )

    update = engine._update_card_state(
        db=FakeDb(),
        card_state=card_state,
        card=card,
        utterance_id="utt_7",
        utterance_text="最後補完資金熱度重點。",
        judgment=make_judgment(
            "listening",
            0.6,
            covered_aspect_ids=["anchor_2"],
        ),
    )

    assert update is not None
    assert update["new_status"] == "covered"
    assert update["confidence"] == 1.0
    assert card_state.status == "covered"
    assert card_state.confidence == 1.0
    assert card_state.evidence["coveredAspectIds"] == ["fact_0", "fact_1", "fact_2"]
    assert card_state.evidence["missingAspectIds"] == []
    assert card_state.covered_at is not None


def test_complete_judgment_fills_required_aspect_ids_when_gpt_omits_them():
    engine = TopicMatchingEngine()
    card = make_card(
        coverage_rule={
            "semanticAnchors": ["交易量重點", "漲跌幅重點", "資金熱度重點"],
            "mustMentionFacts": [{"text": "臺積電量能最大"}],
        }
    )

    covered_ids, missing_ids = engine._normalize_completion_aspect_ids(
        card,
        {
            "covered_aspect_ids": ["anchor_0"],
            "missing_aspect_ids": [],
        },
        completion_percentage=92,
        is_complete=True,
    )

    assert covered_ids == ["fact_0", "fact_1", "fact_2"]
    assert missing_ids == []


def test_missing_aspect_ids_partition_required_aspects():
    engine = TopicMatchingEngine()
    card = make_card(
        coverage_rule={
            "semanticAnchors": ["交易量重點", "漲跌幅重點", "資金熱度重點"],
            "mustMentionFacts": [],
        }
    )

    covered_ids, missing_ids = engine._normalize_completion_aspect_ids(
        card,
        {
            "covered_aspect_ids": ["anchor_0"],
            "missing_aspect_ids": ["anchor_2"],
        },
        completion_percentage=68,
        is_complete=False,
    )

    assert covered_ids == ["fact_0", "fact_1"]
    assert missing_ids == ["fact_2"]


def test_anchor_overflow_maps_back_to_three_important_points():
    engine = TopicMatchingEngine()
    card = make_card(
        coverage_rule={
            "semanticAnchors": ["交易量", "振幅", "漲幅", "跌幅", "市場熱度"],
            "mustMentionFacts": [],
        }
    )

    assert engine._get_required_aspect_ids(card) == ["fact_0", "fact_1", "fact_2"]

    covered_ids, missing_ids = engine._normalize_completion_aspect_ids(
        card,
        {
            "covered_aspect_ids": ["anchor_3", "anchor_4"],
            "missing_aspect_ids": [],
        },
        completion_percentage=50,
        is_complete=False,
    )

    assert covered_ids == ["fact_0", "fact_1"]
    assert missing_ids == []


def test_fact_with_subpoints_requires_every_child_point():
    fact = {
        "text": "交易量前三大",
        "required": True,
        "aliases": [],
        "subpoints": ["台積電", "聯電", "華邦電"],
    }

    assert scoring_service.calculate_fact_score("交易量前三大包含台積電。", [fact]) == 0.0
    assert scoring_service.calculate_fact_score("台積電與聯電是交易量前三大。", [fact]) == 0.0
    assert scoring_service.calculate_fact_score("交易量前三大是台積電、聯電和華邦電。", [fact]) == 1.0
