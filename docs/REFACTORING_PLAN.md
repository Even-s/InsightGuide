# InsightGuide 重構實行計劃書

## 從「BRD 生成器」轉型為「需求研究工作台」

---

## 一、現況分析

### 目前資料流

```
Document Upload → Extract Sections → Generate Themes
    → Create QuestionCards (with coverage rules) → PrepSession Ready
        → Start InterviewSession → Live Transcription (Realtime API)
            → Card Coverage Evaluation (live provisional)
                → End Session → Diarization → FinalUtterances
                    → Q/A Reconstruction → Final Card Coverage
                        → BRD Generation (direct)
```

### 現存問題

1. **無 Project 概念** — 每次訪談都是獨立的，無法跨訪談整合
2. **無受訪者角色概念** — 不知道受訪者是誰、懂什麼
3. **卡片無角色定向** — 所有卡片對所有受訪者一視同仁
4. **直接從單次訪談跳到 BRD** — 缺少中介文件驗證
5. **BRD 生成無守門機制** — 不判斷證據是否足夠
6. **無訪談規劃能力** — 系統不會建議「你該訪誰」

### 目前已有的基礎設施（可直接利用）

| 基礎設施 | 位置 | 備註 |
|---|---|---|
| Q/A Reconstruction | `qa_reconstruction_service.py` | 已有 QuestionInstance + QuestionAnswer |
| Final Utterances | `final_utterance.py` | 已有 diarized 逐字稿 |
| Card Coverage Evaluation | `card_coverage_evaluation.py` | 已有 live/final 兩階段評估 |
| BRD Generation | `brd_generation_service.py` | 已有章節化 BRD 輸出 |
| Prompt Registry | `prompt_registry_service.py` | 可用於管理所有 AI prompt |
| InterviewTheme | `interview_theme.py` | 已有主題分群，含 brd_mapping |

---

## 二、目標資料流

```
建立專案 (Project)
  ↓
定義 BRD 目標與需求範圍 (brd_scope)
  ↓
系統自動產生 Stakeholder Plan（建議角色槽位）
  ↓
使用者登錄受訪者 → Stakeholder Profiles（可隨時增刪改）
  ↓
產生 Role-based Interview Brief（根據角色 + evidence gap）
  ↓
進行訪談 (Interview Session — 角色感知)
  ↓
產生 Final Transcript (已有)
  ↓
產生 Q/A Record (已有)
  ↓
產生 Interview Insight Memo ← 新核心文件
  ↓
更新 Requirement Evidence Matrix ← 新核心文件
  ↓
系統動態更新訪談建議（誰還沒訪？缺什麼證據？）
  ↓
產生 BRD Readiness Report ← 新守門員
  ↓
若證據足夠 → 生成 BRD
否則 → 產生下一輪訪談建議（含具體人選與問題）
```

---

## 三、實作階段規劃

### Phase 0：Project、Stakeholder Plan 與 Stakeholder Profile（基礎層）

**目標**：建立多訪談整合的骨架，包含系統主動建議「該訪問誰」的能力

#### 核心設計：兩層 Stakeholder 架構

```
┌──────────────────────────────────────────────────────────────────┐
│  Layer A: STAKEHOLDER PLAN（利害關係人計劃）                       │
│  系統根據 Project Scope 自動建議「應該訪問哪些角色」                │
│  ← 這是角色槽位（role slot），不是具體的人                         │
└──────────┬───────────────────────────────────────────────────────┘
           │
           │  使用者填入實際的人（可隨時增刪改）
           ▼
┌──────────────────────────────────────────────────────────────────┐
│  Layer B: STAKEHOLDER PROFILES（受訪者側寫）                      │
│  實際登錄的人，可隨時增刪改                                        │
│  一個 role slot 可以對應 0~N 個人                                 │
└──────────────────────────────────────────────────────────────────┘
```

**為什麼需要兩層**：
- Stakeholder Slot = 系統建議的「角色需求」（抽象），專案建立時 AI 自動產生
- Stakeholder Profile = 使用者登錄的「具體受訪者」（實例），隨時可增刪改
- 一個 slot 可對應 0~N 個 profile（約不到人 = 0；同角色多人 = N）
- Profile 也可以不屬於任何 slot（計劃外臨時新增的人）

#### 0-1. 新增 `Project` Model

```python
# backend/app/models/project.py
class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    brd_scope = Column(JSON, nullable=True)
    # {
    #   "target_system": "客戶需求追蹤平台",
    #   "business_domain": "B2B SaaS 銷售流程",
    #   "key_objectives": ["統一需求追蹤", "減少版本混亂", "加速交付"],
    #   "out_of_scope": ["財務模組", "HR 系統整合"]
    # }
    status = Column(String, default="active")
    # active | planning | interviewing | ready_for_brd | completed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    stakeholder_slots = relationship("StakeholderSlot", back_populates="project", cascade="all, delete-orphan")
    stakeholder_profiles = relationship("StakeholderProfile", back_populates="project", cascade="all, delete-orphan")
    interview_sessions = relationship("InterviewSession", back_populates="project")
    insight_memos = relationship("InterviewInsightMemo", back_populates="project")
    evidence_matrix = relationship("RequirementEvidenceMatrix", back_populates="project", uselist=False)
    documents = relationship("Document", back_populates="project")
```

#### 0-2. 新增 `StakeholderSlot` Model（角色槽位 — 系統建議層）

```python
# backend/app/models/stakeholder_slot.py
class StakeholderSlot(Base):
    """角色槽位 — 系統建議的「應該訪問什麼角色」。
    
    專案建立時由 AI 根據 brd_scope 自動產生。
    使用者可手動新增/刪除/調整。
    每個 slot 代表「一種需要的觀點」，而非具體的人。
    """
    __tablename__ = "stakeholder_slots"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)

    # 角色定義
    role_category = Column(String, nullable=False)
    # business | product | engineering | management | operations |
    # customer_support | legal | finance | design | qa

    role_label = Column(String, nullable=False)
    # 顯示用標籤："業務 / 銷售", "工程 / IT", "產品經理" 等

    # 為什麼需要這個角色
    rationale = Column(Text, nullable=True)
    # "了解客戶流程與需求來源，確認業務端痛點"

    # 期望這個角色提供什麼
    expected_contributions = Column(JSON, default=[])
    # ["流程痛點", "客戶需求來源", "成交阻力", "使用情境"]

    # 建議問這個角色的關鍵問題
    key_questions_to_cover = Column(JSON, default=[])
    # ["目前怎麼管理需求？", "最常見的客戶抱怨？", "成交流程卡在哪？"]

    # 優先級
    priority = Column(String, default="required")
    # required | recommended | optional

    # 建議訪問人數
    min_interviews = Column(Integer, default=1)
    # 建議至少訪問幾位這個角色的人

    # 狀態（系統自動更新）
    status = Column(String, default="unassigned")
    # unassigned | partially_assigned | assigned | interviewing | completed | skipped

    # 排序
    order_index = Column(Integer, default=0)

    # 來源（系統建議 or 使用者手動新增 or 訪談中發現）
    source = Column(String, default="ai_suggested")
    # ai_suggested | user_created | interview_discovered

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="stakeholder_slots")
    profiles = relationship("StakeholderProfile", back_populates="slot")
```

#### 0-3. 新增 `StakeholderProfile` Model（具體受訪者 — 使用者登錄層）

```python
# backend/app/models/stakeholder_profile.py
class StakeholderProfile(Base):
    """具體受訪者側寫 — 使用者登錄的實際人員。
    
    可隨時新增、修改、刪除。
    可歸屬於某個 StakeholderSlot，也可以獨立存在（計劃外新增）。
    同一個 slot 可以有多位 profile（同角色多人受訪）。
    """
    __tablename__ = "stakeholder_profiles"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    slot_id = Column(String, ForeignKey("stakeholder_slots.id"), nullable=True, index=True)
    # NULL = 計劃外新增的人（不屬於任何預定角色槽位）

    # 基本資訊
    name = Column(String, nullable=False)
    role_title = Column(String, nullable=True)
    department = Column(String, nullable=True)

    # 角色分類
    stakeholder_type = Column(String, nullable=False)
    # business | operations | engineering | product | management |
    # customer_support | legal | finance | design | qa | other

    # 專長與知識邊界
    expertise_tags = Column(JSON, default=[])
    # ["sales_process", "customer_pain_points", "pricing", "workflow"]
    # 決定「這個人適合回答哪類問題」

    knowledge_boundaries = Column(JSON, default=[])
    # ["technical_architecture", "database_schema", "deployment"]
    # 決定「不該拿哪類問題問這個人」

    # 決策權力
    decision_power = Column(String, nullable=True)
    # decision_maker | influencer | user | operator | subject_matter_expert

    # 訪談狀態追蹤
    status = Column(String, default="scheduled")
    # suggested | scheduled | interviewed | cancelled | unavailable

    interview_count = Column(Integer, default=0)
    last_interviewed_at = Column(DateTime, nullable=True)

    # 推薦來源（如果是訪談中被推薦的人）
    recommended_by_memo_id = Column(String, nullable=True)
    # 哪份 Insight Memo 建議要訪這個人
    recommended_reason = Column(Text, nullable=True)

    # 備註
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="stakeholder_profiles")
    slot = relationship("StakeholderSlot", back_populates="profiles")
    interview_sessions = relationship("InterviewSession", back_populates="stakeholder_profile")
```

#### 0-4. 修改 `InterviewSession` — 加入 Project 與 Stakeholder 關聯

```sql
ALTER TABLE interview_sessions
ADD COLUMN project_id VARCHAR REFERENCES projects(id),
ADD COLUMN stakeholder_profile_id VARCHAR REFERENCES stakeholder_profiles(id),
ADD COLUMN interview_objective TEXT,
ADD COLUMN interview_scope JSONB DEFAULT '{}';
-- interview_scope: {"focus_areas": [...], "excluded_topics": [...]}
```

#### 0-5. 修改 `Document` — 可歸屬於 Project

```sql
ALTER TABLE documents
ADD COLUMN project_id VARCHAR REFERENCES projects(id);
```

#### 0-6. 新增 `StakeholderPlanService`（核心：動態建議引擎）

```python
# backend/app/services/stakeholder_plan_service.py
class StakeholderPlanService:

    def generate_initial_plan(self, db: Session, project_id: str) -> List[StakeholderSlot]:
        """專案建立後，根據 brd_scope 自動產生初始角色槽位。

        Input:
            - project.brd_scope (target_system, business_domain, key_objectives)

        Logic:
            1. AI 分析 brd_scope，判斷「要完成這份 BRD，需要哪些角色的觀點」
            2. 為每個角色產生 slot，包含：
               - rationale (為什麼需要)
               - expected_contributions (預期提供什麼)
               - key_questions_to_cover (建議問什麼)
               - priority (required / recommended / optional)
               - min_interviews (建議至少幾位)
            3. 存入 DB

        Output:
            初始化的 StakeholderSlot 列表

        範例產出：
            - 業務/銷售 (required, min=2) — 了解客戶流程與痛點
            - 產品經理 (required, min=1) — 確認需求優先級與驗收標準
            - 工程/IT (required, min=1) — 確認技術可行性與限制
            - 管理者 (recommended, min=1) — 確認預算、KPI、決策標準
            - 客服 (optional, min=1) — 了解售後痛點與 SLA
        """

    def update_plan_after_interview(self, db: Session, project_id: str, memo_id: str) -> Dict:
        """每場訪談後，根據 Insight Memo 動態更新計劃。

        Logic:
            1. 讀取新產生的 Insight Memo
            2. 從 memo.unresolved_questions 取出建議訪談對象
            3. 從 memo.next_interview_suggestions 取出具體建議
            4. 檢查現有 slots：
               - 如果建議的角色已有 slot → 更新 slot 的 key_questions_to_cover
               - 如果建議的角色沒有 slot → 新增 slot (source='interview_discovered')
            5. 如果受訪者提到具體人名 → 預填 StakeholderProfile (status='suggested')
            6. 更新所有 slot 的 status

        Returns:
            {
                "new_slots_added": [...],
                "slots_updated": [...],
                "suggested_profiles": [...],
                "coverage_summary": {...}
            }
        """

    def update_plan_from_evidence_matrix(self, db: Session, project_id: str) -> Dict:
        """根據 Evidence Matrix 的 gap 動態補充計劃。

        Logic:
            1. 取得 EvidenceMatrix 中所有 entry 的 missing_validation_from
            2. 統計哪些角色被最多需求等待驗證
            3. 如果某角色被 >= 2 條需求等待 → 提升該 slot 的 priority
            4. 如果有衝突需要決策者裁定 → 確保 management slot 存在且 priority=required

        Returns:
            {
                "priority_changes": [...],
                "new_slots_added": [...],
                "urgent_interviews": [...]
            }
        """

    def get_plan_status(self, db: Session, project_id: str) -> Dict:
        """取得當前訪談計劃狀態總覽。

        Returns:
            {
                "total_slots": 5,
                "completed_slots": 2,
                "progress_percentage": 40,
                "slots": [
                    {
                        "role_label": "業務/銷售",
                        "priority": "required",
                        "status": "completed",
                        "profiles_count": 2,
                        "min_interviews": 2,
                        "interviews_done": 2
                    },
                    {
                        "role_label": "工程/IT",
                        "priority": "required",
                        "status": "unassigned",
                        "profiles_count": 0,
                        "min_interviews": 1,
                        "interviews_done": 0,
                        "urgency_reason": "3 條候選需求等待工程確認"
                    },
                    ...
                ],
                "next_recommended_action": {
                    "action": "arrange_interview",
                    "target_role": "engineering",
                    "reason": "有 3 條需求等待技術可行性確認",
                    "suggested_questions": [...]
                }
            }
        """

    def _update_slot_statuses(self, db: Session, project_id: str):
        """根據 profiles 和 sessions 自動更新所有 slot 的 status。

        unassigned: 無 profile
        partially_assigned: 有 profile 但人數 < min_interviews
        assigned: 有足夠 profile 但尚未開始訪談
        interviewing: 有進行中的訪談
        completed: 所有 profile 都已訪談完成
        skipped: 使用者手動標記跳過
        """
```

#### 0-7. 新增 `ProjectService`

```python
# backend/app/services/project_service.py
class ProjectService:

    def create_project(self, db: Session, user_id: str, data: Dict) -> Project:
        """建立專案並自動產生初始 Stakeholder Plan。

        Steps:
            1. 建立 Project record
            2. 呼叫 stakeholder_plan_service.generate_initial_plan()
            3. 返回 Project with slots
        """

    def get_project_dashboard(self, db: Session, project_id: str) -> Dict:
        """取得專案總覽（Dashboard 用）。

        Returns:
            {
                "project": {...},
                "stakeholder_plan": {...},  # from stakeholder_plan_service.get_plan_status()
                "interview_progress": {
                    "total_sessions": 3,
                    "completed_sessions": 2,
                    "memos_generated": 2
                },
                "evidence_summary": {
                    "total_candidates": 12,
                    "validated": 5,
                    "conflicted": 2,
                    "needs_more_evidence": 5
                },
                "readiness_indicator": "not_ready",  # quick check
                "next_action": {...}  # 系統建議的下一步
            }
        """
```

#### 0-8. DB Migration

- 新增 migration `010_add_project_stakeholder_plan.py`
- 建立 tables: `projects`, `stakeholder_slots`, `stakeholder_profiles`
- ALTER: `interview_sessions` 加 `project_id`, `stakeholder_profile_id`, `interview_objective`, `interview_scope`
- ALTER: `documents` 加 `project_id`
- 向後相容：既有 interview_sessions 的 project_id 為 NULL（可視為「獨立訪談」模式）

#### 0-9. API Routes

| Method | Path | 描述 |
|--------|------|------|
| **Project** | | |
| POST | `/api/projects` | 建立專案（自動產生 Stakeholder Plan） |
| GET | `/api/projects` | 列出使用者所有專案 |
| GET | `/api/projects/:id` | 取得專案詳情 |
| GET | `/api/projects/:id/dashboard` | 取得專案 Dashboard 總覽 |
| PUT | `/api/projects/:id` | 更新專案（含 brd_scope） |
| DELETE | `/api/projects/:id` | 刪除專案 |
| **Stakeholder Plan (Slots)** | | |
| GET | `/api/projects/:id/stakeholder-plan` | 取得訪談計劃（所有 slots + 狀態） |
| POST | `/api/projects/:id/stakeholder-plan/regenerate` | 根據 brd_scope 重新產生計劃 |
| POST | `/api/projects/:id/stakeholder-slots` | 手動新增角色槽位 |
| PUT | `/api/stakeholder-slots/:id` | 更新角色槽位 |
| PUT | `/api/stakeholder-slots/:id/skip` | 標記跳過某角色 |
| DELETE | `/api/stakeholder-slots/:id` | 刪除角色槽位 |
| **Stakeholder Profile** | | |
| POST | `/api/projects/:id/stakeholders` | 新增受訪者 |
| GET | `/api/projects/:id/stakeholders` | 列出受訪者 |
| PUT | `/api/stakeholders/:id` | 更新受訪者 |
| DELETE | `/api/stakeholders/:id` | 刪除受訪者 |
| PUT | `/api/stakeholders/:id/cancel` | 標記無法訪談 |

#### 0-10. Frontend

- 新增 `ProjectListPage.tsx` — 專案列表
- 新增 `ProjectDetailPage.tsx` — 專案 Dashboard 總覽
  - 訪談計劃進度條
  - 角色槽位狀態表
  - 系統建議卡片（下一步該做什麼）
  - 快速入口：開始新訪談、查看 Evidence Matrix
- 新增 `StakeholderPlanView.tsx` — 訪談計劃視圖
  - 角色槽位列表（含狀態、優先級）
  - 每個 slot 下掛的 profiles
  - 系統建議 badge（「建議補訪」等）
- 新增 `StakeholderForm.tsx` — 建立/編輯受訪者
  - 可選擇歸入哪個 slot
  - 可不選 slot（計劃外新增）
- 修改 App router — 加入 `/projects`, `/projects/:id` 路由

#### 0-11. 動態建議觸發時機

| 觸發事件 | 行為 |
|----------|------|
| 專案建立 + brd_scope 填入 | AI 自動產生初始 Stakeholder Plan |
| 使用者修改 brd_scope | 重新評估是否需要新角色 |
| Insight Memo 產生 | 根據 unresolved_questions 更新 plan |
| Evidence Matrix 更新 | 根據 missing_validation_from 調整 priority |
| 受訪者提到具體人名 | 預填 suggested profile |
| 使用者標記某 slot 為 skipped | Readiness Report 中標記該觀點缺失 |

#### 0-12. 邊界情境處理

| 情境 | 系統行為 |
|------|----------|
| **約不到某角色** | 使用者可將 slot 標記 `skipped`；Readiness Report 會明確標註「此角色觀點缺失」，BRD 中對應章節標記「未經 X 角色驗證」|
| **同角色多人** | 多份 Memo 來自同角色 → Evidence Matrix 中 `source_roles` 不重複計算角色數，但會記錄「同角色多人一致性」以增加信心度 |
| **計劃外的人** | 使用者隨時可新增 Profile（`slot_id = NULL`），系統根據 expertise_tags 建議歸入或新建 slot |
| **訪談中發現角色搞錯** | 可修改 Profile 的 stakeholder_type / expertise_tags，Memo 會根據新角色重新標記卡片適用性 |
| **受訪者跨角色** | 一個人的 expertise_tags 可涵蓋多領域（如技術型 PM），系統按 tags 而非僅 stakeholder_type 判斷卡片適用性 |
| **受訪者推薦他人** | Insight Memo 擷取到具體人名 → 自動建立 Profile (status='suggested', recommended_by_memo_id=...) |
| **專案範圍變更** | 使用者修改 brd_scope → 系統重新評估 slots（可能新增/降級角色）|

**預估工時**：4-5 天

---

### Phase 1：卡片角色定向（Role Targeting）

**目標**：讓系統知道「這張卡片該問誰」

#### 1-1. 修改 `QuestionCard` Model

```sql
ALTER TABLE question_cards
ADD COLUMN target_roles JSONB DEFAULT '[]',
-- ["engineering", "IT", "operations"]
ADD COLUMN not_recommended_roles JSONB DEFAULT '[]',
-- ["sales", "customer_support"]
ADD COLUMN expertise_required JSONB DEFAULT '[]',
-- ["system_architecture", "API", "data_flow"]
ADD COLUMN question_intent VARCHAR;
-- technical_constraint | business_process | user_experience |
-- decision_criteria | compliance | performance | integration
```

#### 1-2. 新增卡片狀態

目前 `InterviewCardState.status` 有：
```
pending | listening | probably_sufficient | sufficient | at_risk | skipped | manually_checked | disabled
```

新增：
```
not_applicable_for_role | needs_different_stakeholder
```

#### 1-3. 修改 `ai_question_generator.py`

- 生成卡片時根據 document 內容自動推斷 `target_roles` 和 `expertise_required`
- 加入 prompt 指示：「判斷這題適合哪些角色回答」

#### 1-4. 新增 `role_filter_service.py`

```python
# backend/app/services/role_filter_service.py
class RoleFilterService:

    def filter_cards_for_stakeholder(
        self, cards: List[QuestionCard], stakeholder: StakeholderProfile
    ) -> Dict[str, List[QuestionCard]]:
        """根據受訪者角色篩選卡片。

        判斷邏輯（優先順序）：
        1. card.not_recommended_roles 包含 stakeholder.stakeholder_type → not_applicable
        2. card.target_roles 有指定且包含 stakeholder.stakeholder_type → applicable
        3. card.target_roles 有指定但不包含 → uncertain (降低優先)
        4. card.expertise_required 與 stakeholder.expertise_tags 有交集 → applicable
        5. card.expertise_required 與 stakeholder.knowledge_boundaries 有交集 → not_applicable
        6. 無任何角色限定 → applicable (通用問題)

        Returns:
            {
                "applicable": [...],              # 適合這位受訪者
                "not_applicable": [...],          # 不適合，標記 needs_different_stakeholder
                "uncertain": [...]               # 無法確定，保留但降低優先級
            }
        """

    def get_card_coverage_for_project(
        self, db: Session, project_id: str
    ) -> Dict[str, Any]:
        """取得整個專案的卡片角色覆蓋狀況。

        Returns:
            {
                "total_cards": 30,
                "covered_by_any_role": 22,
                "not_covered_yet": 8,
                "coverage_by_role": {
                    "business": {"applicable": 12, "covered": 10},
                    "engineering": {"applicable": 15, "covered": 0},
                    ...
                }
            }
        """
```

#### 1-5. 修改 Card Coverage 評估邏輯

`answer_evaluation_engine.py` 修改：
- 如果卡片的 `target_roles` 不包含當前受訪者的 `stakeholder_type`：
  - 不計入「缺失」
  - 狀態設為 `not_applicable_for_role`
  - 不影響 BRD 完整度評估

#### 1-6. 修改 BRD Generation

`brd_generation_service.py` 的 `_build_open_issues` 修改：
- `not_applicable_for_role` 的卡片不算 open issue
- 改為產出「建議下次訪談對象」清單

**預估工時**：2-3 天

---

### Phase 2：Interview Brief（訪談前計劃）

**目標**：訪談開始前產生角色型訪談指引

#### 2-1. 新增 `InterviewBrief` Model

```python
# backend/app/models/interview_brief.py
class InterviewBrief(Base):
    __tablename__ = "interview_briefs"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False, unique=True)
    stakeholder_profile_id = Column(String, ForeignKey("stakeholder_profiles.id"), nullable=False)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)

    # Brief content (AI-generated)
    interview_objective = Column(Text, nullable=False)

    recommended_topics = Column(JSON, default=[])
    # [{"topic": "...", "reason": "...", "priority": "high|medium|low"}]

    excluded_topics = Column(JSON, default=[])
    # [{"topic": "...", "reason": "..."}]

    suggested_questions = Column(JSON, default=[])
    # [{"question": "...", "intent": "...", "expected_insight": "..."}]

    # 根據 unresolved_questions from prior memos 產生的追問
    follow_up_from_prior_interviews = Column(JSON, default=[])
    # [{
    #   "question": "...",
    #   "origin_memo_id": "...",
    #   "origin_stakeholder": "...",
    #   "reason": "上一場業務訪談中提到此問題但無法回答"
    # }]

    applicable_cards = Column(JSON, default=[])
    # [card_id, ...]
    not_applicable_cards = Column(JSON, default=[])
    # [{"card_id": "...", "reason": "...", "suggested_stakeholder_type": "..."}]

    time_estimate_minutes = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)

    generated_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
```

#### 2-2. 新增 `interview_brief_service.py`

```python
class InterviewBriefService:
    def generate_brief(self, db: Session, session_id: str) -> InterviewBrief:
        """根據 stakeholder profile + project scope + evidence gap 產生訪談指引。

        Logic:
        1. 取得 stakeholder 的 expertise_tags + knowledge_boundaries
        2. 取得 project 的 brd_scope
        3. 取得 document 的 question_cards
        4. 用 role_filter_service 篩選適合此角色的卡片
        5. 檢查先前 Insight Memos 的 unresolved_questions：
           - 如果有問題指向此角色 → 加入 follow_up_from_prior_interviews
        6. 檢查 Evidence Matrix 的 missing_validation_from：
           - 如果有需求等待此角色確認 → 加入 recommended_topics
        7. 用 AI 產生推薦主題 + 建議問法 + 排除主題
        8. 估算時間
        """
```

#### 2-3. API

| Method | Path | 描述 |
|--------|------|------|
| POST | `/api/interview-sessions/:id/brief` | 產生訪談計劃 |
| GET | `/api/interview-sessions/:id/brief` | 取得訪談計劃 |
| PUT | `/api/interview-sessions/:id/brief` | 使用者手動調整計劃 |

#### 2-4. Frontend

- 新增 `InterviewBriefView.tsx` — 顯示訪談計劃（在 PresenterPage 啟動前展示）
  - 訪談目標
  - 推薦主題 / 排除主題
  - 來自先前訪談的追問（標註來源）
  - 適用卡片預覽
  - 時間估計
- 修改訪談啟動流程：選定 Stakeholder → 產生 Brief → 確認/調整 → 開始訪談

**預估工時**：2-3 天

---

### Phase 3：Interview Insight Memo（訪談洞察紀錄）

**目標**：每場訪談後產生結構化洞察文件，取代直接 BRD

#### 3-1. 新增 `InterviewInsightMemo` Model

```python
# backend/app/models/interview_insight_memo.py
class InterviewInsightMemo(Base):
    __tablename__ = "interview_insight_memos"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False, unique=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=True, index=True)
    stakeholder_profile_id = Column(String, ForeignKey("stakeholder_profiles.id"), nullable=True)

    # Section 1: 訪談基本資訊
    interview_date = Column(DateTime, nullable=True)
    interview_duration_minutes = Column(Integer, nullable=True)
    topics_covered = Column(JSON, default=[])  # ["需求管理", "客戶流程", ...]
    stakeholder_summary = Column(JSON, nullable=True)
    # {"name": "...", "role": "...", "department": "...",
    #  "expertise": [...], "boundaries": [...]}

    # Section 2: 每題回答整理 (structured)
    qa_summaries = Column(JSON, default=[])
    # [{
    #   "question": "...",
    #   "answer_summary": "...",
    #   "evidence_quotes": ["..."],
    #   "answer_status": "answered|partial|unanswered",
    #   "confidence": 0.8
    # }]

    # Section 3: 痛點
    pain_points = Column(JSON, default=[])
    # [{
    #   "description": "...",
    #   "evidence_quote": "...",
    #   "affected_roles": ["業務", "PM"],
    #   "severity": "high|medium|low"
    # }]

    # Section 4: 需求線索
    requirement_candidates = Column(JSON, default=[])
    # [{
    #   "description": "...",
    #   "source": "explicit|inferred|unverified",
    #   "confidence": "high|medium|low",
    #   "evidence_quote": "...",
    #   "needs_validation_from": ["engineering", "PM"],
    #   "brd_ready": false
    # }]

    # Section 5: 限制與假設
    constraints_and_assumptions = Column(JSON, default=[])
    # [{
    #   "type": "assumption|constraint|limitation",
    #   "content": "...",
    #   "source": "explicit|inferred",
    #   "evidence_quote": "..."
    # }]

    # Section 6: 流程描述
    process_descriptions = Column(JSON, default=[])
    # [{
    #   "process_name": "...",
    #   "steps": ["..."],
    #   "pain_points": ["..."],
    #   "source_quote": "..."
    # }]

    # Section 7: 未解問題
    unresolved_questions = Column(JSON, default=[])
    # [{
    #   "question": "...",
    #   "suggested_stakeholder_type": "engineering|PM|...",
    #   "suggested_person_name": "...",  # 如果受訪者提到具體人名
    #   "priority": "high|medium|low",
    #   "reason": "..."
    # }]

    # Section 8: 建議下一步
    next_interview_suggestions = Column(JSON, default=[])
    # [{
    #   "target_role": "...",
    #   "objective": "...",
    #   "key_questions": ["..."],
    #   "mentioned_person": "..."  # 受訪者是否指名某人
    # }]

    # Metadata: 來源區分統計
    source_distinction = Column(JSON, nullable=True)
    # {"explicit_statements": count, "inferences": count, "unverified": count}

    # Full markdown render
    markdown_content = Column(Text, nullable=True)

    status = Column(String, default="generating")
    # generating | completed | failed
    generated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### 3-2. 新增 `insight_memo_service.py`

```python
class InsightMemoService:
    def generate_memo(self, db: Session, session_id: str) -> InterviewInsightMemo:
        """從完成的訪談產生 Interview Insight Memo。

        Input Sources:
        1. StakeholderProfile (角色背景)
        2. FinalUtterances (正式逐字稿)
        3. QuestionInstances + QuestionAnswers (Q/A reconstruction)
        4. CardCoverageEvaluations (卡片覆蓋結果)
        5. InterviewBrief (訪談計劃，用於對比預期 vs 實際)

        Processing Steps:
        1. 彙整每題回答摘要 (from QA records)
        2. AI 分析：萃取痛點 + 需求線索 + 流程描述
        3. AI 分析：標記「明確說的」vs「推論的」vs「需要驗證的」
        4. AI 分析：找出未回答的重要問題 + 建議下一位受訪者
        5. 產出候選需求（標記 confidence + needs_validation_from）
        6. Render markdown

        Post-processing:
        7. 呼叫 stakeholder_plan_service.update_plan_after_interview()
           → 更新訪談計劃（新增 slots / 預填 profiles）
        """

    def _extract_pain_points(self, qa_records, transcript) -> List[Dict]:
        """從 Q/A 和逐字稿中萃取痛點。"""

    def _extract_requirement_candidates(self, qa_records, pain_points, stakeholder) -> List[Dict]:
        """從回答中萃取候選需求，標記來源與信心度。"""

    def _identify_unresolved_questions(self, cards, card_states, stakeholder) -> List[Dict]:
        """找出未回答的重要問題，判斷應該問誰。"""

    def _extract_person_mentions(self, transcript) -> List[Dict]:
        """從逐字稿中擷取受訪者提到的具體人名。"""

    def _render_memo_markdown(self, memo: InterviewInsightMemo) -> str:
        """將結構化資料 render 成 markdown 格式。"""
```

#### 3-3. 修改訪談結束流程

目前結束後流程：`End Session → Diarization → Q/A Reconstruction → BRD`

改為：`End Session → Diarization → Q/A Reconstruction → **Insight Memo** → **Update Plan** → (optional) BRD`

```python
# 訪談結束後的 pipeline
async def post_interview_pipeline(db, session_id):
    # 現有流程不變
    await trigger_diarization(session_id)
    await trigger_qa_reconstruction(session_id)

    # 新增：產生 Insight Memo
    memo = await insight_memo_service.generate_memo(db, session_id)

    # 新增：更新 Stakeholder Plan
    if memo.project_id:
        stakeholder_plan_service.update_plan_after_interview(db, memo.project_id, memo.id)

    # 新增：更新 Evidence Matrix（如果已有）
    if memo.project_id:
        evidence_matrix_service.update_matrix(db, memo.project_id)

    # BRD 不再自動生成，改由 Readiness Check 觸發
```

#### 3-4. API

| Method | Path | 描述 |
|--------|------|------|
| POST | `/api/interview-sessions/:id/insight-memo` | 產生/重新產生 Insight Memo |
| GET | `/api/interview-sessions/:id/insight-memo` | 取得 Insight Memo |
| GET | `/api/projects/:id/insight-memos` | 取得專案所有 Insight Memo |

#### 3-5. Frontend

- 新增 `InsightMemoPage.tsx` — 顯示單場訪談洞察紀錄
- 修改 `InterviewReportPage.tsx` — 增加 Insight Memo tab（與逐字稿、Q/A 並列）
- 新增 `InsightMemoCard.tsx` — 在 ProjectDetail 中顯示各場 memo 摘要

**預估工時**：4-5 天

---

### Phase 4：Requirement Evidence Matrix（需求證據矩陣）

**目標**：跨訪談整合，從個人說法提升為有證據支撐的需求候選

#### 4-1. 新增 `RequirementEvidenceMatrix` Model

```python
# backend/app/models/requirement_evidence_matrix.py

class RequirementEvidenceMatrix(Base):
    __tablename__ = "requirement_evidence_matrices"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, unique=True)

    # Matrix state
    status = Column(String, default="draft")
    # draft | updating | ready | stale
    last_updated_at = Column(DateTime, nullable=True)
    memo_count = Column(Integer, default=0)  # 基於幾份 memo
    last_memo_id = Column(String, nullable=True)  # 最後一份納入的 memo

    # Full markdown render
    markdown_content = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EvidenceMatrixEntry(Base):
    """需求證據矩陣的每一列 — 一個候選需求。"""
    __tablename__ = "evidence_matrix_entries"

    id = Column(String, primary_key=True)
    matrix_id = Column(String, ForeignKey("requirement_evidence_matrices.id"), nullable=False, index=True)

    # 候選需求
    requirement_candidate = Column(Text, nullable=False)
    category = Column(String, nullable=True)
    # functional | non_functional | business_process | integration | permission | data | ux

    # 證據來源
    source_roles = Column(JSON, default=[])
    # ["business", "product", "engineering"]
    source_memo_ids = Column(JSON, default=[])
    # [memo_id, ...]
    supporting_evidence = Column(JSON, default=[])
    # [{
    #   "memo_id": "...",
    #   "stakeholder_role": "...",
    #   "stakeholder_name": "...",
    #   "evidence_quote": "...",
    #   "source_type": "explicit|inferred|unverified",
    #   "confidence": "high|medium|low"
    # }]

    # 衝突與風險
    conflicts = Column(JSON, default=[])
    # [{
    #   "description": "...",
    #   "conflicting_roles": ["業務", "工程"],
    #   "details": "..."
    # }]

    # 狀態
    validation_status = Column(String, default="candidate")
    # candidate | validated | conflicted | needs_more_evidence | rejected
    missing_validation_from = Column(JSON, default=[])
    # ["engineering", "PM"]

    # Priority (cross-stakeholder)
    mention_count = Column(Integer, default=1)
    stakeholder_agreement_level = Column(String, nullable=True)
    # unanimous | majority | single_source | conflicted

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### 4-2. 新增 `evidence_matrix_service.py`

```python
class EvidenceMatrixService:
    def update_matrix(self, db: Session, project_id: str) -> RequirementEvidenceMatrix:
        """根據所有 Insight Memos 增量更新需求證據矩陣。

        Logic:
        1. 取得專案所有 completed InsightMemos
        2. 找出尚未被納入矩陣的新 memo
        3. 從新 memo 取出 requirement_candidates
        4. 對每個 candidate：
           - AI 語意比對：與矩陣中現有 entries 是否相似？
             - 相似 → 合併到既有 entry（加入新證據）
             - 不相似 → 新增 entry
        5. 重新計算所有 entries 的：
           - mention_count
           - source_roles
           - stakeholder_agreement_level
           - validation_status
           - missing_validation_from
        6. 偵測衝突（不同角色對同一需求的矛盾意見）
        7. 更新 matrix 的 status 和 memo_count
        8. 觸發 stakeholder_plan_service.update_plan_from_evidence_matrix()
        """

    def _deduplicate_candidates(self, new_candidates: List[Dict], existing_entries: List) -> Dict:
        """用 AI 語意比對新 candidates 與既有 entries。

        Returns:
            {
                "merge": [(candidate, existing_entry), ...],  # 相似的要合併
                "new": [candidate, ...]                        # 新的要建立
            }
        """

    def _detect_conflicts(self, entries: List) -> List[Dict]:
        """偵測不同角色間的矛盾。"""

    def _calculate_agreement_level(self, entry) -> str:
        """計算 stakeholder agreement level。

        unanimous: 所有被問到的角色都支持
        majority: 多數支持
        single_source: 只有一個角色提到
        conflicted: 有角色明確反對
        """

    def get_matrix_summary(self, db: Session, project_id: str) -> Dict:
        """取得矩陣摘要統計。"""
```

#### 4-3. 觸發時機

- 每次新的 Insight Memo 產生後，自動增量更新 Evidence Matrix
- 使用者可手動觸發全量刷新

#### 4-4. API

| Method | Path | 描述 |
|--------|------|------|
| GET | `/api/projects/:id/evidence-matrix` | 取得需求證據矩陣 |
| POST | `/api/projects/:id/evidence-matrix/refresh` | 手動刷新矩陣 |
| PUT | `/api/evidence-matrix-entries/:id` | 手動更新某條目（如標記 rejected） |
| GET | `/api/projects/:id/interview-suggestions` | 取得下一輪訪談建議 |

#### 4-5. Frontend

- 新增 `EvidenceMatrixPage.tsx` — 需求證據矩陣表格視圖
  - 可按 validation_status 篩選
  - 可按 category 分群
  - 顯示 source roles 與 agreement level
  - 衝突項目以紅色標記
  - 點擊可展開查看所有 supporting_evidence
- 新增 `InterviewSuggestionPanel.tsx` — 下一輪訪談建議面板
  - 顯示缺少哪些角色驗證
  - 建議問什麼問題
  - 可直接一鍵建立新訪談

**預估工時**：4-5 天

---

### Phase 5：BRD Readiness Report（BRD 生成準備度報告）

**目標**：在 BRD 生成前進行守門，確保證據充足

#### 5-1. 新增 `BRDReadinessReport` Model

```python
# backend/app/models/brd_readiness_report.py
class BRDReadinessReport(Base):
    __tablename__ = "brd_readiness_reports"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)

    # Overall verdict
    is_ready = Column(Boolean, default=False)
    readiness_score = Column(Float, nullable=True)  # 0.0 - 1.0
    generation_mode = Column(String, nullable=True)
    # full | partial | not_ready
    recommendation = Column(Text, nullable=True)
    # "可生成完整 BRD" | "可生成部分草稿" | "建議補訪後再生成"

    # 已具備足夠證據的區塊
    ready_sections = Column(JSON, default=[])
    # [{
    #   "section": "業務流程痛點",
    #   "evidence_count": 5,
    #   "source_roles": ["business", "product"],
    #   "confidence": "high"
    # }]

    # 證據不足的區塊
    insufficient_sections = Column(JSON, default=[])
    # [{
    #   "section": "系統整合需求",
    #   "reason": "尚無工程/IT角色訪談",
    #   "missing_roles": ["engineering", "IT"],
    #   "priority": "high"
    # }]

    # 衝突待解決
    unresolved_conflicts = Column(JSON, default=[])
    # [{
    #   "topic": "...",
    #   "conflicting_parties": [...],
    #   "details": "..."
    # }]

    # 建議下一輪訪談
    suggested_next_interviews = Column(JSON, default=[])
    # [{
    #   "target_role": "engineering",
    #   "objective": "確認系統整合可行性",
    #   "key_questions": ["..."],
    #   "existing_profile": "...",  # 如果已有 profile 可直接安排
    #   "urgency": "high"
    # }]

    # Stakeholder Plan 覆蓋度
    stakeholder_coverage = Column(JSON, nullable=True)
    # {
    #   "required_roles_total": 4,
    #   "required_roles_covered": 2,
    #   "skipped_roles": ["customer_support"],
    #   "missing_roles": ["engineering", "management"]
    # }

    # Statistics
    total_memos = Column(Integer, default=0)
    total_stakeholders_interviewed = Column(Integer, default=0)
    total_evidence_entries = Column(Integer, default=0)
    validated_requirements = Column(Integer, default=0)

    # Markdown render
    markdown_content = Column(Text, nullable=True)

    generated_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
```

#### 5-2. 新增 `brd_readiness_service.py`

```python
class BRDReadinessService:
    def generate_report(self, db: Session, project_id: str) -> BRDReadinessReport:
        """評估 BRD 生成準備度。

        Logic:
        1. 取得 EvidenceMatrix 所有 entries
        2. 取得 Stakeholder Plan 覆蓋度
        3. 評估每個 BRD 章節的證據覆蓋度
        4. 檢查是否有未解決衝突
        5. 檢查角色覆蓋度（required slots 是否都有訪談）
        6. 檢查 skipped slots 的影響
        7. 計算整體 readiness_score
        8. 決定 generation_mode (full / partial / not_ready)
        9. 產出建議
        """

    def _evaluate_section_readiness(self, section: str, entries: List) -> Dict:
        """評估單一 BRD 章節的準備度。"""

    def _check_stakeholder_coverage(self, db: Session, project_id: str) -> Dict:
        """檢查 Stakeholder Plan 的完成度。

        - required slots 中有幾個已完成訪談？
        - 有哪些 skipped？
        - 對 BRD 的影響？
        """

    def can_generate_brd(self, db: Session, project_id: str) -> Dict:
        """快速檢查：是否可以生成 BRD？

        Returns:
            {
                "can_generate": bool,
                "mode": "full|partial|not_ready",
                "reason": "...",
                "missing_roles": [...],
                "unresolved_conflicts_count": int
            }
        """
```

#### 5-3. 修改 BRD 生成流程

```python
# 修改 brd_generation_service.py — 新增 Project-level BRD 生成
def generate_project_brd(self, db: Session, project_id: str) -> Dict:
    """從 Project 層級生成 BRD（不再是單一 session）。

    1. 先跑 Readiness Check
    2. 如果 not_ready → 返回 readiness report + 建議
    3. 如果 partial → 生成部分 BRD + 標記不足處
    4. 如果 full → 生成完整 BRD

    Evidence sources:
    - EvidenceMatrix 中 validated entries → 正式需求
    - EvidenceMatrix 中 needs_more_evidence → 標記「待確認」
    - 所有 InsightMemos 的 pain_points → 業務痛點章節
    - 所有 InsightMemos 的 constraints_and_assumptions → 限制章節
    - 所有 InsightMemos 的 process_descriptions → 現有流程章節
    - StakeholderProfiles → 利害關係人章節

    每個 BRD 段落都標注：
    - 證據來源（哪些角色支持）
    - 信心度
    - 是否有衝突意見
    """
```

#### 5-4. API

| Method | Path | 描述 |
|--------|------|------|
| POST | `/api/projects/:id/readiness-check` | 產生 BRD Readiness Report |
| GET | `/api/projects/:id/readiness-report` | 取得最新 Readiness Report |
| POST | `/api/projects/:id/generate-brd` | 生成 BRD（會先跑 readiness check） |

#### 5-5. Frontend

- 新增 `BRDReadinessPage.tsx` — 顯示準備度報告
  - 總分 + 進度環
  - 綠色區塊：已具備足夠證據
  - 黃色區塊：部分證據
  - 紅色區塊：證據不足
  - Stakeholder Plan 覆蓋度指示
  - 建議下一步行動 + 一鍵建立新訪談
- 修改 `BRDGenerationPage.tsx` — 加入 readiness gate（未通過則顯示建議）

**預估工時**：3-4 天

---

## 四、DB Migration 總覽

| Migration | 內容 | Phase |
|-----------|------|-------|
| `010_add_project_stakeholder_plan.py` | projects, stakeholder_slots, stakeholder_profiles, FK additions to interview_sessions + documents | Phase 0 |
| `011_add_card_role_targeting.py` | question_cards 加 target_roles, not_recommended_roles, expertise_required, question_intent | Phase 1 |
| `012_add_interview_briefs.py` | interview_briefs table | Phase 2 |
| `013_add_insight_memos.py` | interview_insight_memos table | Phase 3 |
| `014_add_evidence_matrix.py` | requirement_evidence_matrices, evidence_matrix_entries | Phase 4 |
| `015_add_readiness_reports.py` | brd_readiness_reports table | Phase 5 |

---

## 五、向後相容策略

1. **Project 為可選** — 既有的 interview_sessions 可以不屬於任何 project（`project_id = NULL`）。獨立模式下仍可使用原有的單次訪談 → BRD 流程。

2. **Stakeholder 為可選** — 如果沒有填入 stakeholder，系統退化為目前的行為（全部卡片都出）。

3. **Slot 為可選** — Profile 的 `slot_id` 可以為 NULL（計劃外新增的受訪者）。

4. **雙軌並行** — 新的 Project-based BRD 生成路徑與舊的 Session-based 路徑共存，直到遷移完成。

5. **漸進式部署** — 每個 Phase 獨立可部署，Phase N 不 hard depend on Phase N-1 的 UI（但 backend model 有先後順序）。

---

## 六、優先順序建議

```
Priority 1 (立即) ─────────────────────────
  Phase 0: Project + Stakeholder Plan + Stakeholder Profile
  Phase 3: Interview Insight Memo
  → 這兩個加起來就能解決最大痛點：
    「單次訪談直接跳 BRD」+「系統不會建議該訪誰」

Priority 2 (第二輪) ─────────────────────────
  Phase 1: Card Role Targeting
  Phase 2: Interview Brief
  → 讓系統不再問錯人問題

Priority 3 (第三輪) ─────────────────────────
  Phase 4: Evidence Matrix
  Phase 5: BRD Readiness Report
  → 完成整個「需求研究工作台」閉環
```

**建議先做 Phase 0 + Phase 3**，因為：
- Phase 0 建立多訪談整合的基礎骨架 + 系統主動建議能力
- Phase 3 的 Insight Memo 可以直接接在現有 Q/A Reconstruction 後面
- Insight Memo 產生後自動更新 Stakeholder Plan（形成建議閉環）
- 兩者合計約 8-10 天工時
- 完成後系統立即有中介文件層 + 動態訪談建議，不再從訪談直接跳 BRD

---

## 七、新增 Model 與 Service 清單

### Models (新增 7 個)
| Model | File | Phase |
|-------|------|-------|
| `Project` | `backend/app/models/project.py` | 0 |
| `StakeholderSlot` | `backend/app/models/stakeholder_slot.py` | 0 |
| `StakeholderProfile` | `backend/app/models/stakeholder_profile.py` | 0 |
| `InterviewBrief` | `backend/app/models/interview_brief.py` | 2 |
| `InterviewInsightMemo` | `backend/app/models/interview_insight_memo.py` | 3 |
| `RequirementEvidenceMatrix` + `EvidenceMatrixEntry` | `backend/app/models/requirement_evidence_matrix.py` | 4 |
| `BRDReadinessReport` | `backend/app/models/brd_readiness_report.py` | 5 |

### Services (新增 6 個，修改 3 個)
| Service | File | 類型 | Phase |
|---------|------|------|-------|
| `ProjectService` | `backend/app/services/project_service.py` | 新增 | 0 |
| `StakeholderPlanService` | `backend/app/services/stakeholder_plan_service.py` | 新增 | 0 |
| `RoleFilterService` | `backend/app/services/role_filter_service.py` | 新增 | 1 |
| `InterviewBriefService` | `backend/app/services/interview_brief_service.py` | 新增 | 2 |
| `InsightMemoService` | `backend/app/services/insight_memo_service.py` | 新增 | 3 |
| `EvidenceMatrixService` | `backend/app/services/evidence_matrix_service.py` | 新增 | 4 |
| `BRDReadinessService` | `backend/app/services/brd_readiness_service.py` | 新增 | 5 |
| `AnswerEvaluationEngine` | 修改 | 修改 | 1 |
| `BRDGenerationService` | 修改 | 修改 | 5 |
| `AIQuestionGenerator` | 修改 | 修改 | 1 |

### Routes (新增 3 個)
| Route | File | Phase |
|-------|------|-------|
| `/api/projects` (含 stakeholder-plan, stakeholders) | `backend/app/api/routes/projects.py` | 0 |
| `/api/insight-memos` | `backend/app/api/routes/insight_memos.py` | 3 |
| `/api/evidence-matrix` | `backend/app/api/routes/evidence_matrix.py` | 4 |

### Frontend Pages (新增 6 個)
| Page | File | Phase |
|------|------|-------|
| `ProjectListPage` | `frontend/src/routes/ProjectListPage.tsx` | 0 |
| `ProjectDetailPage` (含 Dashboard) | `frontend/src/routes/ProjectDetailPage.tsx` | 0 |
| `StakeholderPlanView` | `frontend/src/components/StakeholderPlanView.tsx` | 0 |
| `InsightMemoPage` | `frontend/src/routes/InsightMemoPage.tsx` | 3 |
| `EvidenceMatrixPage` | `frontend/src/routes/EvidenceMatrixPage.tsx` | 4 |
| `BRDReadinessPage` | `frontend/src/routes/BRDReadinessPage.tsx` | 5 |

---

## 八、總工時估計

| Phase | 內容 | 工時 |
|-------|------|------|
| Phase 0 | Project + Stakeholder Plan + Profile | 4-5 天 |
| Phase 1 | Card Role Targeting | 2-3 天 |
| Phase 2 | Interview Brief | 2-3 天 |
| Phase 3 | Interview Insight Memo | 4-5 天 |
| Phase 4 | Evidence Matrix | 4-5 天 |
| Phase 5 | BRD Readiness Report | 3-4 天 |
| **合計** | | **19-25 天** |

如果按建議優先順序（先做 Phase 0 + 3）：
- **第一輪交付**：8-10 天 → 系統具備中介文件 + 動態訪談建議
- **第二輪交付**：+4-6 天 → 系統具備角色感知能力
- **第三輪交付**：+7-9 天 → 完整需求研究工作台

---

## 九、動態建議系統流程圖

```
               ┌──────────────────────────────┐
               │ 專案建立 + brd_scope 填入     │
               └──────────────┬───────────────┘
                              │
                              ▼
               ┌──────────────────────────────┐
               │ AI 產生初始 Stakeholder Plan   │
               │ (角色槽位 + 建議問題)          │
               └──────────────┬───────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │ 使用者登錄受訪者 (Profile)                    │
        │ → 可直接填、可按系統建議填、可之後再新增       │
        └──────────────┬──────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │ 進行訪談                      │
        └──────────────┬───────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │ 產生 Insight Memo             │
        └──────────────┬───────────────┘
                       │
            ┌──────────┼──────────┐
            │          │          │
            ▼          ▼          ▼
     ┌───────────┐ ┌────────┐ ┌───────────────┐
     │ 更新       │ │ 更新    │ │ 發現新角色/   │
     │ Evidence   │ │ Slot   │ │ 預填新 Profile │
     │ Matrix     │ │ Status │ │ (suggested)   │
     └─────┬─────┘ └────────┘ └───────────────┘
           │
           ▼
     ┌───────────────────────────────────┐
     │ 根據 missing_validation_from       │
     │ 調整 Slot priority                 │
     │ + 產生「下一步建議」               │
     └──────────────┬────────────────────┘
                    │
                    ▼
     ┌───────────────────────────────────┐
     │ Project Dashboard 顯示：           │
     │ - 進度                             │
     │ - 下一步建議                       │
     │ - 可直接一鍵開始新訪談             │
     └──────────────┬────────────────────┘
                    │
                    ▼
              (回到「進行訪談」循環)
```

---

## 十、風險與注意事項

1. **AI Token 成本增加** — Insight Memo、Evidence Matrix、Stakeholder Plan 都需要 AI 分析，每場訪談的 AI 呼叫次數會增加。建議使用 `gpt-5.4-mini` 處理結構化萃取，只在最終 BRD 生成用更高階模型。

2. **現有使用者遷移** — 已有的 interview_sessions 沒有 project_id，需要提供「匯入為新專案」功能或保留獨立模式。

3. **Prompt 品質** — Insight Memo 和 Stakeholder Plan 的品質高度依賴 AI prompt 設計。建議善用現有 Prompt Registry 進行版本管理與 A/B 測試。

4. **前端體驗設計** — 五層文件 (Transcript → Q/A → Memo → Matrix → BRD) 加上 Stakeholder Plan 的導航不能讓使用者迷路。建議用 Project Dashboard 作為中央導航點，一目了然地顯示進度與下一步。

5. **增量更新 vs 全量重算** — Evidence Matrix 在每次新 Memo 加入時應該是增量更新（只處理新 memo 的 candidates），而非全量重新計算所有 entries。

6. **建議過度干預** — 動態建議系統不應該過度 pushy。建議以「資訊展示」為主，而非「強制擋門」。使用者可以忽略建議直接開始訪談。

7. **Stakeholder Plan 初始建議品質** — 第一版 AI 建議可能不完美。提供使用者簡單的編輯介面（新增/刪除/調整 slot）比追求完美建議更重要。
