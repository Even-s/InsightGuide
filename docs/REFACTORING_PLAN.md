# InsightGuide 重構計劃（歷史封存）

此文件原本記錄從單次訪談 BRD 生成器，轉型為多輪需求研究工作台的長版重構方案。當中的舊 diarization、speaker Q&A、alignment、section/deck 相容設計已退役。

現行正式模型已收斂為：

```text
Project
  └─ StakeholderProfile
      └─ InterviewSeries
          └─ InterviewRound
              ├─ GuideDocument
              ├─ QuestionCards
              ├─ InterviewSessions
              │   └─ RealtimeUtterances
              └─ RoundAggregate
                  ├─ coverage_snapshot
                  ├─ evidence_snapshot
                  └─ latest_memo_id
```

正式規則：

- `Document` 只代表訪談大綱 / guide，不再叫 deck。
- `InterviewTheme` 是訪談單元，不再使用 Section / Slide 作為主要單位。
- `QuestionCard` 是唯一卡片名稱，不再保留 TopicCard 命名。
- Realtime transcript 是唯一逐字稿來源。
- `RoundAggregate` 是 BRD / Readiness / Evidence Matrix 的唯一讀取來源。
- 歷史資料可清空，系統不再支援舊 presentation/deck/slide 資料相容。

現行架構請以：

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [FUNCTIONAL_TEST_PLAN.md](FUNCTIONAL_TEST_PLAN.md)

為準。
