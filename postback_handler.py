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
            
            print(f"收到 postback 事件：{data}")  # 新增日誌
                        
            if data == "complete_task":
                # 載入任務數據
                tasks = load_data(user_id)
                if not tasks:
                    reply = "目前沒有任何作業可完成。"
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=reply)]
                            )
                        )
                    return
                
                # 建立完成作業的按鈕
                buttons = []
                for i, task in enumerate(tasks):
                    if not task.get("done", False):
                        buttons.append({
                            "type": "button",
                            "action": {
                                "type": "postback",
                                "label": f"✅ {task['task']}",
                                "data": f"complete_task_{i}"
                            },
                            "style": "secondary"
                        })
                
                if not buttons:
                    reply = "目前沒有未完成的作業。"
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

            # 處理完成特定作業
            elif data.startswith("complete_task_"):
                try:
                    # 獲取任務索引
                    task_index = int(data.split("_")[-1])
                    
                    # 載入任務數據
                    tasks = load_data(user_id)
                    if not tasks:
                        reply = "❌ 找不到任何作業"
                        with ApiClient(configuration) as api_client:
                            MessagingApi(api_client).reply_message(
                                ReplyMessageRequest(
                                    reply_token=event.reply_token,
                                    messages=[TextMessage(text=reply)]
                                )
                            )
                        return
                    
                    # 檢查索引是否有效
                    if task_index < 0 or task_index >= len(tasks):
                        reply = "❌ 無效的作業編號"
                        with ApiClient(configuration) as api_client:
                            MessagingApi(api_client).reply_message(
                                ReplyMessageRequest(
                                    reply_token=event.reply_token,
                                    messages=[TextMessage(text=reply)]
                                )
                            )
                        return
                    
                    # 檢查任務是否已經完成
                    if tasks[task_index].get("done", False):
                        reply = f"⚠️ 作業 {tasks[task_index]['task']} 已經完成了"
                        with ApiClient(configuration) as api_client:
                            MessagingApi(api_client).reply_message(
                                ReplyMessageRequest(
                                    reply_token=event.reply_token,
                                    messages=[TextMessage(text=reply)]
                                )
                            )
                        return
                    
                    # 更新任務狀態
                    tasks[task_index]["done"] = True
                    
                    # 保存更新後的數據
                    try:
                        save_data(user_id, tasks)
                        reply = f"✅ 已完成作業：{tasks[task_index]['task']}"
                    except Exception as e:
                        print(f"保存數據時發生錯誤：{str(e)}")
                        reply = "❌ 保存數據時發生錯誤，請稍後再試"
                    
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=reply)]
                            )
                        )
                    return
                except Exception as e:
                    print(f"處理完成作業時發生錯誤：{str(e)}")
                    reply = "❌ 發生錯誤，請稍後再試"
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=reply)]
                            )
                        )
                    return
                
            elif data == "set_remind_time":
                # 直接顯示提醒時間設定選單
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
                
            elif data == "view_tasks":
                # 直接顯示作業清單
                data = load_data(user_id)
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
                
            elif data == "clear_completed":
                # 直接顯示清除已完成作業選單
                data = load_data(user_id)
                completed_tasks = [task for task in data if task.get("done", False)]
                if not completed_tasks:
                    reply = "✅ 沒有已完成的作業需要清除。"
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
                                "color": "#FF4444"
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
                
            elif data == "clear_expired":
                # 直接顯示清除已截止作業選單
                data = load_data(user_id)
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
                                "style": "primary"
                            },
                            {
                                "type": "button",
                                "action": {
                                    "type": "postback",
                                    "label": "🗑️ 一鍵清除全部",
                                    "data": "clear_expired_all"
                                },
                                "style": "primary",
                                "color": "#FF4444"
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
            
            # 處理其他現有的 postback 事件
            if data == "confirm_add_task":
                print("處理確認新增作業")  # 新增日誌
                temp_task = get_temp_task(user_id)
                if not temp_task:
                    print("找不到暫存任務")  # 新增日誌
                    reply = "⚠️ 發生錯誤，請重新開始新增作業流程"
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=reply)]
                            )
                        )
                    return

                # 檢查必要欄位
                required_fields = ["task", "estimated_time", "category"]
                missing_fields = [field for field in required_fields if field not in temp_task or temp_task[field] is None]
                
                if missing_fields:
                    print(f"缺少必要欄位：{missing_fields}")  # 新增日誌
                    reply = f"⚠️ 缺少必要資訊：{', '.join(missing_fields)}，請重新開始新增作業流程"
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=reply)]
                            )
                        )
                    return

                try:
                    # 確保 estimated_time 是數字
                    if isinstance(temp_task["estimated_time"], str):
                        temp_task["estimated_time"] = float(temp_task["estimated_time"])
                    
                    # 更新歷史記錄
                    print(f"更新歷史記錄：{temp_task}")  # 新增日誌
                    update_task_history(user_id, temp_task["task"], temp_task["category"], temp_task["estimated_time"])
                    
                    # 新增作業
                    print("新增作業到資料庫")  # 新增日誌
                    success = add_task(user_id, temp_task)
                    if not success:
                        raise Exception("新增作業失敗")
                    
                    # 清除暫存資料
                    clear_temp_task(user_id)
                    clear_user_state(user_id)
                    
                    reply = "✅ 作業已成功新增！"
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=reply)]
                            )
                        )
                    return
                except Exception as e:
                    print(f"處理確認新增作業時發生錯誤：{str(e)}")  # 新增日誌
                    raise e

            # 處理取消操作
            if data == "cancel_add_task":
                clear_temp_task(user_id)
                clear_user_state(user_id)
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="❌ 已取消新增作業")]
                        )
                    )
                return

            # 處理選擇作業名稱
            if data.startswith("select_task_name_"):
                task_name = data.replace("select_task_name_", "")
                temp_task = {"task": task_name}
                set_temp_task(user_id, temp_task)
                set_user_state(user_id, "awaiting_task_time")
                
                # 獲取歷史時間記錄
                _, _, time_history = get_task_history(user_id)
                
                # 顯示時間輸入 UI
                bubble = {
                    "type": "bubble",
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "md",
                        "contents": [
                            {"type": "text", "text": "⏰ 請輸入預估完成時間", "weight": "bold", "size": "lg"},
                            {"type": "text", "text": "或選擇歷史記錄：", "size": "sm", "color": "#888888"}
                        ]
                    }
                }
                
                # 添加歷史時間按鈕
                if time_history:
                    for time in time_history:
                        bubble["body"]["contents"].append({
                            "type": "button",
                            "action": {
                                "type": "postback",
                                "label": time,
                                "data": f"select_time_{time.replace('小時', '')}"
                            },
                            "style": "secondary"
                        })
                
                # 添加取消按鈕
                bubble["body"]["contents"].append({
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "❌ 取消",
                        "data": "cancel_add_task"
                    },
                    "style": "secondary"
                })

                messages = [
                    FlexMessage(
                        alt_text="請輸入預估完成時間",
                        contents=FlexContainer.from_dict(bubble)
                    ),
                    TextMessage(text="請輸入預估完成時間（小時）：")
                ]

                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=messages
                        )
                    )
                return

            # 處理選擇歷史時間
            if data.startswith("select_time_"):
                time_value = data.replace("select_time_", "")
                temp_task = get_temp_task(user_id)
                temp_task["estimated_time"] = float(time_value)
                set_temp_task(user_id, temp_task)
                set_user_state(user_id, "awaiting_task_type")
                
                # 顯示作業類型選擇 UI
                bubble = {
                    "type": "bubble",
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "md",
                        "contents": [
                            {"type": "text", "text": "📝 請選擇作業類型", "weight": "bold", "size": "lg"},
                            {"type": "text", "text": "或選擇歷史記錄：", "size": "sm", "color": "#888888"}
                        ]
                    }
                }
                
                # 獲取歷史類型記錄
                _, type_history, _ = get_task_history(user_id)
                
                # 添加歷史類型按鈕
                if type_history:
                    for task_type in type_history:
                        bubble["body"]["contents"].append({
                            "type": "button",
                            "action": {
                                "type": "postback",
                                "label": task_type,
                                "data": f"select_type_{task_type}"
                            },
                            "style": "secondary"
                        })
                
                # 添加取消按鈕
                bubble["body"]["contents"].append({
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "❌ 取消",
                        "data": "cancel_add_task"
                    },
                    "style": "secondary"
                })

                messages = [
                    FlexMessage(
                        alt_text="請選擇作業類型",
                        contents=FlexContainer.from_dict(bubble)
                    ),
                    TextMessage(text="請輸入作業類型：")
                ]

                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=messages
                        )
                    )
                return

            # 處理選擇歷史類型
            if data.startswith("select_type_"):
                type_value = data.replace("select_type_", "")
                temp_task = get_temp_task(user_id)
                temp_task["category"] = type_value
                set_temp_task(user_id, temp_task)
                set_user_state(user_id, "awaiting_task_due")
                
                # 顯示截止日期選擇 UI
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
                                    "initial": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d"),
                                    "max": "2099-12-31",
                                    "min": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")
                                },
                                "style": "primary"
                            },
                            {
                                "type": "button",
                                "action": {
                                    "type": "postback",
                                    "label": "❌ 不設定截止日期",
                                    "data": "no_due_date"
                                },
                                "style": "secondary"
                            },
                            {
                                "type": "button",
                                "action": {
                                    "type": "postback",
                                    "label": "❌ 取消",
                                    "data": "cancel_add_task"
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
                                alt_text="請選擇截止日期",
                                contents=FlexContainer.from_dict(bubble)
                            )]
                        )
                    )
                return

            # 處理選擇截止日期
            if data == "select_task_due":
                # 從 postback 參數中獲取日期
                date = event.postback.params.get('date', '')
                if date:
                    temp_task = get_temp_task(user_id)
                    if not temp_task:
                        clear_temp_task(user_id)
                        clear_user_state(user_id)
                        with ApiClient(configuration) as api_client:
                            MessagingApi(api_client).reply_message(
                                ReplyMessageRequest(
                                    reply_token=event.reply_token,
                                    messages=[TextMessage(text="❌ 發生錯誤，請重新開始新增作業流程")]
                                )
                            )
                        return

                    # 更新截止日期
                    temp_task["due"] = date
                    set_temp_task(user_id, temp_task)
                    
                    # 顯示確認訊息
                    bubble = {
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
                                    "action": {
                                        "type": "postback",
                                        "label": "✅ 確認新增",
                                        "data": "confirm_add_task"
                                    },
                                    "style": "primary"
                                },
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "postback",
                                        "label": "❌ 取消",
                                        "data": "cancel_add_task"
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
                                    alt_text="確認新增作業",
                                    contents=FlexContainer.from_dict(bubble)
                                )]
                            )
                        )
                return

            # 處理不設定截止日期
            if data == "no_due_date":
                temp_task = get_temp_task(user_id)
                if not temp_task:
                    clear_temp_task(user_id)
                    clear_user_state(user_id)
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text="❌ 發生錯誤，請重新開始新增作業流程")]
                            )
                        )
                    return

                # 顯示確認訊息
                bubble = {
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
                                "action": {
                                    "type": "postback",
                                    "label": "✅ 確認新增",
                                    "data": "confirm_add_task"
                                },
                                "style": "primary"
                            },
                            {
                                "type": "button",
                                "action": {
                                    "type": "postback",
                                    "label": "❌ 取消",
                                    "data": "cancel_add_task"
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
                                alt_text="確認新增作業",
                                contents=FlexContainer.from_dict(bubble)
                            )]
                        )
                    )
                return

            # 處理選擇提醒時間
            if data == "select_remind_time":
                # 從 postback 參數中獲取時間
                time = event.postback.params.get('time', '')
                if not time:
                    reply = "❌ 請選擇有效的時間"
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=reply)]
                            )
                        )
                    return

                try:
                    # 驗證時間格式
                    datetime.datetime.strptime(time, "%H:%M")
                    # 儲存時間
                    db.reference(f"users/{user_id}/remind_time").set(time)
                    reply = f"✅ 已設定提醒時間為 {time}"
                except ValueError:
                    reply = "❌ 時間格式無效，請重新選擇"
                
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=reply)]
                        )
                    )
                return

            # 處理一鍵清除已完成作業
            elif data == "clear_completed_all":
                # 載入任務數據
                tasks = load_data(user_id)
                if not tasks:
                    reply = "✅ 目前沒有任何作業"
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=reply)]
                            )
                        )
                    return

                # 過濾掉已完成的作業
                filtered_tasks = [task for task in tasks if not task.get("done", False)]
                if len(filtered_tasks) == len(tasks):
                    reply = "✅ 沒有已完成的作業需要清除"
                else:
                    # 保存更新後的數據
                    save_data(user_id, filtered_tasks)
                    reply = f"✅ 已清除 {len(tasks) - len(filtered_tasks)} 個已完成的作業"
                
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=reply)]
                        )
                    )
                return

            # 處理一鍵清除已截止作業
            elif data == "clear_expired_all":
                try:
                    # 載入任務數據
                    tasks = load_data(user_id)
                    if not tasks:
                        reply = "✅ 目前沒有任何作業"
                        with ApiClient(configuration) as api_client:
                            MessagingApi(api_client).reply_message(
                                ReplyMessageRequest(
                                    reply_token=event.reply_token,
                                    messages=[TextMessage(text=reply)]
                                )
                            )
                        return

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
                        # 保存更新後的數據
                        save_data(user_id, filtered_tasks)
                        reply = f"✅ 已清除 {expired_count} 個已截止的作業"
                    
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=reply)]
                            )
                        )
                    return
                except Exception as e:
                    print(f"處理一鍵清除已截止作業時發生錯誤：{str(e)}")
                    reply = "❌ 發生錯誤，請稍後再試"
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=reply)]
                            )
                        )
                    return

            # 處理手動選擇清除已完成作業
            elif data == "clear_completed_select":
                try:
                    # 載入任務數據
                    tasks = load_data(user_id)
                    if not tasks:
                        reply = "✅ 目前沒有任何作業"
                        with ApiClient(configuration) as api_client:
                            MessagingApi(api_client).reply_message(
                                ReplyMessageRequest(
                                    reply_token=event.reply_token,
                                    messages=[TextMessage(text=reply)]
                                )
                            )
                        return

                    # 找出已完成的作業
                    completed_tasks = []
                    for i, task in enumerate(tasks):
                        if task.get("done", False):
                            completed_tasks.append((i, task))
                    
                    if not completed_tasks:
                        reply = "✅ 沒有已完成的作業需要清除"
                        with ApiClient(configuration) as api_client:
                            MessagingApi(api_client).reply_message(
                                ReplyMessageRequest(
                                    reply_token=event.reply_token,
                                    messages=[TextMessage(text=reply)]
                                )
                            )
                        return

                    # 建立清除按鈕
                    buttons = []
                    for i, task in completed_tasks:
                        buttons.append({
                            "type": "button",
                            "action": {
                                "type": "postback",
                                "label": f"🗑️ {task['task']}",
                                "data": f"delete_completed_{i}"
                            },
                            "style": "secondary"
                        })

                    # 添加取消按鈕
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
                                {"type": "text", "text": "選擇要清除的已完成作業：", "weight": "bold", "size": "lg"},
                                {"type": "text", "text": f"共有 {len(completed_tasks)} 個已完成作業", "size": "sm", "color": "#888888"},
                                *buttons
                            ]
                        }
                    }
                
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[FlexMessage(
                                    alt_text="選擇要清除的已完成作業",
                                    contents=FlexContainer.from_dict(bubble)
                                )]
                            )
                        )
                    return
                except Exception as e:
                    print(f"處理手動選擇清除已完成作業時發生錯誤：{str(e)}")
                    reply = "❌ 發生錯誤，請稍後再試"
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=reply)]
                            )
                        )
                    return

            # 處理刪除已完成作業
            elif data.startswith("delete_completed_"):
                try:
                    # 獲取任務索引
                    task_index = int(data.replace("delete_completed_", ""))
                    
                    # 載入任務數據
                    tasks = load_data(user_id)
                    if not tasks:
                        reply = "❌ 找不到任何作業"
                        with ApiClient(configuration) as api_client:
                            MessagingApi(api_client).reply_message(
                                ReplyMessageRequest(
                                    reply_token=event.reply_token,
                                    messages=[TextMessage(text=reply)]
                                )
                            )
                        return
                    
                    # 檢查索引是否有效
                    if task_index < 0 or task_index >= len(tasks):
                        reply = "❌ 無效的作業編號"
                        with ApiClient(configuration) as api_client:
                            MessagingApi(api_client).reply_message(
                                ReplyMessageRequest(
                                    reply_token=event.reply_token,
                                    messages=[TextMessage(text=reply)]
                                )
                            )
                        return
                    
                    # 刪除指定的作業
                    deleted_task = tasks.pop(task_index)
                    
                    # 保存更新後的數據
                    save_data(user_id, tasks)
                    
                    reply = f"✅ 已清除作業：{deleted_task['task']}"
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=reply)]
                            )
                        )
                    return
                except Exception as e:
                    print(f"處理刪除已完成作業時發生錯誤：{str(e)}")
                    reply = "❌ 發生錯誤，請稍後再試"
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
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
