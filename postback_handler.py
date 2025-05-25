import os
import datetime
import logging

from add_task_flow_manager import AddTaskFlowManager
from complete_task_flow_manager import (
    CompleteTaskFlowManager,
    handle_complete_task,
    handle_confirm_complete,
    handle_execute_complete,
    handle_batch_complete_tasks,
    handle_toggle_batch,
    handle_execute_batch_complete,
    handle_cancel_complete_task as handle_cancel_complete_task_new
)

from firebase_utils import (
    load_data, save_data, set_user_state,
    clear_user_state, set_temp_task, get_temp_task, clear_temp_task,
    get_task_history,
    update_task_history, add_task,
    save_remind_time,
    get_remind_time,  
    get_add_task_remind_time,  
    save_add_task_remind_time,  
    get_add_task_remind_enabled,  
    save_add_task_remind_enabled  
)
from firebase_admin import db
from linebot.v3.webhooks import PostbackEvent
from linebot.v3.messaging import MessagingApi, ReplyMessageRequest
from linebot.v3.messaging.models import TextMessage, FlexMessage, FlexContainer
from linebot.v3.messaging import ApiClient
from linebot.v3.messaging import Configuration


# 設定 logger
logger = logging.getLogger(__name__)

configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))

def register_postback_handlers(handler):
    # 定義所有的處理器映射
    POSTBACK_HANDLERS = {
        "add_task": handle_add_task,
        "show_schedule": handle_show_schedule,
        "view_tasks": handle_view_tasks,
        "set_remind_time": handle_set_remind_time,
        "clear_completed": handle_clear_completed,
        "clear_expired": handle_clear_expired,
        "cancel_add_task": handle_cancel_add_task,
        "confirm_add_task": handle_confirm_add_task,
        "no_due_date": handle_no_due_date,
        "cancel_set_remind": handle_cancel_set_remind,
        "clear_completed_select": handle_clear_completed_select,
        "clear_expired_select": handle_clear_expired_select,
        "cancel_clear_completed": handle_cancel_clear_completed,
        "cancel_clear_expired": handle_cancel_clear_expired,
        "clear_completed_all": handle_clear_completed_all,
        "clear_expired_all": handle_clear_expired_all,
        "set_task_remind": handle_set_task_remind,
        "set_add_task_remind": handle_set_add_task_remind,
        "toggle_add_task_remind": handle_toggle_add_task_remind,
        "complete_task": lambda u, r: CompleteTaskFlowManager.start_complete_task_flow(u, r),
        "batch_complete_tasks": lambda u, r: CompleteTaskFlowManager.handle_batch_complete(u, r),
        "cancel_complete_task": lambda u, r: CompleteTaskFlowManager.cancel_complete_task(u, r),
        "execute_batch_complete": lambda u, r: handle_execute_batch_complete(u, r),
        "cancel_schedule": handle_cancel_schedule,
    }

    SPECIAL_HANDLERS = {
        "select_task_due": lambda e, u, r: handle_select_task_due(e, u),
        "select_remind_time": lambda e, u, r: handle_select_remind_time(e, u, r),
        "select_add_task_remind_time": lambda e, u, r: handle_select_add_task_remind_time(e, u, r),
    }

    PREFIX_HANDLERS = {
        "quick_task_": handle_quick_task,           # 新增：快速選擇作業
        "history_task_": handle_history_task,      # 新增：歷史作業選擇
        "select_task_name_": handle_select_task_name,  # 保持兼容
        "select_time_": handle_select_time,
        "select_type_": handle_select_type,
        "quick_due_": handle_quick_due,             # 新增：快速截止日期
        "delete_completed_": handle_delete_completed,
        "delete_expired_": handle_delete_expired,
        "confirm_complete_": lambda d, u, r: handle_confirm_complete(d, u, r),
        "execute_complete_": lambda d, u, r: handle_execute_complete(d, u, r),
        "toggle_batch_": lambda d, u, r: handle_toggle_batch(d, u, r),
        "schedule_hours_": handle_schedule_hours,
    }

    @handler.add(PostbackEvent)
    def handle_postback(event):
        try:
            data = event.postback.data
            user_id = event.source.user_id
            reply_token = event.reply_token
            
            print(f"收到 postback 事件：{data}")
            
            # 1. 先檢查是否為特殊處理
            if data in SPECIAL_HANDLERS:
                SPECIAL_HANDLERS[data](event, user_id, reply_token)
                return
            
            # 2. 檢查是否為帶前綴的 postback
            for prefix, handler_func in PREFIX_HANDLERS.items():
                if data.startswith(prefix):
                    handler_func(data, user_id, reply_token)
                    return
            
            # 3. 檢查是否為固定的 postback
            if data in POSTBACK_HANDLERS:
                POSTBACK_HANDLERS[data](user_id, reply_token)
                return
                
            # 4. 未知的 postback
            print(f"警告：未知的 postback data: {data}")
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[TextMessage(text="❌ 無法處理此操作")]
                    )
                )
            
        except Exception as e:
            print(f"處理 postback 事件時發生錯誤：{str(e)}")
            import traceback
            traceback.print_exc()
            
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="❌ 發生錯誤，請稍後再試")]
                    )
                )

def handle_add_task(user_id, reply_token):
    """使用新的統一流程"""
    AddTaskFlowManager.start_add_task_flow(user_id, reply_token)

def handle_select_task_name(data, user_id, reply_token):
    """保持兼容性的作業名稱選擇"""
    task_name = data.replace("select_task_name_", "")
    AddTaskFlowManager.handle_task_name_selection(user_id, task_name, reply_token)

def handle_select_time(data, user_id, reply_token):
    """更新時間選擇邏輯"""
    time_value = data.replace("select_time_", "")
    AddTaskFlowManager.handle_time_selection(user_id, time_value, reply_token)

def handle_select_type(data, user_id, reply_token):
    """更新類型選擇邏輯"""
    type_value = data.replace("select_type_", "")
    AddTaskFlowManager.handle_type_selection(user_id, type_value, reply_token)

def handle_quick_due(data, user_id, reply_token):
    """新增：處理快速截止日期選擇"""
    due_date = data.replace("quick_due_", "")
    AddTaskFlowManager.handle_due_date_selection(user_id, due_date, reply_token)

def handle_no_due_date(user_id, reply_token):
    """更新不設定截止日期處理"""
    AddTaskFlowManager.handle_no_due_date(user_id, reply_token)

def handle_select_task_due(event, user_id):
    """更新日期選擇器處理"""
    date = event.postback.params.get("date", "")
    reply_token = event.reply_token
    
    if date:
        AddTaskFlowManager.handle_due_date_selection(user_id, date, reply_token)
    else:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="❌ 沒有取得日期，請重新選擇")]
                )
            )

def handle_confirm_add_task(user_id, reply_token):
    """更新確認新增處理"""
    AddTaskFlowManager.confirm_add_task(user_id, reply_token)

def handle_quick_task(data, user_id, reply_token):
    """處理快速選擇作業名稱"""
    task_name = data.replace("quick_task_", "")
    AddTaskFlowManager.handle_task_name_selection(user_id, task_name, reply_token, is_quick=True)

def handle_history_task(data, user_id, reply_token):
    """處理歷史作業名稱選擇"""
    task_name = data.replace("history_task_", "")
    AddTaskFlowManager.handle_task_name_selection(user_id, task_name, reply_token)

def handle_quick_due(data, user_id, reply_token):
    """處理快速選擇截止日期"""
    due_date = data.replace("quick_due_", "")
    temp_task = get_temp_task(user_id)
    temp_task["due"] = due_date
    set_temp_task(user_id, temp_task)
    
    # 直接顯示確認畫面
    reply_bubble = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "✅ 確認新增作業",
                    "color": "#FFFFFF",
                    "size": "lg",
                    "weight": "bold"
                }
            ],
            "backgroundColor": "#10B981",
            "paddingAll": "15px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "📝", "flex": 0},
                        {"type": "text", "text": "作業名稱", "flex": 2, "color": "#6B7280"},
                        {"type": "text", "text": temp_task.get('task', '未設定'), "flex": 3, "weight": "bold"}
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "⏰", "flex": 0},
                        {"type": "text", "text": "預估時間", "flex": 2, "color": "#6B7280"},
                        {"type": "text", "text": f"{temp_task.get('estimated_time', 0)} 小時", "flex": 3, "weight": "bold"}
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "📚", "flex": 0},
                        {"type": "text", "text": "作業類型", "flex": 2, "color": "#6B7280"},
                        {"type": "text", "text": temp_task.get('category', '未設定'), "flex": 3, "weight": "bold"}
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "📅", "flex": 0},
                        {"type": "text", "text": "截止日期", "flex": 2, "color": "#6B7280"},
                        {"type": "text", "text": temp_task.get('due', '未設定'), "flex": 3, "weight": "bold"}
                    ]
                }
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
                    "style": "primary",
                    "color": "#10B981"
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

def handle_cancel_add_task(user_id, reply_token):
    """更新取消處理"""
    AddTaskFlowManager.cancel_add_task(user_id, reply_token)

def handle_confirm_complete(data, user_id, reply_token):
    """處理確認完成單一作業"""
    try:
        task_index = int(data.replace("confirm_complete_", ""))
        CompleteTaskFlowManager.handle_confirm_complete(user_id, task_index, reply_token)
    except ValueError:
        print(f"無效的作業索引：{data}")
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="❌ 無效的作業編號")]
                )
            )

def handle_execute_complete(data, user_id, reply_token):
    """執行完成作業"""
    try:
        task_index = int(data.replace("execute_complete_", ""))
        CompleteTaskFlowManager.execute_complete_task(user_id, task_index, reply_token)
    except ValueError:
        print(f"無效的作業索引：{data}")
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="❌ 無效的作業編號")]
                )
            )

def handle_toggle_batch(data, user_id, reply_token):
    """處理 toggle 選項，委託給流程管理器統一處理邏輯（切換選擇 + 更新畫面）"""
    try:
        task_index = int(data.replace("toggle_batch_", ""))
        CompleteTaskFlowManager.handle_toggle_batch_selection(user_id, task_index, reply_token)
    except Exception as e:
        print(f"批次選擇錯誤：{e}")
        CompleteTaskFlowManager._send_error(reply_token)


def handle_execute_batch_complete(user_id, reply_token):
    CompleteTaskFlowManager.execute_batch_complete(user_id, reply_token)


def handle_show_schedule(user_id, reply_token):
    """開始排程流程 - 先詢問剩餘時間"""
    
    # 設定使用者狀態為等待輸入剩餘時間
    set_user_state(user_id, "awaiting_available_hours")
    
    # 快速時間選項
    quick_hours_options = ["2小時", "3小時", "4小時", "5小時", "6小時", "7小時", "8小時"]
    hour_buttons = []
    
    for hours in quick_hours_options:
        hour_buttons.append({
            "type": "button",
            "action": {
                "type": "postback",
                "label": f"⏰ {hours}",
                "data": f"schedule_hours_{hours.replace('小時', '')}"
            },
            "style": "secondary",
            "color": "#4A90E2"
        })
    
    bubble = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "📅 安排今日排程",
                    "color": "#FFFFFF",
                    "size": "xl",
                    "weight": "bold"
                }
            ],
            "backgroundColor": "#FF6B6B",
            "paddingAll": "20px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "lg",
            "contents": [
                {
                    "type": "text",
                    "text": "您今天還有多少時間可以安排作業？",
                    "size": "md",
                    "weight": "bold",
                    "color": "#333333"
                },
                {
                    "type": "text",
                    "text": "💡 我會根據您的時間和作業優先順序，為您安排最佳的學習計畫",
                    "size": "sm",
                    "color": "#666666",
                    "wrap": True,
                    "margin": "sm"
                },
                {
                    "type": "separator",
                    "margin": "lg"
                },
                {
                    "type": "text",
                    "text": "⚡ 快速選擇",
                    "size": "sm",
                    "weight": "bold",
                    "color": "#4B5563"
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "margin": "sm",
                    "contents": hour_buttons[:4]  # 第一行顯示4個
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "margin": "sm",
                    "contents": hour_buttons[4:]  # 第二行顯示剩餘的
                },
                {
                    "type": "text",
                    "text": "或直接輸入時數（例如：4.5）",
                    "size": "xs",
                    "color": "#888888",
                    "margin": "lg",
                    "align": "center"
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "❌ 取消",
                        "data": "cancel_schedule"
                    },
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
                    alt_text="設定可用時間",
                    contents=FlexContainer.from_dict(bubble)
                )]
            )
        )

def handle_view_tasks(user_id, reply_token):
    """顯示作業列表為一頁式表格"""
    tasks = load_data(user_id)
    if not tasks:
        reply = "目前沒有任何作業。"
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)])
            )
        return

    # 創建表格內容
    table_contents = [
        {"type": "text", "text": "📋 作業列表", "weight": "bold", "size": "xl", "color": "#1DB446"},
        {"type": "separator", "margin": "md"}
    ]
    
    # 統計資訊
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.get("done", False)])
    pending_tasks = total_tasks - completed_tasks
    
    # 添加統計資訊
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
                ],
                "flex": 1
            },
            {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": str(pending_tasks), "size": "xl", "weight": "bold", "align": "center", "color": "#FF5551"},
                    {"type": "text", "text": "待完成", "size": "sm", "color": "#666666", "align": "center"}
                ],
                "flex": 1
            },
            {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": str(completed_tasks), "size": "xl", "weight": "bold", "align": "center", "color": "#1DB446"},
                    {"type": "text", "text": "已完成", "size": "sm", "color": "#666666", "align": "center"}
                ],
                "flex": 1
            }
        ]
    }
    table_contents.append(stats_box)
    table_contents.append({"type": "separator", "margin": "md"})
    
    # 添加表格標題行
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
    
    # 添加每個作業的行
    for i, task in enumerate(tasks):
        # 處理作業狀態和顏色
        is_done = task.get("done", False)
        due_date = task.get("due", "未設定")
        
        # 判斷是否過期
        is_expired = False
        if due_date != "未設定" and not is_done:
            try:
                due_datetime = datetime.datetime.strptime(due_date, "%Y-%m-%d").date()
                now_date = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()
                is_expired = due_datetime < now_date
            except:
                pass
        
        # 設定狀態文字和顏色
        if is_done:
            status_text = "✅"
            status_color = "#1DB446"
        elif is_expired:
            status_text = "⏰"
            status_color = "#FF5551"
        else:
            status_text = "⏳"
            status_color = "#FFAA00"
        
        # 處理截止日期顯示
        due_display = due_date if due_date != "未設定" else "-"
        if due_date != "未設定":
            try:
                due_datetime = datetime.datetime.strptime(due_date, "%Y-%m-%d")
                due_display = due_datetime.strftime("%m/%d")
            except:
                due_display = "(未設定)"   # 解析失敗也給未設定
        else:
            due_display = "(未設定)"
        
        # 創建作業行
        task_row = {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "margin": "sm",
            "contents": [
                {
                    "type": "text",
                    "text": task.get("task", "未命名"),
                    "size": "sm",
                    "flex": 2,
                    "wrap": True,
                    "color": "#666666" if is_done else "#333333"
                },
                {
                    "type": "text",
                    "text": task.get("category", "-"),
                    "size": "xs",
                    "flex": 1,
                    "align": "center",
                    "color": "#888888"
                },
                {
                    "type": "text",
                    "text": f"{task.get('estimated_time', 0)}h",
                    "size": "xs",
                    "flex": 1,
                    "align": "center",
                    "color": "#888888"
                },
                {
                    "type": "text",
                    "text": due_display if due_date != "未設定" else "未設定",
                    "size": "xs",
                    "flex": 1,
                    "align": "center",
                    "color": "#FF5551" if is_expired else "#888888"
                },
                {
                    "type": "text",
                    "text": status_text,
                    "size": "sm",
                    "flex": 1,
                    "align": "center",
                    "color": status_color
                }
            ]
        }
        
        table_contents.append(task_row)
        # 添加分隔線（除了最後一個）
        if i < len(tasks) - 1:
            table_contents.append({"type": "separator", "margin": "sm", "color": "#EEEEEE"})
    
    # 創建完整的卡片
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
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "✅ 完成作業", "data": "complete_task"},
                    "style": "primary",
                    "flex": 1
                },
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "➕ 新增作業", "data": "add_task"},
                    "style": "secondary",
                    "flex": 1
                }
            ]
        }
    }
    
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[FlexMessage(
                    alt_text="作業列表",
                    contents=FlexContainer.from_dict(bubble)
                )]
            )
        )

def handle_select_remind_time(event, user_id, reply_token):
    try:
        time_param = event.postback.params.get("time", "")
        if not time_param:
            reply = "❌ 未取得提醒時間，請重新選擇"
        else:
            # 確保 save_remind_time 函數正常工作
            try:
                save_remind_time(user_id, time_param)
                reply = f"⏰ 已設定提醒時間為：{time_param}"
            except Exception as e:
                print(f"保存提醒時間失敗：{e}")
                reply = "❌ 保存提醒時間失敗，請稍後再試"

    except Exception as e:
        print(f"選擇提醒時間錯誤：{e}")
        reply = "❌ 設定提醒時間時發生錯誤"

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
                    "style": "primary",
                    "color": "#FF3B30"  # ← 紅色
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
                    "style": "primary",
                    "color": "#FF3B30"  # ← 紅色
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
                
                # 記錄今天已新增作業
                today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")
                db.reference(f"users/{user_id}/last_add_task_date").set(today)
                
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

def handle_set_remind_time(user_id, reply_token):
    """顯示提醒設定選擇介面"""
    try:
        bubble = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "⏰ 提醒設定",
                        "color": "#FFFFFF",
                        "size": "xl",
                        "weight": "bold"
                    }
                ],
                "backgroundColor": "#FF6B6B",
                "paddingAll": "20px"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "lg",
                "contents": [
                    {
                        "type": "text",
                        "text": "請選擇要設定的提醒類型",
                        "size": "md",
                        "color": "#333333",
                        "weight": "bold"
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "md",
                        "contents": [
                            {
                                "type": "button",
                                "action": {
                                    "type": "postback",
                                    "label": "📋 未完成作業提醒",
                                    "data": "set_task_remind"
                                },
                                "style": "secondary",
                                "height": "sm"
                            },
                            {
                                "type": "button",
                                "action": {
                                    "type": "postback",
                                    "label": "📝 每日新增作業提醒",
                                    "data": "set_add_task_remind"
                                },
                                "style": "secondary",
                                "height": "sm"
                            }
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "lg",
                        "contents": [
                            {
                                "type": "text",
                                "text": "💡 小提示",
                                "size": "sm",
                                "color": "#666666",
                                "weight": "bold"
                            },
                            {
                                "type": "text",
                                "text": "• 未完成作業提醒：每天提醒您待辦的作業",
                                "size": "xs",
                                "color": "#888888",
                                "wrap": True,
                                "margin": "sm"
                            },
                            {
                                "type": "text",
                                "text": "• 每日新增作業提醒：提醒您今天記錄作業",
                                "size": "xs",
                                "color": "#888888",
                                "wrap": True,
                                "margin": "sm"
                            }
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "❌ 取消",
                            "data": "cancel_set_remind"
                        },
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
                        alt_text="提醒設定",
                        contents=FlexContainer.from_dict(bubble)
                    )]
                )
            )
            
    except Exception as e:
        print(f"設定提醒時間功能錯誤：{e}")
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="❌ 提醒時間功能發生錯誤，請稍後再試")]
                )
            )

def handle_set_task_remind(user_id, reply_token):
    """設定未完成作業提醒時間"""
    try:
        now_time = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%H:%M")
        current_remind_time = get_remind_time(user_id)
        
        bubble = {
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "📋 未完成作業提醒",
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
                        "text": f"目前提醒時間：{current_remind_time}",
                        "size": "md",
                        "weight": "bold",
                        "color": "#333333"
                    },
                    {
                        "type": "text",
                        "text": "每天在設定的時間提醒您未完成的作業",
                        "size": "sm",
                        "color": "#666666",
                        "wrap": True
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "datetimepicker",
                            "label": "⏰ 選擇新的提醒時間",
                            "data": "select_remind_time",
                            "mode": "time",
                            "initial": current_remind_time,
                            "max": "23:59",
                            "min": "00:00"
                        },
                        "style": "primary",
                        "margin": "lg"
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "← 返回",
                            "data": "set_remind_time"
                        },
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
                        alt_text="設定未完成作業提醒",
                        contents=FlexContainer.from_dict(bubble)
                    )]
                )
            )
    except Exception as e:
        print(f"設定未完成作業提醒錯誤：{e}")

def handle_set_add_task_remind(user_id, reply_token):
    """設定新增作業提醒"""
    try:
        current_time = get_add_task_remind_time(user_id)
        is_enabled = get_add_task_remind_enabled(user_id)
        
        bubble = {
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "📝 新增作業提醒",
                        "color": "#FFFFFF",
                        "size": "lg",
                        "weight": "bold"
                    }
                ],
                "backgroundColor": "#00BFA5",
                "paddingAll": "15px"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {
                                "type": "text",
                                "text": "提醒狀態：",
                                "size": "md",
                                "color": "#333333",
                                "flex": 0
                            },
                            {
                                "type": "text",
                                "text": "已啟用" if is_enabled else "已停用",
                                "size": "md",
                                "weight": "bold",
                                "color": "#00BFA5" if is_enabled else "#FF6B6B",
                                "flex": 0,
                                "margin": "sm"
                            }
                        ]
                    },
                    {
                        "type": "text",
                        "text": f"提醒時間：{current_time}",
                        "size": "md",
                        "color": "#333333"
                    },
                    {
                        "type": "text",
                        "text": "每天提醒您記錄今天的作業",
                        "size": "sm",
                        "color": "#666666",
                        "wrap": True,
                        "margin": "sm"
                    },
                    {
                        "type": "separator",
                        "margin": "lg"
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "margin": "lg",
                        "contents": [
                            {
                                "type": "button",
                                "action": {
                                    "type": "postback",
                                    "label": "🔔 啟用提醒" if not is_enabled else "🔕 停用提醒",
                                    "data": "toggle_add_task_remind"
                                },
                                "style": "primary" if not is_enabled else "secondary",
                                "color": "#00BFA5" if not is_enabled else "#FF6B6B"
                            },
                            {
                                "type": "button",
                                "action": {
                                    "type": "datetimepicker",
                                    "label": "⏰ 變更提醒時間",
                                    "data": "select_add_task_remind_time",
                                    "mode": "time",
                                    "initial": current_time,
                                    "max": "23:59",
                                    "min": "00:00"
                                },
                                "style": "secondary"
                            }
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "← 返回",
                            "data": "set_remind_time"
                        },
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
                        alt_text="設定新增作業提醒",
                        contents=FlexContainer.from_dict(bubble)
                    )]
                )
            )
    except Exception as e:
        print(f"設定新增作業提醒錯誤：{e}")

def handle_toggle_add_task_remind(user_id, reply_token):
    """切換新增作業提醒狀態"""
    try:
        current_status = get_add_task_remind_enabled(user_id)
        new_status = not current_status
        save_add_task_remind_enabled(user_id, new_status)
        
        if new_status:
            reply = "🔔 已啟用新增作業提醒！\n每天都會提醒您記錄作業喔～"
        else:
            reply = "🔕 已停用新增作業提醒。"
        
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=reply)]
                )
            )
            
        # 重新顯示設定介面
        handle_set_add_task_remind(user_id, reply_token)
        
    except Exception as e:
        print(f"切換新增作業提醒狀態失敗：{e}")

def handle_select_add_task_remind_time(event, user_id, reply_token):
    """處理新增作業提醒時間選擇"""
    try:
        time_param = event.postback.params.get("time", "")
        if not time_param:
            reply = "❌ 未取得提醒時間，請重新選擇"
        else:
            try:
                save_add_task_remind_time(user_id, time_param)
                reply = f"✅ 新增作業提醒時間已設定為：{time_param}"
            except Exception as e:
                print(f"保存新增作業提醒時間失敗：{e}")
                reply = "❌ 保存提醒時間失敗，請稍後再試"

    except Exception as e:
        print(f"選擇新增作業提醒時間錯誤：{e}")
        reply = "❌ 設定提醒時間時發生錯誤"

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply)])
        )

def handle_schedule_hours(data, user_id, reply_token):
    """處理快速選擇的時數"""
    hours = float(data.replace("schedule_hours_", ""))
    
    # 清除狀態
    clear_user_state(user_id)
    
    # 生成排程
    from line_message_handler import generate_schedule_for_user
    response = generate_schedule_for_user(user_id, hours)
    
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=response if isinstance(response, list) else [TextMessage(text=response)]
            )
        )

def handle_cancel_schedule(user_id, reply_token):
    """取消排程設定"""
    clear_user_state(user_id)
    
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="❌ 已取消排程設定")]
            )
        )