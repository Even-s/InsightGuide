"""Tests for adaptive stakeholder plan generation."""

import json
from types import SimpleNamespace
from unittest.mock import patch

from app.models.project import Project
from app.services.openai_service import openai_service
from app.services.stakeholder_plan_service import (
    INTERVIEW_GUIDE_DRAFT_RESPONSE_FORMAT,
    STAKEHOLDER_PLAN_RESPONSE_FORMAT,
    STAKEHOLDER_PROFILE_DRAFT_RESPONSE_FORMAT,
    STAKEHOLDER_SLOT_DRAFT_RESPONSE_FORMAT,
    StakeholderPlanService,
)


def _slot(label: str, category: str, *, first_wave: bool) -> dict:
    return {
        "role_category": category,
        "role_label": label,
        "rationale": f"了解 {label} 的獨有資訊",
        "expected_contributions": ["流程", "限制", "例外"],
        "key_questions_to_cover": [
            "最近一次處理這件事時發生了什麼？",
            "上次遇到例外時怎麼處理？",
            "哪一個步驟最花時間？",
            "能不能舉一個最近的例子？",
        ],
        "priority": "required",
        "min_interviews": 1,
        "conditions": "",
        "first_wave": first_wave,
    }


def _healthcare_plan() -> dict:
    return {
        "slots": [
            _slot("掛號櫃台人員", "operations", first_wave=True),
            _slot("門診行政主管", "management", first_wave=True),
            _slot("病患 / 代掛號家屬", "user", first_wave=False),
            _slot("院內資訊室 / HIS 人員", "engineering", first_wave=False),
            _slot("個資與法遵人員", "legal", first_wave=False),
        ]
    }


def _project() -> Project:
    return Project(
        id="proj_test",
        user_id="user_default",
        title="網上預約掛號系統",
        description="為醫療櫃台人員提供線上預約掛號與當日掛號管理。",
        status="active",
    )


def test_ai_plan_uses_structured_object_and_keeps_adaptive_role_count():
    service = StakeholderPlanService()
    with patch.object(openai_service, "chat_completion", return_value=_healthcare_plan()) as chat:
        slots = service._ai_suggest_slots(_project())

    assert len(slots) == 5
    assert [slot["role_label"] for slot in slots[:2]] == ["掛號櫃台人員", "門診行政主管"]
    assert all(slot["source"] == "ai_suggested" for slot in slots)
    assert sum(slot["first_wave"] for slot in slots) == 2

    request = chat.call_args.kwargs
    assert request["response_format"] == STAKEHOLDER_PLAN_RESPONSE_FORMAT
    system_prompt = request["messages"][0]["content"]
    user_prompt = request["messages"][1]["content"]
    assert "不要為了符合固定數量" in system_prompt
    assert "first_wave" in system_prompt
    assert "不要使用「只有他／他們能」" in user_prompt
    assert "第一手經驗、職責或決策權限" in user_prompt


def test_invalid_single_role_object_is_retried_instead_of_silently_falling_back():
    service = StakeholderPlanService()
    single_role = _slot("掛號櫃台主管", "management", first_wave=True)
    with patch.object(
        openai_service,
        "chat_completion",
        side_effect=[single_role, _healthcare_plan()],
    ) as chat:
        slots = service._ai_suggest_slots(_project())

    assert chat.call_count == 2
    assert slots[0]["role_label"] == "掛號櫃台人員"
    assert all(slot["source"] == "ai_suggested" for slot in slots)


def test_persistently_invalid_output_uses_transparent_fallback():
    service = StakeholderPlanService()
    with patch.object(openai_service, "chat_completion", return_value={"unexpected": []}) as chat:
        slots = service._ai_suggest_slots(_project())

    assert chat.call_count == 2
    assert [slot["role_label"] for slot in slots] == [
        "實際使用者",
        "流程負責人 / 決策者",
        "技術 / 系統整合負責人",
    ]
    assert all(slot["source"] == "fallback" for slot in slots)
    assert sum(slot["first_wave"] for slot in slots) == 2


def test_first_wave_is_normalized_to_two_or_three_roles():
    service = StakeholderPlanService()
    plan = _healthcare_plan()
    for slot in plan["slots"]:
        slot["first_wave"] = True

    slots = service._validate_ai_slots(plan)

    assert sum(slot["first_wave"] for slot in slots) == 3
    assert all(slot["first_wave"] for slot in slots[:3])


def test_exclusive_rationale_prefix_is_neutralized():
    service = StakeholderPlanService()
    plan = _healthcare_plan()
    plan["slots"][0]["rationale"] = "只有他們能直接說出線上預約在櫃台現場怎麼被使用。"
    plan["slots"][1]["rationale"] = "只有他能說清楚掛號規則與例外處理標準。"

    slots = service._validate_ai_slots(plan)

    assert slots[0]["rationale"] == "了解線上預約在櫃台現場怎麼被使用。"
    assert slots[1]["rationale"] == "了解掛號規則與例外處理標準。"
    assert all("只有他" not in slot["rationale"] for slot in slots)


def test_openai_wrapper_parses_json_schema_responses():
    payload = _healthcare_plan()
    response = SimpleNamespace(
        usage=None,
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))],
    )

    with patch.object(openai_service.client.chat.completions, "create", return_value=response):
        result = openai_service.chat_completion(
            messages=[{"role": "user", "content": "Return JSON"}],
            response_format=STAKEHOLDER_PLAN_RESPONSE_FORMAT,
            purpose="stakeholder_plan_test",
        )

    assert isinstance(result, dict)
    assert result["slots"][0]["role_label"] == "掛號櫃台人員"


def test_refine_slot_draft_improves_text_but_preserves_planning_choices():
    service = StakeholderPlanService()
    current_draft = {
        "role_category": "operations",
        "role_label": "櫃台",
        "rationale": "想問流程",
        "expected_contributions": [],
        "key_questions_to_cover": [],
        "priority": "recommended",
        "min_interviews": 2,
        "first_wave": True,
    }
    generated = {
        "role_category": "management",
        "role_label": "門診掛號櫃台人員",
        "rationale": "只有他們能直接說出每日掛號流程與常見例外。",
        "expected_contributions": ["每日掛號流程", "尖峰時段需求", "常見例外"],
        "key_questions_to_cover": [
            "最近一次遇到掛號尖峰時，哪個步驟最容易塞車？",
            "上次處理重複掛號時，你怎麼確認資料？",
            "能不能舉一個病患臨時改期的例子？",
            "最近一次系統中斷時，你怎麼繼續作業？",
        ],
        "priority": "required",
        "min_interviews": 1,
        "first_wave": False,
    }

    with patch.object(openai_service, "chat_completion", return_value=generated) as chat:
        draft = service.assist_slot_draft(
            _project(),
            current_draft=current_draft,
            existing_role_labels=["門診行政主管"],
        )

    assert draft["role_label"] == "門診掛號櫃台人員"
    assert draft["rationale"] == "了解每日掛號流程與常見例外。"
    assert draft["expected_contributions"] == ["每日掛號流程", "尖峰時段需求", "常見例外"]
    assert draft["role_category"] == "operations"
    assert draft["priority"] == "recommended"
    assert draft["min_interviews"] == 2
    assert draft["first_wave"] is True

    request = chat.call_args.kwargs
    assert request["response_format"] == STAKEHOLDER_SLOT_DRAFT_RESPONSE_FORMAT
    assert request["purpose"] == "stakeholder_slot_refine"
    assert "門診行政主管" in request["messages"][1]["content"]


def test_voice_slot_draft_uses_transcript_and_can_infer_all_fields():
    service = StakeholderPlanService()
    generated = {
        "role_category": "user",
        "role_label": "病患或代掛號家屬",
        "rationale": "了解線上預約的實際操作經驗與障礙。",
        "expected_contributions": ["預約流程", "操作困難", "通知需求"],
        "key_questions_to_cover": [
            "最近一次線上掛號時，你從哪裡開始操作？",
            "上次找不到可預約時段時，你怎麼處理？",
            "能不能舉一個需要替家人掛號的例子？",
            "最近一次收到掛號通知時，哪些資訊最有用？",
        ],
        "priority": "required",
        "min_interviews": 3,
        "first_wave": True,
    }

    with patch.object(openai_service, "chat_completion", return_value=generated) as chat:
        draft = service.assist_slot_draft(
            _project(),
            transcript="我想加病患跟幫家人掛號的人，了解他們線上操作會卡在哪裡。",
        )

    assert draft == generated
    request = chat.call_args.kwargs
    assert request["purpose"] == "stakeholder_slot_voice_parse"
    assert "我想加病患跟幫家人掛號的人" in request["messages"][1]["content"]
    assert request["response_format"] == STAKEHOLDER_SLOT_DRAFT_RESPONSE_FORMAT


def test_voice_profile_draft_extracts_only_spoken_participant_fields():
    service = StakeholderPlanService()
    generated = {
        "name": "王小明",
        "role_title": "門診櫃台組長",
        "department": "門診行政部",
        "stakeholder_type": "operations",
        "expertise_tags": ["掛號流程", "尖峰人流處理"],
        "knowledge_boundaries": ["系統架構"],
    }

    with patch.object(openai_service, "chat_completion", return_value=generated) as chat:
        draft = service.assist_profile_draft(
            _project(),
            transcript="王小明是門診櫃台組長，熟悉掛號和尖峰人流，但不熟系統架構。",
            slot_context={"role_category": "operations", "role_label": "掛號櫃台人員"},
        )

    assert draft == generated
    request = chat.call_args.kwargs
    assert request["purpose"] == "stakeholder_profile_voice_parse"
    assert request["response_format"] == STAKEHOLDER_PROFILE_DRAFT_RESPONSE_FORMAT
    assert "不可杜撰個人資料" in request["messages"][0]["content"]
    assert "掛號櫃台人員" in request["messages"][1]["content"]


def test_voice_interview_guide_draft_changes_only_spoken_fields():
    service = StakeholderPlanService()
    current = {
        "duration_minutes": 30,
        "interview_purpose": "了解現有掛號流程",
        "focus_topics": "每日作業",
        "exclude_topics": "",
        "interview_style": "structured",
    }
    generated = {
        "duration_minutes": 43,
        "interview_purpose": "不應覆蓋原值",
        "focus_topics": "掛號尖峰、例外處理",
        "exclude_topics": "系統架構",
        "interview_style": "exploratory",
        "changed_fields": [
            "duration_minutes",
            "focus_topics",
            "exclude_topics",
            "interview_style",
        ],
    }

    with patch.object(openai_service, "chat_completion", return_value=generated) as chat:
        draft = service.assist_interview_guide_draft(
            _project(),
            transcript="改成 45 分鐘，聚焦掛號尖峰和例外，不問系統架構，採探索型。",
            profile_context={"name": "王小明", "role_title": "門診櫃台組長"},
            current_draft=current,
        )

    assert draft == {
        "duration_minutes": 45,
        "interview_purpose": "了解現有掛號流程",
        "focus_topics": "掛號尖峰、例外處理",
        "exclude_topics": "系統架構",
        "interview_style": "exploratory",
    }
    request = chat.call_args.kwargs
    assert request["purpose"] == "interview_guide_voice_parse"
    assert request["response_format"] == INTERVIEW_GUIDE_DRAFT_RESPONSE_FORMAT
    assert "changed_fields" in request["messages"][0]["content"]
    assert "王小明" in request["messages"][1]["content"]
