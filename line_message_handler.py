import os
import datetime
import re
from firebase_utils import (
    load_data, save_data, set_user_state, get_user_state,
    clear_user_state, set_temp_task, get_temp_task, clear_temp_task,
    get_task_history, update_task_history
)

from flex_utils import make_schedule_carousel, extract_schedule_blocks, make_timetable_card, make_weekly_progress_card
from firebase_admin import db
from gemini_client import call_gemini_schedule
from scheduler import generate_schedule_prompt

from linebot.v3.webhook import MessageEvent
from linebot.v3.messaging import MessagingApi, ReplyMessageRequest, ApiClient, Configuration
from linebot.v3.messaging.models import TextMessage, FlexMessage, FlexContainer

configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))

def register_message_handlers(handler):
    @handler.add(MessageEvent)
    def handle_message(event):
        user_id = event.source.user_id

        if event.message.type != 'text':
            return

        text = event.message.text.strip()
        data = load_data(user_id)

        if handle_add_task_flow(event, user_id, text):
            return
        
        if text == "完成作業":
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
        
        elif text == "今日排程":
            response = get_today_schedule_for_user(user_id)
            if isinstance(response, list):
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=response
                        )
                    )
            else:
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                                messages=[TextMessage(text=response)]
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

        elif text == "查看進度":
            response = get_weekly_progress_for_user(user_id)
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[response]
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

def get_today_schedule_for_user(user_id):
    """
    獲取用戶今日排程
    """
    try:
        tasks = load_data(user_id)
        habits = {
            "prefered_morning": "閱讀、寫作",
            "prefered_afternoon": "計算、邏輯"
        }
        today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")
        available_hours = 5

        prompt = generate_schedule_prompt(user_id, tasks, habits, today, available_hours)
        raw_text = call_gemini_schedule(prompt)

        explanation, schedule_text, total_hours = parse_schedule_response(raw_text)
        blocks = extract_schedule_blocks(schedule_text)
        timetable_card = make_timetable_card(blocks, total_hours)
        
        messages = []
        if explanation:
            messages.append(TextMessage(text=explanation))
        if timetable_card:
            messages.append(FlexMessage(
                alt_text="📅 今日排程",
                contents=FlexContainer.from_dict(timetable_card)
            ))
        
        return messages if messages else "抱歉，無法生成排程，請稍後再試。"
    except Exception as e:
        print(f"生成排程時發生錯誤：{str(e)}")
        return "抱歉，生成排程時發生錯誤，請稍後再試。"

def get_weekly_progress_for_user(user_id):
    """
    獲取用戶週進度
    """
    try:
        progress = get_weekly_progress(user_id)
        if not progress:
            return "本週還沒有完成任何任務喔！"
        
        card = make_weekly_progress_card(
            completed_tasks=progress.get("completed_tasks", 0),
            total_hours=progress.get("total_hours", 0),
            avg_hours_per_day=progress.get("avg_hours_per_day", 0)
        )
        
        return FlexMessage(
            alt_text="本週進度",
            contents=FlexContainer.from_dict(card)
        )
        
    except Exception as e:
        print(f"獲取週進度時發生錯誤：{str(e)}")
        return "抱歉，獲取週進度時發生錯誤，請稍後再試。"

def parse_schedule_response(raw_text):
    """
    解析排程回應
    """
    print("原始回應：", raw_text)
    
    # 檢查是否包含排程標記
    if "📅 今日排程" in raw_text:
        parts = raw_text.split("📅 今日排程")
        explanation = parts[0].strip()
        schedule_text = "📅 今日排程" + parts[1].strip()
        
        # 從排程文字中提取總時數
        total_hours_match = re.search(r'✅ 今日總時長：(\d+(?:\.\d+)?)', raw_text)
        total_hours = float(total_hours_match.group(1)) if total_hours_match else 0
    else:
        # 如果沒有標記，嘗試直接解析
        lines = raw_text.strip().split('\n')
        schedule_lines = []
        explanation_lines = []
        
        for line in lines:
            if re.match(r'\d+\.\s*[^\s]+', line):
                schedule_lines.append(line)
            else:
                explanation_lines.append(line)
        
        explanation = '\n'.join(explanation_lines).strip()
        schedule_text = '\n'.join(schedule_lines).strip()
        
        # 計算總時數
        blocks = extract_schedule_blocks(schedule_text)
        total_hours = sum(float(block['duration'].replace('分鐘', '')) / 60 for block in blocks)

    return explanation, schedule_text, total_hours

def get_weekly_progress(user_id):
    """
    計算並回傳使用者的週進度
    """
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    start_of_week = now - datetime.timedelta(days=now.weekday())
    end_of_week = start_of_week + datetime.timedelta(days=6)
    
    tasks = load_data(user_id)
    completed_tasks = 0
    total_hours = 0
    
    for task in tasks:
        if task.get("done", False):
            completed_tasks += 1
            total_hours += task.get("estimated_time", 0)
    
    avg_hours_per_day = total_hours / 7 if completed_tasks > 0 else 0

    return {
        "completed_tasks": completed_tasks,
        "total_hours": total_hours,
        "avg_hours_per_day": avg_hours_per_day
    }

def handle_add_task_flow(event, user_id, text):
    """
    處理新增作業流程
    """
    state = get_user_state(user_id)
    temp_task = get_temp_task(user_id)

    # 處理取消操作
    if text == "取消":
        clear_temp_task(user_id)
        clear_user_state(user_id)
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="❌ 已取消新增作業")]
                )
            )
        return True

    if text == "新增作業":
        # 第一步：輸入作業名稱
        set_user_state(user_id, "awaiting_task_name")
        
        # 獲取歷史記錄
        name_history, _ = get_task_history(user_id)
        
        # 建立歷史記錄按鈕
        buttons = []
        for name in name_history[-3:]:  # 最多顯示3個
            buttons.append({
                "type": "button",
                "action": {
                    "type": "postback",
                    "label": name,
                    "data": f"select_task_name_{name}"
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

        # 建立 Flex Message
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
            TextMessage(text="請輸入作業名稱，或從歷史記錄中選擇")
        ]

        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=messages
                )
            )
        return True

    elif state == "awaiting_task_name":
        # 處理手動輸入的作業名稱
        temp_task = {"task": text}  # 創建新的任務字典
        set_temp_task(user_id, temp_task)
        set_user_state(user_id, "awaiting_task_time")
        
        # 第二步：選擇預估時間
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
                alt_text="選擇預估時間",
                contents=FlexContainer.from_dict(bubble)
            ),
            TextMessage(text="請輸入預估時間（小時），或從選項中選擇")
        ]

        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=messages
                )
            )
        return True

    elif state == "awaiting_task_time":
        # 處理手動輸入的時間
        try:
            hours = float(text)
            temp_task["estimated_time"] = hours
            set_temp_task(user_id, temp_task)
            set_user_state(user_id, "awaiting_task_type")
            
            # 第三步：選擇作業類型
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
            return True
        except:
            reply = "⚠️ 請輸入有效的時間（例如：1.5）"
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply)]
                    )
                )
            return True

    elif state == "awaiting_task_type":
        # 處理手動輸入的類型
        temp_task = get_temp_task(user_id)  # 重新獲取臨時任務
        if not temp_task or 'task' not in temp_task or 'estimated_time' not in temp_task:
            # 如果缺少必要資訊，重置流程
            clear_temp_task(user_id)
            clear_user_state(user_id)
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="❌ 發生錯誤，請重新開始新增作業流程")]
                    )
                )
            return True

        # 更新作業類型
        temp_task["category"] = text
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
                    {"type": "text", "text": f"作業類型：{temp_task.get('category', '未設定')}", "size": "md"}
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
        return True

    return False
