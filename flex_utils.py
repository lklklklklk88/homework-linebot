import re
import datetime

# 常數定義
TIME_RANGE_PATTERN = r'\d+\.\s*([^\s]+)?\s*(\d{1,2}:\d{2})\s*[~-]\s*(\d{1,2}:\d{2})\s*[｜|]\s*(.*?)(?:\s*[（(](\d+)分鐘[）)])?$'
EMOJI_MAP = {
    'default': '🕘',
    'meal': '🥪',
    'study': '📖',
    'rest': '🧠',
    'coding': '💻',
    'writing': '✍️',
    'reading': '📚',
    'exercise': '🏃',
    'meeting': '👥'
}

def calculate_duration(start, end):
    """
    計算時間區間的持續時間（分鐘）
    """
    try:
        start_time = datetime.datetime.strptime(start, "%H:%M")
        end_time = datetime.datetime.strptime(end, "%H:%M")
        return int((end_time - start_time).total_seconds() / 60)
    except:
        return 0

def extract_schedule_blocks(text):
    """
    從 Gemini 回傳文字中擷取時間表內容
    支援格式：
    1. 🕘 09:00 ~ 12:30｜快點完成（210 分鐘）
    2. 🥪 12:30 ~ 13:00｜午餐（30 分鐘）
    3. 📖 13:00 ~ 14:00｜作業系統｜閱讀
    """
    blocks = []
    
    # 調試訊息
    print("開始解析排程文字：", text)
    
    # 先將文字按行分割
    lines = text.strip().split('\n')
    
    for line in lines:
        # 跳過空行
        if not line.strip():
            continue
            
        # 匹配新格式
        pattern = re.compile(TIME_RANGE_PATTERN)
        match = pattern.search(line)
        
        if match:
            emoji, start, end, task, duration = match.groups()
            
            # 檢查任務是否包含類別
            task_parts = task.split('｜')
            task_name = task_parts[0].strip()
            category = task_parts[1].strip() if len(task_parts) > 1 else "未分類"
            
            # 如果沒有找到時長，計算時長
            if not duration:
                duration = str(calculate_duration(start, end))
            
            blocks.append({
                'start': start,
                'end': end,
                'task': task_name,
                'duration': f"{duration}分鐘",
                'category': category,
                'emoji': emoji if emoji else EMOJI_MAP['default']
            })
            continue
            
        # 如果沒有匹配到新格式，嘗試更簡單的格式
        pattern_simple = re.compile(r'\d+\.\s*(\d{1,2}:\d{2})\s*[~-]\s*(\d{1,2}:\d{2})\s*[｜|]\s*(.*?)(?:\s*[（(](\d+)分鐘[）)])?$')
        match_simple = pattern_simple.search(line)
        
        if match_simple:
            start, end, task, duration = match_simple.groups()
            
            # 計算時長
            if not duration:
                duration = str(calculate_duration(start, end))
            
            blocks.append({
                'start': start,
                'end': end,
                'task': task.strip(),
                'duration': f"{duration}分鐘",
                'category': "未分類",
                'emoji': EMOJI_MAP['default']
            })
    
    print("解析結果：", blocks)
    return blocks

def make_timetable_card(blocks, total_hours):
    """
    製作時間表卡片，使用簡潔的表格格式
    """
    if not blocks:
        return None

    rows = []
    for block in blocks:
        time_range = f"{block['start']} ~ {block['end']}"
        task_text = block['task']
        emoji = block.get('emoji', EMOJI_MAP['default'])
        
        # 組合任務文字，只顯示時間和任務名稱
        task_display = f"{emoji} {time_range}｜{task_text}"

        rows.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": task_display,
                    "size": "sm",
                    "wrap": True,
                    "color": "#111111"
                }
            ]
        })

    # 添加總時數資訊
    total_hours_text = f"✅ 今日總時長：{total_hours} 小時"
    if total_hours > 7:
        total_hours_text += "\n⚠️ 今天安排較滿，建議保留喘息時間"

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "text",
                    "text": "📅 今日排程",
                    "weight": "bold",
                    "size": "md"
                },
                {"type": "separator"},
                *rows,
                {
                    "type": "text",
                    "text": total_hours_text,
                    "size": "sm",
                    "color": "#666666",
                    "margin": "md"
                }
            ]
        }
    }
    return bubble

def make_schedule_card(task):
    name = task.get("task", "未命名")
    category = task.get("category", "未分類")
    time = task.get("estimated_time", "未知")
    due = task.get("due", "未設定")
    icon = "📝" if "寫" in category else "📚" if "讀" in category else "💻" if "程式" in category else "✅"

    bubble = {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {"type": "text", "text": f"{icon} {name}", "weight": "bold", "size": "lg", "wrap": True},
                {"type": "box", "layout": "baseline", "spacing": "sm", "contents": [
                    {"type": "text", "text": "⏰ 時間：", "size": "sm", "color": "#555555"},
                    {"type": "text", "text": f"{time} 小時", "size": "sm", "color": "#111111"}
                ]},
                {"type": "box", "layout": "baseline", "spacing": "sm", "contents": [
                    {"type": "text", "text": "📅 截止：", "size": "sm", "color": "#555555"},
                    {"type": "text", "text": due, "size": "sm", "color": "#111111"}
                ]},
                {"type": "box", "layout": "baseline", "spacing": "sm", "contents": [
                    {"type": "text", "text": "📚 類別：", "size": "sm", "color": "#555555"},
                    {"type": "text", "text": category, "size": "sm", "color": "#111111"}
                ]}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": [
                {"type": "button", "style": "primary", "color": "#4CAF50", "action": {"type": "postback", "label": "✅ 完成", "data": f"done_{name}"}},
                {"type": "button", "style": "secondary", "action": {"type": "postback", "label": "⏰ 延後", "data": f"delay_{name}"}},
                {"type": "button", "style": "secondary", "action": {"type": "postback", "label": "🗑 刪除", "data": f"delete_{name}"}}
            ]
        }
    }
    return bubble


def make_schedule_carousel(tasks):
    bubbles = []
    for task in tasks[:10]:
        name = task.get("task", "未命名")
        due = task.get("due", "未設定")

        bubble = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": f"📘 {name}", "weight": "bold", "size": "md", "wrap": True},
                    {"type": "text", "text": f"📅 截止：{due}", "size": "sm", "color": "#888888"}
                ]
            }
        }

        bubbles.append(bubble)

    return {
        "type": "carousel",
        "contents": bubbles
    }

def make_weekly_progress_card(completed_tasks, total_hours, avg_hours_per_day):
    """
    製作週進度卡片
    """
    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "📊 本週進度",
                    "weight": "bold",
                    "size": "lg"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "text",
                            "text": f"✅ 已完成任務：{completed_tasks} 項",
                            "size": "md"
                        },
                        {
                            "type": "text",
                            "text": f"⏱️ 總工作時數：{total_hours} 小時",
                            "size": "md"
                        },
                        {
                            "type": "text",
                            "text": f"📈 平均每日：{avg_hours_per_day:.1f} 小時",
                            "size": "md"
                        }
                    ]
                }
            ]
        }
    }
    return bubble