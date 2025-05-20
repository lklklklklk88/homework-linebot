import re
import datetime

def extract_schedule_blocks(text):
    """
    從 Gemini 回傳文字中擷取時間表內容
    支援多種格式：
    1. 09:30 - 10:30｜寫 C# 判斷式｜60分鐘｜類型：高專注
    2. 09:30 - 10:30 寫 C# 判斷式（60分鐘）
    3. 09:30 - 10:30 寫 C# 判斷式
    """
    blocks = []
    
    # 嘗試第一種格式（完整格式）
    pattern1 = re.compile(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\s*｜(.+?)\s*｜(\d+)分鐘\s*｜類型：(.+)")
    matches1 = pattern1.findall(text)
    if matches1:
        for start, end, task, duration, category in matches1:
            blocks.append({
                'start': start,
                'end': end,
                'task': task,
                'duration': f"{duration}分鐘",
                'category': category
            })
        return blocks
    
    # 嘗試第二種格式（帶括號的時長）
    pattern2 = re.compile(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\s*(.+?)\s*（(\d+)分鐘）")
    matches2 = pattern2.findall(text)
    if matches2:
        for start, end, task, duration in matches2:
            blocks.append({
                'start': start,
                'end': end,
                'task': task,
                'duration': f"{duration}分鐘",
                'category': "未分類"
            })
        return blocks
    
    # 嘗試第三種格式（簡單格式）
    pattern3 = re.compile(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\s*(.+)")
    matches3 = pattern3.findall(text)
    if matches3:
        for start, end, task in matches3:
            # 計算時長
            start_time = datetime.datetime.strptime(start, "%H:%M")
            end_time = datetime.datetime.strptime(end, "%H:%M")
            duration_minutes = int((end_time - start_time).total_seconds() / 60)
            
            blocks.append({
                'start': start,
                'end': end,
                'task': task.strip(),
                'duration': f"{duration_minutes}分鐘",
                'category': "未分類"
            })
        return blocks
    
    return blocks

def make_timetable_card(blocks, total_hours):
    """
    製作時間表卡片，包含任務列表和操作按鈕
    """
    rows = []
    for idx, block in enumerate(blocks, start=1):
        time_range = f"{block['start']} - {block['end']}"
        task_text = block['task']
        duration = block.get('duration', '')
        category = block.get('category', '')

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
                    "text": time_range,
                    "size": "sm",
                    "flex": 4,
                    "color": "#1E88E5"
                },
                {
                    "type": "text",
                    "text": task_text,
                    "size": "sm",
                    "flex": 6,
                    "wrap": True,
                    "color": "#111111"
                },
                {
                    "type": "text",
                    "text": f"{duration}｜{category}",
                    "size": "sm",
                    "flex": 4,
                    "color": "#666666"
                }
            ]
        })

        # 添加操作按鈕
        rows.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "✅ 完成",
                        "data": f"complete_task_{idx}"
                    },
                    "style": "primary",
                    "color": "#4CAF50",
                    "flex": 1
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "⏰ 延後",
                        "data": f"delay_task_{idx}"
                    },
                    "style": "secondary",
                    "flex": 1
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "🗑️ 刪除",
                        "data": f"delete_task_{idx}"
                    },
                    "style": "secondary",
                    "color": "#FF3B30",
                    "flex": 1
                }
            ],
            "spacing": "sm",
            "margin": "sm"
        })

        rows.append({"type": "separator"})

    # 添加總時數資訊
    total_hours_text = f"⏱️ 今日任務總長：{total_hours}小時"
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
                    "text": "🕘 建議排程",
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
