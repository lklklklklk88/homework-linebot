# homework-linebot

一個使用 LINE Messaging API 與 Firebase Realtime Database 製作的作業提醒小幫手 Bot，部署於 Render 平台。

---

## 📦 功能簡介

- 新增作業
- 查看作業
- 完成作業
- 作業資料儲存於 Firebase RTDB
- 使用 `.env` 管理憑證與金鑰，安全又可部署

---

## ⚙️ 環境變數設定（`.env`）

請參考 `.env.example`，需要設定以下變數：

- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_CHANNEL_SECRET`
- `GOOGLE_CREDENTIALS`：建議將整份 Firebase Admin 金鑰轉為一行 JSON 並 escape `\n` 為 `\\n`
- `FIREBASE_DB_URL`：請填入對應地區的 Firebase Realtime Database 網址，例如：https://your-project-id-default-rtdb.asia-southeast1.firebasedatabase.app

---

## 🚀 快速啟動（本地端）

```bash
# 安裝套件
pip install -r requirements.txt

# 啟動伺服器
python app.py