import os
import datetime
from firebase_utils import (
    load_data, save_data, set_user_state, get_user_state,
    clear_user_state, set_temp_task, get_temp_task, clear_temp_task
)
from flex_utils import make_schedule_carousel
from firebase_admin import db  # 因為你還在用 reference 拿 remind_time

from linebot.v3.webhook import MessageEvent
from linebot.v3.messaging import MessagingApi, ReplyMessageRequest
from linebot.v3.messaging.models import TextMessage, FlexMessage, FlexContainer
from linebot.v3.messaging import ApiClient, Configuration

configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))


def register_message_handlers(handler):
    @handler.add(MessageEvent)
    def handle_message(event):
        user_id = event.source.user_id

        if event.message.type != 'text':
            return

        text = event.message.text.strip()
        data = load_data(user_id)

        if text == "新增作業":
            set_user_state(user_id, "awaiting_full_task_input")
            reply = (
                "請輸入作業內容，格式為：\n"
                "作業名稱 預估時間(小時) 類型\n\n"
                "📌 例如：\n"
                "英文報告 1.5 閱讀\n"
                "歷史小論文 2.5 寫作"
            )
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply)]
                    )
                )
            return
        
        elif get_user_state(user_id) == "awaiting_full_task_input":
            parts = text.strip().split()
            if len(parts) < 3:
                reply = (
                    "⚠️ 格式錯誤，請輸入完整內容：\n"
                    "作業名稱 預估時間(小時) 類型\n"
                    "📌 範例：英文報告 1.5 閱讀"
                )
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=reply)]
                        )
                    )
                return
            try:
                # 拆解格式
                task_name = " ".join(parts[:-2])
                estimated_time = float(parts[-2])
                category = parts[-1]

                task = {
                    "task": task_name,
                    "estimated_time": estimated_time,
                    "category": category
                }
                set_temp_task(user_id, task)
                set_user_state(user_id, "awaiting_due_date")

                # 回覆日期選擇 UI
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

            except:
                reply = (
                    "⚠️ 預估時間格式錯誤，請再試一次！\n"
                    "格式應為：名稱 預估時間 類型\n"
                    "📌 範例：英文報告 1.5 閱讀"
                )
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=reply)]
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
        
        elif text == "今日排程卡片":
            tasks = load_data(user_id)
            if not tasks:
                reply = "😅 目前沒有任何未完成的作業可以排程喔～請先新增作業！"
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=reply)]
                        )
                    )
                return

            flex_content = make_schedule_carousel(tasks[:10])
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[FlexMessage(
                            alt_text="今日任務排程",
                            contents=FlexContainer.from_dict(flex_content)
                        )]
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
                            label = "\n(🔥今天到期)"
                        elif due_date == now + datetime.timedelta(days=1):
                            label = "\n(⚠️明天到期)"
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

        elif text == "操作":
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
                                alt_text="操作",
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