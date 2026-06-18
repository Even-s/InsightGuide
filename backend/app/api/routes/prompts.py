"""Prompt Registry API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.prompt_registry_service import prompt_registry_service

router = APIRouter(prefix="/prompts", tags=["prompts"])


class PromptVersionCreate(BaseModel):
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    notes: Optional[str] = None


class PublishRequest(BaseModel):
    version_id: str


class ArchiveRequest(BaseModel):
    version_id: str


class PreviewRequest(BaseModel):
    version_id: Optional[str] = None
    variables: dict = {}


class AssistRequest(BaseModel):
    goal: str
    mode: str = "improve"  # generate | improve
    current_system_prompt: Optional[str] = None
    current_user_prompt: Optional[str] = None
    language: str = "auto"  # zh | en | auto


class ABTestCreate(BaseModel):
    name: str
    variant_a_id: str
    variant_b_id: str
    traffic_percent_b: int = 50


class ABTestStop(BaseModel):
    winner: Optional[str] = None  # a | b | null


class ApprovalRequestCreate(BaseModel):
    version_id: str
    requester: Optional[str] = None


class ApprovalDecision(BaseModel):
    reviewer: Optional[str] = None
    comment: Optional[str] = None


def _serialize_template(t):
    active = next((v for v in t.versions if v.status == "published"), None)
    return {
        "id": t.id,
        "key": t.key,
        "name": t.name,
        "description": t.description,
        "category": t.category,
        "model": t.model,
        "riskLevel": t.risk_level,
        "serviceFile": t.service_file,
        "serviceFunction": t.service_function,
        "inputVariables": t.input_variables,
        "outputFormat": t.output_format,
        "responseSchema": t.response_schema,
        "isActive": t.is_active,
        "activeVersion": _serialize_version(active) if active else None,
        "versionCount": len(t.versions),
        "createdAt": t.created_at.isoformat() if t.created_at else None,
        "updatedAt": t.updated_at.isoformat() if t.updated_at else None,
    }


def _serialize_version(v):
    if not v:
        return None
    return {
        "id": v.id,
        "versionNumber": v.version_number,
        "status": v.status,
        "systemPrompt": v.system_prompt,
        "userPromptTemplate": v.user_prompt_template,
        "notes": v.notes,
        "publishedAt": v.published_at.isoformat() if v.published_at else None,
        "createdAt": v.created_at.isoformat() if v.created_at else None,
        "updatedAt": v.updated_at.isoformat() if v.updated_at else None,
    }


@router.get("/")
async def list_prompts(category: Optional[str] = None, db: Session = Depends(get_db)):
    """List all prompt templates."""
    templates = prompt_registry_service.get_all_templates(db, category=category)
    return [_serialize_template(t) for t in templates]


@router.get("/drift")
async def detect_drift(db: Session = Depends(get_db)):
    """Detect drift between code defaults and registry."""
    return prompt_registry_service.detect_drift(db)


@router.get("/export")
async def export_prompts(db: Session = Depends(get_db)):
    """Export all prompt templates as JSON."""
    return prompt_registry_service.export_all(db)


@router.post("/import")
async def import_prompts(data: list, db: Session = Depends(get_db)):
    """Import prompt templates from JSON."""
    result = prompt_registry_service.import_all(db, data)
    return result


@router.get("/{key}")
async def get_prompt(key: str, db: Session = Depends(get_db)):
    """Get a single prompt template by key."""
    template = prompt_registry_service.get_template_by_key(db, key)
    if not template:
        raise HTTPException(status_code=404, detail=f"Prompt '{key}' not found")
    return _serialize_template(template)


@router.get("/{key}/versions")
async def get_versions(key: str, db: Session = Depends(get_db)):
    """Get all versions of a prompt template."""
    versions = prompt_registry_service.get_versions(db, key)
    if not versions:
        template = prompt_registry_service.get_template_by_key(db, key)
        if not template:
            raise HTTPException(status_code=404, detail=f"Prompt '{key}' not found")
    return [_serialize_version(v) for v in versions]


@router.post("/{key}/versions", status_code=status.HTTP_201_CREATED)
async def create_version(key: str, body: PromptVersionCreate, db: Session = Depends(get_db)):
    """Create a new draft version."""
    try:
        version = prompt_registry_service.create_version(
            db, key,
            system_prompt=body.system_prompt,
            user_prompt_template=body.user_prompt_template,
            notes=body.notes,
        )
        return _serialize_version(version)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{key}/publish")
async def publish_version(key: str, body: PublishRequest, db: Session = Depends(get_db)):
    """Publish a specific version (archives the current published version)."""
    try:
        version = prompt_registry_service.publish_version(db, key, body.version_id)
        return _serialize_version(version)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{key}/rollback")
async def rollback_version(key: str, db: Session = Depends(get_db)):
    """Rollback to the most recent archived version."""
    try:
        version = prompt_registry_service.rollback(db, key)
        if not version:
            raise HTTPException(status_code=400, detail="No archived version to rollback to")
        return _serialize_version(version)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{key}/archive")
async def archive_version(key: str, body: ArchiveRequest, db: Session = Depends(get_db)):
    """Archive a specific version."""
    try:
        version = prompt_registry_service.archive_version(db, key, body.version_id)
        return _serialize_version(version)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{key}/preview")
async def preview_prompt(key: str, body: PreviewRequest, db: Session = Depends(get_db)):
    """Render a prompt version with sample variables."""
    from app.models.prompt_template import PromptVersion

    template = prompt_registry_service.get_template_by_key(db, key)
    if not template:
        raise HTTPException(status_code=404, detail=f"Prompt '{key}' not found")

    if body.version_id:
        version = db.query(PromptVersion).filter(PromptVersion.id == body.version_id).first()
    else:
        version = prompt_registry_service.get_active_version(db, key)

    if not version:
        raise HTTPException(status_code=404, detail="No version found to preview")

    result = {}
    variables = body.variables
    if version.system_prompt:
        try:
            result["systemPrompt"] = version.system_prompt.format(**variables)
        except KeyError as e:
            result["systemPrompt"] = version.system_prompt
            result["missingVariables"] = [str(e).strip("'")]
    if version.user_prompt_template:
        try:
            result["userPrompt"] = version.user_prompt_template.format(**variables)
        except KeyError as e:
            result["userPrompt"] = version.user_prompt_template
            result.setdefault("missingVariables", []).append(str(e).strip("'"))

    return result


@router.get("/{key}/ab-test")
async def get_ab_test(key: str, db: Session = Depends(get_db)):
    """Get the active A/B test for a prompt."""
    test = prompt_registry_service.get_active_ab_test(db, key)
    if not test:
        return None
    stats = prompt_registry_service.get_ab_test_stats(db, test.id)
    return {
        "id": test.id,
        "name": test.name,
        "status": test.status,
        "variantAId": test.variant_a_id,
        "variantBId": test.variant_b_id,
        "trafficPercentB": test.traffic_percent_b,
        "startedAt": test.started_at.isoformat() if test.started_at else None,
        "winner": test.winner,
        "stats": stats,
    }


@router.post("/{key}/ab-test", status_code=status.HTTP_201_CREATED)
async def create_ab_test(key: str, body: ABTestCreate, db: Session = Depends(get_db)):
    """Create an A/B test between two versions."""
    try:
        test = prompt_registry_service.create_ab_test(
            db, key,
            name=body.name,
            variant_a_id=body.variant_a_id,
            variant_b_id=body.variant_b_id,
            traffic_percent_b=body.traffic_percent_b,
        )
        return {"id": test.id, "name": test.name, "status": test.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{key}/ab-test/stop")
async def stop_ab_test(key: str, body: ABTestStop, db: Session = Depends(get_db)):
    """Stop the active A/B test, optionally declaring a winner."""
    try:
        test = prompt_registry_service.stop_ab_test(db, key, winner=body.winner)
        return {"id": test.id, "status": test.status, "winner": test.winner}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{key}/approvals")
async def get_pending_approvals(key: str, db: Session = Depends(get_db)):
    """Get pending approval requests for a prompt."""
    approvals = prompt_registry_service.get_pending_approvals(db, key)
    return [
        {
            "id": a.id,
            "versionId": a.version_id,
            "requester": a.requester,
            "status": a.status,
            "reviewer": a.reviewer,
            "reviewComment": a.review_comment,
            "requestedAt": a.requested_at.isoformat() if a.requested_at else None,
            "reviewedAt": a.reviewed_at.isoformat() if a.reviewed_at else None,
        }
        for a in approvals
    ]


@router.post("/{key}/approvals", status_code=status.HTTP_201_CREATED)
async def request_approval(key: str, body: ApprovalRequestCreate, db: Session = Depends(get_db)):
    """Request approval to publish a high-risk prompt version."""
    try:
        req = prompt_registry_service.request_approval(db, key, body.version_id, requester=body.requester)
        return {"id": req.id, "status": req.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{key}/approvals/{request_id}/approve")
async def approve_request(key: str, request_id: str, body: ApprovalDecision, db: Session = Depends(get_db)):
    """Approve a pending request (auto-publishes the version)."""
    try:
        req = prompt_registry_service.approve(db, request_id, reviewer=body.reviewer, comment=body.comment)
        return {"id": req.id, "status": req.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{key}/approvals/{request_id}/reject")
async def reject_request(key: str, request_id: str, body: ApprovalDecision, db: Session = Depends(get_db)):
    """Reject a pending request."""
    try:
        req = prompt_registry_service.reject(db, request_id, reviewer=body.reviewer, comment=body.comment)
        return {"id": req.id, "status": req.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{key}/assist")
async def prompt_assist(key: str, body: AssistRequest, db: Session = Depends(get_db)):
    """AI-powered prompt writing assistant."""
    from openai import OpenAI
    from app.core.config import settings

    template = prompt_registry_service.get_template_by_key(db, key)
    if not template:
        raise HTTPException(status_code=404, detail=f"Prompt '{key}' not found")

    meta_context = f"""Template metadata:
- Key: {template.key}
- Name: {template.name}
- Category: {template.category}
- Description: {template.description or 'N/A'}
- Input variables: {template.input_variables or []}
- Output format: {template.output_format or 'N/A'}
- Risk level: {template.risk_level}"""

    if body.mode == "improve" and body.current_system_prompt:
        user_msg = f"""用戶目標：{body.goal}

{meta_context}

目前的 System Prompt：
```
{body.current_system_prompt}
```

{f'目前的 User Prompt Template：' + chr(10) + '```' + chr(10) + body.current_user_prompt + chr(10) + '```' if body.current_user_prompt else ''}

請改善這個 prompt，讓它更能達成用戶的目標。"""
    else:
        user_msg = f"""用戶目標：{body.goal}

{meta_context}

請根據目標和 metadata 生成一個高品質的 prompt。"""

    lang_instruction = ""
    if body.language == "zh":
        lang_instruction = "用繁體中文撰寫 prompt。"
    elif body.language == "en":
        lang_instruction = "Write the prompt in English."

    output_fmt = template.output_format
    output_instruction = f"""4. 此 prompt 預期的輸出格式已定義為：「{output_fmt}」。在 prompt 中引用此格式作為對 AI 的輸出指示，但不要重複定義或發明新的格式。直接要求 AI 按照此格式回覆即可。""" if output_fmt else "4. 如果任務需要結構化輸出，在 prompt 中明確指定輸出格式（JSON schema 或具體範例）。"

    system_msg = f"""你是 Prompt Engineering 專家。你的任務是幫使用者撰寫或改善用於 LLM 的 system prompt 和 user prompt template。

規則：
1. 回覆必須是 JSON 格式：{{"system_prompt": "...", "user_prompt_template": "...|null", "explanation": ["改善點1", "改善點2", ...]}}
2. user_prompt_template 中用 {{variable_name}} 表示變數（必須與 input_variables 對應）
3. prompt 要明確、具體、有結構
{output_instruction}
5. 避免模糊指令如「盡量」「適當」
6. 如果是判斷/分類型任務，加入明確的判斷標準
7. prompt 裡不需要重複描述 metadata 中已有的資訊（如變數名稱清單），專注在行為指示
{lang_instruction}

只回覆 JSON，不要其他文字。"""

    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=30.0)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
            max_completion_tokens=2000,
        )

        import json
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        result = json.loads(content)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI assist failed: {str(e)}")


@router.get("/{key}/audit")
async def get_audit_log(key: str, db: Session = Depends(get_db)):
    """Get audit log for a prompt template."""
    logs = prompt_registry_service.get_audit_logs(db, key)
    return [
        {
            "id": log.id,
            "action": log.action,
            "actor": log.actor,
            "versionId": log.version_id,
            "details": log.details,
            "createdAt": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@router.get("/{key}/usage")
async def get_usage_stats(key: str, db: Session = Depends(get_db)):
    """Get usage statistics for a prompt template."""
    return prompt_registry_service.get_usage_stats(db, key)


@router.get("/{key}/diff")
async def diff_versions(key: str, v1: str, v2: str, db: Session = Depends(get_db)):
    """Compare two versions of a prompt."""
    from app.models.prompt_template import PromptVersion

    template = prompt_registry_service.get_template_by_key(db, key)
    if not template:
        raise HTTPException(status_code=404, detail=f"Prompt '{key}' not found")

    ver1 = db.query(PromptVersion).filter(PromptVersion.id == v1, PromptVersion.template_id == template.id).first()
    ver2 = db.query(PromptVersion).filter(PromptVersion.id == v2, PromptVersion.template_id == template.id).first()

    if not ver1 or not ver2:
        raise HTTPException(status_code=404, detail="One or both versions not found")

    return {
        "left": _serialize_version(ver1),
        "right": _serialize_version(ver2),
    }
