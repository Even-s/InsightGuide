"""Tests for ScriptPlan cursor advancement."""

from types import SimpleNamespace

import pytest

import app.api.routes.script_plan as script_plan_routes
from app.services.hallucination_filter import HallucinationFilter
from app.services.script_plan_service import (
    AdvanceResult,
    ScriptPlan,
    ScriptPlanService,
    ScriptSentence,
)


def test_serialize_topic_card_for_plan_preserves_coverage_rule():
    coverage_rule = {
        "semanticAnchors": ["熱門股票期貨的交易量和價格變動情況"],
        "expectedKeywords": ["交易量", "振幅", "股票期貨"],
        "mustMentionFacts": [{"text": "前五大排名", "required": True}],
    }
    topic_card = SimpleNamespace(
        id="card_1",
        slide_id="slide_1",
        title="熱門股票期貨速覽",
        description="提供交易量、振幅、漲幅和跌幅排名。",
        importance="must",
        suggested_script="今天我們看熱門股票期貨現況。",
        coverage_rule=coverage_rule,
        slide_page_number=2,
        order_index=0,
    )

    serialized = script_plan_routes.serialize_topic_card_for_plan(topic_card)

    assert serialized["coverage_rule"] == coverage_rule
    assert serialized["coverage_rule"]["semanticAnchors"]
    assert serialized["coverage_rule"]["expectedKeywords"]
    assert serialized["coverage_rule"]["mustMentionFacts"]
    assert serialized["suggested_script"] == "今天我們看熱門股票期貨現況。"
    assert serialized["slide_page_number"] == 2
    assert serialized["order_index"] == 0


def test_sort_cards_for_script_plan_uses_slide_page_and_card_order_not_slide_id():
    cards = [
        {"id": "card_c", "slide_id": "slide_a", "slide_page_number": 2, "order_index": 0},
        {"id": "card_b", "slide_id": "slide_z", "slide_page_number": 1, "order_index": 1},
        {"id": "card_a", "slide_id": "slide_z", "slide_page_number": 1, "order_index": 0},
    ]

    sorted_cards = script_plan_routes.sort_cards_for_script_plan(cards)

    assert [card["id"] for card in sorted_cards] == ["card_a", "card_b", "card_c"]


def test_existing_script_plan_alignment_rejects_out_of_order_card_targets():
    plan = ScriptPlan(
        session_id="session_order",
        version=1,
        created_at="2026-06-03T00:00:00",
        cursor=0,
        sentences=[
            ScriptSentence(
                id="sent_1",
                slide_id="slide_1",
                text="先講第三張卡",
                target_card_id="card_3",
                intent="elaborate",
                keywords=[],
                semantic_anchor="第三張卡",
                order_index=0,
            ),
            ScriptSentence(
                id="sent_2",
                slide_id="slide_1",
                text="再講第一張卡",
                target_card_id="card_1",
                intent="elaborate",
                keywords=[],
                semantic_anchor="第一張卡",
                order_index=1,
            ),
        ],
    )
    ordered_cards = [{"id": "card_1"}, {"id": "card_2"}, {"id": "card_3"}]

    assert not script_plan_routes.is_plan_aligned_with_card_order(plan, ordered_cards)


def test_existing_script_plan_alignment_rejects_undercovered_card_targets():
    plan = ScriptPlan(
        session_id="session_undercovered",
        version=1,
        created_at="2026-06-03T00:00:00",
        cursor=0,
        sentences=[
            ScriptSentence(
                id="sent_1",
                slide_id="slide_1",
                text="第一張卡第一句",
                target_card_id="card_1",
                intent="elaborate",
                keywords=[],
                semantic_anchor="第一張卡",
                order_index=0,
            ),
            ScriptSentence(
                id="sent_2",
                slide_id="slide_1",
                text="第一張卡第二句",
                target_card_id="card_1",
                intent="elaborate",
                keywords=[],
                semantic_anchor="第一張卡",
                order_index=1,
            ),
            ScriptSentence(
                id="sent_3",
                slide_id="slide_1",
                text="第一張卡第三句",
                target_card_id="card_1",
                intent="elaborate",
                keywords=[],
                semantic_anchor="第一張卡",
                order_index=2,
            ),
            ScriptSentence(
                id="sent_4",
                slide_id="slide_1",
                text="第二張卡只有一句",
                target_card_id="card_2",
                intent="elaborate",
                keywords=[],
                semantic_anchor="第二張卡",
                order_index=3,
            ),
            ScriptSentence(
                id="sent_5",
                slide_id="slide_1",
                text="第三張卡第一句",
                target_card_id="card_3",
                intent="elaborate",
                keywords=[],
                semantic_anchor="第三張卡",
                order_index=4,
            ),
            ScriptSentence(
                id="sent_6",
                slide_id="slide_1",
                text="第三張卡第二句",
                target_card_id="card_3",
                intent="elaborate",
                keywords=[],
                semantic_anchor="第三張卡",
                order_index=5,
            ),
        ],
    )
    ordered_cards = [{"id": "card_1"}, {"id": "card_2"}, {"id": "card_3"}]

    assert not script_plan_routes.is_plan_aligned_with_card_order(plan, ordered_cards)


def test_generated_sentence_data_is_forced_into_card_order():
    script_plan_service = ScriptPlanService()
    sentence_data = [
        {"target_card_id": "card_3", "text": "第三張卡"},
        {"target_card_id": "card_1", "text": "第一張卡"},
        {"target_card_id": "card_2", "text": "第二張卡"},
    ]
    ordered_cards = [{"id": "card_1"}, {"id": "card_2"}, {"id": "card_3"}]

    sorted_sentence_data = script_plan_service._sort_sentence_data_by_card_order(
        sentence_data,
        ordered_cards,
    )

    assert [sentence["target_card_id"] for sentence in sorted_sentence_data] == [
        "card_1",
        "card_2",
        "card_3",
    ]


def test_generated_sentence_normalization_preserves_model_order():
    script_plan_service = ScriptPlanService()
    sentence_data = [
        {"target_card_id": "card_3", "text": "先用開場建立今天的主軸。"},
        {"target_card_id": "card_1", "text": "再回到交易量排行補充市場熱度。"},
        {"target_card_id": "missing_card", "text": "最後整合力積電的 AI 題材。"},
    ]
    reference_cards = [{"id": "card_1"}, {"id": "card_2"}, {"id": "card_3"}]

    normalized_sentence_data = script_plan_service._normalize_generated_sentence_data(
        sentence_data,
        reference_cards,
    )

    assert [sentence["text"] for sentence in normalized_sentence_data] == [
        "先用開場建立今天的主軸。",
        "再回到交易量排行補充市場熱度。",
        "最後整合力積電的 AI 題材。",
    ]
    assert normalized_sentence_data[2]["target_card_id"] is None


def test_plan_generation_prompt_lets_model_choose_length_and_flow():
    script_plan_service = ScriptPlanService()

    prompt = script_plan_service._build_plan_generation_prompt(
        {
            "slides": [
                {"page_number": index, "title": f"投影片 {index}", "ai_summary": "", "extracted_text": ""}
                for index in range(1, 7)
            ],
            "uncovered_cards": [
                {"id": f"card_{index}", "title": f"第 {index} 張卡片"}
                for index in range(1, 7)
            ],
            "speaker_profile": {"language": "zh-TW", "style": "專業親切"},
            "presentation_info": {"title": "測試簡報"},
        },
        num_sentences=None,
    )

    assert "自行判斷需要幾句" in prompt
    assert "主題卡片是素材和提醒，不是逐張平均分配的清單" in prompt
    assert "每張 must/should 卡片至少要有一個可辨識的重點" in prompt
    assert "以卡片順序作為主線骨架" in prompt
    assert "第 6 張卡片" in prompt
    assert "投影片 6" in prompt
    assert "請生成 12 句" not in prompt
    assert "嚴格依照卡片順序" not in prompt
    assert "不需要照卡片清單順序" not in prompt
    assert "前 5 個" not in prompt


def test_full_transcript_segmenter_splits_presenter_sized_chunks():
    script_plan_service = ScriptPlanService()

    segments = script_plan_service._segment_transcript_for_presenting(
        "大家好，今天先看熱門股票期貨速覽。接著我們會把焦點放在力積電的 3D AI Foundry，說明它如何回應 AI 與 HPC 的高頻寬記憶體需求。最後再回到交易量、振幅、漲跌幅排行榜，快速看今天市場熱度。"
    )

    assert len(segments) >= 3
    assert segments[0].startswith("大家好")
    assert all(segment.endswith("。") for segment in segments)
    assert any("3D AI Foundry" in segment for segment in segments)


def test_full_transcript_segmenter_keeps_prompt_chunks_short():
    script_plan_service = ScriptPlanService()

    segments = script_plan_service._segment_transcript_for_presenting(
        "力積電在 Computex 主打 3D AI Foundry，展示 3D WoW DRAM 堆疊、IPD 和 Interposer 等先進封裝技術，鎖定生成式 AI 與 HPC 的高頻寬記憶體需求。"
    )

    assert len(segments) >= 2
    assert max(len(segment) for segment in segments) <= 52
    assert any("3D AI Foundry" in segment for segment in segments)
    assert any("高頻寬記憶體需求" in segment for segment in segments)


def test_full_transcript_segmenter_adds_polite_closing_when_missing():
    script_plan_service = ScriptPlanService()

    segments = script_plan_service._segment_transcript_for_presenting(
        "跌幅榜看到南電和南亞科走弱，提醒大家今天盤面仍然有明顯的強弱分歧。"
    )

    assert "謝謝大家" in segments[-1]
    assert "提醒大家今天盤面仍然有明顯的強弱分歧" in " ".join(segments)


def test_build_sentence_data_uses_full_transcript_instead_of_model_sentence_order():
    script_plan_service = ScriptPlanService()

    sentence_data = script_plan_service._build_sentence_data_from_full_transcript(
        "大家好，今天先看力積電的 AI 題材。交易量方面，力積電也進入前五名。",
        [
            {
                "id": "card_ai",
                "slide_id": "slide_1",
                "title": "力積電 AI 題材",
                "coverage_rule": {"expectedKeywords": ["AI"]},
            },
            {
                "id": "card_volume",
                "slide_id": "slide_2",
                "title": "交易量排行",
                "coverage_rule": {"expectedKeywords": ["交易量"]},
            },
        ],
    )

    assert [sentence["text"] for sentence in sentence_data] == [
        "大家好，今天先看力積電的 AI 題材。",
        "交易量方面，力積電也進入前五名，以上是今天的整理，謝謝大家。",
    ]
    assert sentence_data[0]["intent"] == "introduce"
    assert sentence_data[-1]["intent"] == "conclude"


@pytest.mark.asyncio
async def test_reorder_plan_can_edit_sentence_text_before_presenting():
    script_plan_service = ScriptPlanService()
    session_id = "session_reorder_edit_test"
    await script_plan_service.clear_plan(session_id)

    script_plan_service._plans[session_id] = ScriptPlan(
        session_id=session_id,
        version=1,
        created_at="2026-06-03T00:00:00",
        cursor=0,
        generation_context={
            "cards": [
                {
                    "id": "card_1",
                    "title": "力積電 AI 題材",
                    "coverage_rule": {
                        "expectedKeywords": ["力積電", "AI", "Memory Wall"],
                        "mustMentionFacts": [{"text": "高階封裝"}],
                    },
                },
                {
                    "id": "card_2",
                    "title": "交易量排行",
                    "coverage_rule": {
                        "expectedKeywords": ["交易量", "期貨"],
                    },
                },
            ],
        },
        sentences=[
            ScriptSentence(
                id="sent_1",
                slide_id="slide_1",
                text="第一句原文。",
                target_card_id="card_1",
                intent="introduce",
                keywords=["第一句"],
                semantic_anchor="第一句原文",
                status="active",
                order_index=0,
            ),
            ScriptSentence(
                id="sent_2",
                slide_id="slide_1",
                text="第二句原文。",
                target_card_id="card_2",
                intent="elaborate",
                keywords=["第二句"],
                semantic_anchor="第二句原文",
                status="pending",
                order_index=1,
            ),
        ],
    )

    plan = await script_plan_service.reorder_plan(
        session_id,
        ordered_sentence_ids=["sent_2", "sent_1"],
        sentence_text_updates={
            "sent_2": "交易量方面，力積電期貨進入前五名。",
            "sent_1": "力積電 AI 題材聚焦 Memory Wall。",
        },
    )

    assert [sentence.id for sentence in plan.sentences] == ["sent_2", "sent_1"]
    assert [sentence.text for sentence in plan.sentences] == [
        "交易量方面，力積電期貨進入前五名。",
        "力積電 AI 題材聚焦 Memory Wall。",
    ]
    assert set(plan.sentences[0].keywords) >= {"交易量", "期貨"}
    assert set(plan.sentences[1].keywords) >= {"力積電", "AI", "Memory Wall"}
    assert [sentence.status for sentence in plan.sentences] == ["active", "pending"]
    assert plan.metadata["manually_edited"] is True
    assert "交易量方面" in plan.metadata["full_transcript"]

    await script_plan_service.clear_plan(session_id)


@pytest.mark.asyncio
async def test_reorder_plan_can_delete_sentence_before_presenting():
    script_plan_service = ScriptPlanService()
    session_id = "session_reorder_delete_test"
    await script_plan_service.clear_plan(session_id)

    script_plan_service._plans[session_id] = ScriptPlan(
        session_id=session_id,
        version=1,
        created_at="2026-06-03T00:00:00",
        cursor=0,
        generation_context={},
        sentences=[
            ScriptSentence(
                id="sent_1",
                slide_id="slide_1",
                text="第一句保留。",
                target_card_id="card_1",
                intent="introduce",
                keywords=["第一句"],
                semantic_anchor="第一句保留",
                status="active",
                order_index=0,
            ),
            ScriptSentence(
                id="sent_2",
                slide_id="slide_1",
                text="第二句刪除。",
                target_card_id="card_2",
                intent="elaborate",
                keywords=["第二句"],
                semantic_anchor="第二句刪除",
                status="pending",
                order_index=1,
            ),
            ScriptSentence(
                id="sent_3",
                slide_id="slide_1",
                text="第三句保留。",
                target_card_id="card_3",
                intent="conclude",
                keywords=["第三句"],
                semantic_anchor="第三句保留",
                status="pending",
                order_index=2,
            ),
        ],
    )

    plan = await script_plan_service.reorder_plan(
        session_id,
        ordered_sentence_ids=["sent_3", "sent_1"],
        sentence_text_updates={"sent_3": "第三句移到前面。"},
    )

    assert [sentence.id for sentence in plan.sentences] == ["sent_3", "sent_1"]
    assert [sentence.order_index for sentence in plan.sentences] == [0, 1]
    assert [sentence.status for sentence in plan.sentences] == ["active", "pending"]
    assert plan.sentences[0].text == "第三句移到前面。"
    assert "第二句刪除" not in plan.metadata["full_transcript"]
    assert plan.metadata["manually_deleted_count"] == 1

    await script_plan_service.clear_plan(session_id)


def test_generated_sentence_data_fills_underallocated_cards():
    script_plan_service = ScriptPlanService()
    ordered_cards = [
        {
            "id": "card_1",
            "slide_id": "slide_1",
            "title": "熱門股票期貨數據分析",
            "coverage_rule": {
                "expectedKeywords": ["交易量"],
                "mustMentionFacts": [{"text": "交易量前三大", "subpoints": ["台積電", "聯電", "華邦電"]}],
            },
        },
        {
            "id": "card_2",
            "slide_id": "slide_1",
            "title": "力積電在Computex的技術展示",
            "coverage_rule": {
                "expectedKeywords": ["力積電", "Computex"],
                "mustMentionFacts": [{"text": "技術展示與成長想像"}],
            },
        },
        {
            "id": "card_3",
            "slide_id": "slide_1",
            "title": "投影片重要聲明",
            "coverage_rule": {
                "expectedKeywords": ["風險"],
                "mustMentionFacts": [{"text": "資料僅供參考"}],
            },
        },
    ]
    sentence_data = [
        {"target_card_id": "card_1", "text": "第一張卡第一句"},
        {"target_card_id": "card_1", "text": "第一張卡第二句"},
        {"target_card_id": "card_1", "text": "第一張卡第三句"},
        {"target_card_id": "card_2", "text": "第二張卡只有一句"},
    ]

    filled_sentence_data = script_plan_service._ensure_minimum_card_sentence_coverage(
        sentence_data,
        ordered_cards,
        min_sentences_per_card=2,
        max_sentences=12,
    )

    target_counts = {
        card_id: sum(1 for sentence in filled_sentence_data if sentence["target_card_id"] == card_id)
        for card_id in ["card_1", "card_2", "card_3"]
    }

    assert target_counts == {"card_1": 4, "card_2": 2, "card_3": 2}
    assert [sentence["target_card_id"] for sentence in filled_sentence_data[:6]] == [
        "card_1",
        "card_1",
        "card_2",
        "card_2",
        "card_3",
        "card_3",
    ]
    assert "交易量方面" in filled_sentence_data[1]["text"]
    assert "台積電" in filled_sentence_data[1]["text"]
    assert "聯電" in filled_sentence_data[1]["text"]
    assert "要完整講到" not in filled_sentence_data[1]["text"]
    assert "並提到" not in filled_sentence_data[1]["text"]
    assert "技術展示與成長想像" in filled_sentence_data[3]["text"]
    assert filled_sentence_data[4]["keywords"] == ["風險"]


def test_generated_sentence_data_fills_missing_subpoints_even_when_card_has_sentences():
    script_plan_service = ScriptPlanService()
    ordered_cards = [
        {
            "id": "card_market",
            "slide_id": "slide_1",
            "title": "熱門股票期貨數據分析",
            "coverage_rule": {
                "expectedKeywords": ["交易量"],
                "mustMentionFacts": [
                    {"text": "交易量前三大", "subpoints": ["台積電", "聯電", "華邦電"]},
                    {"text": "振幅最大標的", "subpoints": ["華邦電"]},
                ],
            },
        },
    ]
    sentence_data = [
        {"target_card_id": "card_market", "text": "交易量前三大裡面先看到台積電。"},
        {"target_card_id": "card_market", "text": "振幅最大標的是華邦電。"},
    ]

    filled_sentence_data = script_plan_service._ensure_minimum_card_sentence_coverage(
        sentence_data,
        ordered_cards,
        min_sentences_per_card=2,
        max_sentences=12,
    )

    combined_text = " ".join(sentence["text"] for sentence in filled_sentence_data)

    assert "台積電" in combined_text
    assert "聯電" in combined_text
    assert "華邦電" in combined_text
    assert "要完整講到" not in combined_text
    assert "並提到" not in combined_text
    assert combined_text.count("振幅最大標的") == 1


def test_required_sentence_composer_avoids_checklist_language():
    script_plan_service = ScriptPlanService()

    text = script_plan_service._compose_natural_required_sentence(
        "AI營運機會",
        ["突破Memory Wall", "切入AI晶片代工"],
        {"title": "力積電 3D AI Foundry"},
    )

    assert "AI" in text
    assert "Memory Wall" in text
    assert "晶片代工" in text
    assert "並提到" not in text
    assert "要涵蓋" not in text
    assert "這張卡" not in text


def test_sanitize_script_sentence_rewrites_meta_card_summary():
    script_plan_service = ScriptPlanService()

    text = script_plan_service._sanitize_script_sentence_text(
        "這張卡要說明本日焦點是力積電，其中Computex焦點。",
        {
            "semantic_anchor": "力積電 Computex 焦點",
            "keywords": ["力積電", "Computex", "3D AI Foundry"],
        },
    )

    assert "力積電" in text
    assert "Computex" in text
    assert "這張卡" not in text
    assert "本日焦點是" not in text


def test_presenter_sentence_for_market_numbers_is_not_fragmentary():
    script_plan_service = ScriptPlanService()

    text = script_plan_service._compose_presenter_sentence(
        "交易量前三大",
        ["小型台積電 53,412口", "聯電 45,550口", "華邦電 24,316口"],
    )

    assert text.startswith("交易量方面")
    assert "小型台積電" in text
    assert "聯電" in text
    assert "另外還有" in text
    assert "並提到" not in text


def test_non_final_sentence_drops_misleading_final_prefix():
    script_plan_service = ScriptPlanService()

    normalized = script_plan_service._normalize_sentence_text_for_position(
        "最後，我們回到力積電在 Computex 的技術展示。",
        index=3,
        total=8,
    )

    assert normalized == "我們回到力積電在 Computex 的技術展示。"


def test_initial_sentence_text_drops_continuation_prefix():
    script_plan_service = ScriptPlanService()

    normalized = script_plan_service._normalize_initial_sentence_text(
        "了解這個前提後，我們就先來看今天熱門股票期貨的整體表現。"
    )

    assert normalized == "我們就先來看今天熱門股票期貨的整體表現。"
    assert "了解這個前提後" not in normalized


def test_script_plan_card_format_prioritizes_important_points():
    script_plan_service = ScriptPlanService()
    formatted = script_plan_service._format_card_for_script_plan({
        "id": "card_1",
        "slide_page_number": 1,
        "order_index": 0,
        "title": "熱門股票期貨速覽",
        "description": "提供交易量、振幅、漲幅和跌幅排名。",
        "importance": "must",
        "coverage_rule": {
            "semanticAnchors": ["一般語意線索"],
            "expectedKeywords": ["交易量", "振幅"],
            "mustMentionFacts": [{"text": "重要重點一", "required": True}],
        },
        "suggested_script": "今天我們看熱門股票期貨現況。",
    })

    assert "重要重點: 重要重點一" in formatted
    assert "語意錨點背景: 一般語意線索" in formatted
    assert "必講事實:" not in formatted
    assert formatted.index("重要重點") < formatted.index("語意錨點背景")


def test_script_plan_card_format_falls_back_to_anchors_when_facts_missing():
    script_plan_service = ScriptPlanService()
    formatted = script_plan_service._format_card_for_script_plan({
        "id": "card_1",
        "title": "熱門股票期貨速覽",
        "description": "提供交易量、振幅、漲幅和跌幅排名。",
        "importance": "must",
        "coverage_rule": {
            "semanticAnchors": ["交易量排行", "漲跌幅排行"],
            "expectedKeywords": ["交易量", "振幅"],
            "mustMentionFacts": [],
        },
        "suggested_script": "今天我們看熱門股票期貨現況。",
    })

    assert "重要重點: 交易量排行；漲跌幅排行" in formatted
    assert "語意錨點背景: 交易量排行；漲跌幅排行" in formatted


@pytest.mark.asyncio
async def test_single_off_topic_signal_holds_instead_of_regenerating():
    script_plan_service = ScriptPlanService()
    session_id = "session_script_plan_off_topic_test"
    await script_plan_service.clear_plan(session_id)

    def fake_progression_mode(**_kwargs):
        return {"mode": "regenerate", "coverage": 0, "reason_code": "off_topic"}

    script_plan_service.semantic_judge.judge_script_progression_mode = fake_progression_mode

    result = await script_plan_service._judge_match(
        session_id=session_id,
        transcript="這段先講完全不同的背景資訊。",
        expected_sentence=ScriptSentence(
            id="sent_1",
            slide_id="slide_1",
            text="各位好，今天先看熱門股票期貨的現況。",
            target_card_id="card_market",
            intent="introduce",
            keywords=["股票期貨", "現況"],
            semantic_anchor="熱門股票期貨現況",
            status="active",
            order_index=0,
        ),
        next_sentences=[],
    )

    assert result["action"] == "hold"
    assert "mismatch_count=1" in result["reason"]

    await script_plan_service.clear_plan(session_id)


def test_local_paraphrase_handles_memory_bottleneck_asr_error():
    script_plan_service = ScriptPlanService()
    expected_sentence = ScriptSentence(
        id="sent_memory_bottleneck",
        slide_id="slide_1",
        text="它的重點之一，是想突破記憶體瓶頸，讓整體運算效率可以再往上提升。",
        target_card_id="card_memory",
        intent="elaborate",
        keywords=["記憶體瓶頸", "運算效率", "提升"],
        semantic_anchor="突破記憶體瓶頸並提升整體運算效率",
        status="active",
        order_index=0,
    )

    assert script_plan_service._is_likely_paraphrase(
        expected_sentence,
        "那它的重點之一是想要普及的瓶頸，讓整體的運算效能可以再往上提升一個檔次。",
    )


def test_polite_closing_inside_meaningful_sentence_is_not_hallucination():
    hallucination_filter = HallucinationFilter()

    standalone = hallucination_filter.is_hallucination("謝謝大家")
    meaningful_closing = hallucination_filter.is_hallucination(
        "那以上就是我們今天想要整理給大家的重點。謝謝大家。"
    )

    assert standalone["is_hallucination"]
    assert meaningful_closing["is_hallucination"] is False


@pytest.mark.asyncio
async def test_manual_next_skips_current_sentence():
    script_plan_service = ScriptPlanService()
    session_id = "session_manual_next_test"
    await script_plan_service.clear_plan(session_id)

    script_plan_service._plans[session_id] = ScriptPlan(
        session_id=session_id,
        version=1,
        created_at="2026-06-02T00:00:00",
        cursor=0,
        sentences=[
            ScriptSentence(
                id="sent_1",
                slide_id="slide_1",
                text="First prompt",
                target_card_id="card_1",
                intent="introduce",
                keywords=["first"],
                semantic_anchor="first prompt",
                status="active",
                order_index=0,
            ),
            ScriptSentence(
                id="sent_2",
                slide_id="slide_1",
                text="Second prompt",
                target_card_id="card_2",
                intent="elaborate",
                keywords=["second"],
                semantic_anchor="second prompt",
                status="pending",
                order_index=1,
            ),
        ],
    )

    result = await script_plan_service.skip_to_next(session_id)

    assert result.action == "advance"
    assert result.new_cursor == 1
    assert result.current is not None
    assert result.current.id == "sent_2"
    assert result.progress["skipped"] == 1

    plan = await script_plan_service.get_plan(session_id)
    assert plan is not None
    assert plan.sentences[0].status == "skipped"
    assert plan.sentences[1].status == "active"

    final_result = await script_plan_service.skip_to_next(session_id)

    assert final_result.new_cursor == 2
    assert final_result.current is None
    assert final_result.progress["completion_rate"] == 100

    await script_plan_service.clear_plan(session_id)


@pytest.mark.asyncio
async def test_advance_returns_after_one_step_even_when_transcript_contains_final_sentence():
    script_plan_service = ScriptPlanService()
    session_id = "session_final_sentence_cascade_test"
    await script_plan_service.clear_plan(session_id)

    script_plan_service._plans[session_id] = ScriptPlan(
        session_id=session_id,
        version=1,
        created_at="2026-06-02T00:00:00",
        cursor=0,
        sentences=[
            ScriptSentence(
                id="sent_risk",
                slide_id="slide_1",
                text="接下來就請各位依照自己的風險承受度，來留意後續的變化。",
                target_card_id="card_risk",
                intent="closing",
                keywords=["風險承受度", "後續變化"],
                semantic_anchor="依照風險承受度留意後續變化",
                status="active",
                order_index=0,
            ),
            ScriptSentence(
                id="sent_final",
                slide_id="slide_1",
                text="以上是今天的簡要分享，謝謝大家。",
                target_card_id="card_final",
                intent="closing",
                keywords=["以上", "分享", "謝謝大家"],
                semantic_anchor="今天的簡要分享謝謝大家",
                status="pending",
                order_index=1,
            ),
        ],
    )

    def fake_progression_mode(current_text, actual_text, **_kwargs):
        if "風險承受度" in current_text:
            return {"mode": "advance", "coverage": 95, "reason_code": "matched"}
        if "謝謝大家" in current_text and "謝謝大家" in actual_text:
            return {"mode": "advance", "coverage": 95, "reason_code": "matched"}
        return {"mode": "hold", "coverage": 0, "reason_code": "unclear"}

    script_plan_service.semantic_judge.judge_script_progression_mode = fake_progression_mode

    result = await script_plan_service.advance(
        session_id,
        "接下來就請各位依照自己的風險承受度來留意後續的變化。那以上是我今天的分享，謝謝大家。",
    )

    assert result.action == "advance"
    assert result.new_cursor == 1
    assert result.current is not None
    assert result.current.id == "sent_final"
    assert result.next is None
    assert result.progress["completion_rate"] == 50

    plan = await script_plan_service.get_plan(session_id)
    assert plan is not None
    assert [sentence.status for sentence in plan.sentences] == ["spoken", "active"]

    await script_plan_service.clear_plan(session_id)


@pytest.mark.asyncio
async def test_cascade_probe_does_not_increment_mismatch_count():
    script_plan_service = ScriptPlanService()
    session_id = "session_cascade_probe_mismatch_test"
    await script_plan_service.clear_plan(session_id)

    script_plan_service._plans[session_id] = ScriptPlan(
        session_id=session_id,
        version=1,
        created_at="2026-06-02T00:00:00",
        cursor=0,
        sentences=[
            ScriptSentence(
                id="sent_1",
                slide_id="slide_1",
                text="先整理交易量、振幅、漲幅和跌幅的前五大。",
                target_card_id="card_1",
                intent="elaborate",
                keywords=["交易量", "振幅", "漲幅", "跌幅"],
                semantic_anchor="交易量振幅漲幅跌幅前五大",
                status="active",
                order_index=0,
            ),
            ScriptSentence(
                id="sent_2",
                slide_id="slide_1",
                text="接著看力積電在 Computex 的展示亮點。",
                target_card_id="card_2",
                intent="transition",
                keywords=["力積電", "Computex", "展示"],
                semantic_anchor="力積電Computex展示亮點",
                status="pending",
                order_index=1,
            ),
        ],
    )

    def fake_progression_mode(current_text, **_kwargs):
        if "交易量" in current_text:
            return {"mode": "advance", "coverage": 90, "reason_code": "matched"}
        return {"mode": "regenerate", "coverage": 0, "reason_code": "off_topic"}

    script_plan_service.semantic_judge.judge_script_progression_mode = fake_progression_mode

    result = await script_plan_service.advance(
        session_id,
        "那我們今天會整理交易量、振幅、漲幅和跌幅的前五大。",
    )

    assert result.action == "advance"
    assert result.new_cursor == 1
    assert script_plan_service._mismatch_counts.get(session_id, 0) == 0

    await script_plan_service.clear_plan(session_id)


@pytest.mark.asyncio
async def test_disclaimer_sentence_holds_without_regenerating():
    script_plan_service = ScriptPlanService()
    session_id = "session_disclaimer_hold_test"
    await script_plan_service.clear_plan(session_id)
    script_plan_service._mismatch_counts[session_id] = 2

    def fake_progression_mode(**_kwargs):
        return {"mode": "regenerate", "coverage": 0, "reason_code": "off_topic"}

    script_plan_service.semantic_judge.judge_script_progression_mode = fake_progression_mode

    result = await script_plan_service._judge_match(
        session_id=session_id,
        transcript="不構成任何的買賣建議哦。",
        expected_sentence=ScriptSentence(
            id="sent_next",
            slide_id="slide_1",
            text="接著看力積電在 Computex 的展示亮點。",
            target_card_id="card_2",
            intent="transition",
            keywords=["力積電", "Computex", "展示"],
            semantic_anchor="力積電Computex展示亮點",
            status="active",
            order_index=1,
        ),
        next_sentences=[],
    )

    assert result["action"] == "hold"
    assert "soft hold" in result["reason"]
    assert script_plan_service._mismatch_counts[session_id] == 2

    await script_plan_service.clear_plan(session_id)


@pytest.mark.asyncio
async def test_advance_route_does_not_use_card_state_to_advance_on_hold(monkeypatch):
    active_sentence = ScriptSentence(
        id="sent_1",
        slide_id="slide_1",
        text="先看熱門股票期貨的交易量排名。",
        target_card_id="card_market",
        intent="elaborate",
        keywords=["交易量", "排名"],
        semantic_anchor="熱門股票期貨交易量排名",
        status="active",
        order_index=0,
    )
    plan = ScriptPlan(
        session_id="session_route_test",
        version=1,
        created_at="2026-06-02T00:00:00",
        cursor=0,
        sentences=[active_sentence],
    )

    class FakeScriptPlanService:
        async def get_plan(self, _session_id):
            return plan

        async def advance(self, **_kwargs):
            return AdvanceResult(
                action="hold",
                new_cursor=0,
                confidence=0.2,
                reason="partial hold",
                current=active_sentence,
            )

    class FakeDb:
        def query(self, model):
            raise AssertionError(f"advance route should not query card state, got {model}")

    fake_service = FakeScriptPlanService()
    monkeypatch.setattr(script_plan_routes, "script_plan_service", fake_service)

    response = await script_plan_routes.advance_script_plan(
        "session_route_test",
        script_plan_routes.AdvanceRequest(
            transcript="我們先看熱門股票期貨的交易量排名。",
            current_slide_id="slide_1",
        ),
        db=FakeDb(),
    )

    assert response.result.action == "hold"
    assert response.result.current == active_sentence
