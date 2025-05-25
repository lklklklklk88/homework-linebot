import os
import datetime
import re

from add_task_flow_manager import AddTaskFlowManager
from complete_task_flow_manager import CompleteTaskFlowManager
from firebase_utils import (
    load_data, save_data, set_user_state, get_user_state,
    clear_user_state, set_temp_task, get_temp_task, clear_temp_task,
    get_task_history, update_task_history, add_task
)
from postback_handler import (
    handle_add_task,
    handle_show_schedule,
    handle_view_tasks,
    handle_set_remind_time,
    handle_clear_completed,
    handle_clear_expired
)
from task_parser import parse_task_from_text
from intent_utils import classify_intent_by_gemini, parse_task_info_from_text
from flex_utils import make_optimized_schedule_card, extract_schedule_blocks, make_timetable_card, make_weekly_progress_card
from firebase_admin import db
from gemini_client import call_gemini_schedule
from scheduler import generate_optimized_schedule_prompt
from linebot.v3.webhook import MessageEvent
from linebot.v3.messaging import MessagingApi, ReplyMessageRequest, ApiClient, Configuration
from linebot.v3.messaging.models import TextMessage, FlexMessage, FlexContainer

configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))

# 更新訊息處理器中的狀態處理函數
def handle_task_name_input(user_id: str, text: str, reply_token: str):
    """使用新的統一處理"""
    AddTaskFlowManager.handle_manual_task_name_input(user_id, text, reply_token)

def handle_estimated_time_input(user_id: str, text: str, reply_token: str):
    """使用新的統一處理"""
    AddTaskFlowManager.handle_manual_time_input(user_id, text, reply_token)

def handle_task_type_input(user_id: str, text: str, reply_token: str):
    """使用新的統一處理"""
    AddTaskFlowManager.handle_manual_type_input(user_id, text, reply_token)

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
        elif state == "awaiting_available_hours":
            handle_available_hours_input(user_id, text, event.reply_token)
            return
        # ===============================================
    
        # 只有在沒有狀態時才進行意圖分類
        intent = None
        if not state:
            intent = classify_intent_by_gemini(text)

            # 處理自然語言新增作業
            if intent == "add_task_natural":
                # 解析作業資訊
                task_info = parse_task_info_from_text(text)
                if task_info:
                    AddTaskFlowManager.handle_natural_language_add_task(user_id, text, event.reply_token, task_info)
                else:
                    # 解析失敗，回到一般新增流程
                    handle_add_task(user_id, event.reply_token)
                return
            
            # 處理自然語言完成作業
            elif intent == "complete_task_natural":
                CompleteTaskFlowManager.handle_natural_language_complete_task(user_id, text, event.reply_token)
                return
                
            elif intent == "add_task":
                handle_add_task(user_id, event.reply_token)
                return
            elif intent == "view_tasks":
                handle_view_tasks(user_id, event.reply_token)
                return
            elif intent == "complete_task":
                CompleteTaskFlowManager.start_complete_task_flow(user_id, event.reply_token)
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
                            "type": "text",
                            "text": "💡 提示：您可以直接用自然語言新增或完成作業",
                            "size": "xs",
                            "color": "#8B5CF6",
                            "wrap": True,
                            "margin": "sm"
                        },
                        {
                            "type": "separator",
                            "margin": "md"
                        },
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
                            TextMessage(text="😊 您好！我可以幫您管理作業。\n\n💡 您可以直接說：\n• 「下週一要交作業系統，大概花三小時」\n• 「我要完成作業系統」\n• 「查看作業」\n\n或輸入「操作」查看所有功能")
                        ]
                    )
                )

def generate_schedule_for_user(user_id, available_hours):
    """根據使用者可用時間生成優化的排程"""
    try:
        tasks = load_data(user_id)
        
        # 過濾出未完成的作業
        pending_tasks = [t for t in tasks if not t.get("done", False)]
        
        if not pending_tasks:
            return [TextMessage(text="😊 太棒了！您目前沒有待完成的作業。\n好好享受您的空閒時間吧！")]
        
        # 根據截止日期和優先級排序
        now_date = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()
        
        def task_priority(task):
            due = task.get("due", "未設定")
            if due == "未設定":
                return 999  # 沒有截止日期的優先級最低
            try:
                due_date = datetime.datetime.strptime(due, "%Y-%m-%d").date()
                days_until_due = (due_date - now_date).days
                return days_until_due
            except:
                return 999
        
        pending_tasks.sort(key=task_priority)
        
        # 獲取使用者習慣（可以從歷史資料分析）
        habits = analyze_user_habits(user_id)
        
        today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")
        
        # 生成排程提示詞
        prompt = generate_optimized_schedule_prompt(user_id, pending_tasks, habits, today, available_hours)
        raw_text = call_gemini_schedule(prompt)
        
        # 解析回應
        explanation, schedule_text, total_hours = parse_schedule_response(raw_text)
        blocks = extract_schedule_blocks(schedule_text)
        
        # 創建優化的排程卡片
        schedule_card = make_optimized_schedule_card(blocks, total_hours, available_hours, pending_tasks)
        
        messages = []
        if explanation:
            messages.append(TextMessage(text=explanation))
        if schedule_card:
            messages.append(FlexMessage(
                alt_text="📅 今日最佳排程",
                contents=FlexContainer.from_dict(schedule_card)
            ))
        
        return messages if messages else [TextMessage(text="抱歉，無法生成排程，請稍後再試。")]
        
    except Exception as e:
        print(f"生成排程時發生錯誤：{str(e)}")
        return [TextMessage(text="抱歉，生成排程時發生錯誤，請稍後再試。")]

def analyze_user_habits(user_id):
    """分析使用者習慣（可以根據歷史資料）"""
    # 這裡可以擴展為真實的習慣分析
    return {
        "preferred_morning": "閱讀、寫作、需要高專注的任務",
        "preferred_afternoon": "計算、程式設計",
        "preferred_evening": "複習、整理筆記",
        "break_frequency": "每90分鐘休息15分鐘"
    }

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

def handle_available_hours_input(user_id: str, text: str, reply_token: str):
    """處理使用者輸入的可用時數"""
    try:
        # 嘗試解析數字
        hours = float(text.strip())
        
        if hours <= 0 or hours > 24:
            raise ValueError("時數必須在 0-24 之間")
        
        # 清除狀態
        clear_user_state(user_id)
        
        # 生成排程
        response = generate_schedule_for_user(user_id, hours)
        
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=response if isinstance(response, list) else [TextMessage(text=response)]
                )
            )
    except ValueError:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="❌ 請輸入有效的時數（例如：4 或 4.5）")]
                )
            )