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
        # 移除括號說明、emoji與多餘空格
        cleaned_task = re.sub(r"[（(][^）)]+[）)]", "", task)  # 括號內容
        cleaned_task = re.sub(r"[\u2600-\u26FF\u2700-\u27BF\U0001F300-\U0001FAFF]+", "", cleaned_task)  # emoji
        cleaned_task = cleaned_task.strip()
        blocks.append({
            'start': start,
            'end': end,
            'task': cleaned_task
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
