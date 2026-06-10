# InsightGuide Development Roadmap

**Vision**: AI-powered requirements interview assistant that helps analysts conduct thorough, consistent interviews and generate complete BRD documents.

**Current Status**: 70% Complete | **Target Launch**: ~9 weeks

---

## 🗺️ Visual Roadmap

```
Past ──────────────── Present ─────────────── Future ────────────────►

    ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
    │ M1: Setup   │   │ M2: Core    │   │ M3: Cleanup │   │ M4: Advanced│
    │  ✅ DONE    │──►│  🟡 80%     │──►│  🔴 40%     │──►│  ⏸️ 10%     │
    │             │   │             │   │ ◄─ YOU ARE  │   │             │
    │ • Docker    │   │ • Upload    │   │    HERE     │   │ • BRD Gen   │
    │ • Models    │   │ • AI Cards  │   │             │   │ • Templates │
    │ • APIs      │   │ • Interview │   │ • Remove    │   │ • Export    │
    │ • Brand     │   │ • Eval      │   │   legacy    │   │             │
    └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
                                              │
                                              │
        ┌─────────────┐   ┌─────────────┐   │   ┌─────────────┐
        │ M6: Launch  │   │ M5: Testing │   │   │             │
        │  ⏸️ 0%      │◄──│  🟡 15%     │◄──┘   │  Phase 3.1  │
        │             │   │             │       │  Phase 3.2  │
        │ • Deploy    │   │ • Unit Test │       │  Phase 3.3  │
        │ • Monitor   │   │ • E2E Test  │       │  Phase 3.4  │
        │ • Support   │   │ • Security  │       │  Phase 3.5  │
        └─────────────┘   └─────────────┘       └─────────────┘

Legend: ✅ Done | 🟡 In Progress | 🔴 Blocked | ⏸️ Not Started
```

---

## 📅 Timeline

### Phase 1: Foundation (COMPLETED ✅)
**Duration**: Past work  
**Status**: 95% Complete

```
Week -8 ──────── Week -4 ──────── Week 0 (Today)
    │                 │                 │
    ├─ Project Setup  ├─ Core Features  ├─ Status Check
    ├─ Docker Config  ├─ AI Integration ├─ Documentation
    ├─ Models         ├─ Transcription  └─ You are here
    └─ Brand Rename   └─ Reports              ▼
```

**Achievements**:
- ✅ Full stack infrastructure (Docker, PostgreSQL, Redis, MinIO)
- ✅ Data models (Document, Section, QuestionCard, InterviewSession)
- ✅ Answer Evaluation Engine (15KB implementation)
- ✅ Real-time transcription via OpenAI
- ✅ Session reports with PDF/JSON export
- ✅ Project renamed from SlideCue to InsightGuide

---

### Phase 2: Current Sprint (IN PROGRESS 🔴)
**Duration**: Week 1-2 (June 10 - June 24)  
**Focus**: Code Cleanup - Critical Priority

```
Week 1                    Week 2
Mon ──── Wed ──── Fri ──── Mon ──── Wed ──── Fri
 │        │        │        │        │        │
 ├─ Start ├─ Phase ├─ Phase ├─ Phase ├─ Final ├─ Merge
 │  M3    │  3.1   │  3.2   │  3.3-5 │  Test  │  & Tag
 │        │  Done  │  Done  │  Done  │  Pass  │  v0.8
 ▼        │        │        │        │        │
You       └────────┴────────┴────────┴────────┘
Start                Cleanup Sprint
Here
```

**Goals**:
1. **Week 1**: Remove PresentationSession, Deck references
2. **Week 2**: Remove Slide, TopicCard references, test & merge

**Success Criteria**:
- [ ] Zero legacy references in services (175 → 0)
- [ ] All imports work correctly
- [ ] All tests pass
- [ ] Services start without errors

---

### Phase 3: Polish & Features (NEXT 🟡)
**Duration**: Week 3-5 (June 24 - July 15)  
**Focus**: Complete Core Features + BRD Generation

```
Week 3          Week 4          Week 5
Jun 24 ──────── Jul 1 ──────── Jul 8 ──────── Jul 15
  │               │               │               │
  ├─ Frontend     ├─ BRD Service  ├─ BRD API     ├─ Testing
  │  Polish       │  Backend      │  & Frontend  │  & Polish
  │               │               │               │
  ├─ Loading      ├─ Templates    ├─ Preview     ├─ User
  │  States       │  & Logic      │  Component   │  Testing
  │               │               │               │
  └─ Error        └─ Generation   └─ Export      └─ Fixes
     Handling        Logic            PDF/MD         v0.9
```

**Deliverables**:
- ✅ Polished interview UI
- ✅ BRD generation service
- ✅ BRD preview & export
- ✅ Enhanced editor features

---

### Phase 4: Quality Assurance (PLANNED ⏸️)
**Duration**: Week 6-7 (July 15 - July 29)  
**Focus**: Comprehensive Testing

```
Week 6                      Week 7
Jul 15 ──────────────────── Jul 22 ──────────────────── Jul 29
  │                           │                           │
  ├─ Unit Tests (Backend)     ├─ Performance Testing     ├─ Security
  │  Target: 80% coverage     │  Load testing            │  Audit
  │                           │  Optimization            │  
  ├─ Integration Tests        │                           │
  │  Full workflows           ├─ E2E Tests               └─ Final
  │                           │  Cypress/Playwright         QA Pass
  └─ Fix Bugs Found          └─ Fix Issues                 v1.0-rc1
```

**Quality Targets**:
- 80% backend test coverage
- All integration tests pass
- E2E tests for critical paths
- Performance < 2s for 95% requests
- Zero critical security vulnerabilities

---

### Phase 5: Production Launch (TARGET 🎯)
**Duration**: Week 8-9 (July 29 - August 12)  
**Focus**: Deployment & Go-Live

```
Week 8                      Week 9
Jul 29 ──────────────────── Aug 5 ──────────────────── Aug 12
  │                           │                           │
  ├─ Infra Setup              ├─ Beta Launch             ├─ Public
  │  AWS/GCP                  │  Internal users           │  Launch
  │  CI/CD                    │                           │
  │  Monitoring               ├─ Gather Feedback         ├─ Monitor
  │                           │  Fix critical bugs        │  Support
  └─ Staging Deploy          └─ Polish & Improve         └─ Celebrate! 🎉
     Load Testing               v1.0-beta                   v1.0
```

**Launch Checklist**:
- [ ] Production environment configured
- [ ] CI/CD pipeline working
- [ ] Monitoring & alerts set up
- [ ] Documentation complete
- [ ] Support team trained
- [ ] Beta testing complete
- [ ] All critical bugs fixed

---

## 🎯 Feature Roadmap by Release

### v0.8 - Code Cleanup (Week 2)
**Target**: 2026-06-24

- [x] Project foundation complete
- [x] Core features implemented
- [ ] **All legacy code removed** ⭐
- [ ] Clean import structure
- [ ] No broken references

### v0.9 - Feature Complete (Week 5)
**Target**: 2026-07-15

- [ ] BRD generation service ⭐
- [ ] Polished interview UI
- [ ] Enhanced editor features
- [ ] Error handling & loading states
- [ ] Performance optimized

### v1.0-rc1 - Release Candidate (Week 7)
**Target**: 2026-07-29

- [ ] 80% test coverage ⭐
- [ ] E2E tests passing
- [ ] Security audit complete
- [ ] Performance targets met
- [ ] Documentation complete

### v1.0 - Public Launch 🚀 (Week 9)
**Target**: 2026-08-12

- [ ] Production deployment ⭐
- [ ] Beta testing complete
- [ ] All critical bugs fixed
- [ ] Monitoring & support ready
- [ ] Launch announcement

### v1.1 - Post-Launch (Future)
**Target**: 2026-09-01

- [ ] User feedback incorporated
- [ ] Performance improvements
- [ ] UI/UX refinements
- [ ] Additional templates

### v2.0 - Advanced Features (Future)
**Target**: Q4 2026

- [ ] Collaboration features
- [ ] Analytics dashboard
- [ ] Team workspaces
- [ ] Advanced AI features
- [ ] Mobile support

---

## 🚦 Priority Matrix

### Must Have (P0) - For v1.0 Launch
```
┌────────────────────────────────────┐
│  ✅ Document upload & analysis     │
│  ✅ AI question generation         │
│  ✅ Interview mode with transcription │
│  ✅ Answer evaluation              │
│  ✅ Session reports                │
│  🔴 Code cleanup (M3)              │ ← BLOCKING
│  ⏸️ BRD generation (M4)            │
│  ⏸️ Comprehensive testing (M5)     │
│  ⏸️ Production deployment (M6)     │
└────────────────────────────────────┘
```

### Should Have (P1) - Nice to Have for v1.0
```
┌────────────────────────────────────┐
│  ⏸️ Enhanced editor features       │
│  ⏸️ Card templates library         │
│  ⏸️ Bulk operations                │
│  ⏸️ Advanced analytics             │
└────────────────────────────────────┘
```

### Could Have (P2) - Defer to v2.0
```
┌────────────────────────────────────┐
│  ⏸️ Collaboration features         │
│  ⏸️ Team workspaces                │
│  ⏸️ Mobile support                 │
│  ⏸️ Custom AI model training       │
└────────────────────────────────────┘
```

---

## 📊 Progress by Component

### Backend Services
```
Core Services:          ████████████████░░░░  80% ✅
Answer Evaluation:      ████████████████████  100% ✅
AI Integration:         ███████████████████░  95% ✅
Report Generation:      ████████████████████  100% ✅
BRD Generation:         ░░░░░░░░░░░░░░░░░░░░  0% ⏸️
Code Quality:           ████████░░░░░░░░░░░░  40% 🔴
Testing:                ███░░░░░░░░░░░░░░░░░  15% 🔴
```

### Frontend Components
```
Upload & Analysis:      ████████████████████  100% ✅
Editor Mode:            ████████████████░░░░  80% 🟡
Interview Mode:         ██████████████░░░░░░  70% 🟡
Session Reports:        ████████████████████  100% ✅
BRD Preview:            ░░░░░░░░░░░░░░░░░░░░  0% ⏸️
UI Polish:              ████████░░░░░░░░░░░░  40% 🔴
Testing:                ██░░░░░░░░░░░░░░░░░░  10% 🔴
```

### Infrastructure
```
Docker Setup:           ████████████████████  100% ✅
Database:               ████████████████████  100% ✅
Redis/Cache:            ████████████████████  100% ✅
S3/Storage:             ████████████████████  100% ✅
CI/CD:                  ░░░░░░░░░░░░░░░░░░░░  0% ⏸️
Monitoring:             ░░░░░░░░░░░░░░░░░░░░  0% ⏸️
Production Deploy:      ░░░░░░░░░░░░░░░░░░░░  0% ⏸️
```

---

## 🎬 Critical Path

The fastest path to launch:

```
START → M3 Cleanup → M4 BRD → M5 Testing → M6 Deploy → LAUNCH
        (2 weeks)    (2 wks)   (2 weeks)    (1 week)   (9 wks)
           ↓            ↓          ↓            ↓         ↓
        Required     Core      Quality      Deploy    Public
        for all     Feature   Assurance    to Prod   Release
        future                                          🎉
        work
```

**Cannot skip**: M3 is blocking everything else  
**Cannot defer**: BRD generation is in README/promised feature  
**Cannot rush**: Testing is critical for quality

---

## 🔄 Iteration Strategy

### Sprint Structure (2-week sprints)
```
Sprint 1 (Jun 10-24):  M3 Code Cleanup
Sprint 2 (Jun 24-Jul 8):  M2 Polish + M4 BRD (Part 1)
Sprint 3 (Jul 8-22):  M4 BRD (Part 2) + M5 Testing Start
Sprint 4 (Jul 22-Aug 5):  M5 Testing Complete + M6 Deploy
Sprint 5 (Aug 5-12):  Beta Launch + Fixes
```

### Weekly Cadence
- **Monday**: Sprint planning, set weekly goals
- **Wednesday**: Mid-week check-in, unblock issues
- **Friday**: Sprint review, update docs, plan next week

### Daily Rhythm
- **Morning**: Review PROGRESS.md, plan today's tasks
- **Work**: Focus on current milestone tasks
- **Evening**: Update PROGRESS.md daily log, commit code

---

## 📞 Stakeholder Updates

### Weekly Status Report Format
```markdown
**Week of**: [Date]
**Milestone**: [Current milestone]
**Progress**: [X%]
**Completed**: [Major achievements]
**In Progress**: [Current work]
**Blocked By**: [Blockers]
**Next Week**: [Upcoming work]
**Risks**: [Any concerns]
```

### Monthly Review Topics
1. Progress vs. plan
2. Budget vs. actual
3. Risks and mitigation
4. Timeline adjustments
5. Feature scope changes

---

## 🎯 Success Metrics

### Development Metrics
- **Code Quality**: 40% → 90% (after cleanup)
- **Test Coverage**: 15% → 80%
- **Performance**: TBD → < 2s (95th percentile)
- **Bugs**: Unknown → < 5 critical bugs at launch

### Business Metrics (Post-Launch)
- **User Satisfaction**: Target > 4.0/5.0
- **Feature Usage**: 80% of users use BRD generation
- **Time Savings**: 50% reduction in interview time
- **Adoption**: 100 active users in first month

---

## 🔗 Quick Links

- **Daily Progress**: [PROGRESS.md](./PROGRESS.md)
- **Detailed Milestones**: [MILESTONES.md](./MILESTONES.md)
- **Cleanup Status**: [CLEANUP_STATUS.md](./CLEANUP_STATUS.md)
- **Architecture**: [docs/architecture/InsightGuide_開發架構書.md](docs/architecture/InsightGuide_開發架構書.md)

---

## 📝 Roadmap Changes

| Date | Change | Reason |
|------|--------|--------|
| 2026-06-10 | Initial roadmap created | Need high-level plan |
| 2026-06-10 | Prioritized M3 cleanup | Blocking future work |
| 2026-06-10 | Set target launch ~9 weeks | Based on milestone estimates |

---

**Next Review**: 2026-06-17 (after first cleanup sprint)  
**Maintained By**: Development Team Lead  
**Last Updated**: 2026-06-10

