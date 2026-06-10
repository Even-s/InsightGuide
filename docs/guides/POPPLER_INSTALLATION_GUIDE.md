# Poppler 安裝指南

**問題**: 簡報處理失敗 - 缺少 Poppler 工具
**影響**: 無法將 PDF 轉換為投影片圖片
**Deck ID**: `deck_2730ee69fe11`

---

## 🔍 問題診斷

您的 deck 處理流程：
1. ✅ PPTX 文件上傳成功
2. ✅ LibreOffice 將 PPTX 轉換為 PDF 成功
3. ❌ **失敗於**: PDF → 圖片轉換（需要 Poppler）

錯誤訊息：
```
FileNotFoundError: [Errno 2] No such file or directory: 'pdfinfo'
```

---

## 💡 解決方案

### 方案 1: 安裝 Homebrew 和 Poppler（推薦）

```bash
# 1. 安裝 Homebrew（如果還沒有）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. 安裝 Poppler
brew install poppler

# 3. 驗證安裝
which pdfinfo
pdfinfo -v
```

### 方案 2: 使用預編譯的 Poppler 二進制檔案

**macOS (Apple Silicon/M1/M2/M3):**

```bash
# 下載預編譯版本
curl -L https://github.com/oschwartz10612/poppler-windows/releases/download/v23.08.0-0/Release-23.08.0-0.zip -o /tmp/poppler.zip

# 解壓縮
unzip /tmp/poppler.zip -d /tmp/poppler

# 將二進制文件移動到 PATH
sudo cp /tmp/poppler/Library/bin/* /usr/local/bin/

# 驗證
which pdfinfo
```

### 方案 3: 使用 MacPorts

```bash
# 安裝 MacPorts（如果還沒有）
# 從 https://www.macports.org/install.php 下載安裝程式

# 安裝 Poppler
sudo port install poppler

# 驗證
which pdfinfo
```

### 方案 4: 從源碼編譯（高級用戶）

```bash
# 下載源碼
curl -L https://poppler.freedesktop.org/poppler-23.08.0.tar.xz -o /tmp/poppler.tar.xz
tar -xf /tmp/poppler.tar.xz -C /tmp

# 編譯安裝（需要先安裝 cmake）
cd /tmp/poppler-23.08.0
mkdir build && cd build
cmake ..
make
sudo make install
```

---

## ✅ 驗證安裝

安裝完成後，執行以下命令驗證：

```bash
# 檢查 pdfinfo
which pdfinfo
# 應該顯示: /usr/local/bin/pdfinfo 或類似路徑

# 檢查版本
pdfinfo -v
# 應該顯示版本信息

# 檢查其他 poppler 工具
which pdftoppm
which pdfimages
```

---

## 🔄 重新處理您的簡報

### 選項 A: 通過前端重新上傳

1. 訪問 http://localhost:5173
2. 重新上傳您的 PPTX 文件（計價方案比較.pptx）
3. 等待處理完成

### 選項 B: 手動觸發重新處理

```bash
# 啟動 Python shell
cd /Users/cfh00914977/Project/SlideCue/backend
source venv/bin/activate
python

# 在 Python shell 中執行：
from app.workers.file_conversion_worker import convert_pptx_to_pdf
convert_pptx_to_pdf.delay(
    'deck_2730ee69fe11',
    'http://localhost:9000/slidecue-uploads/decks/deck_2730ee69fe11/source/20260525_070718.pptx'
)
```

### 選項 C: 使用 API 觸發

```bash
# 如果有重新處理的 API endpoint
curl -X POST http://localhost:8001/api/decks/deck_2730ee69fe11/reprocess
```

---

## 📊 監控處理進度

### 1. 檢查 Deck 狀態

```bash
# 持續檢查狀態
watch -n 2 "curl -s http://localhost:8001/api/decks/deck_2730ee69fe11 | jq '.status'"
```

### 2. 查看 Celery Worker 日誌

```bash
tail -f /tmp/celery_worker.log
```

### 3. 前端自動輪詢

前端會自動每 3 秒檢查一次狀態，處理完成後會自動進入編輯模式。

---

## 📝 預期的狀態流程

```
uploaded (已上傳)
    ↓
processing (處理中 - PPTX → PDF)
    ↓
converted (轉換完成 - 已有 PDF 和圖片)
    ↓
analyzing (分析中 - AI 生成 Topic Cards)
    ↓
analyzed (分析完成 - 可以開始編輯)
```

---

## 🐛 如果仍然失敗

### 檢查 Celery Worker 是否運行

```bash
ps aux | grep "celery.*worker" | grep -v grep
```

如果沒有運行，啟動它：

```bash
cd /Users/cfh00914977/Project/SlideCue/backend
source venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info
```

### 檢查其他依賴

```bash
# 檢查 LibreOffice（用於 PPTX → PDF）
ls /Applications/LibreOffice.app/Contents/MacOS/soffice

# 檢查 Python 包
cd /Users/cfh00914977/Project/SlideCue/backend
source venv/bin/activate
python -c "import pdf2image; print('pdf2image OK')"
python -c "from pptx import Presentation; print('python-pptx OK')"
```

---

## 🎯 快速解決方案（推薦）

**最簡單的方式：**

```bash
# 1. 開啟終端
open -a Terminal

# 2. 複製貼上並執行以下命令（一行一行執行）

# 安裝 Homebrew（如果還沒有，可能需要 5-10 分鐘）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安裝 Poppler（1-2 分鐘）
brew install poppler

# 驗證安裝
pdfinfo -v

# 如果看到版本號（例如 poppler version 23.xx.x），就成功了！
```

然後重新上傳您的簡報文件。

---

## 📞 需要幫助？

如果安裝過程中遇到問題：

1. **檢查系統架構**
   ```bash
   uname -m
   # 顯示 arm64 = Apple Silicon (M1/M2/M3)
   # 顯示 x86_64 = Intel Mac
   ```

2. **檢查 macOS 版本**
   ```bash
   sw_vers
   ```

3. **查看完整錯誤日誌**
   ```bash
   cat /tmp/celery_worker.log | grep -A 50 "deck_2730ee69fe11"
   ```

---

## ✨ 安裝完成後

一旦 Poppler 安裝成功，您的 SlideCue 系統將能夠：

- ✅ 上傳 PPTX 文件
- ✅ 自動轉換為 PDF
- ✅ 提取每頁投影片為圖片
- ✅ 使用 AI 分析內容
- ✅ 生成 Topic Cards
- ✅ 進入演講模式
- ✅ 即時轉錄和主題匹配

祝安裝順利！🚀
