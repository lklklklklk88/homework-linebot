import os
import datetime
import logging
from firebase_utils import (
    load_data, save_data, set_user_state, get_user_state,
    clear_user_state, set_temp_task, get_temp_task, clear_temp_task,
    update_task_status, delete_task, delay_task, get_task_history,
    update_task_history, add_task
)
from firebase_admin import db
from firebase_utils import save_remind_time
from linebot.v3.webhooks import PostbackEvent
from linebot.v3.messaging import MessagingApi, ReplyMessageRequest
from linebot.v3.messaging.models import TextMessage, FlexMessage, FlexContainer
from linebot.v3.messaging import ApiClient
from linebot.v3.messaging import Configuration
from linebot.models import TextSendMessage, FlexSendMessage
from flex_utils import make_schedule_carousel

# 設定 logger
logger = logging.getLogger(__name__)

configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))

def register_postback_handlers(handler):
    @handler.add(PostbackEvent)
    def handle_postback(event):
        try:
            data = event.postback.data
            user_id = event.source.user_id
            reply_token = event.reply_token
            
            print(f"收到 postback 事件：{data}")  # 新增日誌

            if data == "add_task":
                handle_add_task(user_id, reply_token)
                return
            
            elif data.startswith("select_task_name_"):
                handle_select_task_name(data, user_id, reply_token)
                return

            elif data.startswith("select_time_"):
                handle_select_time(data, user_id, reply_token)
                return

            elif data.startswith("select_type_"):
                handle_select_type(data, user_id, reply_token)
                return

            elif data == "cancel_add_task":
                handle_cancel_add_task(user_id, reply_token)
                return

            elif data == "confirm_add_task":
                handle_confirm_add_task(user_id, reply_token)
                return

            elif data == "show_schedule":
                handle_show_schedule(user_id, reply_token)
                return

            elif data == "view_tasks":
                handle_view_tasks(user_id, reply_token)
                return

            elif data == "complete_task":
                handle_complete_task_direct(user_id, reply_token)
                return

            elif data == "select_task_due":
                handle_select_task_due(event, user_id)
                return

            elif data == "no_due_date":
                handle_no_due_date(user_id, reply_token)
                return

            elif data == "set_remind_time":
                handle_set_remind_time(user_id, reply_token)
                return

            elif data == "clear_completed":
                handle_clear_completed(user_id, reply_token)
                return

            elif data == "clear_expired":
                handle_clear_expired(user_id, reply_token)
                return
            
            elif data == "select_remind_time":
                handle_select_remind_time(event, user_id, reply_token)
                return
            
            elif data == "cancel_set_remind":
                handle_cancel_set_remind(user_id, reply_token)
                return

            elif data == "clear_completed_select":
                handle_clear_completed_select(user_id, reply_token)
                return

            elif data.startswith("delete_completed_"):
                handle_delete_completed(data, user_id, reply_token)
                return
            
            elif data == "clear_expired_select":
                handle_clear_expired_select(user_id, reply_token)
                return

            elif data.startswith("delete_expired_"):
                handle_delete_expired(data, user_id, reply_token)
                return

            elif data == "cancel_clear_completed":
                handle_cancel_clear_completed(user_id, reply_token)
                return

            elif data == "cancel_clear_expired":
                handle_cancel_clear_expired(user_id, reply_token)
                return
            
            elif data == "clear_completed_all":
                handle_clear_completed_all(user_id, reply_token)
                return

            elif data == "clear_expired_all":
                handle_clear_expired_all(user_id, reply_token)
                return


            elif data.startswith("mark_done_"):
                try:
                    task_index = int(data.replace("mark_done_", ""))
                    tasks = load_data(user_id)

                    if 0 <= task_index < len(tasks):
                        tasks[task_index]["done"] = True
                        save_data(user_id, tasks)
                        reply = f"✅ 已完成作業：{tasks[task_index]['task']}"
                    else:
                        reply = "❌ 找不到該作業"

                except Exception as e:
                    print(f"完成作業失敗：{str(e)}")
                    reply = "❌ 發生錯誤，請稍後再試"

                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=reply_token,
                            messages=[TextMessage(text=reply)]
                        )
                    )
                return

        except Exception as e:
            print(f"處理 postback 事件時發生錯誤：{str(e)}")
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="❌ 發生錯誤，請稍後再試")]
                    )
                )

def handle_add_task(user_id, reply_token):
    set_user_state(user_id, "awaiting_task_name")
    clear_temp_task(user_id)
    name_history, _, _ = get_task_history(user_id)

    buttons = []
    for name in name_history[-3:]:
        buttons.append({
            "type": "button",
            "action": {
                "type": "postback",
                "label": name,
                "data": f"select_task_name_{name}"
            },
            "style": "secondary"
        })

    buttons.append({
        "type": "button",
        "action": {
            "type": "postback",
            "label": "❌ 取消",
            "data": "cancel_add_task"
        },
        "style": "secondary"
    })

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {"type": "text", "text": "📝 請輸入作業名稱", "weight": "bold", "size": "lg"},
                {"type": "text", "text": "或選擇歷史記錄：", "size": "sm", "color": "#888888"},
                *buttons
            ]
        }
    }

    messages = [
        FlexMessage(
            alt_text="請輸入作業名稱",
            contents=FlexContainer.from_dict(bubble)
        ),
        TextMessage(text="請輸入作業名稱：")
    ]

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages
            )
        )

def handle_select_task_name(data, user_id, reply_token):
    task_name = data.replace("select_task_name_", "")
    temp_task = {"task": task_name}
    set_temp_task(user_id, temp_task)
    set_user_state(user_id, "awaiting_task_time")

    _, _, time_history = get_task_history(user_id)

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {"type": "text", "text": "⏰ 請輸入預估完成時間", "weight": "bold", "size": "lg"},
                {"type": "text", "text": "或選擇歷史記錄：", "size": "sm", "color": "#888888"}
            ] + [
                {
                    "type": "button",
                    "action": {"type": "postback", "label": t, "data": f"select_time_{t.replace('小時', '')}"},
                    "style": "secondary"
                } for t in time_history
            ] + [
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "❌ 取消", "data": "cancel_add_task"},
                    "style": "secondary"
                }
            ]
        }
    }

    messages = [
        FlexMessage(alt_text="請輸入預估完成時間", contents=FlexContainer.from_dict(bubble)),
        TextMessage(text="請輸入預估完成時間（小時）：")
    ]

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=messages)
        )

def handle_select_time(data, user_id, reply_token):
    time_value = data.replace("select_time_", "")
    temp_task = get_temp_task(user_id)
    temp_task["estimated_time"] = float(time_value)
    set_temp_task(user_id, temp_task)
    set_user_state(user_id, "awaiting_task_type")

    _, type_history, _ = get_task_history(user_id)

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {"type": "text", "text": "📝 請選擇作業類型", "weight": "bold", "size": "lg"},
                {"type": "text", "text": "或選擇歷史記錄：", "size": "sm", "color": "#888888"}
            ] + [
                {
                    "type": "button",
                    "action": {"type": "postback", "label": t, "data": f"select_type_{t}"},
                    "style": "secondary"
                } for t in type_history
            ] + [
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "❌ 取消", "data": "cancel_add_task"},
                    "style": "secondary"
                }
            ]
        }
    }

    messages = [
        FlexMessage(alt_text="請選擇作業類型", contents=FlexContainer.from_dict(bubble)),
        TextMessage(text="請輸入作業類型：")
    ]

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=messages)
        )

def handle_select_type(data, user_id, reply_token):
    type_value = data.replace("select_type_", "")
    temp_task = get_temp_task(user_id)
    temp_task["category"] = type_value
    set_temp_task(user_id, temp_task)
    set_user_state(user_id, "awaiting_task_due")

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {"type": "text", "text": "📅 請選擇截止日期", "weight": "bold", "size": "md"},
                {
                    "type": "button",
                    "action": {
                        "type": "datetimepicker",
                        "label": "📅 選擇日期",
                        "data": "select_task_due",
                        "mode": "date",
                        "initial": now,
                        "max": "2099-12-31",
                        "min": now
                    },
                    "style": "primary"
                },
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "❌ 不設定截止日期", "data": "no_due_date"},
                    "style": "secondary"
                },
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "❌ 取消", "data": "cancel_add_task"},
                    "style": "secondary"
                }
            ]
        }
    }

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[
                FlexMessage(alt_text="請選擇截止日期", contents=FlexContainer.from_dict(bubble))
            ])
        )

def handle_no_due_date(user_id, reply_token):
    temp_task = get_temp_task(user_id)
    if not temp_task:
        clear_temp_task(user_id)
        clear_user_state(user_id)
        reply = "❌ 發生錯誤，請重新開始新增作業流程"
    else:
        reply_bubble = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {"type": "text", "text": "📝 確認新增作業", "weight": "bold", "size": "lg"},
                    {"type": "text", "text": f"作業名稱：{temp_task.get('task', '未設定')}", "size": "md"},
                    {"type": "text", "text": f"預估時間：{temp_task.get('estimated_time', 0)} 小時", "size": "md"},
                    {"type": "text", "text": f"作業類型：{temp_task.get('category', '未設定')}", "size": "md"},
                    {"type": "text", "text": "截止日期：未設定", "size": "md"}
                ]
            },
            "footer": {
                "type": "box",
                "layout": "horizontal",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "action": {"type": "postback", "label": "✅ 確認新增", "data": "confirm_add_task"},
                        "style": "primary"
                    },
                    {
                        "type": "button",
                        "action": {"type": "postback", "label": "❌ 取消", "data": "cancel_add_task"},
                        "style": "secondary"
                    }
                ]
            }
        }

        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[FlexMessage(alt_text="確認新增作業", contents=FlexContainer.from_dict(reply_bubble))]
                )
            )
        return

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)])
        )

def handle_select_task_due(event, user_id):
    date = event.postback.params.get("date", "")
    reply_token = event.reply_token

    if not date:
        reply = "❌ 沒有取得日期，請重新選擇"
    else:
        temp_task = get_temp_task(user_id)
        if not temp_task:
            clear_temp_task(user_id)
            clear_user_state(user_id)
            reply = "❌ 發生錯誤，請重新開始新增作業流程"
        else:
            temp_task["due"] = date
            set_temp_task(user_id, temp_task)

            reply_bubble = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "md",
                    "contents": [
                        {"type": "text", "text": "📝 確認新增作業", "weight": "bold", "size": "lg"},
                        {"type": "text", "text": f"作業名稱：{temp_task.get('task', '未設定')}", "size": "md"},
                        {"type": "text", "text": f"預估時間：{temp_task.get('estimated_time', 0)} 小時", "size": "md"},
                        {"type": "text", "text": f"作業類型：{temp_task.get('category', '未設定')}", "size": "md"},
                        {"type": "text", "text": f"截止日期：{temp_task.get('due', '未設定')}", "size": "md"}
                    ]
                },
                "footer": {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "button",
                            "action": {"type": "postback", "label": "✅ 確認新增", "data": "confirm_add_task"},
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "action": {"type": "postback", "label": "❌ 取消", "data": "cancel_add_task"},
                            "style": "secondary"
                        }
                    ]
                }
            }

            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[FlexMessage(alt_text="確認新增作業", contents=FlexContainer.from_dict(reply_bubble))]
                    )
                )
            return

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=reply)]
            )
        )

def handle_confirm_add_task(user_id, reply_token):
    temp_task = get_temp_task(user_id)
    if not temp_task:
        reply = "⚠️ 發生錯誤，請重新開始新增作業流程"
    else:
        try:
            required_fields = ["task", "estimated_time", "category"]
            if any(f not in temp_task or temp_task[f] is None for f in required_fields):
                reply = "⚠️ 缺少必要資訊，請重新開始新增作業流程"
            else:
                if isinstance(temp_task["estimated_time"], str):
                    temp_task["estimated_time"] = float(temp_task["estimated_time"])

                update_task_history(user_id, temp_task["task"], temp_task["category"], temp_task["estimated_time"])
                add_task(user_id, temp_task)
                clear_temp_task(user_id)
                clear_user_state(user_id)
                reply = "✅ 作業已成功新增！"
        except Exception as e:
            print(f"新增作業失敗：{e}")
            reply = "❌ 發生錯誤，請稍後再試"

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)])
        )

def handle_cancel_add_task(user_id, reply_token):
    clear_temp_task(user_id)
    clear_user_state(user_id)
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text="❌ 已取消新增作業")])
        )

def handle_show_schedule(user_id, reply_token):
    from line_message_handler import get_today_schedule_for_user  # 避免 import 循環

    response = get_today_schedule_for_user(user_id)

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=response if isinstance(response, list) else [TextMessage(text=response)]
            )
        )

def handle_view_tasks(user_id, reply_token):
    from flex_utils import make_schedule_carousel
    tasks = load_data(user_id)
    if not tasks:
        reply = "目前沒有任何作業。"
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)])
            )
        return

    # 顯示作業卡片
    card = make_schedule_carousel(tasks)
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[FlexMessage(
                alt_text="作業清單", contents=FlexContainer.from_dict(card)
            )])
        )

def handle_complete_task_direct(user_id, reply_token):
    from postback_handler import register_postback_handlers  # 防止循環 import
    event = type("Event", (), {
        "postback": type("Postback", (), {"data": "complete_task"}),
        "source": type("Source", (), {"user_id": user_id}),
        "reply_token": reply_token
    })
    register_postback_handlers(lambda _: None).handle_postback(event)

def handle_set_remind_time(user_id, reply_token):
    now_time = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%H:%M")

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {"type": "text", "text": "⏰ 請選擇提醒時間", "weight": "bold", "size": "lg"},
                {
                    "type": "button",
                    "action": {
                        "type": "datetimepicker",
                        "label": "選擇時間",
                        "data": "select_remind_time",
                        "mode": "time",
                        "initial": now_time,
                        "max": "23:59",
                        "min": "00:00"
                    },
                    "style": "primary"
                },
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "❌ 取消", "data": "cancel_set_remind"},
                    "style": "secondary"
                }
            ]
        }
    }

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[FlexMessage(
                    alt_text="設定提醒時間",
                    contents=FlexContainer.from_dict(bubble)
                )]
            )
        )

def handle_select_remind_time(event, user_id, reply_token):
    time_param = event.postback.params.get("time", "")
    if not time_param:
        reply = "❌ 未取得提醒時間，請重新選擇"
    else:
        save_remind_time(user_id, time_param)
        reply = f"⏰ 已設定提醒時間為：{time_param}"

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)])
        )

def handle_cancel_set_remind(user_id, reply_token):
    reply = "❌ 已取消設定提醒時間"
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)])
        )

def handle_clear_completed(user_id, reply_token):
    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {"type": "text", "text": "🧹 清除已完成作業", "weight": "bold", "size": "lg"},
                {"type": "text", "text": "請選擇清除方式：", "size": "sm", "color": "#888888"},
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "🧼 手動選擇清除", "data": "clear_completed_select"},
                    "style": "secondary"
                },
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "⚡ 一鍵清除全部", "data": "clear_completed_all"},
                    "style": "primary"
                }
            ]
        }
    }

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[FlexMessage(
                    alt_text="清除已完成作業",
                    contents=FlexContainer.from_dict(bubble)
                )]
            )
        )

def handle_clear_completed_all(user_id, reply_token):
    tasks = load_data(user_id)
    if not tasks:
        reply = "✅ 目前沒有任何作業"
    else:
        filtered_tasks = [task for task in tasks if not task.get("done", False)]
        if len(filtered_tasks) == len(tasks):
            reply = "✅ 沒有已完成的作業需要清除"
        else:
            save_data(user_id, filtered_tasks)
            reply = f"✅ 已清除 {len(tasks) - len(filtered_tasks)} 個已完成的作業"

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)])
        )

def handle_clear_completed_select(user_id, reply_token):
    tasks = load_data(user_id)
    completed = [(i, t) for i, t in enumerate(tasks) if t.get("done")]

    if not completed:
        reply = "✅ 沒有已完成作業需要清除"
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)])
            )
        return

    buttons = [
        {
            "type": "button",
            "action": {
                "type": "postback",
                "label": f"🗑️ {task['task']}",
                "data": f"delete_completed_{i}"
            },
            "style": "secondary"
        }
        for i, task in completed
    ]

    buttons.append({
        "type": "button",
        "action": {
            "type": "postback",
            "label": "❌ 取消",
            "data": "cancel_clear_completed"
        },
        "style": "secondary"
    })

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {"type": "text", "text": "選擇要刪除的已完成作業", "weight": "bold", "size": "lg"},
                {"type": "text", "text": f"共有 {len(completed)} 筆作業", "size": "sm", "color": "#888888"},
                *buttons
            ]
        }
    }

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[FlexMessage(alt_text="手動刪除已完成作業", contents=FlexContainer.from_dict(bubble))]
            )
        )

def handle_cancel_clear_completed(user_id, reply_token):
    reply = "❌ 已取消清除已完成作業"
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)])
        )

def handle_delete_completed(data, user_id, reply_token):
    try:
        index = int(data.replace("delete_completed_", ""))
        tasks = load_data(user_id)
        if index < 0 or index >= len(tasks) or not tasks[index].get("done"):
            reply = "❌ 找不到對應的已完成作業"
        else:
            deleted = tasks.pop(index)
            save_data(user_id, tasks)
            reply = f"🗑️ 已刪除：{deleted['task']}"

    except Exception as e:
        print(f"刪除已完成作業失敗：{e}")
        reply = "❌ 刪除過程中發生錯誤"

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)])
        )

def handle_clear_expired(user_id, reply_token):
    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {"type": "text", "text": "🗑️ 清除已截止作業", "weight": "bold", "size": "lg"},
                {"type": "text", "text": "請選擇清除方式：", "size": "sm", "color": "#888888"},
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "🧼 手動選擇清除", "data": "clear_expired_select"},
                    "style": "secondary"
                },
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "⚡ 一鍵清除全部", "data": "clear_expired_all"},
                    "style": "primary"
                }
            ]
        }
    }

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[FlexMessage(
                    alt_text="清除已截止作業",
                    contents=FlexContainer.from_dict(bubble)
                )]
            )
        )

def handle_clear_expired_select(user_id, reply_token):
    tasks = load_data(user_id)
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()

    expired_tasks = []
    for i, task in enumerate(tasks):
        if task.get("done", False):
            continue
        due = task.get("due", "未設定")
        if due == "未設定":
            continue
        try:
            due_date = datetime.datetime.strptime(due, "%Y-%m-%d").date()
            if due_date < now:
                expired_tasks.append((i, task))
        except:
            continue

    if not expired_tasks:
        reply = "✅ 沒有已截止作業需要清除"
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)])
            )
        return

    buttons = [
        {
            "type": "button",
            "action": {
                "type": "postback",
                "label": f"🗑️ {task['task']}",
                "data": f"delete_expired_{i}"
            },
            "style": "secondary"
        }
        for i, task in expired_tasks
    ]

    buttons.append({
        "type": "button",
        "action": {
            "type": "postback",
            "label": "❌ 取消",
            "data": "cancel_clear_expired"
        },
        "style": "secondary"
    })

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {"type": "text", "text": "選擇要刪除的已截止作業", "weight": "bold", "size": "lg"},
                {"type": "text", "text": f"共有 {len(expired_tasks)} 筆作業", "size": "sm", "color": "#888888"},
                *buttons
            ]
        }
    }

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[FlexMessage(alt_text="手動刪除已截止作業", contents=FlexContainer.from_dict(bubble))]
            )
        )

def handle_clear_expired_all(user_id, reply_token):
    try:
        tasks = load_data(user_id)
        if not tasks:
            reply = "✅ 目前沒有任何作業"
        else:
            now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()
            expired_count = 0
            filtered_tasks = []

            for task in tasks:
                due = task.get("due", "未設定")
                done = task.get("done", False)
                if done or due == "未設定":
                    filtered_tasks.append(task)
                    continue

                try:
                    due_date = datetime.datetime.strptime(due, "%Y-%m-%d").date()
                    if due_date >= now:
                        filtered_tasks.append(task)
                    else:
                        expired_count += 1
                except:
                    filtered_tasks.append(task)

            if expired_count == 0:
                reply = "✅ 沒有已截止的作業需要清除"
            else:
                save_data(user_id, filtered_tasks)
                reply = f"✅ 已清除 {expired_count} 個已截止的作業"
    except Exception as e:
        print(f"一鍵清除已截止作業失敗：{str(e)}")
        reply = "❌ 發生錯誤，請稍後再試"

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)])
        )

def handle_delete_expired(data, user_id, reply_token):
    try:
        index = int(data.replace("delete_expired_", ""))
        tasks = load_data(user_id)
        if index < 0 or index >= len(tasks):
            raise Exception("索引無效")

        deleted_task = tasks.pop(index)
        save_data(user_id, tasks)
        reply = f"🗑️ 已刪除：{deleted_task['task']}"

    except Exception as e:
        print(f"刪除已截止作業失敗：{str(e)}")
        reply = "❌ 刪除過程中發生錯誤"

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)])
        )

def handle_cancel_clear_expired(user_id, reply_token):
    reply = "❌ 已取消清除已截止作業"
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)])
        )
