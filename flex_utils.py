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
    接收時間段字典列表，輸出 Flex Bubble 卡片（升級美化版）
    """
    rows = []
    for block in blocks:
        task_text = block['task']
        is_done = '完成作業' in task_text

        # 判斷任務主體與完成標記
        main_text = task_text.replace('完成作業', '').strip()
        emoji = "✍️" if any(x in main_text for x in ["寫", "作", "報告"]) else "📚" if "讀" in main_text else "💻"

        # 時段主體
        if main_text:
            rows.append({
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {"type": "text", "text": f"⏰ {block['start']} - {block['end']}", "size": "sm", "color": "#666666", "flex": 5},
                    {"type": "text", "text": f"{emoji} {main_text}", "size": "sm", "color": "#111111", "flex": 7, "wrap": True}
                ]
            })

        # 補上 ✅ 完成作業提示（獨立行）
        if is_done:
            rows.append({
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {"type": "text", "text": "", "size": "sm", "flex": 5},
                    {"type": "text", "text": "✅ 完成作業", "size": "sm", "color": "#2E7D32", "flex": 7}
                ]
            })

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {"type": "text", "text": "🕘 建議排程表", "weight": "bold", "size": "lg", "color": "#1E88E5"},
                {"type": "separator"},
                *rows
            ]
        }
    }
    return bubble

# 其他卡片略（保持不變）...
# make_schedule_card, make_schedule_carousel 保留原樣
