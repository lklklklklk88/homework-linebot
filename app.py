import os
import datetime
from flask import Flask, request, abort
from dotenv import load_dotenv

from firebase_utils import (
    load_data, save_data,
    get_add_task_remind_enabled,
    get_add_task_remind_time,
    get_task_remind_enabled,
    save_add_task_remind_enabled,
    save_add_task_remind_time,
    get_remind_time
)
# LINE SDK
from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.messaging.models import PushMessageRequest, FlexMessage, FlexContainer, TextMessage
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
        # 解析提醒時間
        remind_hour, remind_minute = map(int, remind_time.split(':'))
        
        # 獲取當前時間的小時和分鐘
        current_hour = now.hour
        current_minute = now.minute
        
        # 比較時間
        if current_hour > remind_hour:
            return True
        elif current_hour == remind_hour and current_minute >= remind_minute:
            return True
        else:
            return False
            
    except Exception as e:
        print(f"【DEBUG】解析提醒時間錯誤：{remind_time}, {e}")
        return False

def send_view_tasks_push(user_id):
    """推播作業列表 (Flex Message)"""
    tasks = load_data(user_id)
    if not tasks:
        return

    # 創建表格內容 (與 postback_handler.py 的 handle_view_tasks 相似)
    table_contents = [
        {"type": "text", "text": "📋 作業列表", "weight": "bold", "size": "xl", "color": "#1DB446"},
        {"type": "separator", "margin": "md"}
    ]

    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.get("done", False)])
    pending_tasks = total_tasks - completed_tasks

    stats_box = {
        "type": "box",
        "layout": "horizontal",
        "spacing": "md",
        "margin": "md",
        "contents": [
            {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": str(total_tasks), "size": "xl", "weight": "bold", "align": "center"},
                    {"type": "text", "text": "總計", "size": "sm", "color": "#666666", "align": "center"}
                ], "flex": 1
            },
            {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": str(pending_tasks), "size": "xl", "weight": "bold", "align": "center", "color": "#FF5551"},
                    {"type": "text", "text": "待完成", "size": "sm", "color": "#666666", "align": "center"}
                ], "flex": 1
            },
            {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": str(completed_tasks), "size": "xl", "weight": "bold", "align": "center", "color": "#1DB446"},
                    {"type": "text", "text": "已完成", "size": "sm", "color": "#666666", "align": "center"}
                ], "flex": 1
            }
        ]
    }
    table_contents.append(stats_box)
    table_contents.append({"type": "separator", "margin": "md"})

    header_box = {
        "type": "box",
        "layout": "horizontal",
        "spacing": "sm",
        "margin": "md",
        "contents": [
            {"type": "text", "text": "作業名稱", "size": "sm", "weight": "bold", "flex": 2},
            {"type": "text", "text": "類型", "size": "sm", "weight": "bold", "flex": 1, "align": "center"},
            {"type": "text", "text": "時間", "size": "sm", "weight": "bold", "flex": 1, "align": "center"},
            {"type": "text", "text": "截止日", "size": "sm", "weight": "bold", "flex": 1, "align": "center"},
            {"type": "text", "text": "狀態", "size": "sm", "weight": "bold", "flex": 1, "align": "center"}
        ]
    }
    table_contents.append(header_box)
    table_contents.append({"type": "separator", "margin": "sm"})

    now_date = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()

    for i, task in enumerate(tasks):
        is_done = task.get("done", False)
        due_date = task.get("due", "未設定")
        is_expired = False
        if due_date != "未設定" and not is_done:
            try:
                due_datetime = datetime.datetime.strptime(due_date, "%Y-%m-%d").date()
                is_expired = due_datetime < now_date
            except:
                pass

        if is_done:
            status_text = "✅"
            status_color = "#1DB446"
        elif is_expired:
            status_text = "⏰"
            status_color = "#FF5551"
        else:
            status_text = "⏳"
            status_color = "#FFAA00"

        due_display = due_date
        if due_date != "未設定":
            try:
                due_datetime = datetime.datetime.strptime(due_date, "%Y-%m-%d")
                due_display = due_datetime.strftime("%m/%d")
            except:
                due_display = "(未設定)"
        else:
            due_display = "(未設定)"

        task_row = {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "margin": "sm",
            "contents": [
                {"type": "text", "text": task.get("task", "未命名"), "size": "sm", "flex": 2, "wrap": True, "color": "#666666" if is_done else "#333333"},
                {"type": "text", "text": task.get("category", "-"), "size": "xs", "flex": 1, "align": "center", "color": "#888888"},
                {"type": "text", "text": f"{task.get('estimated_time', 0)}h", "size": "xs", "flex": 1, "align": "center", "color": "#888888"},
                {"type": "text", "text": due_display, "size": "xs", "flex": 1, "align": "center", "color": "#FF5551" if is_expired else "#888888"},
                {"type": "text", "text": status_text, "size": "sm", "flex": 1, "align": "center", "color": status_color}
            ]
        }
        table_contents.append(task_row)
        if i < len(tasks) - 1:
            table_contents.append({"type": "separator", "margin": "sm", "color": "#EEEEEE"})

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "none",
            "contents": table_contents
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": [
                {"type": "button", "action": {"type": "postback", "label": "✅ 完成作業", "data": "complete_task"}, "style": "primary", "flex": 1},
                {"type": "button", "action": {"type": "postback", "label": "➕ 新增作業", "data": "add_task"}, "style": "secondary", "flex": 1}
            ]
        }
    }

    try:
        line_bot_api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=[FlexMessage(
                    alt_text="作業列表",
                    contents=FlexContainer.from_dict(bubble)
                )]
            )
        )
        print(f"[remind][task] 推播作業列表給 {user_id}")
    except Exception as e:
        print(f"[remind][task] 推播作業列表失敗 {user_id}：{e}")


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
            try:
                if not isinstance(user_data, dict):
                    continue

                # ========== 檢查新增作業提醒 ==========
                add_task_remind_enabled = get_add_task_remind_enabled(user_id)
                add_task_remind_time = get_add_task_remind_time(user_id)
                last_add_task_remind_date = user_data.get("last_add_task_remind_date", "")
                
                print(f"[remind][add_task] user={user_id}, enabled={add_task_remind_enabled}, "
                      f"remind_time={add_task_remind_time}, now={current_time_str}, "
                      f"last_remind={last_add_task_remind_date}, today={today_str}")

                # 檢查是否應該發送新增作業提醒
                if add_task_remind_enabled and time_should_remind(add_task_remind_time, now):
                    # 確保今天還沒提醒過
                    if last_add_task_remind_date != today_str:
                        # 發送提醒
                        send_add_task_reminder(user_id)
                        # 記錄今天已提醒
                        db.reference(f"users/{user_id}/last_add_task_remind_date").set(today_str)
                        print(f"[remind][add_task] 已發送新增作業提醒給 {user_id}")

                # ========== 檢查未完成作業提醒 ==========
                task_remind_enabled = get_task_remind_enabled(user_id)
                remind_time = get_remind_time(user_id)
                last_task_remind_date = user_data.get("last_task_remind_date", "")
                tasks = user_data.get("tasks", [])
                
                print(f"[remind][task] user={user_id}, enabled={task_remind_enabled}, "
                      f"remind_time={remind_time}, now={current_time_str}, "
                      f"last_remind={last_task_remind_date}, today={today_str}")

                # 檢查是否應該發送未完成作業提醒
                if task_remind_enabled and time_should_remind(remind_time, now):
                    # 確保今天還沒提醒過
                    if last_task_remind_date != today_str:
                        # 檢查是否有未完成作業
                        has_incomplete_task = False
                        for task in tasks:
                            if not task.get("done", False):
                                has_incomplete_task = True
                                break

                        if has_incomplete_task:
                            display_name = get_line_display_name(user_id)

                            # 發送文字提醒
                            try:
                                line_bot_api.push_message(
                                    PushMessageRequest(
                                        to=user_id,
                                        messages=[TextMessage(
                                            text=f"⏰ {display_name}，您還有尚未完成的作業喔！來看看吧 👇"
                                        )]
                                    )
                                )
                                print(f"[remind][task] 推播文字提醒給 {user_id}")
                            except Exception as e:
                                print(f"[remind][task] 推播文字提醒失敗 {user_id}：{e}")

                            # 推播作業列表
                            send_view_tasks_push(user_id)

                            # 記錄今天已提醒
                            db.reference(f"users/{user_id}/last_task_remind_date").set(today_str)
                            print(f"[remind][task] 已更新 {user_id} 的提醒日期")
                        else:
                            print(f"[remind][task] {user_id} 沒有未完成的作業，跳過提醒")

                processed_count += 1

            except Exception as e:
                print(f"[remind] 處理用戶 {user_id} 時發生錯誤：{e}")
                continue

        print(f"[remind] 完成處理 {processed_count} 個用戶")
        return f"OK - Processed {processed_count} users"

    except Exception as e:
        print(f"[remind] 整體錯誤：{e}")
        return f"Error: {str(e)}"

def send_add_task_reminder(user_id):
    """發送新增作業提醒"""
    try:
        display_name = get_line_display_name(user_id)
        user_data = db.reference(f"users/{user_id}").get()
        last_add_task_date = user_data.get("last_add_task_date", "")

        today_str = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")
        
        # 根據今天是否已新增作業，顯示不同內容
        if last_add_task_date == today_str:
            # 今天已經有新增作業
            main_text = "你今天已經有新增作業囉 🎉"
            sub_text = "如果還有新的作業，記得馬上補上來，才不會漏掉！"
            button_text = "➕ 繼續新增作業"
        else:
            # 今天尚未新增作業
            main_text = "今天還沒有新增作業喔！"
            sub_text = "記得把今天的作業記錄下來，這樣才不會忘記 😊"
            button_text = "➕ 立即新增作業"

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
                        "text": main_text,
                        "size": "sm",
                        "color": "#666666",
                        "wrap": True
                    },
                    {
                        "type": "text",
                        "text": sub_text,
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
                            "label": button_text,
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
                    alt_text=main_text,
                    contents=FlexContainer.from_dict(bubble)
                )]
            )
        )
        print(f"[remind] 已發送新增作業提醒給 {user_id}")

    except Exception as e:
        print(f"[remind] 發送新增作業提醒失敗：{e}")

if __name__ == "__main__":
    app.run()