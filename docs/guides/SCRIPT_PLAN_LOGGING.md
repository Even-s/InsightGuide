# Script Plan 日誌說明

**日期**: 2026-06-01  
**目的**: 追蹤 Plan 生成和推進的時間戳

---

## 📋 日誌格式

### 1. 生成 Plan

**開始**:
```
2026-06-01 15:30:45,123 - app.services.script_plan_service - INFO - [ScriptPlan] Generating new plan for session session_xxx, 12 sentences
```

**完成**:
```
2026-06-01 15:30:48,456 - app.services.script_plan_service - INFO - [ScriptPlan] ✅ Generated plan in 3.33s: 12 sentences, session=session_xxx
```

**時間計算**: `完成時間 - 開始時間 = 生成耗時`

---

### 2. 推進 Cursor (Advance)

**收到請求**:
```
2026-06-01 15:31:10,789 - app.services.script_plan_service - INFO - [ScriptPlan] Advance request: session=session_xxx, transcript='大家好，今天要為各位介紹...'
```

**推進成功** (action = advance):
```
2026-06-01 15:31:10,801 - app.services.script_plan_service - INFO - [ScriptPlan] ✅ ADVANCE: cursor 0 → 1, confidence=0.65
```

**跳過句子** (action = skip_to_matched):
```
2026-06-01 15:31:15,234 - app.services.script_plan_service - INFO - [ScriptPlan] ⏭️ SKIP: cursor 1 → 3, skipped 2 sentences
```

**保持不變** (action = hold):
```
2026-06-01 15:31:20,567 - app.services.script_plan_service - INFO - [ScriptPlan] ⏸️ HOLD: cursor=2, confidence=0.25, reason=Partial match, holding (score: 0.25)
```

**忽略** (action = ignore):
```
2026-06-01 15:31:25,890 - app.services.script_plan_service - INFO - [ScriptPlan] ⏭️ IGNORE: transcript too short or meaningless
```

**完成**:
```
2026-06-01 15:31:10,812 - app.services.script_plan_service - INFO - [ScriptPlan] ⏱️ Advance completed in 0.023s: action=advance, new_cursor=1/12
```

**時間計算**: `完成時間 - 請求時間 = 推進耗時`

---

## 🔍 查看日誌

### 即時監看

```bash
# 監看所有 ScriptPlan 日誌
tail -f /tmp/backend.log | grep ScriptPlan

# 只看推進動作
tail -f /tmp/backend.log | grep "ADVANCE\|SKIP\|HOLD"

# 看時間戳
tail -f /tmp/backend.log | grep "ScriptPlan.*⏱️"
```

### 歷史分析

```bash
# 查看最近的 Plan 生成
grep "Generated plan" /tmp/backend.log | tail -10

# 查看所有推進動作
grep "ADVANCE:" /tmp/backend.log

# 統計推進成功率
grep "ADVANCE\|HOLD" /tmp/backend.log | tail -20

# 分析耗時
grep "completed in" /tmp/backend.log | tail -20
```

---

## 📊 日誌範例

### 完整流程範例

```
# 1. 使用者進入簡報模式
2026-06-01 15:30:45,123 INFO [ScriptPlan] Generating new plan for session session_abc, 12 sentences
2026-06-01 15:30:48,456 INFO [ScriptPlan] ✅ Generated plan in 3.33s: 12 sentences, session=session_abc

# 2. 使用者講第一句話
2026-06-01 15:31:10,789 INFO [ScriptPlan] Advance request: session=session_abc, transcript='大家好，今天要為各位介紹我們的產品...'
2026-06-01 15:31:10,801 INFO [ScriptPlan] ✅ ADVANCE: cursor 0 → 1, confidence=0.65
2026-06-01 15:31:10,812 INFO [ScriptPlan] ⏱️ Advance completed in 0.023s: action=advance, new_cursor=1/12

# 3. 使用者講第二句話
2026-06-01 15:31:15,123 INFO [ScriptPlan] Advance request: session=session_abc, transcript='首先我們來看市場現況...'
2026-06-01 15:31:15,145 INFO [ScriptPlan] ✅ ADVANCE: cursor 1 → 2, confidence=0.72
2026-06-01 15:31:15,156 INFO [ScriptPlan] ⏱️ Advance completed in 0.033s: action=advance, new_cursor=2/12

# 4. 使用者說了不太相關的話
2026-06-01 15:31:20,456 INFO [ScriptPlan] Advance request: session=session_abc, transcript='嗯...'
2026-06-01 15:31:20,478 INFO [ScriptPlan] ⏸️ HOLD: cursor=2, confidence=0.15, reason=Low match, holding (score: 0.15)
2026-06-01 15:31:20,489 INFO [ScriptPlan] ⏱️ Advance completed in 0.033s: action=hold, new_cursor=2/12

# 5. 使用者繼續講第三句
2026-06-01 15:31:25,789 INFO [ScriptPlan] Advance request: session=session_abc, transcript='這張圖表顯示了...'
2026-06-01 15:31:25,801 INFO [ScriptPlan] ✅ ADVANCE: cursor 2 → 3, confidence=0.68
2026-06-01 15:31:25,812 INFO [ScriptPlan] ⏱️ Advance completed in 0.023s: action=advance, new_cursor=3/12
```

---

## 📈 效能指標

### 預期耗時

| 操作 | 預期耗時 | 說明 |
|------|----------|------|
| **生成 Plan** | 2-5 秒 | 取決於句數和 GPT-5.4-mini 回應速度 |
| **Advance 判斷** | < 50ms | MVP 使用簡單匹配，非常快速 |
| **總延遲** | < 100ms | 從使用者講話到前端更新 |

### 時間戳格式

```
2026-06-01 15:30:45,123
^^^^^^^^   ^^^^^^^^ ^^^
日期       時間     毫秒
```

- 精確到毫秒（3位）
- UTC 時間
- 格式：`YYYY-MM-DD HH:MM:SS,mmm`

---

## 🔧 如何使用日誌分析問題

### 問題 1: 推進太慢

**檢查**:
```bash
grep "Advance completed" /tmp/backend.log | tail -20
```

**預期**: < 50ms  
**如果過慢**: 檢查是否有其他耗時操作

### 問題 2: 不推進

**檢查**:
```bash
grep "HOLD\|ADVANCE" /tmp/backend.log | tail -20
```

**分析**:
- 如果全是 `HOLD`: 匹配閾值太嚴格
- 如果有 `confidence` 很低: 使用者說的話與建議稿差異太大

### 問題 3: 生成太慢

**檢查**:
```bash
grep "Generated plan" /tmp/backend.log | tail -10
```

**預期**: 2-5 秒  
**如果過慢**: 
- 檢查 OpenAI API 延遲
- 檢查句數是否過多

### 問題 4: 追蹤單一 Session

**命令**:
```bash
grep "session_abc" /tmp/backend.log | grep ScriptPlan
```

**輸出**: 該 session 的完整生命週期

---

## 🎯 日誌等級

### INFO (預設)
- Plan 生成/完成
- Advance 動作
- 時間戳記

### DEBUG (需要啟用)
- 詳細的匹配分數
- 關鍵詞匹配細節
- 中間計算過程

**啟用 DEBUG**:
```python
# backend/app/core/logging.py
logging.getLogger("app.services.script_plan_service").setLevel(logging.DEBUG)
```

---

## 📝 日誌符號說明

| 符號 | 意義 | 說明 |
|------|------|------|
| ✅ | 成功 | 操作成功完成 |
| ⏭️ | 跳過 | 跳過句子或忽略 |
| ⏸️ | 暫停 | Hold 不推進 |
| ⏱️ | 時間 | 耗時記錄 |

---

## 🔄 實時監控範例

### 監控腳本

```bash
#!/bin/bash
# monitor_script_plan.sh

echo "📊 Monitoring Script Plan Activity..."
echo "Press Ctrl+C to stop"
echo ""

tail -f /tmp/backend.log | while read line; do
  if [[ $line == *"ScriptPlan"* ]]; then
    # 提取時間戳
    timestamp=$(echo $line | cut -d' ' -f1,2)
    
    # 高亮不同類型
    if [[ $line == *"ADVANCE"* ]]; then
      echo -e "\033[0;32m[$timestamp] ✅ $line\033[0m"
    elif [[ $line == *"HOLD"* ]]; then
      echo -e "\033[0;33m[$timestamp] ⏸️ $line\033[0m"
    elif [[ $line == *"SKIP"* ]]; then
      echo -e "\033[0;36m[$timestamp] ⏭️ $line\033[0m"
    elif [[ $line == *"Generated plan"* ]]; then
      echo -e "\033[0;35m[$timestamp] 📋 $line\033[0m"
    else
      echo "[$timestamp] $line"
    fi
  fi
done
```

**使用**:
```bash
chmod +x monitor_script_plan.sh
./monitor_script_plan.sh
```

---

## ✅ 總結

**已添加的日誌**:
1. ✅ Plan 生成開始/完成（含耗時）
2. ✅ Advance 請求（含 transcript）
3. ✅ 推進動作（ADVANCE/SKIP/HOLD/IGNORE）
4. ✅ 推進完成（含耗時）
5. ✅ 信心分數和原因

**時間戳精度**: 毫秒級（3位）

**查看方式**:
```bash
tail -f /tmp/backend.log | grep ScriptPlan
```

**現在可以追蹤**:
- Plan 生成花了多久
- 每次推進花了多久
- 使用者說了什麼
- 系統如何判斷（advance/hold）
- 當前進度（cursor/total）

🎉 完整的時間戳記錄已完成！
