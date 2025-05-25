import os
import datetime

from firebase_admin import db
from line_utils import get_line_display_name
from firebase_utils import (
    get_all_user_ids,
    get_remind_time,  # 未完成作業
    get_add_task_remind_time,  # 新增作業
    get_task_remind_enabled,
    get_add_task_remind_enabled,
)
from linebot.v3.messaging import MessagingApi, Configuration, TextMessage
from linebot.v3.messaging import ApiClient

configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))

def get_rounded_start_time(minutes_ahead=30):
    """
    計算四捨五入後的開始時間
    """
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    total_minutes = now.hour * 60 + now.minute + minutes_ahead
    remainder = total_minutes % 60
    rounded_minutes = total_minutes - remainder + (30 if remainder < 30 else 60)
    start_hour = (rounded_minutes // 60) % 24
    start_minute = rounded_minutes % 60
    return f"{int(start_hour):02d}:{start_minute:02d}"

def format_task_list(tasks):
    """
    格式化任務列表
    """
    task_list = []
    for i, task in enumerate(tasks, 1):
        name = task.get("task", "未命名")
        due = task.get("due", "未設定")
        est = task.get("estimated_time", "未提供")
        category = task.get("category", "未分類")
        task_list.append(f"{i}. {name}｜D: {due}｜約 {est} 小時｜分類：{category}")
    return "\n".join(task_list)

def generate_optimized_schedule_prompt(user_id, tasks, habits, today, available_hours):
    """生成優化的排程提示詞"""
    display_name = get_line_display_name(user_id)
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    start_str = get_rounded_start_time()
    
    # 分析任務急迫性
    urgent_tasks = []
    normal_tasks = []
    
    for task in tasks:
        due = task.get("due", "未設定")
        if due != "未設定":
            try:
                due_date = datetime.datetime.strptime(due, "%Y-%m-%d").date()
                days_until = (due_date - now.date()).days
                if days_until <= 2:
                    urgent_tasks.append(task)
                else:
                    normal_tasks.append(task)
            except:
                normal_tasks.append(task)
        else:
            normal_tasks.append(task)
    
    prompt = f"""
你是一位專業的時間管理顧問，請為 {display_name} 在 {today} 設計最佳學習排程。

⏰ 現在時間：{now.hour}:{now.minute:02d}
⏱️ 可用時間：{available_hours} 小時
📍 開始時間：{start_str}

🎯 排程原則：
1. 緊急任務（2天內截止）必須優先安排：{len(urgent_tasks)} 個
2. 根據專注度曲線安排任務：
   - 上午：高專注任務（{habits['preferred_morning']}）
   - 下午：中等專注任務（{habits['preferred_afternoon']}）
   - 晚上：輕鬆任務（{habits['preferred_evening']}）
3. 休息安排：{habits['break_frequency']}
4. 確保總時數不超過可用時間，並預留緩衝

請用以下格式回覆：

📝 排程說明：
[簡短說明今天的重點安排，用鼓勵的語氣]

💡 溫馨提醒：
[根據任務情況給予具體建議]

📅 今日排程

1. 🕘 {start_str} ~ XX:XX｜任務名稱｜任務類型
2. ☕ XX:XX ~ XX:XX｜短暫休息（10分鐘）
3. 📖 XX:XX ~ XX:XX｜任務名稱｜任務類型
...

✅ 今日總時長：X.X 小時

緊急任務（必須今天完成）：
{format_urgent_tasks(urgent_tasks)}

一般任務：
{format_task_list(normal_tasks)}
"""
    
    return prompt

def format_urgent_tasks(tasks):
    """格式化緊急任務"""
    if not tasks:
        return "無"
    
    urgent_list = []
    for task in tasks:
        name = task.get("task", "未命名")
        due = task.get("due", "未設定")
        est = task.get("estimated_time", 0)
        urgent_list.append(f"🚨 {name} - 截止：{due} - 需時：{est}小時")
    
    return "\n".join(urgent_list)
