from flask import Flask, request, abort
from linebot.v3.webhook import WebhookHandler, MessageEvent
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.messaging.models import TextMessage, ReplyMessageRequest
from linebot.exceptions import InvalidSignatureError

import firebase_admin
from firebase_admin import credentials, db
import os
from dotenv import load_dotenv

app = Flask(__name__)

# 載入 .env 環境變數
load_dotenv()

# LINE 設定（從 .env 讀取）
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Firebase 初始化
cred = credentials.Certificate("homework-linebot-firebase-adminsdk-fbsvc-a7cf0dc76e.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://homework-linebot-default-rtdb.firebaseio.com/'
})

# 從 Firebase 載入作業資料
def load_data():
    ref = db.reference("tasks")
    data = ref.get()
    return data if data else []

# 將資料存回 Firebase
def save_data(data):
    ref = db.reference("tasks")
    ref.set(data)

@app.route("/")
def home():
    return "Bot is running"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent)
def handle_message(event):
    if event.message.type != 'text':
        return

    text = event.message.text.strip()
    data = load_data()

    if text.startswith("新增作業"):
        task = text.replace("新增作業", "").strip()
        data.append({"task": task, "done": False})
        save_data(data)
        reply = f"已新增作業：{task}"

    elif text.startswith("完成作業"):
        try:
            index = int(text.replace("完成作業", "").strip()) - 1
            data[index]["done"] = True
            save_data(data)
            reply = f"已完成第 {index+1} 項作業：{data[index]['task']}"
        except:
            reply = "找不到該作業編號，請確認輸入格式。"

    elif text == "查看作業":
        undone = [f"{i+1}. {d['task']}" for i, d in enumerate(data) if not d["done"]]
        reply = "目前未完成作業：\n" + "\n".join(undone) if undone else "所有作業都完成了，太棒了！"

    else:
        reply = "請使用以下指令：\n1. 新增作業 作業內容\n2. 完成作業 編號\n3. 查看作業"

    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )

if __name__ == "__main__":
    app.run()
