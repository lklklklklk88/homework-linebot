import os
import datetime
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
            
            # 處理確認新增作業
            if data == "confirm_add_task":
                temp_task = get_temp_task(user_id)
                if not temp_task:
                    reply = "⚠️ 發生錯誤，請重新開始新增作業流程"
                    with ApiClient(configuration) as api_client:
                        MessagingApi(api_client).reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=reply)]
                            )
                        )
                    return

                # 更新歷史記錄
                update_task_history(user_id, temp_task["task"], temp_task["category"])
                
                # 新增作業
                add_task(user_id, temp_task)
                
                # 清除暫存資料
                clear_temp_task(user_id)
                set_user_state(user_id, None)
                
                reply = "✅ 作業已成功新增！"
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=reply)]
                        )
                    )
                return

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
                
                # 顯示時間選擇 UI
                bubble = {
                    "type": "bubble",
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "md",
                        "contents": [
                            {"type": "text", "text": "⏰ 請選擇預估完成時間", "weight": "bold", "size": "lg"},
                            {
                                "type": "button",
                                "action": {
                                    "type": "postback",
                                    "label": "30 分鐘",
                                    "data": "select_time_30"
                                },
                                "style": "secondary"
                            },
                            {
                                "type": "button",
                                "action": {
                                    "type": "postback",
                                    "label": "60 分鐘",
                                    "data": "select_time_60"
                                },
                                "style": "secondary"
                            },
                            {
                                "type": "button",
                                "action": {
                                    "type": "postback",
                                    "label": "90 分鐘",
                                    "data": "select_time_90"
                                },
                                "style": "secondary"
                            },
                            {
                                "type": "button",
                                "action": {
                                    "type": "datetimepicker",
                                    "label": "⏰ 自訂時間",
                                    "data": "select_time_custom",
                                    "mode": "time"
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
                                alt_text="選擇預估時間",
                                contents=FlexContainer.from_dict(bubble)
                            )]
                        )
                    )
                return

            # 處理選擇時間
            if data.startswith("select_time_"):
                time_str = data.replace("select_time_", "")
                if time_str == "custom":
                    return  # 自訂時間會在 datetimepicker 事件中處理
                
                hours = float(time_str) / 60  # 轉換為小時
                temp_task = get_temp_task(user_id)
                temp_task["estimated_time"] = hours
                set_temp_task(user_id, temp_task)
                set_user_state(user_id, "awaiting_task_type")
                
                # 顯示類型選擇 UI
                _, type_history = get_task_history(user_id)
                
                buttons = []
                for task_type in type_history[-3:]:  # 最多顯示3個
                    buttons.append({
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": task_type,
                            "data": f"select_task_type_{task_type}"
                        },
                        "style": "secondary"
                    })
                
                # 添加取消按鈕
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
                            {"type": "text", "text": "📚 請選擇作業類型", "weight": "bold", "size": "lg"},
                            {"type": "text", "text": "或選擇歷史記錄：", "size": "sm", "color": "#888888"},
                            *buttons
                        ]
                    }
                }

                messages = [
                    FlexMessage(
                        alt_text="請選擇作業類型",
                        contents=FlexContainer.from_dict(bubble)
                    ),
                    TextMessage(text="請輸入作業類型，或從歷史記錄中選擇")
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
                
                # 顯示確認訊息
                bubble = {
                    "type": "bubble",
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "md",
                        "contents": [
                            {"type": "text", "text": "📝 確認新增作業", "weight": "bold", "size": "lg"},
                            {"type": "text", "text": f"作業名稱：{temp_task['task']}", "size": "md"},
                            {"type": "text", "text": f"預估時間：{temp_task['estimated_time']} 小時", "size": "md"},
                            {"type": "text", "text": f"作業類型：{temp_task['category']}", "size": "md"}
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