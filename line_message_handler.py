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
    handle_clear_tasks
)
from intent_utils import classify_intent_by_gemini, parse_task_info_from_text
from flex_utils import make_optimized_schedule_card, extract_schedule_blocks
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
            elif intent == "clear_completed" or intent == "clear_expired":
                handle_clear_tasks(user_id, event.reply_token)
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
                            "action": {"type": "postback", "label": "🧹 清除作業", "data": "clear_tasks"},
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
        
        elif text == "使用說明":
            handle_user_guide(user_id, event.reply_token)
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

def parse_time_input(text):
    """
    解析使用者輸入的時間
    支援格式：
    - 純數字：4、4.5
    - 中文數字：四小時、三小時半
    - 混合格式：4小時、3.5小時
    
    返回：浮點數（小時），如果無法解析則返回 None
    """
    
    # 移除空格
    text = text.strip()
    
    # 中文數字對應表
    chinese_numbers = {
        '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
        '十': 10, '十一': 11, '十二': 12
    }
    
    try:
        # 1. 純數字（包含小數點）
        if re.match(r'^[\d.]+$', text):
            return float(text)
        
        # 2. 數字+小時（例如：4小時、3.5小時）
        match = re.match(r'^([\d.]+)\s*小時?$', text)
        if match:
            return float(match.group(1))
        
        # 3. 中文數字+小時（例如：四小時、三小時半）
        # 先處理"半"的情況
        has_half = '半' in text
        text_no_half = text.replace('半', '')
        
        # 嘗試匹配中文數字
        for chinese, number in chinese_numbers.items():
            if chinese in text_no_half:
                # 替換中文數字為阿拉伯數字
                text_no_half = text_no_half.replace(chinese, str(number))
                # 再次嘗試匹配
                match = re.match(r'^(\d+)\s*小時?$', text_no_half)
                if match:
                    hours = float(match.group(1))
                    if has_half:
                        hours += 0.5
                    return hours
        
        # 4. 特殊情況：半小時
        if text in ['半小時', '半個小時']:
            return 0.5
        
        # 5. 一個小時的各種寫法
        if text in ['一個小時', '1個小時']:
            return 1.0
            
    except ValueError:
        pass
    
    return None

def handle_available_hours_input(user_id: str, text: str, reply_token: str):
    """處理使用者輸入的可用時數"""
    try:
        # 使用 parse_time_input 函數來解析各種格式的時間輸入
        hours = parse_time_input(text)
        
        if hours is None:
            raise ValueError("無法解析時間")
        
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
        # 無法解析或超出範圍
        error_message = "❌ 請輸入有效的時間（0-24小時）\n\n支援格式：\n• 數字：4、4.5\n• 中文：四小時、三小時半\n• 混合：4小時、3.5小時"
        
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=error_message)]
                )
            )

def handle_user_guide(user_id, reply_token):
    """顯示使用說明"""
    bubble = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "📖 使用說明",
                    "color": "#FFFFFF",
                    "size": "xl",
                    "weight": "bold"
                },
                {
                    "type": "text",
                    "text": "快速上手作業管理助手",
                    "color": "#FFFFFF",
                    "size": "sm",
                    "margin": "sm"
                }
            ],
            "backgroundColor": "#6366F1",
            "paddingAll": "20px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "lg",
            "contents": [
                {
                    "type": "text",
                    "text": "🚀 快速開始",
                    "size": "md",
                    "weight": "bold",
                    "color": "#1F2937"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "text",
                            "text": "• 輸入「操作」- 查看所有功能按鈕",
                            "size": "sm",
                            "color": "#4B5563",
                            "wrap": True
                        },
                        {
                            "type": "text",
                            "text": "• 直接說話 - 用自然語言操作",
                            "size": "sm",
                            "color": "#4B5563",
                            "wrap": True
                        }
                    ]
                },
                {
                    "type": "separator",
                    "margin": "md"
                },
                {
                    "type": "text",
                    "text": "💬 自然語言範例",
                    "size": "md",
                    "weight": "bold",
                    "color": "#1F2937"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "text",
                            "text": "📝 新增作業：",
                            "size": "sm",
                            "weight": "bold",
                            "color": "#059669"
                        },
                        {
                            "type": "text",
                            "text": "「明天要交作業系統，大概3小時」",
                            "size": "xs",
                            "color": "#6B7280",
                            "wrap": True,
                            "margin": "xs"
                        },
                        {
                            "type": "text",
                            "text": "✅ 完成作業：",
                            "size": "sm",
                            "weight": "bold",
                            "color": "#DC2626",
                            "margin": "sm"
                        },
                        {
                            "type": "text",
                            "text": "「我完成作業系統了」",
                            "size": "xs",
                            "color": "#6B7280",
                            "wrap": True,
                            "margin": "xs"
                        },
                        {
                            "type": "text",
                            "text": "📋 查看作業：",
                            "size": "sm",
                            "weight": "bold",
                            "color": "#3B82F6",
                            "margin": "sm"
                        },
                        {
                            "type": "text",
                            "text": "「查看作業」或「我的作業」",
                            "size": "xs",
                            "color": "#6B7280",
                            "wrap": True,
                            "margin": "xs"
                        }
                    ]
                },
                {
                    "type": "separator",
                    "margin": "md"
                },
                {
                    "type": "text",
                    "text": "⚡ 主要功能",
                    "size": "md",
                    "weight": "bold",
                    "color": "#1F2937"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "text",
                            "text": "➕ 新增作業 - 記錄待辦事項",
                            "size": "sm",
                            "color": "#4B5563"
                        },
                        {
                            "type": "text",
                            "text": "✅ 完成作業 - 標記已完成項目",
                            "size": "sm",
                            "color": "#4B5563"
                        },
                        {
                            "type": "text",
                            "text": "📋 查看作業 - 檢視所有作業狀態",
                            "size": "sm",
                            "color": "#4B5563"
                        },
                        {
                            "type": "text",
                            "text": "⏰ 提醒設定 - 自動提醒功能",
                            "size": "sm",
                            "color": "#4B5563"
                        },
                        {
                            "type": "text",
                            "text": "📅 今日排程 - AI 智慧安排時間",
                            "size": "sm",
                            "color": "#4B5563"
                        },
                        {
                            "type": "text",
                            "text": "🧹 清除作業 - 管理舊作業",
                            "size": "sm",
                            "color": "#4B5563"
                        }
                    ]
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "button",
                            "action": {
                                "type": "postback",
                                "label": "🎯 開始使用",
                                "data": "add_task"
                            },
                            "style": "primary",
                            "color": "#6366F1",
                            "flex": 1
                        }
                    ]
                },
                {
                    "type": "text",
                    "text": "💡 隨時輸入「操作」查看完整功能列表",
                    "size": "xs",
                    "color": "#6B7280",
                    "align": "center",
                    "margin": "sm"
                }
            ]
        }
    }
    
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[FlexMessage(
                    alt_text="使用說明",
                    contents=FlexContainer.from_dict(bubble)
                )]
            )
        )