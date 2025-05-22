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

# 常數定義
ACTION_TYPES = {
    'done': '完成',
    'delete': '刪除',
    'delay': '延後'
}

def register_postback_handlers(handler):
    @handler.add(PostbackEvent)
    def handle_postback(event):
        try:
            data = event.postback.data
            user_id = event.source.user_id
            
            print(f"收到 postback 事件：{data}")  # 新增日誌
            
            # 處理確認新增作業
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
                
                # 顯示時間輸入 UI
                bubble = {
                    "type": "bubble",
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "md",
                        "contents": [
                            {"type": "text", "text": "⏰ 請輸入預估完成時間", "weight": "bold", "size": "lg"},
                            {"type": "text", "text": "或選擇歷史記錄：", "size": "sm", "color": "#888888"},
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

                messages = [
                    FlexMessage(
                        alt_text="請輸入預估完成時間",
                        contents=FlexContainer.from_dict(bubble)
                    ),
                    TextMessage(text="請輸入預估完成時間（小時），或從歷史記錄中選擇")
                ]

                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=messages
                        )
                    )
                return

            # 處理選擇作業類型
            if data.startswith("select_task_type_"):
                task_type = data.replace("select_task_type_", "")
                temp_task = get_temp_task(user_id)
                temp_task["category"] = task_type
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
                            {"type": "text", "text": "📝 作業資訊", "weight": "bold", "size": "lg"},
                            {"type": "text", "text": f"作業名稱：{temp_task.get('task', '未設定')}", "size": "md"},
                            {"type": "text", "text": f"預估時間：{temp_task.get('estimated_time', 0)} 小時", "size": "md"},
                            {"type": "text", "text": f"作業類型：{temp_task.get('category', '未設定')}", "size": "md"},
                            {"type": "separator"},
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
                return True

            # 處理選擇截止日期
            if data == "select_task_due":
                temp_task = get_temp_task(user_id)
                if not temp_task:
                    messages = [TextMessage(text="❌ 發生錯誤，請重新開始新增作業流程")]
                else:
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
                    
                    messages = [FlexMessage(
                        alt_text="確認新增作業",
                        contents=FlexContainer.from_dict(bubble)
                    )]
                
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=messages
                        )
                    )
                return True

            # 處理不設定截止日期
            elif data == "no_due_date":
                temp_task = get_temp_task(user_id)
                if not temp_task:
                    messages = [TextMessage(text="❌ 發生錯誤，請重新開始新增作業流程")]
                else:
                    temp_task["due"] = "未設定"
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
                    
                    messages = [FlexMessage(
                        alt_text="確認新增作業",
                        contents=FlexContainer.from_dict(bubble)
                    )]
                
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=messages
                        )
                    )
                return True

            # 處理完成作業
            if data.startswith("complete_task_"):
                try:
                    task_index = int(data.split("_")[-1])
                    tasks = load_data(user_id)
                    
                    if 0 <= task_index < len(tasks):
                        tasks[task_index]["done"] = True
                        save_data(tasks, user_id)
                        
                        # 發送確認訊息
                        messages = [
                            TextMessage(text=f"✅ 已完成任務：{tasks[task_index]['task']}")
                        ]
                        
                        with ApiClient(configuration) as api_client:
                            MessagingApi(api_client).reply_message(
                                ReplyMessageRequest(
                                    reply_token=event.reply_token,
                                    messages=messages
                                )
                            )
                        return True
                    else:
                        messages = [
                            TextMessage(text="❌ 無效的任務索引")
                        ]
                        
                        with ApiClient(configuration) as api_client:
                            MessagingApi(api_client).reply_message(
                                ReplyMessageRequest(
                                    reply_token=event.reply_token,
                                    messages=messages
                                )
                            )
                        return True
                except Exception as e:
                    logger.error(f"完成任務時發生錯誤: {str(e)}")
                    messages = [
                        TextMessage(text="❌ 完成任務時發生錯誤，請稍後再試")
                    ]
                    
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=messages
                            )
                        )
                    return True

            # 處理清除已完成作業
            if data == "clear_completed_select":
                tasks = load_data(user_id)
                completed_tasks = [(i, task) for i, task in enumerate(tasks) if task.get("done", False)]
                
                if not completed_tasks:
                    messages = [TextMessage(text="✅ 沒有已完成的作業需要清除。")]
                else:
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
                    
                    messages = [FlexMessage(
                        alt_text="選擇要清除的已完成作業",
                        contents=FlexContainer.from_dict(bubble)
                    )]
                
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=messages
                        )
                    )
                return True

            elif data == "clear_completed_all":
                tasks = load_data(user_id)
                remaining_tasks = [task for task in tasks if not task.get("done", False)]
                save_data(remaining_tasks, user_id)
                
                messages = [TextMessage(text="✅ 已清除所有已完成的作業。")]
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=messages
                        )
                    )
                return True

            # 處理清除已截止作業
            elif data == "clear_expired_select":
                now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()
                tasks = load_data(user_id)
                expired_tasks = []
                
                for i, task in enumerate(tasks):
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
                    messages = [TextMessage(text="✅ 沒有已截止的作業需要清除。")]
                else:
                    buttons = []
                    for i, task in expired_tasks:
                        buttons.append({
                            "type": "button",
                            "action": {
                                "type": "postback",
                                "label": f"🗑️ {task['task']}",
                                "data": f"delete_expired_{i}"
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
                                {"type": "text", "text": "選擇要清除的已截止作業", "weight": "bold", "size": "lg"},
                                *buttons
                            ]
                        }
                    }
                    
                    messages = [FlexMessage(
                        alt_text="選擇要清除的已截止作業",
                        contents=FlexContainer.from_dict(bubble)
                    )]
                
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=messages
                        )
                    )
                return True

            elif data == "clear_expired_all":
                now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()
                tasks = load_data(user_id)
                remaining_tasks = []
                
                for task in tasks:
                    due = task.get("due", "未設定")
                    done = task.get("done", False)
                    if done or due == "未設定":
                        remaining_tasks.append(task)
                    else:
                        try:
                            due_date = datetime.datetime.strptime(due, "%Y-%m-%d").date()
                            if due_date >= now:
                                remaining_tasks.append(task)
                        except:
                            remaining_tasks.append(task)
                
                save_data(remaining_tasks, user_id)
                
                messages = [TextMessage(text="✅ 已清除所有已截止的作業。")]
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=messages
                        )
                    )
                return True

            # 處理刪除特定已完成作業
            elif data.startswith("delete_completed_"):
                try:
                    task_index = int(data.split("_")[-1])
                    tasks = load_data(user_id)
                    
                    if 0 <= task_index < len(tasks) and tasks[task_index].get("done", False):
                        task_name = tasks[task_index]["task"]
                        del tasks[task_index]
                        save_data(tasks, user_id)
                        
                        messages = [TextMessage(text=f"✅ 已清除已完成作業：{task_name}")]
                    else:
                        messages = [TextMessage(text="❌ 無效的作業索引")]
                    
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=messages
                            )
                        )
                    return True
                except Exception as e:
                    print(f"刪除已完成作業時發生錯誤：{str(e)}")
                    messages = [TextMessage(text="❌ 刪除作業時發生錯誤，請稍後再試")]
                    
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=messages
                            )
                        )
                    return True

            # 處理刪除特定已截止作業
            elif data.startswith("delete_expired_"):
                try:
                    task_index = int(data.split("_")[-1])
                    tasks = load_data(user_id)
                    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()
                    
                    if 0 <= task_index < len(tasks):
                        task = tasks[task_index]
                        due = task.get("due", "未設定")
                        done = task.get("done", False)
                        
                        if not done and due != "未設定":
                            try:
                                due_date = datetime.datetime.strptime(due, "%Y-%m-%d").date()
                                if due_date < now:
                                    task_name = task["task"]
                                    del tasks[task_index]
                                    save_data(tasks, user_id)
                                    
                                    messages = [TextMessage(text=f"✅ 已清除已截止作業：{task_name}")]
                                else:
                                    messages = [TextMessage(text="❌ 該作業尚未截止")]
                            except:
                                messages = [TextMessage(text="❌ 日期格式錯誤")]
                        else:
                            messages = [TextMessage(text="❌ 該作業未截止或已完成")]
                    else:
                        messages = [TextMessage(text="❌ 無效的作業索引")]
                    
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=messages
                            )
                        )
                    return True
                except Exception as e:
                    print(f"刪除已截止作業時發生錯誤：{str(e)}")
                    messages = [TextMessage(text="❌ 刪除作業時發生錯誤，請稍後再試")]
                    
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=messages
                            )
                        )
                    return True

            # 處理其他 postback 事件
            action_type, task_name = parse_postback_data(data)
            if not action_type or not task_name:
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="無效的操作，請重試。")]
                        )
                    )
                return
            
            # 根據動作類型處理
            if action_type == 'done':
                handle_task_completion(event, user_id, task_name)
            elif action_type == 'delete':
                handle_task_deletion(event, user_id, task_name)
            elif action_type == 'delay':
                handle_task_delay(event, user_id, task_name)
            else:
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="不支援的操作類型。")]
                        )
                    )
                return
                
        except Exception as e:
            print(f"處理回傳事件時發生錯誤：{str(e)}")
            print(f"錯誤類型：{type(e)}")  # 新增日誌
            print(f"錯誤詳情：{str(e)}")  # 新增日誌
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="處理操作時發生錯誤，請稍後再試。")]
                    )
                )
            return

def parse_postback_data(data):
    """
    解析回傳資料
    """
    try:
        parts = data.split('_', 1)
        if len(parts) != 2:
            return None, None
        return parts[0], parts[1]
    except:
        return None, None

def handle_task_completion(event, user_id, task_name):
    """
    處理任務完成
    """
    try:
        success = update_task_status(user_id, task_name, "completed")
        if success:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f"✅ 恭喜完成任務：{task_name}")]
                    )
                )
        else:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="更新任務狀態失敗，請稍後再試。")]
                    )
                )
    except Exception as e:
        print(f"處理任務完成時發生錯誤：{str(e)}")
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="處理任務完成時發生錯誤，請稍後再試。")]
                )
            )

def handle_task_deletion(event, user_id, task_name):
    """
    處理任務刪除
    """
    try:
        success = delete_task(user_id, task_name)
        if success:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f"🗑️ 已刪除任務：{task_name}")]
                    )
                )
        else:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="刪除任務失敗，請稍後再試。")]
                    )
                )
    except Exception as e:
        print(f"處理任務刪除時發生錯誤：{str(e)}")
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="處理任務刪除時發生錯誤，請稍後再試。")]
                )
            )

def handle_task_delay(event, user_id, task_name):
    """
    處理任務延後
    """
    try:
        success = delay_task(user_id, task_name)
        if success:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f"⏰ 已延後任務：{task_name}")]
                    )
                )
        else:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="延後任務失敗，請稍後再試。")]
                    )
                )
    except Exception as e:
        print(f"處理任務延後時發生錯誤：{str(e)}")
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="處理任務延後時發生錯誤，請稍後再試。")]
                )
            )