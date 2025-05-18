import os
import json
import datetime
import tempfile

from scheduler import generate_gemini_prompt
from flask import Flask, request, abort
from dotenv import load_dotenv

import firebase_admin
from firebase_admin import credentials, db  # db 有用到
from scheduler import generate_gemini_prompt
from gemini_client import call_gemini_schedule  # 新增

from linebot.v3.webhook import WebhookHandler, MessageEvent
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.messaging.models import TextMessage, ReplyMessageRequest
from linebot.exceptions import InvalidSignatureError
from linebot.v3.messaging.models import PushMessageRequest
from linebot.v3.messaging.models import FlexMessage, FlexContainer
from linebot.v3.webhooks import PostbackEvent

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

def get_today_schedule_for_user(user_id):
    tasks = load_data(user_id)

    # 測試先用固定偏好（之後可從 Firebase 抓）
    habits = {
        "prefered_morning": "閱讀、寫作",
        "prefered_afternoon": "計算、邏輯"
    }

    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")
    available_hours = 5

    prompt = generate_gemini_prompt(user_id, tasks, habits, today, available_hours)
    result = call_gemini_schedule(prompt)
    return result

# 將資料存回 Firebase
def save_data(data, user_id):
    ref = db.reference(f"users/{user_id}/tasks")
    ref.set(data)
def set_user_state(user_id, state):
    db.reference(f"users/{user_id}/state").set(state)

def get_user_state(user_id):
    return db.reference(f"users/{user_id}/state").get()

def clear_user_state(user_id):
    db.reference(f"users/{user_id}/state").delete()

def set_temp_task(user_id, task):
    db.reference(f"users/{user_id}/temp_task").set(task)

def get_temp_task(user_id):
    return db.reference(f"users/{user_id}/temp_task").get() or {}

def clear_temp_task(user_id):
    db.reference(f"users/{user_id}/temp_task").delete()

#   這段用來Debug Gemini的
#  
# @app.route("/generate_schedule", methods=["GET"])
# def generate_schedule():
#     user_id = "test123"  # 測試用固定 ID，你之後可改為 LINE 使用者 ID
#     tasks = load_data(user_id)

#     # 模擬習慣資料（未來可存進 Firebase）
#     habits = {
#         "prefered_morning": "閱讀、寫作",
#         "prefered_afternoon": "計算、邏輯"
#     }

#     today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")
#     available_hours = 5

#     prompt = generate_gemini_prompt(user_id, tasks, habits, today, available_hours)
#     return prompt



# @app.route("/generate_schedule_with_ai", methods=["GET"])
# def generate_schedule_with_ai():
#     user_id = "test123"
#     tasks = load_data(user_id)

#     habits = {
#         "prefered_morning": "閱讀、寫作",
#         "prefered_afternoon": "計算、邏輯"
#     }

#     today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")
#     available_hours = 5

#     prompt = generate_gemini_prompt(user_id, tasks, habits, today, available_hours)
#     result = call_gemini_schedule(prompt)

#     return result

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

        # 每天只重置一次提醒狀態
        last_reset_date = user_data.get("last_reset_date")
        today_str = now.strftime("%Y-%m-%d")

        if last_reset_date != today_str:
            for task in tasks:
                task["reminded"] = False
            user_data["last_reset_date"] = today_str
            db.reference(f"users/{user_id}").set(user_data)

        try:
            remind_dt = datetime.datetime.strptime(remind_time, "%H:%M")
            remind_datetime = now.replace(hour=remind_dt.hour, minute=remind_dt.minute, second=0, microsecond=0)

            time_diff = (now - remind_datetime).total_seconds()
            if time_diff < 0 or time_diff > 600:
                continue

        except Exception as e:
            print(f"[remind] 使用者 {user_id} 的提醒時間格式錯誤：{remind_time}")
            continue

        rows = []
        has_task = False
        for i, task in enumerate(tasks):
            if not task.get("done", False) and not task.get("reminded", False):
                has_task = True
                due = task.get("due", "未設定")
                label = ""

                if due != "未設定":
                    try:
                        due_date = datetime.datetime.strptime(due, "%Y-%m-%d").date()
                        if due_date == now.date():
                            label = "\n（🔥 今天到期）"
                        elif due_date == now.date() + datetime.timedelta(days=1):
                            label = "\n（⚠️ 明天到期）"
                    except:
                        pass

                rows.append({
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": f"{i+1}.", "size": "sm", "flex": 1},
                        {"type": "text", "text": f"🔲 {task['task']}", "size": "sm", "flex": 6, "wrap": True, "maxLines": 3},
                        {"type": "text", "text": f"{due}{label}", "size": "sm", "flex": 5, "wrap": True}
                    ]
                })

        if has_task:
            bubble = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {"type": "text", "text": "📋 以下是你尚未完成的作業：", "weight": "bold", "size": "md"},
                        {"type": "separator"},
                        *rows
                    ]
                }
            }

            try:
                line_bot_api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[FlexMessage(
                            alt_text="提醒作業清單",
                            contents=FlexContainer.from_dict(bubble)
                        )]
                    )
                )
                print(f"[remind] 已推送提醒給 {user_id}")

                for task in tasks:
                    if not task.get("done", False) and not task.get("reminded", False):
                        task["reminded"] = True

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

    if text == "新增作業":
        set_user_state(user_id, "awaiting_task_name")
        reply = "請輸入作業名稱："

    elif get_user_state(user_id) == "awaiting_task_name":
        task_name = text
        set_temp_task(user_id, {"task": task_name})
        set_user_state(user_id, "awaiting_due_date")

        bubble = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {"type": "text", "text": f"作業名稱：{task_name}", "weight": "bold", "size": "md"},
                    {"type": "text", "text": "請選擇截止日期：", "size": "sm", "color": "#888888"},
                    {
                        "type": "button",
                        "action": {
                            "type": "datetimepicker",
                            "label": "📅 選擇日期",
                            "data": "select_due_date",
                            "mode": "date"
                        },
                        "style": "primary"
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "🚫 不設定截止日",
                            "data": "no_due_date"
                        },
                        "style": "secondary"
                    }
                ]
            }
        }

        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(
                        alt_text="選擇截止日期",
                        contents=FlexContainer.from_dict(bubble)
                    )]
                )
            )
        return
    elif get_user_state(user_id) == "awaiting_estimated_time":
        try:
            estimated_time = float(text)
            if estimated_time <= 0:
                raise ValueError
            task = get_temp_task(user_id)
            task["estimated_time"] = estimated_time
            set_temp_task(user_id, task)
            set_user_state(user_id, "awaiting_category")

            bubble = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "md",
                    "contents": [
                        {"type": "text", "text": "請選擇作業類型：", "weight": "bold", "size": "md"},
                        {
                            "type": "button",
                            "action": {"type": "postback", "label": "📖 閱讀", "data": "category_閱讀"},
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "action": {"type": "postback", "label": "📐 計算", "data": "category_計算"},
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "action": {"type": "postback", "label": "📝 寫作", "data": "category_寫作"},
                            "style": "primary"
                        }
                    ]
                }
            }

            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[FlexMessage(
                            alt_text="選擇作業類型",
                            contents=FlexContainer.from_dict(bubble)
                        )]
                    )
                )
            return
        except:
            reply = "⚠️ 請輸入有效的時間（以小時為單位，例如 1.5）"
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply)]
                    )
                )
            return

    elif data.startswith("category_"):
        category = data.replace("category_", "")
        task = get_temp_task(user_id)
        task["category"] = category
        set_temp_task(user_id, task)
        set_user_state(user_id, "awaiting_due_date")

        bubble = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {"type": "text", "text": f"作業名稱：{task['task']}", "weight": "bold", "size": "md"},
                    {"type": "text", "text": "請選擇截止日期：", "size": "sm", "color": "#888888"},
                    {
                        "type": "button",
                        "action": {
                            "type": "datetimepicker",
                            "label": "📅 選擇日期",
                            "data": "select_due_date",
                            "mode": "date"
                        },
                        "style": "primary"
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "🚫 不設定截止日",
                            "data": "no_due_date"
                        },
                        "style": "secondary"
                    }
                ]
            }
        }

        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(
                        alt_text="選擇截止日期",
                        contents=FlexContainer.from_dict(bubble)
                    )]
                )
            )
        return

    elif text == "完成作業":
        if not data:
            reply = "目前沒有任何作業可完成。"
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply)]
                    )
                )
            return

        buttons = []
        for i, task in enumerate(data):
            if not task.get("done", False):
                buttons.append({
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": f"✅ {task['task']}",
                        "data": f"complete_task_{i}"
                    },
                    "style": "secondary"  # ← 原本是 primary，改為 secondary（灰色）
                })

        bubble = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {"type": "text", "text": "選擇要完成的作業", "weight": "bold", "size": "lg"},
                    *buttons
                ]
            }
        }

        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(
                        alt_text="選擇要完成的作業",
                        contents=FlexContainer.from_dict(bubble)
                    )]
                )
            )
        return
    
    elif text == "今日排程":
        schedule = get_today_schedule_for_user(user_id)
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=schedule)]
                )
            )
        return

    elif text == "提醒時間":
        # 取得目前使用者的提醒時間，預設為 08:00
        current_time = db.reference(f"users/{user_id}/remind_time").get() or "08:00"

        bubble = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": f"目前提醒時間：{current_time}",
                        "weight": "bold",
                        "size": "md"
                    },
                    {
                        "type": "text",
                        "text": "請選擇新的提醒時間：",
                        "size": "sm",
                        "color": "#888888"
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "datetimepicker",
                            "label": "⏰ 選擇時間",
                            "data": "select_remind_time",
                            "mode": "time",
                            "initial": current_time,
                            "max": "23:59",
                            "min": "00:00"
                        },
                        "style": "primary"
                    }
                ]
            }
        }

        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(
                        alt_text="設定提醒時間",
                        contents=FlexContainer.from_dict(bubble)
                    )]
                )
            )
        return

    elif text == "查看作業":
        if not data:
            reply = "目前沒有任何作業。"
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply)]
                    )
                )
            return

        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()
        rows = []

        for i, task in enumerate(data):
            done = task.get("done", False)
            due = task.get("due", "未設定")
            symbol = "✅" if done else "🔲"
            label = ""

            if not done and due != "未設定":
                try:
                    due_date = datetime.datetime.strptime(due, "%Y-%m-%d").date()
                    if due_date < now:
                        symbol = "❌"
                    elif due_date == now:
                        label = "\n（🔥 今天到期）"
                    elif due_date == now + datetime.timedelta(days=1):
                        label = "\n（⚠️ 明天到期）"
                except:
                    pass

            rows.append({
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {"type": "text", "text": f"{i+1}.", "size": "sm", "flex": 1},
                    {"type": "text", "text": f"{symbol} {task['task']}", "size": "sm", "flex": 6, "wrap": True, "maxLines": 3},
                    {"type": "text", "text": f"{due}{label}", "size": "sm", "flex": 5, "wrap": True}
                ]
            })

        bubble = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {"type": "text", "text": "📋 你的作業清單：", "weight": "bold", "size": "md"},
                    {"type": "separator"},
                    *rows
                ]
            }
        }

        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(
                        alt_text="作業清單",
                        contents=FlexContainer.from_dict(bubble)
                    )]
                )
            )
        return

    elif text == "清除已完成作業":
        completed_tasks = [task for task in data if task.get("done", False)]
        if not completed_tasks:
            reply = "✅ 沒有已完成的作業需要清除。"
        else:
            bubble = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "md",
                    "contents": [
                        {"type": "text", "text": "你想怎麼清除已完成作業？", "weight": "bold", "size": "md"},
                        {
                            "type": "button",
                            "action": {
                                "type": "postback",
                                "label": "📝 手動選擇清除",
                                "data": "clear_completed_select"
                            },
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "action": {
                                "type": "postback",
                                "label": "🧹 一鍵清除全部",
                                "data": "clear_completed_all"
                            },
                            "style": "primary",
                            "color": "#FF4444"  # 紅色
                        }
                    ]
                }
            }
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[FlexMessage(
                            alt_text="清除已完成作業",
                            contents=FlexContainer.from_dict(bubble)
                            )]
                        )
                    )
            return

    elif text == "清除已截止作業":
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()
        expired_tasks = []
        for i, task in enumerate(data):
            due = task.get("due", "未設定")
            done = task.get("done", False)
            if not done and due != "未設定":
                try:
                    due_date = datetime.datetime.strptime(due, "%Y-%m-%d").date()
                    if due_date < now:
                        expired_tasks.append((i, task))
                except:
                    pass

        if not expired_tasks:
            reply = "✅ 沒有需要清除的已截止作業。"
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply)]
                    )
                )
            return

        bubble = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {"type": "text", "text": "你想怎麼清除已截止的作業？", "weight": "bold", "size": "md"},
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "📝 手動選擇清除",
                            "data": "clear_expired_select"
                        },
                        "style": "secondary"
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "🗑️ 一鍵清除全部",
                            "data": "clear_expired_all"
                        },
                        "style": "primary"
                    }
                ]
            }
        }
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(
                        alt_text="清除已截止作業",
                        contents=FlexContainer.from_dict(bubble)
                    )]
                )
            )
        return

    elif text == "選單":
        bubble = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {"type": "text", "text": "請選擇操作", "weight": "bold", "size": "lg"},
                    {
                        "type": "button",
                        "action": {"type": "message", "label": "➕ 新增作業", "text": "新增作業"},
                        "style": "primary"
                    },
                    {
                        "type": "button",
                        "action": {"type": "message", "label": "✅ 完成作業", "text": "完成作業"},
                        "style": "secondary"
                    },
                    {
                        "type": "button",
                        "action": {"type": "message", "label": "⏰ 提醒時間", "text": "提醒時間"},
                        "style": "secondary"
                    },
                    {
                        "type": "button",
                        "action": {"type": "message", "label": "📋 查看作業", "text": "查看作業"},
                        "style": "secondary"
                    },
                    {
                        "type": "button",
                        "action": {"type": "message", "label": "🧹 清除已完成作業", "text": "清除已完成作業"},
                        "style": "primary",
                        "color": "#FF3B30"  # ← 紅色
                    },
                    {
                        "type": "button",
                        "action": {"type": "message", "label": "🗑️ 清除已截止作業", "text": "清除已截止作業"},
                        "style": "primary",
                        "color": "#FF3B30"
                    }

                ]
            }
        }

        with ApiClient(configuration) as api_client:
            messaging_api = MessagingApi(api_client)
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        FlexMessage(
                            alt_text="選單",
                            contents=FlexContainer.from_dict(bubble)
                        )
                    ]
                )
            )
        return

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
    return

@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
    params = event.postback.params

    if data == "select_due_date":
        selected_date = params.get("date")
        task = get_temp_task(user_id)
        if task:
            task["due"] = selected_date
            task["done"] = False
            data_list = load_data(user_id)
            data_list.append(task)
            save_data(data_list, user_id)
            clear_user_state(user_id)
            clear_temp_task(user_id)
            message = f"✅ 已新增作業：{task['task']}（截止日：{selected_date}）"
        else:
            message = "⚠️ 找不到暫存作業，請重新新增。"

    elif data == "no_due_date":
        task = get_temp_task(user_id)
        if task:
            task["due"] = "未設定"
            task["done"] = False
            data_list = load_data(user_id)
            data_list.append(task)
            save_data(data_list, user_id)
            clear_user_state(user_id)
            clear_temp_task(user_id)
            message = f"✅ 已新增作業：{task['task']}（未設定截止日）"
        else:
            message = "⚠️ 找不到暫存作業，請重新新增。"
    
    elif data.startswith("complete_task_"):
        try:
            index = int(data.replace("complete_task_", ""))
            tasks = load_data(user_id)
            if 0 <= index < len(tasks):
                tasks[index]["done"] = True
                save_data(tasks, user_id)
                message = f"✅ 已完成作業：{tasks[index]['task']}"
            else:
                message = "⚠️ 無法找到指定作業。"
        except:
            message = "⚠️ 操作錯誤，請稍後再試。"

    elif data == "clear_completed_select":
        tasks = load_data(user_id)
        buttons = []
        for i, task in enumerate(tasks):
            if task.get("done", False):
                buttons.append({
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": f"🗑️ {task['task']}",
                        "data": f"delete_completed_{i}"
                    },
                    "style": "secondary"
                })
        if not buttons:
            message = "✅ 沒有可選擇的已完成作業。"
        else:
            bubble = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "md",
                    "contents": [
                        {"type": "text", "text": "選擇要清除的已完成作業", "weight": "bold", "size": "lg"},
                        *buttons
                    ]
                }
            }
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[FlexMessage(
                            alt_text="選擇要刪除的已完成作業",
                            contents=FlexContainer.from_dict(bubble)
                        )]
                    )
                )
            return

    elif data.startswith("delete_completed_"):
        index = int(data.replace("delete_completed_", ""))
        tasks = load_data(user_id)
        if 0 <= index < len(tasks) and tasks[index].get("done", False):
            task_name = tasks[index]["task"]
            del tasks[index]
            save_data(tasks, user_id)
            message = f"🧹 已刪除：{task_name}"
        else:
            message = "⚠️ 找不到可刪除的作業。"

    elif data == "clear_expired_select":
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()
        tasks = load_data(user_id)
        buttons = []
        for i, task in enumerate(tasks):
            due = task.get("due", "未設定")
            if task.get("done") or due == "未設定":
                continue
            try:
                if datetime.datetime.strptime(due, "%Y-%m-%d").date() < now:
                    buttons.append({
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": f"🗑️ {task['task']}",
                            "data": f"delete_expired_{i}"
                        },
                        "style": "secondary"
                    })
            except:
                continue
        if not buttons:
            message = "✅ 沒有可選擇的已截止作業。"
        else:
            bubble = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "md",
                    "contents": [
                        {"type": "text", "text": "選擇要清除的已截止作業", "weight": "bold", "size": "lg"},
                        *buttons
                    ]
                }
            }
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[FlexMessage(
                            alt_text="選擇要刪除的已截止作業",
                            contents=FlexContainer.from_dict(bubble)
                        )]
                    )
                )
            return

    elif data == "clear_completed_all":
        tasks = load_data(user_id)
        original_len = len(tasks)
        new_data = [task for task in tasks if not task.get("done", False)]
        removed = original_len - len(new_data)
        save_data(new_data, user_id)

        if removed > 0:
            message = f"🧹 已清除 {removed} 筆已完成的作業。"
        else:
            message = "✅ 沒有已完成的作業需要清除。"
        
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=message)]
                )
            )
        return

    elif data == "clear_expired_all":
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()
        tasks = load_data(user_id)
        original_len = len(tasks)
        new_data = []
        for task in tasks:
            due = task.get("due", "未設定")
            if task.get("done", False) or due == "未設定":
                new_data.append(task)
                continue
            try:
                if datetime.datetime.strptime(due, "%Y-%m-%d").date() >= now:
                    new_data.append(task)
            except:
                new_data.append(task)

        removed = original_len - len(new_data)
        save_data(new_data, user_id)

        if removed > 0:
            message = f"🗑️ 已清除 {removed} 筆已截止的作業。"
        else:
            message = "✅ 沒有需要清除的已截止作業。"
    
    elif data == "select_remind_time":
        selected_time = params.get("time")  # 格式為 HH:MM
        db.reference(f"users/{user_id}/remind_time").set(selected_time)

        # 清除所有作業的 reminded 標記
        tasks = load_data(user_id)
        for task in tasks:
            task["reminded"] = False
        save_data(tasks, user_id)

        message = f"⏰ 提醒時間已設定為：{selected_time}（提醒狀態已重置）"

    else:
        message = "⚠️ 無法識別的操作。"

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=message)]
            )
        )
    return

if __name__ == "__main__":
    app.run()
