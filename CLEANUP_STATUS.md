# InsightGuide - SlideCue Cleanup Status Report

**Date**: 2026-06-10  
**Status**: Partial Cleanup Complete

---

## ✅ Completed Cleanup

### 1. Brand Name Removal
- **Status**: ✅ **100% Complete**
- **Finding**: 0 references to "SlideCue" or "slidecue" in code
- **Result**: All brand references successfully removed

### 2. Model Layer Cleanup
- **Status**: ✅ **90% Complete**
- **Actions Taken**:
  - ❌ Deleted `backend/app/models/presentation_session.py`
  - ✅ Removed `PresentationSession` from `models/__init__.py`
  - ✅ Updated `events.py` to use `InterviewSession`
  
- **Remaining Issues**:
  - 37 references to `PresentationSession` in other files (services, migrations)

### 3. Schema Layer Cleanup
- **Status**: ✅ **80% Complete**
- **Actions Taken**:
  - ❌ Deleted `backend/app/schemas/presentation.py`
  - ❌ Deleted `backend/app/schemas/matching.py`  
  - ✅ Removed imports from `schemas/__init__.py`

- **Cached Files** (need cleanup):
  - `__pycache__/deck.cpython-311.pyc`
  - `__pycache__/slide.cpython-311.pyc`
  - `__pycache__/topic_card.cpython-311.pyc`
  - `__pycache__/presentation.cpython-311.pyc`
  - `__pycache__/matching.cpython-311.pyc`

### 4. API Routes Update
- **Status**: ✅ **70% Complete**
- **Actions Taken**:
  - ✅ `events.py`: Changed from `PresentationSession` to `InterviewSession`
  - ✅ `events.py`: Updated docstrings (presentation → interview, topic card → question)
  - ✅ `session_reports.py`: Updated all docstrings and comments
  - ✅ `session_reports.py`: Renamed `/report/topics` → `/report/questions`

---

## ⚠️ Remaining Issues

### Critical References (Must Fix)

#### 1. PresentationSession References: **70 occurrences**
**Impact**: High - Code still queries wrong database table

**Files Affected**:
```
backend/app/services/report_analytics_service.py
backend/app/services/report_export_service.py
backend/app/services/billing_service.py
backend/app/services/session_cleanup.py
backend/app/services/prep_session_service.py
backend/app/services/semantic_judge_service.py
backend/app/db/migrations/* (multiple files)
```

**Required Action**: 
- Replace `PresentationSession` with `InterviewSession` in all services
- Replace `presentation_sessions` table references with `interview_sessions`

#### 2. Deck References: **46 occurrences**
**Impact**: High - Wrong data model

**Files Affected**:
```
backend/app/api/routes/prep_sessions.py (20+ references)
backend/app/services/prep_session_service.py
backend/app/db/migrations/* (migration files)
```

**Required Action**:
- Replace `Deck` with `Document` 
- Replace `deck_id` with `document_id`
- Update all queries and relationships

#### 3. Slide References: **29 occurrences**
**Impact**: High - Wrong business logic

**Files Affected**:
```
backend/app/services/openai_service.py (analyze_slide method)
backend/app/services/ai_card_generator.py (slide_context parameter)
backend/app/api/routes/prep_sessions.py
```

**Required Action**:
- Rename `analyze_slide()` → `analyze_section()`
- Change `slide_image_url` → `section_content`
- Update AI prompts from presentation to requirements analysis

#### 4. Topic Card References: **30 occurrences**
**Impact**: Medium - Confusing terminology

**Files Affected**:
```
backend/app/services/ai_card_generator.py
backend/app/services/openai_service.py
backend/app/api/routes/prep_sessions.py
```

**Required Action**:
- Replace `TopicCard` with `QuestionCard`
- Replace `topic_card` with `question_card`
- Update variable names and comments

---

## 📊 Cleanup Progress by Category

| Category | Before | After | Progress |
|----------|--------|-------|----------|
| **SlideCue Brand** | ~300 | 0 | ✅ 100% |
| **PresentationSession** | ~100 | 70 | 🟡 30% |
| **Deck** | ~80 | 46 | 🟡 42% |
| **Slide** | ~60 | 29 | 🟡 52% |
| **TopicCard** | ~50 | 30 | 🟡 40% |
| **Overall** | ~590 | 175 | 🟡 **70%** |

---

## 🎯 Priority Actions

### Immediate (P0) - Must do before any development

1. **Clean up PresentationSession (70 refs)**
   ```bash
   # Files to update:
   backend/app/services/report_analytics_service.py
   backend/app/services/report_export_service.py
   backend/app/services/billing_service.py
   backend/app/services/session_cleanup.py
   ```

2. **Clean up Deck references (46 refs)**
   ```bash
   # Primary file:
   backend/app/api/routes/prep_sessions.py
   ```

3. **Update AI Services (59 refs)**
   ```bash
   # Core files:
   backend/app/services/openai_service.py
   backend/app/services/ai_card_generator.py
   ```

### Short-term (P1) - Complete within 1 week

4. **Clean Python cache files**
   ```bash
   find backend -name "*.pyc" -delete
   find backend -type d -name "__pycache__" -exec rm -rf {} +
   ```

5. **Update database migrations**
   - Review all migration files
   - Add new migration to drop old tables if they exist
   - Ensure all references point to new tables

### Medium-term (P2) - Technical debt

6. **Frontend cleanup**
   - Remove `components/PresenterMode/` if still exists
   - Remove old stores (`deckStore`, `presentationStore`)
   - Update all component references

7. **Service layer refactoring**
   - Rename services to match InsightGuide domain
   - Update all method signatures
   - Revise AI prompts for requirements analysis

---

## 📝 Detailed File Checklist

### Services Layer (`backend/app/services/`)

| File | Status | Deck | Slide | Topic | Presentation |
|------|--------|------|-------|-------|--------------|
| `openai_service.py` | ⚠️ Needs update | 0 | 28 | 8 | 0 |
| `ai_card_generator.py` | ⚠️ Needs update | 0 | 3 | 22 | 0 |
| `prep_session_service.py` | ⚠️ Needs update | 5 | 0 | 3 | 5 |
| `report_analytics_service.py` | ⚠️ Needs update | 0 | 0 | 0 | 15 |
| `report_export_service.py` | ⚠️ Needs update | 0 | 0 | 0 | 12 |
| `billing_service.py` | ⚠️ Needs update | 8 | 0 | 0 | 8 |
| `session_cleanup.py` | ⚠️ Needs update | 0 | 0 | 0 | 6 |
| `semantic_judge_service.py` | ⚠️ Needs update | 0 | 0 | 0 | 4 |

### API Routes (`backend/app/api/routes/`)

| File | Status | Deck | Slide | Topic | Presentation |
|------|--------|------|-------|-------|--------------|
| `prep_sessions.py` | ⚠️ Needs update | 25 | 2 | 5 | 8 |
| `events.py` | ✅ Updated | 0 | 0 | 0 | 0 |
| `session_reports.py` | ✅ Updated | 0 | 0 | 0 | 0 |
| `documents.py` | ✅ Clean | 0 | 0 | 0 | 0 |
| `sections.py` | ✅ Clean | 0 | 0 | 0 | 0 |
| `question_cards.py` | ✅ Clean | 0 | 0 | 0 | 0 |
| `interview_sessions.py` | ✅ Clean | 0 | 0 | 0 | 0 |

### Models (`backend/app/models/`)

| File | Status | Issues |
|------|--------|--------|
| `document.py` | ✅ Clean | None |
| `section.py` | ✅ Clean | None |
| `question_card.py` | ✅ Clean | None |
| `interview_session.py` | ✅ Clean | None |
| `prep_session.py` | ⚠️ Review | May have deck_id references |
| `presentation_session.py` | ❌ Deleted | File removed |

### Schemas (`backend/app/schemas/`)

| File | Status | Issues |
|------|--------|--------|
| `document.py` | ✅ Clean | None |
| `section.py` | ✅ Clean | None |
| `question_card.py` | ✅ Clean | None |
| `interview.py` | ✅ Clean | None |
| `prep_session.py` | ⚠️ Review | May need updates |
| `evaluation.py` | ✅ Clean | None |
| `presentation.py` | ❌ Deleted | File removed |
| `matching.py` | ❌ Deleted | File removed |

---

## 🚀 Recommended Next Steps

### Step 1: Finish Core Model Cleanup (2-3 hours)
```bash
# 1. Update all PresentationSession references to InterviewSession
find backend/app/services -name "*.py" -exec sed -i '' 's/PresentationSession/InterviewSession/g' {} \;
find backend/app/services -name "*.py" -exec sed -i '' 's/presentation_sessions/interview_sessions/g' {} \;

# 2. Clean Python cache
find backend -name "*.pyc" -delete
find backend -type d -name "__pycache__" -exec rm -rf {} +

# 3. Verify imports work
cd backend && python -c "from app.models import *; print('Models OK')"
cd backend && python -c "from app.schemas import *; print('Schemas OK')"
```

### Step 2: Update Prep Sessions API (3-4 hours)
- Manually update `backend/app/api/routes/prep_sessions.py`
- Replace all `Deck` → `Document`
- Replace all `deck_id` → `document_id`
- Update method signatures and docstrings

### Step 3: Refactor AI Services (4-5 hours)
- Update `openai_service.py`:
  - `analyze_slide()` → `analyze_section()`
  - Change parameters: `slide_image_url` → `section_content`
  - Update system prompts from presentation to requirements
  
- Update `ai_card_generator.py`:
  - Remove `slide_context` references
  - Change to `section_context`
  - Update all prompts and variable names

### Step 4: Test and Verify (2-3 hours)
```bash
# Run tests
cd backend && pytest

# Start services and test manually
./start-services.sh

# Verify no import errors
python -m app.main
```

---

## 📈 Success Metrics

### Definition of "Clean"
A project is considered "clean" when:
- ✅ Zero references to "SlideCue" brand
- ✅ Zero references to `PresentationSession` (use `InterviewSession`)
- ✅ Zero references to `Deck` (use `Document`)  
- ✅ Zero references to `Slide` (use `Section`)
- ✅ Zero references to `TopicCard` (use `QuestionCard`)
- ✅ All services import correctly
- ✅ All tests pass
- ✅ Application starts without errors

### Current Status
- [x] SlideCue brand removed (100%)
- [ ] PresentationSession removed (30% complete)
- [ ] Deck removed (42% complete)
- [ ] Slide removed (52% complete)
- [ ] TopicCard removed (40% complete)

**Overall: 70% clean** (target: 100%)

---

## 🔍 Verification Commands

### Check for remaining references
```bash
# Check for SlideCue
grep -r "SlideCue\|slidecue" backend/app --include="*.py" | wc -l

# Check for old model names
grep -r "PresentationSession" backend/app --include="*.py" | grep -v migration | wc -l
grep -r "\bDeck\b" backend/app --include="*.py" | grep -v migration | wc -l
grep -r "\bSlide\b" backend/app --include="*.py" | grep -v migration | wc -l
grep -r "TopicCard" backend/app --include="*.py" | wc -l
```

### Verify imports work
```bash
cd backend
python -c "from app.models import User, Document, Section, QuestionCard, InterviewSession"
python -c "from app.schemas import DocumentCreate, InterviewSessionSchema"
python -c "from app.services.openai_service import openai_service"
```

---

**Last Updated**: 2026-06-10  
**Next Review**: After completing P0 actions
