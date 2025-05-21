import os
import datetime
import re
from firebase_utils import (
    load_data, save_data, set_user_state, get_user_state,
    clear_user_state, set_temp_task, get_temp_task, clear_temp_task
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
        # 獲取用戶資料
        tasks = load_data(user_id)
        habits = {
            "prefered_morning": "閱讀、寫作",
            "prefered_afternoon": "計算、邏輯"
        }
        today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")
        available_hours = 5

        prompt = generate_schedule_prompt(user_id, tasks, habits, today, available_hours)
        raw_text = call_gemini_schedule(prompt)

        # 解析回應
        explanation, schedule_text, total_hours = parse_schedule_response(raw_text)
        
        # 生成時間表卡片
        blocks = extract_schedule_blocks(schedule_text)
        timetable_card = make_timetable_card(blocks, total_hours)
        
        # 組合回應
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
