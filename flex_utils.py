import re

def extract_schedule_blocks(text):
    """
    強化版：從 Gemini 回傳文字中擷取時間表內容
    支援格式：
    - 20:00 ~ 20:50 任務內容（備註）
    - 13:30 - 14:00 任務內容
    - 各種括號/emoji會被移除
    """
    pattern = re.compile(r"(\d{1,2}:\d{2})\s*[\-~～]\s*(\d{1,2}:\d{2})\s*(.+)")
    matches = pattern.findall(text)
    blocks = []
    for start, end, task in matches:
        cleaned_task = re.sub(r"[（(][^）)]+[）)]", "", task)  # 移除括號
        cleaned_task = re.sub(r"[\u2600-\u26FF\u2700-\u27BF\U0001F300-\U0001FAFF]+", "", cleaned_task)
        cleaned_task = cleaned_task.strip()
        blocks.append({
            'start': start,
            'end': end,
            'task': cleaned_task
        })
    return blocks

def make_timetable_card(blocks):
    """
    接收時間段字典列表，輸出乾淨無 emoji 的 Flex Bubble 卡片
    """
    rows = []
    for block in blocks:
        start = block['start']
        end = block['end']
        task_text = block['task']

        # 移除 emoji 與雜訊（已由 extract_schedule_blocks 預清理）
        clean_text = task_text.strip()

        rows.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": f"{start} - {end}",
                    "size": "sm",
                    "color": "#555555",
                    "flex": 4
                },
                {
                    "type": "text",
                    "text": clean_text,
                    "size": "sm",
                    "color": "#111111",
                    "flex": 8,
                    "wrap": True
                }
            ]
        })

        rows.append({"type": "separator"})

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "text",
                    "text": "建議排程表",
                    "weight": "bold",
                    "size": "lg",
                    "color": "#1E88E5"
                },
                {"type": "separator"},
                *rows
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
    return {
        "type": "carousel",
        "contents": [make_schedule_card(task) for task in tasks[:10]]
    }


# 其他卡片略（保持不變）...
# make_schedule_card, make_schedule_carousel 保留原樣
