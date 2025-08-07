# 智慧作業管理 LINE Bot (homework-linebot)

這是一個基於 **LINE Messaging API**、**Google Gemini AI** 與 **Firebase Realtime Database** 的智慧作業管理機器人。它不僅能幫助使用者記錄、追蹤作業，更能透過 AI 理解自然語言，並自動產生最佳化的學習排程。

此專案部署於 **Render** 平台，並透過排程服務實現每日自動提醒。

---

## 🚀 核心功能

### 🧠 AI 智慧核心
*   **自然語言處理 (NLP)**: 使用 Google Gemini AI 分析使用者輸入的文字，自動判斷其意圖（新增作業、完成作業、查詢等）。
*   **智慧資訊擷取**: 自動從句子中擷取作業的關鍵資訊，例如：「下週一要交作業系統，大概要寫三小時」 -> `{作業名稱: "作業系統", 截止日期: "下週一", 預估時間: 3}`。
*   **智慧排程 (AI Scheduler)**: 根據使用者的待辦事項、緊急程度、預估時間與可用時間，動態生成每日最佳化的學習排程。
*   **個人化習慣分析**: 記錄並分析使用者常做的作業類型與花費時間，在新增作業時提供個人化的快速選項。

### ✅ 作業管理
*   **新增作業**: 支援「引導式流程」與「自然語言」兩種新增方式。
*   **完成作業**: 支援「單一完成」、「批次完成」與「自然語言」三種方式。
*   **查看作業**: 使用精美的 Flex Message 表格呈現所有作業，並根據狀態（已完成、待完成、已過期）使用不同顏色與圖示標記。
*   **清除作業**: 提供多種清除選項，可批次選擇、一鍵清除已完成或一鍵清除已過期項目。
*   **歷史紀錄**: 自動儲存常輸入的作業名稱、類型、時間，加速新增流程。

### ⏰ 智慧提醒系統
*   **每日未完成作業提醒**: 每日定時推播尚 未完成的作業列表。
*   **每日新增作業提醒**: 每日定時提醒使用者記得記錄當天的作業。
*   **自訂提醒時間**: 使用者可自行設定兩種提醒的每日推播時間。
*   **智慧狀態重設**: 當使用者修改提醒時間後，系統會自動重置當日的提醒狀態，確保新的設定能即時生效。

### ✨ 豐富的互動介面 (Flex Message)
*   **動態卡片**: 所有核心功能皆採用 LINE Flex Message 打造豐富的互動介面，包含按鈕、日期選擇器、表格、統計圖表等。
*   **流程引導**: 透過清晰的介面引導使用者完成每一步操作，降低學習成本。
*   **視覺化排程**: 將 AI 生成的排程以美觀的時間軸 (Timeline) 方式呈現，一目了然。

---

## 🛠️ 專案結構

本專案採用模組化的方式設計，各檔案職責分明：

| 檔案 | 功能描述 |
| :--- | :--- |
| `app.py` | **主應用程式 (Flask)**。負責接收 LINE Webhook、處理 HTTP 請求、並作為排程任務的進入點。 |
| `line_message_handler.py`| **訊息處理核心**。接收文字訊息，調用 `intent_utils` 判斷意圖，並分派給對應的處理函式。 |
| `postback_handler.py` | **按鈕回傳處理核心**。處理所有 Flex Message 按鈕的 `postback` 事件。 |
| `add_task_flow_manager.py`| **新增作業流程管理器**。封裝了從開始到結束所有新增作業的步驟與狀態。 |
| `complete_task_flow_manager.py`| **完成作業流程管理器**。封裝了單一與批次完成作業的所有流程。 |
| `intent_utils.py` | **AI 意圖判斷工具**。串接 Gemini API，負責解析自然語言的意圖與實體。 |
| `scheduler.py` | **AI 排程生成工具**。根據任務與時間，產生給 Gemini 的詳細 `prompt` 以生成排程。 |
| `flex_utils.py` | **Flex Message 產生器**。所有美觀的 Flex Message 卡片都在此定義。 |
| `firebase_utils.py` | **Firebase 資料庫工具**。封裝所有對 Firebase RTDB 的讀寫操作。 |
| `gemini_client.py` | **Gemini API 客戶端**。負責與 Google Gemini API 進行通訊。 |
| `line_utils.py` | **LINE API 工具**。提供獲取使用者名稱等輔助功能。 |

---

## ⚙️ 環境變數設定 (`.env`)

在專案根目錄建立 `.env` 檔案，並設定以下變數：

*   `LINE_CHANNEL_ACCESS_TOKEN`: LINE Bot 的 Channel Access Token。
*   `LINE_CHANNEL_SECRET`: LINE Bot 的 Channel Secret。
*   `GEMINI_API_KEY`: Google Gemini 的 API 金鑰。
*   `GOOGLE_CREDENTIALS`: Firebase Admin SDK 的服務帳戶金鑰 (建議將 JSON 內容轉為單行字串)。
*   `FIREBASE_DB_URL`: Firebase Realtime Database 的網址。

---

## 🚀 本地端快速啟動

```bash
# 1. 安裝依賴套件
pip install -r requirements.txt

# 2. 啟動 Flask 伺服器
python app.py
```

您需要搭配 `ngrok` 等內網穿透工具，將本地的 `http://127.0.0.1:5000/callback` 網址設定到 LINE Developer 的 Webhook URL，才能在本地進行測試。

---

## 🌐 Render 部署說明

1.  在 Render 建立一個新的 **Web Service**，並連結到您的 GitHub Repo。
2.  **Environment** 設定頁面，將 `.env` 中的所有環境變數一一填入。
3.  Render 會自動偵測 `render.yaml` 與 `Procfile`，並根據 `requirements.txt` 安裝依賴後啟動服務。
4.  **排程提醒**：
    *   在 Render 新增一個 **Cron Job**。
    *   **Command** 設定為：`curl -s YOUR_WEB_SERVICE_URL/remind` (請替換成您的服務網址)。
    *   **Schedule** 設定為您希望的執行時間 (例如：`0 0 * * *` 表示每天午夜執行)。
    *   **穩定性輔助**: 為了防止 Render 的免費 Web Service 因長時間無活動而休眠，建議使用 [UptimeRobot](https://uptimerobot.com/) 等外部服務，設定一個 HTTP(s) 監控，每 20-30 分鐘 ping 一次您的服務首頁 (`YOUR_WEB_SERVICE_URL`)。這不僅可以觸發排程，也能確保您的 Bot 隨時在線。

---

## 🔒 資安說明

*   **金鑰不入庫**: `firebase_utils.py` 採用了安全的金鑰處理方式。它會從環境變數讀取 JSON 字串，並在執行時動態生成一個暫時的憑證檔案。此暫存檔會在程式結束時自動刪除，確保金鑰本身不會被寫入到專案目錄或版本控制中。
*   **`.gitignore`**: 專案已設定好 `.gitignore`，會自動忽略 `.env` 檔案與 Python 的快取檔案。

---

## 👥 多使用者資料隔離

系統透過 LINE User ID 來區分不同的使用者，所有資料（作業、設定、歷史紀錄）都儲存在各自獨立的路徑下，確保資料的隱私與安全。

**資料庫結構範例:**
```json
{
  "users": {
    "Uxxxxxxxxxxxxxxxxx1": {
      "tasks": [...],
      "state": "awaiting_task_name",
      "task_history": {...},
      "remind_time": "08:00"
    },
    "Uxxxxxxxxxxxxxxxxx2": {
      "tasks": [...],
      ...
    }
  }
}
```

---
MIT License.
