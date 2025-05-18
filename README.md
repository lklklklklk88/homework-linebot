# homework-linebot

一個使用 LINE Messaging API 與 Firebase Realtime Database 製作的作業提醒小幫手 Bot，部署於 Render 平台。

---

## 📦 功能簡介

* ✅ 新增作業
* ✅ 查看作業（Flex 表格顯示）
* ✅ 完成作業（完成後自動重新編號）
* ✅ 多使用者作業清單（每位 LINE 使用者有自己專屬清單）
* ✅ 作業資料儲存於 Firebase RTDB
* ✅ 使用 `.env` 管理憑證與金鑰，安全又可部署
* ✅ 每日提醒未完成作業（含 Flex 表格提醒樣式）
* ✅ 支援提醒時間設定、自動重設提醒狀態
* ✅ 支援查看某天作業、今日到期、明日到期等排程提醒（擴充可自訂）

---

## 🧠 Flex Message 互動式功能

* ➕ **新增作業**：使用者輸入作業名稱後，選擇截止日期（datetime picker）
* 📋 **查看作業**：以表格方式顯示清單，支援過期 / 今天到期 / 明天到期 emoji 標記
* ✅ **完成作業**：點選待辦作業即可標記完成（支援 UI 操作）
* 🧹 **清除作業**：支援一鍵清除 / 手動選擇（已完成、已截止）
* ⏰ **提醒時間**：使用 datetime picker 設定每日推播提醒時間
* 🔔 **提醒推播**：每日自動發送 Flex Message 通知，僅推送未完成且尚未提醒者

---

## ⚙️ 環境變數設定（`.env`）

請參考 `.env.example`，需要設定以下變數：

* `LINE_CHANNEL_ACCESS_TOKEN`
* `LINE_CHANNEL_SECRET`
* `GOOGLE_CREDENTIALS`：建議將整份 Firebase Admin 金鑰轉為一行 JSON 並 escape `\n`
* `FIREBASE_DB_URL`：Firebase Realtime Database 網址

---

## 🚀 快速啟動（本地端）

```bash
# 安裝套件
pip install -r requirements.txt

# 啟動伺服器
python app.py
```

---

## 📬 LINE 操作方式（互動式）

```text
選單 ➜ 點「新增作業」 ➜ 輸入名稱 ➜ 選日期
Bot 會幫你記錄作業，並在到期日提醒你
```

也支援文字指令輸入：

```text
新增作業 數學作業
完成作業 2
查看作業
```

---

## 🌐 Render 部署

1. 建立新專案，連結 GitHub
2. 新增環境變數（與 .env 一致）
3. Render 會自動讀取 `render.yaml` + `Procfile` 部署應用程式
4. 建議搭配 UptimeRobot 固定喚醒 + ping `/remind` 執行推播

---

## 📄 資安說明

請**勿將完整 `.json` 金鑰檔加入 Git**。
本專案使用環境變數 `GOOGLE_CREDENTIALS` 傳入金鑰 JSON 字串，避免機敏資料外洩。

---

## 👥 多使用者資料分離設計

系統會根據 LINE 使用者 ID 自動將作業儲存於：

```
/users/<userId>/tasks
```

每位使用者的資料獨立，彼此不互相干擾，支援多用戶共用一個 Bot。

---

## 🔮 推薦進階延伸方向

* 🔍 加入「查詢某天作業」功能
* 📅 建立簡易「週計畫表」視覺（模擬日曆）
* 📊 統計本週完成率、剩餘項目、自動排序優先級
* 🧠 使用 GPT API 協助判斷作業優先順序（推薦可擴充）

---

MIT License. 作者：屎蛋