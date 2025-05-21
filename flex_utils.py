import re
import datetime

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
    
    # 匹配新格式（更寬鬆的匹配）
    pattern = re.compile(r'\d+\.\s*([^\s]+)?\s*(\d{1,2}:\d{2})\s*[~-]\s*(\d{1,2}:\d{2})\s*[｜|]\s*(.+?)(?:\s*[（(](\d+)分鐘[）)])?')
    matches = pattern.findall(text)
    
    print("匹配結果：", matches)
    
    if matches:
        for emoji, start, end, task, duration in matches:
            # 檢查任務是否包含類別
            task_parts = task.split('｜')
            task_name = task_parts[0].strip()
            category = task_parts[1].strip() if len(task_parts) > 1 else "未分類"
            
            # 如果沒有找到時長，計算時長
            if not duration:
                try:
                    start_time = datetime.datetime.strptime(start, "%H:%M")
                    end_time = datetime.datetime.strptime(end, "%H:%M")
                    duration_minutes = int((end_time - start_time).total_seconds() / 60)
                    duration = str(duration_minutes)
                except:
                    duration = "0"
            
            blocks.append({
                'start': start,
                'end': end,
                'task': task_name,
                'duration': f"{duration}分鐘",
                'category': category,
                'emoji': emoji if emoji else "🕘"
            })
        return blocks
    
    # 如果沒有匹配到新格式，嘗試更簡單的格式
    pattern_simple = re.compile(r'\d+\.\s*(\d{1,2}:\d{2})\s*[~-]\s*(\d{1,2}:\d{2})\s*(.+)')
    matches_simple = pattern_simple.findall(text)
    
    if matches_simple:
        for start, end, task in matches_simple:
            # 計算時長
            try:
                start_time = datetime.datetime.strptime(start, "%H:%M")
                end_time = datetime.datetime.strptime(end, "%H:%M")
                duration_minutes = int((end_time - start_time).total_seconds() / 60)
            except:
                duration_minutes = 0
            
            blocks.append({
                'start': start,
                'end': end,
                'task': task.strip(),
                'duration': f"{duration_minutes}分鐘",
                'category': "未分類",
                'emoji': "🕘"
            })
        return blocks
    
    return blocks

def make_timetable_card(blocks, total_hours):
    """
    製作時間表卡片，使用簡潔的表格格式
    """
    if not blocks:
        return None

    rows = []
    for idx, block in enumerate(blocks, start=1):
        time_range = f"{block['start']} ~ {block['end']}"
        task_text = block['task']
        duration = block.get('duration', '')
        category = block.get('category', '')
        
        # 根據任務類型選擇表情符號
        emoji = "🕘"  # 預設
        if "休息" in task_text:
            emoji = "🧠"
        elif "午餐" in task_text:
            emoji = "🥪"
        elif "閱讀" in category:
            emoji = "📖"
        elif "寫程式" in category:
            emoji = "💻"

        # 組合任務文字
        task_display = f"{emoji} {time_range}｜{task_text}"
        if category and category != "未分類":
            task_display += f"｜{category}"

        rows.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": f"{idx}.",
                    "size": "sm",
                    "flex": 1,
                    "color": "#666666"
                },
                {
                    "type": "text",
                    "text": f"{task_display}（{duration}）",
                    "size": "sm",
                    "flex": 9,
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
    return {
        "type": "carousel",
        "contents": [make_schedule_card(task) for task in tasks[:10]]
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

# 其他卡片略（保持不變）...
# make_schedule_card, make_schedule_carousel 保留原樣
