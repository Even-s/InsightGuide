# InsightGuide Progress Tracking System

**Created**: 2026-06-10  
**Purpose**: Guide for using the project tracking documents

---

## 📚 Document Overview

This project has **5 tracking documents** to help you monitor progress at different levels:

| Document | Purpose | Update Frequency | When to Use |
|----------|---------|------------------|-------------|
| **[QUICK_STATUS.md](./QUICK_STATUS.md)** | Quick overview card | As needed | Want instant status check |
| **[PROGRESS.md](./PROGRESS.md)** | Daily progress log | Daily | Track day-to-day work |
| **[MILESTONES.md](./MILESTONES.md)** | Detailed milestone tracking | Weekly | Review progress, plan sprints |
| **[ROADMAP.md](./ROADMAP.md)** | High-level development plan | Monthly | Strategic planning |
| **[CLEANUP_STATUS.md](./CLEANUP_STATUS.md)** | Legacy code cleanup details | During M3 | Working on code cleanup |

---

## 🎯 Which Document Should I Use?

### I want to...

**Check overall status quickly**
→ Read [QUICK_STATUS.md](./QUICK_STATUS.md) (1 minute read)

**See what was done today/this week**
→ Read [PROGRESS.md](./PROGRESS.md) daily log section

**Understand what needs to be done**
→ Read [MILESTONES.md](./MILESTONES.md) for current milestone

**See the big picture/timeline**
→ Read [ROADMAP.md](./ROADMAP.md) visual timeline

**Work on code cleanup**
→ Read [CLEANUP_STATUS.md](./CLEANUP_STATUS.md) for detailed steps

**Report to stakeholders**
→ Use [PROGRESS.md](./PROGRESS.md) weekly summary section

---

## 🔄 How to Use the System

### Daily Routine (5 minutes)

1. **Morning**: Read [PROGRESS.md](./PROGRESS.md)
   - Check "Today's Tasks"
   - Note any blockers

2. **During Work**: Focus on current milestone tasks
   - Check [MILESTONES.md](./MILESTONES.md) for acceptance criteria
   - Use [CLEANUP_STATUS.md](./CLEANUP_STATUS.md) if working on M3

3. **Evening**: Update [PROGRESS.md](./PROGRESS.md)
   - Add to daily log (what done, blocked, next)
   - Update task checkboxes
   - Commit code with meaningful messages

### Weekly Routine (30 minutes)

**Every Friday:**

1. **Review Progress**
   - Read [PROGRESS.md](./PROGRESS.md) full document
   - Check milestone progress in [MILESTONES.md](./MILESTONES.md)
   - Update percentage complete for current milestone

2. **Update Documents**
   - Update [PROGRESS.md](./PROGRESS.md) weekly summary
   - Update [MILESTONES.md](./MILESTONES.md) task statuses
   - Adjust [QUICK_STATUS.md](./QUICK_STATUS.md) if needed

3. **Plan Next Week**
   - Set "This Week's Goals" in [PROGRESS.md](./PROGRESS.md)
   - Review "Next Steps" in [MILESTONES.md](./MILESTONES.md)
   - Identify blockers to resolve

### Monthly Routine (1-2 hours)

**First Monday of each month:**

1. **Strategic Review**
   - Review [ROADMAP.md](./ROADMAP.md) timeline
   - Update progress percentages
   - Adjust timeline if needed

2. **Milestone Planning**
   - Review completed milestones in [MILESTONES.md](./MILESTONES.md)
   - Plan next 1-2 milestones in detail
   - Update estimates and dates

3. **Documentation**
   - Update [ROADMAP.md](./ROADMAP.md) if scope changed
   - Archive old logs in [PROGRESS.md](./PROGRESS.md)
   - Update [QUICK_STATUS.md](./QUICK_STATUS.md) metrics

---

## 📊 Information Flow

```
                    ┌──────────────────┐
                    │  ROADMAP.md      │  ← Strategic (Monthly)
                    │  (High-level)    │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  MILESTONES.md   │  ← Tactical (Weekly)
                    │  (Detailed plan) │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  PROGRESS.md     │  ← Operational (Daily)
                    │  (Daily work)    │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  QUICK_STATUS.md │  ← Summary (Anytime)
                    │  (At-a-glance)   │
                    └──────────────────┘

                    CLEANUP_STATUS.md ─────── Special purpose (M3 only)
```

---

## 📝 Update Templates

### Daily Log Template (for PROGRESS.md)

```markdown
### YYYY-MM-DD (Day of Week)
- **Done**: What was completed today
- **Blocked**: Any blockers encountered
- **Decided**: Important decisions made
- **Next**: Tomorrow's plan
```

### Weekly Summary Template (for PROGRESS.md)

```markdown
## Week of YYYY-MM-DD

**Milestone**: MX: Name
**Progress**: X/Y tasks completed (Z%)
**Blockers**: 
- [Blocker description and impact]
**Decisions**:
- [Decision made and rationale]
**Next Week**:
- [Goals for next week]
```

### Milestone Update Template (for MILESTONES.md)

When updating a milestone:
1. Update progress percentage: `**Status**: 🟡 **80% Complete**`
2. Check off completed tasks: `- [x] Task name`
3. Update deliverables: `- [x] Deliverable name`
4. Note blockers in "Current Blockers" section
5. Update "Next Steps" section

---

## 🎯 Tracking Best Practices

### Do's ✅

- **Update daily**: Keep [PROGRESS.md](./PROGRESS.md) current
- **Be specific**: "Replaced 30 PresentationSession refs" not "Did cleanup"
- **Track blockers**: Note them immediately, don't let them surprise you
- **Commit often**: Small commits with clear messages
- **Celebrate wins**: Note completed tasks, even small ones
- **Link issues**: Reference file names and line numbers

### Don'ts ❌

- **Don't skip updates**: Even "no progress" is worth noting
- **Don't be vague**: "Made progress" tells you nothing later
- **Don't ignore blockers**: Call them out early
- **Don't work without planning**: Check milestones before starting
- **Don't update just one doc**: Keep related docs in sync
- **Don't commit tracking docs**: These are for local use (add to .gitignore if desired)

---

## 🚀 Quick Start

**First time using this system?**

1. **Read this order**:
   ```
   QUICK_STATUS.md (1 min)
        ↓
   PROGRESS.md (5 min)
        ↓
   MILESTONES.md (15 min)
        ↓
   ROADMAP.md (10 min)
   ```

2. **Today's Action**:
   - [ ] Open [QUICK_STATUS.md](./QUICK_STATUS.md) - understand current state
   - [ ] Read [PROGRESS.md](./PROGRESS.md) "This Week's Goals"
   - [ ] Start working on first task
   - [ ] Update [PROGRESS.md](./PROGRESS.md) tonight

3. **Set up routine**:
   - [ ] Add calendar reminder: Daily 9am "Check PROGRESS.md"
   - [ ] Add calendar reminder: Friday 5pm "Weekly review"
   - [ ] Add calendar reminder: First Monday "Monthly review"

---

## 📊 Metrics to Track

### In PROGRESS.md (Daily/Weekly)
- Tasks completed vs planned
- Blockers encountered
- Time spent on each phase

### In MILESTONES.md (Weekly)
- Percentage complete for current milestone
- Tasks completed vs total
- Actual vs estimated time

### In ROADMAP.md (Monthly)
- Overall project percentage
- Milestones completed vs planned
- Launch date adjustments

---

## 🔧 Customization

Feel free to adjust these documents for your workflow:

**Add sections** for:
- Dependencies tracking
- Risk register
- Decision log
- Team assignments

**Remove sections** that:
- You never use
- Add too much overhead
- Duplicate other tools

**Adjust frequency**:
- Daily → Every 2 days if solo developer
- Weekly → Bi-weekly if slow-moving project
- Monthly → Quarterly for long-term projects

---

## 🎓 Learning from Other Projects

### Good Examples

**[Project Name]**: Uses daily logs effectively
- Lesson: Brief but consistent updates work better than detailed but sporadic

**[Project Name]**: Great milestone tracking
- Lesson: Visual progress bars motivate team

### Anti-patterns to Avoid

❌ **Updating only when asked**: Documents become stale
❌ **Too much detail**: No one reads 50-page updates
❌ **Too little detail**: "Made progress" isn't useful
❌ **Inconsistent format**: Hard to scan and compare
❌ **No actionable next steps**: Team doesn't know what to do

---

## 📞 Questions?

**Where should I track [X]?**
- General progress → [PROGRESS.md](./PROGRESS.md)
- Milestone tasks → [MILESTONES.md](./MILESTONES.md)
- Strategic changes → [ROADMAP.md](./ROADMAP.md)
- Quick lookup → [QUICK_STATUS.md](./QUICK_STATUS.md)

**How detailed should I be?**
- Daily: Brief (1-2 sentences per section)
- Weekly: Moderate (1 paragraph per section)
- Monthly: Comprehensive (full review)

**What if I miss an update?**
- Daily: Update when you can, note the gap
- Weekly: Do a catch-up review
- Monthly: Critical - don't skip

---

## 🔗 Related Documents

- **Architecture**: [docs/architecture/InsightGuide_開發架構書.md](docs/architecture/InsightGuide_開發架構書.md)
- **Implementation**: `IMPLEMENTATION_SUMMARY.md`
- **Assessment**: `DEVELOPMENT_ASSESSMENT.md` (⚠️ Outdated, use with caution)
- **README**: [README.md](./README.md)

---

**Remember**: These documents are **tools to help you**, not bureaucracy. If something doesn't work, change it. The goal is to always know where you are and where you're going.

**Pro Tip**: Start with [QUICK_STATUS.md](./QUICK_STATUS.md) every morning. Everything else follows from there.

---

**Need Help?** Check the documents themselves - they all have "How to Use" sections!

**Last Updated**: 2026-06-10  
**Next Review**: When system needs adjustment
