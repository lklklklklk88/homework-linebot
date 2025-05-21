import os
import datetime
from firebase_utils import (
    load_data, save_data, set_user_state, get_user_state,
    clear_user_state, set_temp_task, get_temp_task, clear_temp_task,
    update_task_status, delete_task, delay_task
)
from firebase_admin import db

from linebot.v3.webhooks import PostbackEvent
from linebot.v3.messaging import MessagingApi, ReplyMessageRequest
from linebot.v3.messaging.models import TextMessage, FlexMessage, FlexContainer
from linebot.v3.messaging import ApiClient
from linebot.v3.messaging import Configuration
from linebot.models import TextSendMessage, FlexSendMessage
from flex_utils import make_schedule_carousel

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

def handle_postback(event):
    """
    處理回傳事件
    """
    try:
        data = event.postback.data
        user_id = event.source.user_id
        
        # 解析動作類型和任務名稱
        action_type, task_name = parse_postback_data(data)
        if not action_type or not task_name:
            return TextSendMessage(text="無效的操作，請重試。")
        
        # 根據動作類型處理
        if action_type == 'done':
            return handle_task_completion(user_id, task_name)
        elif action_type == 'delete':
            return handle_task_deletion(user_id, task_name)
        elif action_type == 'delay':
            return handle_task_delay(user_id, task_name)
        else:
            return TextSendMessage(text="不支援的操作類型。")
            
    except Exception as e:
        print(f"處理回傳事件時發生錯誤：{str(e)}")
        return TextSendMessage(text="處理操作時發生錯誤，請稍後再試。")

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

def handle_task_completion(user_id, task_name):
    """
    處理任務完成
    """
    try:
        success = update_task_status(user_id, task_name, "completed")
        if success:
            return TextSendMessage(text=f"✅ 恭喜完成任務：{task_name}")
        else:
            return TextSendMessage(text="更新任務狀態失敗，請稍後再試。")
    except Exception as e:
        print(f"處理任務完成時發生錯誤：{str(e)}")
        return TextSendMessage(text="處理任務完成時發生錯誤，請稍後再試。")

def handle_task_deletion(user_id, task_name):
    """
    處理任務刪除
    """
    try:
        success = delete_task(user_id, task_name)
        if success:
            return TextSendMessage(text=f"🗑️ 已刪除任務：{task_name}")
        else:
            return TextSendMessage(text="刪除任務失敗，請稍後再試。")
    except Exception as e:
        print(f"處理任務刪除時發生錯誤：{str(e)}")
        return TextSendMessage(text="處理任務刪除時發生錯誤，請稍後再試。")

def handle_task_delay(user_id, task_name):
    """
    處理任務延後
    """
    try:
        success = delay_task(user_id, task_name)
        if success:
            return TextSendMessage(text=f"⏰ 已延後任務：{task_name}")
        else:
            return TextSendMessage(text="延後任務失敗，請稍後再試。")
    except Exception as e:
        print(f"處理任務延後時發生錯誤：{str(e)}")
        return TextSendMessage(text="處理任務延後時發生錯誤，請稍後再試。")