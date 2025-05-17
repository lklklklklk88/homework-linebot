import os
import json
import datetime
import tempfile

from flask import Flask, request, abort
from dotenv import load_dotenv

import firebase_admin
from firebase_admin import credentials, db  # db 有用到
from firebase_admin import initialize_app   # 你如果用 initialize_app() 就留

from linebot.v3.webhook import WebhookHandler, MessageEvent
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.messaging.models import TextMessage, ReplyMessageRequest
from linebot.exceptions import InvalidSignatureError
from linebot.v3.messaging.models import PushMessageRequest

app = Flask(__name__)

# 載入 .env 環境變數
load_dotenv()

# LINE 設定（從 .env 讀取）
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
line_bot_api = MessagingApi(ApiClient(configuration))
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Firebase 初始化
cred_json = os.getenv("GOOGLE_CREDENTIALS")
if not cred_json:
    raise Exception("GOOGLE_CREDENTIALS 環境變數未設定")

cred_dict = json.loads(cred_json)
cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")  # 修正換行

with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".json") as temp:
    json.dump(cred_dict, temp)
    temp.flush()
    cred = credentials.Certificate(temp.name)

firebase_admin.initialize_app(cred, {
    'databaseURL': os.getenv("FIREBASE_DB_URL")
})


# 從 Firebase 載入作業資料
def load_data(user_id):
    ref = db.reference(f"users/{user_id}/tasks")
    data = ref.get()
    return data if data else []

# 將資料存回 Firebase
def save_data(data, user_id):
    ref = db.reference(f"users/{user_id}/tasks")
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

@app.route("/remind", methods=["GET"])
def remind():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))  # 台灣時區
    current_time_str = now.strftime("%H:%M")

    users = db.reference("users").get()
    for user_id, user_data in users.items():
        tasks = user_data.get("tasks", [])
        remind_time = user_data.get("remind_time", "08:00")
        try:
            # 將提醒時間字串轉成時間物件
            remind_dt = datetime.datetime.strptime(remind_time, "%H:%M")
            remind_datetime = now.replace(hour=remind_dt.hour, minute=remind_dt.minute, second=0, microsecond=0)

            # 若提醒時間晚於現在，就跳過
            if now < remind_datetime:
                continue

            # 若提醒時間比現在早超過 5 分鐘，也跳過
            if (now - remind_datetime).total_seconds() > 300:
                continue

        except Exception as e:
            print(f"[remind] 使用者 {user_id} 的提醒時間格式錯誤：{remind_time}")
            continue


        message = "📋 以下是你尚未完成的作業：\n"
        has_task = False
        for task in tasks:
            if not task.get("done", False) and not task.get("reminded", False):
                has_task = True
                due_str = task.get("due", "")
                highlight = ""

                # 判斷是否為今天或明天到期
                try:
                    due_date = datetime.datetime.strptime(due_str, "%Y-%m-%d").date()
                    if due_date == now.date():
                        highlight = "（🔥 今天到期）"
                    elif due_date == now.date() + datetime.timedelta(days=1):
                        highlight = "（⚠️ 明天到期）"
                except:
                    pass

                message += f"🔸 {task['task']} {highlight}\n"

        if has_task:
            try:
                line_bot_api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[TextMessage(text=message)]
                    )
                )
                print(f"[remind] 已推送提醒給 {user_id}")
                save_data(tasks, user_id)
            except Exception as e:
                print(f"[remind] 推送失敗給 {user_id}：{e}")
    return "OK"


@handler.add(MessageEvent)
def handle_message(event):
    user_id = event.source.user_id

    if event.message.type != 'text':
        return

    text = event.message.text.strip()
    data = load_data(user_id)

    if text.startswith("新增作業"):
        content = text.replace("新增作業", "").strip()
        parts = content.rsplit(" ", 1)  # 嘗試把最後一個當作日期處理
        if len(parts) == 2:
            task, due = parts
        else:
            task = parts[0]
            due = "未設定"
        data.append({"task": task.strip(), "due": due.strip(), "done": False})
        save_data(data, user_id)
        reply = f"已新增作業：{task.strip()}（截止日：{due.strip()})"


    elif text.startswith("完成作業"):
        try:
            index = int(text.replace("完成作業", "").strip()) - 1
            if 0 <= index < len(data):
                removed_task = data.pop(index)  # ✅ 刪除指定作業
                save_data(data, user_id)
                reply = f"已完成作業：{removed_task['task']}"
            else:
                reply = "作業編號無效。請輸入正確的編號。"
        except ValueError:
            reply = "請輸入正確格式，例如：完成作業 2"


    elif text == "查看作業":
        if data:
            reply = "📋 你的作業清單：\n"
            for i, task in enumerate(data):
                status = "✅" if task["done"] else "🔲"
                due = task.get("due", "未設定")
                reply += f"{i+1}. {status} {task['task']}({due})\n"
        else:
            reply = "目前沒有任何作業。"

    elif text.startswith("提醒時間"):
        time_str = text.replace("提醒時間", "").strip()
        try:
            datetime.datetime.strptime(time_str, "%H:%M")
            db.reference(f"users/{user_id}/remind_time").set(time_str)
            reply = f"提醒時間已設定為：{time_str}"
        except ValueError:
            reply = "請輸入正確格式，例如：提醒時間 08:30"

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
