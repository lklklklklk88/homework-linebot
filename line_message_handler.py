import os
import datetime
import re
from firebase_utils import (
    load_data, save_data, set_user_state, get_user_state,
    clear_user_state, set_temp_task, get_temp_task, clear_temp_task,
    get_task_history, update_task_history, add_task
)
from task_parser import parse_task_from_text
from intent_utils import classify_intent_by_gemini
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
        state = get_user_state(user_id) 

        # 使用 Gemini 判斷自然語言意圖
        intent = classify_intent_by_gemini(text)

        # 只有當沒有流程進行中，才進行語意判斷與快速新增
        if not state:
            intent = classify_intent_by_gemini(text)

            if intent == "add_task":
                trigger_postback(event, "add_task", "➕ 新增作業")
                return
            elif intent == "view_task":
                trigger_postback(event, "view_tasks", "📋 查看作業")
                return
            elif intent == "complete_task":
                trigger_postback(event, "complete_task", "✅ 完成作業")
                return
            elif intent == "set_reminder":
                trigger_postback(event, "set_remind_time", "⏰ 設定提醒時間")
                return
            elif intent == "clear_completed":
                trigger_postback(event, "clear_completed", "🧹 清除已完成作業")
                return
            elif intent == "clear_expired":
                trigger_postback(event, "clear_expired", "🗑️ 清除已截止作業")
                return

            # 將意圖轉為原有的指令字串
            intent_map = {
                "add_task": "新增作業",
                "view_task": "查看作業",
                "complete_task": "完成作業",
                "set_reminder": "提醒時間",
                "clear_completed": "清除已完成作業",
                "clear_expired": "清除已截止作業",
                "show_schedule": "今日排程"
            }

            if intent in intent_map:
                text = intent_map[intent]      

        # 🌟 處理使用者輸入作業名稱
        if state == "awaiting_task_name":
            temp_task = {"task": text}
            set_temp_task(user_id, temp_task)
            set_user_state(user_id, "awaiting_task_time")

            # 接著顯示「請輸入預估完成時間」的 UI
            from firebase_utils import get_task_history
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
                    ]
                }
            }

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
                            "action": {"type": "postback", "label": "➕ 新增作業", "data": "add_task"},
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "action": {"type": "postback", "label": "✅ 完成作業", "data": "complete_task"},
                            "style": "secondary"
                        },
                        {
                            "type": "button",
                            "action": {"type": "postback", "label": "⏰ 提醒時間", "data": "set_remind_time"},
                            "style": "secondary"
                        },
                        {
                            "type": "button",
                            "action": {"type": "postback", "label": "📋 查看作業", "data": "view_tasks"},
                            "style": "secondary"
                        },
                        {
                            "type": "button",
                            "action": {"type": "postback", "label": "🧹 清除已完成作業", "data": "clear_completed"},
                            "style": "primary",
                            "color": "#FF3B30"  # ← 紅色
                        },
                        {
                            "type": "button",
                            "action": {"type": "postback", "label": "🗑️ 清除已截止作業", "data": "clear_expired"},
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
        
        elif data == "show_schedule":
            from line_message_handler import get_today_schedule_for_user  # 放在函式內避免循環 import
            response = get_today_schedule_for_user(user_id)

            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=response if isinstance(response, list) else [TextMessage(text=response)]
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

def trigger_postback(event, data, label):
    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": f"👉 請點擊下方按鈕執行：{label}",
                    "wrap": True
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": label,
                        "data": data
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
                    alt_text=label,
                    contents=FlexContainer.from_dict(bubble)
                )]
            )
        )
