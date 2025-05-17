# homework-linebot

一個使用 LINE Messaging API 與 Firebase Realtime Database 製作的作業提醒小幫手 Bot，部署於 Render 平台。

---

## 📦 功能簡介

* ✅ 新增作業
* ✅ 查看作業
* ✅ 完成作業（完成後會自動重新編號）
* ✅ 多使用者作業清單（每位 LINE 使用者有自己專屬清單）
* ✅ 作業資料儲存於 Firebase RTDB
* ✅ 使用 `.env` 管理憑證與金鑰，安全又可部署

---

## 🧠 新增互動式功能

* ✅ Flex Message「新增作業」按鈕支援
* ✅ 使用者先輸入作業名稱，再選擇截止日
* ✅ 日期選擇使用 LINE datetime picker
* ✅ 暫存輸入資料至 Firebase `/users/{userId}/session`

---
## ⚙️ 環境變數設定（`.env`）

請參考 `.env.example`，需要設定以下變數：

* `LINE_CHANNEL_ACCESS_TOKEN`
* `LINE_CHANNEL_SECRET`
* `GOOGLE_CREDENTIALS`：建議將整份 Firebase Admin 金鑰轉為一行 JSON 並escape `\n` 為 `\\n`
* `FIREBASE_DB_URL`：請填入對應地區的 Firebase Realtime Database 網址，例如：[https://your-project-id-default-rtdb.asia-southeast1.firebasedatabase.app](https://your-project-id-default-rtdb.asia-southeast1.firebasedatabase.app)

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
點擊「新增作業」按鈕 ➜ 輸入作業名稱 ➜ 選擇截止日期
Bot 將會幫你記錄下來 📅
```

也支援舊指令輸入：

```text
完成作業 2
查看作業
```

---

## 🌐 Render 部署

1. 建立新專案，連結 GitHub
2. 新增環境變數（與 .env 一致）
3. Render 會自動讀取 `render.yaml` + `Procfile` 部署應用程式

---

## 📄 資安說明

請**勿將完整 `.json` 金鑰檔加入 Git 版本控制**。本專案透過 `GOOGLE_CREDENTIALS` 字串方式管理憑證，避免金鑰外洩風險。

---

## 👥 多使用者資料分離

系統會根據 LINE 使用者 ID 自動將作業資料儲存至：

```
/users/<userId>/tasks
```

每位使用者的作業資料互不干擾，對話體驗更個人化。
