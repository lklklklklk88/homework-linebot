import os
import datetime
from flask import Flask, request, abort
from dotenv import load_dotenv

from firebase_utils import (
    load_data, save_data,
    get_add_task_remind_enabled,
    get_add_task_remind_time,
    save_add_task_remind_enabled,
    save_add_task_remind_time,
    get_remind_time
)
# LINE SDK
from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.messaging.models import PushMessageRequest,FlexMessage, FlexContainer
from linebot.exceptions import InvalidSignatureError

# 初始化 app
from postback_handler import register_postback_handlers
from line_message_handler import register_message_handlers
from firebase_admin import db

app = Flask(__name__)

# 載入 .env 環境變數
load_dotenv()

# LINE 設定（從 .env 讀取）
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
line_bot_api = MessagingApi(ApiClient(configuration))
handler = WebhookHandler(LINE_CHANNEL_SECRET)
register_message_handlers(handler)
register_postback_handlers(handler)

def get_line_display_name(user_id):
    with ApiClient(configuration) as api_client:
        profile = MessagingApi(api_client).get_profile(user_id)
        return profile.display_name

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

def time_should_remind(remind_time, now):
    """判斷提醒時間是否應該觸發（只要現在 >= 設定時間）"""
    try:
        remind_dt = datetime.datetime.strptime(remind_time, "%H:%M").replace(
            year=now.year, month=now.month, day=now.day, tzinfo=now.tzinfo)
        return now >= remind_dt
    except Exception as e:
        print(f"【DEBUG】解析提醒時間錯誤：{remind_time}, {e}")
        return False

@app.route("/remind", methods=["GET"])
def remind():
    try:
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
        current_time_str = now.strftime("%H:%M")
        today_str = now.strftime("%Y-%m-%d")

        users = db.reference("users").get()
        if not users:
            print("[remind] 沒有用戶")
            return "OK - No users"
        
        processed_count = 0
        
        for user_id, user_data in users.items():
            # if processed_count >= MAX_USERS_PER_RUN:
            #     break

            try:
                if not isinstance(user_data, dict):
                    continue

                # 檢查新增作業提醒
                add_task_remind_enabled = get_add_task_remind_enabled(user_id)
                add_task_remind_time = get_add_task_remind_time(user_id)
                last_add_task_remind_date = user_data.get("last_add_task_remind_date", "")
                last_add_task_date = user_data.get("last_add_task_date", "")

                print(f"[remind][add_task] user={user_id}, enabled={add_task_remind_enabled}, remind_time={add_task_remind_time}, now={current_time_str}, last_remind={last_add_task_remind_date}, last_add={last_add_task_date}, today={today_str}")

                if add_task_remind_enabled and time_should_remind(add_task_remind_time, now):
                    if last_add_task_remind_date != today_str:
                        if last_add_task_date != today_str:
                            # 今天還沒新增作業，發送提醒
                            send_add_task_reminder(user_id)
                            db.reference(f"users/{user_id}/last_add_task_remind_date").set(today_str)
                            print(f"[remind][add_task] 推播新增作業提醒給 {user_id}")

                # 檢查未完成作業提醒
                remind_time = get_remind_time(user_id)
                last_task_remind_date = user_data.get("last_task_remind_date", "")
                tasks = user_data.get("tasks", [])
                print(f"[remind][task] user={user_id}, remind_time={remind_time}, now={current_time_str}, last_remind={last_task_remind_date}, today={today_str}")

                if time_should_remind(remind_time, now) and last_task_remind_date != today_str:
                    # 是否有未完成作業
                    rows = []
                    has_task = False
                    for i, task in enumerate(tasks):
                        if not task.get("done", False):
                            has_task = True
                            due = task.get("due", "未設定")
                            label = ""
                            if due != "未設定":
                                try:
                                    due_date = datetime.datetime.strptime(due, "%Y-%m-%d").date()
                                    if due_date == now.date():
                                        label = "\n(🔥今天到期)"
                                    elif due_date == now.date() + datetime.timedelta(days=1):
                                        label = "\n(⚠️明天到期)"
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
                        display_name = get_line_display_name(user_id)
                        bubble = {
                            "type": "bubble",
                            "body": {
                                "type": "box",
                                "layout": "vertical",
                                "spacing": "sm",
                                "contents": [
                                    {"type": "text", "text": f"👤 {display_name}，以下是你尚未完成的作業：", "weight": "bold", "size": "md"},
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
                            db.reference(f"users/{user_id}/last_task_remind_date").set(today_str)
                            print(f"[remind][task] 推播未完成作業提醒給 {user_id}")
                        except Exception as e:
                            print(f"[remind][task] 推播失敗 {user_id}：{e}")

                processed_count += 1

            except Exception as e:
                print(f"[remind] 處理用戶 {user_id} 時發生錯誤：{e}")
                continue

    except Exception as e:
        print(f"[remind] 整體錯誤：{e}")

    return "OK"

def send_add_task_reminder(user_id):
    """發送新增作業提醒"""
    try:
        display_name = get_line_display_name(user_id)
        
        bubble = {
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "📝 作業提醒",
                        "color": "#FFFFFF",
                        "size": "lg",
                        "weight": "bold"
                    }
                ],
                "backgroundColor": "#4A90E2",
                "paddingAll": "15px"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": f"Hi {display_name}! 👋",
                        "size": "md",
                        "weight": "bold"
                    },
                    {
                        "type": "text",
                        "text": "今天還沒有新增作業喔！",
                        "size": "sm",
                        "color": "#666666",
                        "wrap": True
                    },
                    {
                        "type": "text",
                        "text": "記得把今天的作業記錄下來，這樣才不會忘記 😊",
                        "size": "sm",
                        "color": "#666666",
                        "wrap": True,
                        "margin": "sm"
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "➕ 立即新增作業",
                            "data": "add_task"
                        },
                        "style": "primary",
                        "color": "#4A90E2"
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "⏰ 調整提醒設定",
                            "data": "set_remind_time"
                        },
                        "style": "secondary"
                    }
                ]
            }
        }
        
        line_bot_api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=[FlexMessage(
                    alt_text="今天還沒有新增作業喔！",
                    contents=FlexContainer.from_dict(bubble)
                )]
            )
        )
        print(f"[remind] 已發送新增作業提醒給 {user_id}")
        
    except Exception as e:
        print(f"[remind] 發送新增作業提醒失敗：{e}")

if __name__ == "__main__":
    app.run()
