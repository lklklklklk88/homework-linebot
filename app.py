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

@app.route("/remind", methods=["GET"])
def remind():
    try:
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
        current_time_str = now.strftime("%H:%M")

        users = db.reference("users").get()
        if not users:
            return "OK - No users"
        
        processed_count = 0
        MAX_USERS_PER_RUN = 50
        
        for user_id, user_data in users.items():
            if processed_count >= MAX_USERS_PER_RUN:
                break
                
            try:
                if not isinstance(user_data, dict):
                    continue
                    
                 # 檢查新增作業提醒
                add_task_remind_enabled = get_add_task_remind_enabled(user_id)
                add_task_remind_time = get_add_task_remind_time(user_id)
                
                if add_task_remind_enabled:
                    try:
                        add_remind_dt = datetime.datetime.strptime(add_task_remind_time, "%H:%M")
                        add_remind_datetime = now.replace(hour=add_remind_dt.hour, minute=add_remind_dt.minute, second=0, microsecond=0)
                        
                        time_diff = (now - add_remind_datetime).total_seconds()
                        if 0 <= time_diff <= 600:  # 10分鐘內
                            # 檢查今天是否已經有新增作業
                            tasks = user_data.get("tasks", [])
                            today_str = now.strftime("%Y-%m-%d")
                            
                            # 檢查最後新增作業日期
                            last_add_date = user_data.get("last_add_task_date", "")
                            
                            if last_add_date != today_str:
                                # 今天還沒新增作業，發送提醒
                                send_add_task_reminder(user_id)
                                
                    except Exception as e:
                        print(f"[remind] 處理新增作業提醒時發生錯誤：{e}")

                tasks = user_data.get("tasks", [])
                remind_time = user_data.get("remind_time", "08:00")
                
                # 每天只重置一次提醒狀態
                last_reset_date = user_data.get("last_reset_date")
                today_str = now.strftime("%Y-%m-%d")

                if last_reset_date != today_str:
                    for task in tasks:
                        task["reminded"] = False
                    user_data["last_reset_date"] = today_str
                    db.reference(f"users/{user_id}").update({
                        "tasks": tasks,
                        "last_reset_date": today_str
                    })

                # 檢查是否到提醒時間
                try:
                    remind_dt = datetime.datetime.strptime(remind_time, "%H:%M")
                    remind_datetime = now.replace(hour=remind_dt.hour, minute=remind_dt.minute, second=0, microsecond=0)

                    time_diff = (now - remind_datetime).total_seconds()
                    if time_diff < 0 or time_diff > 600:  # 10分鐘內
                        continue

                except Exception as e:
                    print(f"[remind] 使用者 {user_id} 的提醒時間格式錯誤：{remind_time}")
                    continue

                # 建立提醒內容
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
                        print(f"[remind] 已推送提醒給 {user_id}")

                        # 標記已提醒
                        for task in tasks:
                            if not task.get("done", False) and not task.get("reminded", False):
                                task["reminded"] = True

                        save_data(user_id, tasks)

                    except Exception as e:
                        print(f"[remind] 推送失敗給 {user_id}：{e}")
                
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
