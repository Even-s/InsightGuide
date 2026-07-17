# 訪談逐字稿與卡片匹配改進計劃（歷史封存）

此文件原本描述「Realtime 逐字稿 + 完整錄音 diarization + speaker Q&A reconstruction」的雙軌方案。該方案已退役。

自 2026-07-15 起，InsightGuide 的正式架構是：

- Realtime transcript 是唯一逐字稿來源。
- 不再上傳完整錄音做 diarization。
- 不再保存 speaker role、speaker label、Q/A reconstruction 舊資料表。
- AI 只建議問題卡與補充 evidence；人工確認目前題目與是否完成。
- BRD、Readiness、Evidence Matrix 只讀取 `InterviewRoundAggregate` 的累積快照。

現行架構請以：

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [FUNCTIONAL_TEST_PLAN.md](FUNCTIONAL_TEST_PLAN.md)

為準。

保留此檔只為記錄：曾經評估過雙軌逐字稿方案，但已因資料流複雜、延遲高、角色辨識不穩與證據指向容易失真而正式放棄。
