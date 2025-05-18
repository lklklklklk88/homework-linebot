import re

def make_schedule_card(task):
    """
    將單一任務轉為 Flex Bubble 卡片格式。
    task 必須包含：task（名稱）、category、estimated_time、due
    """
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
    """
    接收任務列表，產出 Flex Carousel 多卡片格式
    """
    return {
        "type": "carousel",
        "contents": [make_schedule_card(task) for task in tasks[:10]]  # 最多顯示前10個
    }

def extract_schedule_blocks(text):
    """
    從 Gemini 回傳文字中擷取時間表內容，例如：
    "09:00 ~ 11:00 英文報告"
    "13:30 ~ 14:00 閱讀歷史資料"
    回傳格式：[{'start': '09:00', 'end': '11:00', 'task': '英文報告'}, ...]
    """
    pattern = re.compile(r"(\d{1,2}:\d{2})\s*~\s*(\d{1,2}:\d{2})\s*(.+)")
    matches = pattern.findall(text)
    blocks = []
    for start, end, task in matches:
        blocks.append({
            'start': start,
            'end': end,
            'task': task.strip()
        })
    return blocks

def make_timetable_card(blocks):
    """
    接收時間段字典列表，輸出 Flex Bubble 卡片。
    """
    rows = []
    for i, block in enumerate(blocks, 1):
        rows.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": f"{block['start']} - {block['end']}", "size": "sm", "flex": 4},
                {"type": "text", "text": block['task'], "size": "sm", "flex": 8, "wrap": True}
            ]
        })

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {"type": "text", "text": "🕘 建議排程表", "weight": "bold", "size": "md"},
                {"type": "separator"},
                *rows
            ]
        }
    }
    return bubble

