import os
import datetime
import re
from firebase_utils import (
    load_data, save_data, set_user_state, get_user_state,
    clear_user_state, set_temp_task, get_temp_task, clear_temp_task,
    get_task_history, update_task_history, add_task
)
from postback_handler import (
    handle_add_task,
    handle_show_schedule,
    handle_complete_task_direct,
    handle_view_tasks,
    handle_set_remind_time,
    handle_clear_completed,
    handle_clear_expired
)
from flex_utils import (
    make_time_history_bubble,
    make_type_history_bubble,
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

# === ➊ 處理「手寫作業名稱」 ================================
def handle_task_name_input(user_id: str, text: str, reply_token: str):
    """
    使用者輸入作業名稱 → 儲存暫存資料 → 切換 state → 推送「請輸入預估時間」卡片
    """
    temp_task = {"task": text}
    set_temp_task(user_id, temp_task)
    set_user_state(user_id, "awaiting_task_time")

    # 讀取時間歷史（最多 3 筆）
    _, _, time_history = get_task_history(user_id)
    buttons = [{
        "type": "button",
        "action": {"type": "postback", "label": t, "data": f"select_time_{t.replace('小時', '')}"},
        "style": "secondary"
    } for t in time_history[-3:]]

    bubble = make_time_history_bubble(time_history)

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    FlexMessage(alt_text="請輸入預估完成時間",
                                contents=FlexContainer.from_dict(bubble)),
                    TextMessage(text="請輸入預估完成時間（小時）：")
                ]
            )
        )

# === ➋ 處理「手寫預估時間」 ================================
def handle_estimated_time_input(user_id: str, text: str, reply_token: str):
    """
    使用者輸入預估時間 → 更新 temp_task → 切換 state → 推送「請輸入作業類型」卡片
    """
    try:
        hours = _parse_hours(text.strip())
    except ValueError:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[
                        TextMessage(text="⚠️ 請輸入有效的時間，例如 2、2.5、2小時、兩小時")
                    ]
                )
            )
        return

    temp_task = get_temp_task(user_id) or {}
    temp_task["estimated_time"] = hours
    set_temp_task(user_id, temp_task)
    set_user_state(user_id, "awaiting_task_type")

    name_history, type_history, _ = get_task_history(user_id)
    buttons = [{
        "type": "button",
        "action": {"type": "postback", "label": t, "data": f"select_type_{t}"},
        "style": "secondary"
    } for t in type_history[-3:]]

    bubble = make_type_history_bubble(type_history)

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    FlexMessage(alt_text="請輸入作業類型",
                                contents=FlexContainer.from_dict(bubble)),
                    TextMessage(text="請輸入作業類型：")
                ]
            )
        )

# === ➌ 處理「手寫作業類型」 ================================
def handle_task_type_input(user_id: str, text: str, reply_token: str):
    """
    使用者輸入作業類型 → 更新 temp_task → 切到選截止日期 state → 推送日期選擇器
    """
    temp_task = get_temp_task(user_id) or {}
    temp_task["category"] = text.strip()
    set_temp_task(user_id, temp_task)
    set_user_state(user_id, "awaiting_task_due")

    today = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=8))
    ).strftime("%Y-%m-%d")

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "md",
            "contents": [
                {"type": "text", "text": "📅 請選擇截止日期", "weight": "bold", "size": "md"},
                {"type": "button",
                 "action": {"type": "datetimepicker", "label": "📅 選擇日期",
                            "data": "select_task_due", "mode": "date",
                            "initial": today, "max": "2099-12-31", "min": today},
                 "style": "primary"},
                {"type": "button",
                 "action": {"type": "postback", "label": "❌ 不設定截止日期", "data": "no_due_date"},
                 "style": "secondary"},
                {"type": "button",
                 "action": {"type": "postback", "label": "❌ 取消", "data": "cancel_add_task"},
                 "style": "secondary"}
            ]
        }
    }

    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    FlexMessage(
                        alt_text="請選擇截止日期",
                        contents=FlexContainer.from_dict(bubble)
                    )
                ]
            )
        )

def register_message_handlers(handler):
    @handler.add(MessageEvent)
    def handle_message(event):

        user_id = event.source.user_id

        if event.message.type != 'text':
            return

        text = event.message.text.strip()
        state = get_user_state(user_id) 

        # ============= 修復區域：處理用戶狀態 =============
        # 如果用戶正在進行新增作業流程，優先處理狀態相關的輸入
        if state == "awaiting_task_name":
            handle_task_name_input(user_id, text, event.reply_token)
            return
        elif state == "awaiting_task_time":
            handle_estimated_time_input(user_id, text, event.reply_token)
            return
        elif state == "awaiting_task_type":
            handle_task_type_input(user_id, text, event.reply_token)
            return
        # ===============================================
    
        # 只有在沒有狀態時才進行意圖分類
        intent = None
        if not state:
            intent = classify_intent_by_gemini(text)

            if intent == "add_task":
                handle_add_task(user_id, event.reply_token)
                return
            elif intent == "view_tasks":
                handle_view_tasks(user_id, event.reply_token)
                return
            elif intent == "complete_task":
                handle_complete_task_direct(user_id, event.reply_token)
                return
            elif intent == "set_reminder":
                handle_set_remind_time(user_id, event.reply_token)
                return
            elif intent == "clear_completed":
                handle_clear_completed(user_id, event.reply_token)
                return
            elif intent == "clear_expired":
                handle_clear_expired(user_id, event.reply_token)
                return
            elif intent == "show_schedule":
                handle_show_schedule(user_id, event.reply_token)
                return 
        
        # 處理固定指令
        if text == "操作":
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

        # 如果沒有匹配到任何處理邏輯，可以給個預設回應
        if not state and not intent:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[
                            TextMessage(text="😊 您好！輸入「操作」可以查看所有功能，或直接說出您想要做的事情（例如：新增作業、查看作業等）")
                        ]
                    )
                )

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

def _parse_hours(raw: str) -> float:
    # 將全形數字轉半形
    trans = str.maketrans("０１２３４５６７８９．", "0123456789.")
    raw = raw.translate(trans)

    # 先找阿拉伯數字
    m = re.search(r"(\d+(?:\.\d+)?)", raw)
    if m:
        return float(m.group(1))

    # 改進的中文數字處理
    zh_map = {
        "零":0, "一":1, "二":2, "兩":2, "三":3, "四":4, 
        "五":5, "六":6, "七":7, "八":8, "九":9, "十":10,
        "半":0.5, "個半":1.5, "點":0, "點五":0.5
    }
    
    # 處理 "一個半小時" 這類特殊情況
    if "個半" in raw:
        # 提取 "X個半" 的 X
        match = re.search(r"([一二三四五六七八九十]+)個半", raw)
        if match:
            num_str = match.group(1)
            base_num = zh_map.get(num_str, 0)
            return base_num + 0.5
    
    # 處理一般中文數字
    total = 0
    for ch in raw:
        if ch in zh_map:
            total += zh_map[ch]
    
    if total > 0:
        return float(total)

    # 仍然失敗就拋例外
    raise ValueError(f"無法解析時間：{raw}")