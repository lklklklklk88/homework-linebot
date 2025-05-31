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

def calculate_end_time(start_time, available_hours):
    """
    計算結束時間
    """
    try:
        start_hour, start_minute = map(int, start_time.split(':'))
        total_minutes = start_hour * 60 + start_minute + int(available_hours * 60)
        end_hour = (total_minutes // 60) % 24
        end_minute = total_minutes % 60
        return f"{end_hour:02d}:{end_minute:02d}"
    except:
        return "23:59"

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
    end_str = calculate_end_time(start_str, available_hours)
    
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
    
    # 計算總需求時間
    total_required_time = sum(task.get("estimated_time", 0) for task in tasks)
    
    prompt = f"""
你是一位專業的時間管理顧問，請為 {display_name} 在 {today} 設計最佳學習排程。

⏰ 現在時間：{now.hour}:{now.minute:02d}
⏱️ 可用時間：{available_hours} 小時（從 {start_str} 到 {end_str}）
📊 任務總需時：{total_required_time} 小時

🚨 重要限制：
1. **絕對不可超過 {available_hours} 小時的總時長**
2. 所有活動（包含作業、休息、用餐）的總時間必須 ≤ {available_hours} 小時
3. 結束時間不可超過 {end_str}

🎯 排程原則：
1. 如果任務總時間 > 可用時間：
   - 優先安排緊急任務（2天內截止）
   - 其他任務按優先級部分安排或縮短時間
   - 明確說明哪些任務今天無法完成
2. 休息時間控制：
   - 如果時間充裕（< 4小時工作）：每90分鐘休息10-15分鐘
   - 如果時間緊張（≥ 4小時工作）：每2小時休息10分鐘
   - 如果時間極度緊張：可減少休息，但至少保留1-2次5分鐘休息
3. 用餐時間（只在時間範圍內包含用餐時段時安排）：
   - 午餐（12:00-13:00）：如果時間充裕30分鐘，時間緊張15-20分鐘
   - 晚餐（18:00-19:00）：如果時間充裕30分鐘，時間緊張15-20分鐘

請用以下格式回覆：

📝 排程說明：
[說明今天的安排策略，如果有任務無法完成要明確指出]

💡 時間分配：
- 作業時間：X.X 小時
- 休息時間：X.X 小時
- 總計：{available_hours} 小時（必須等於可用時間）

📅 今日排程

1. 🕘 {start_str} ~ XX:XX｜任務名稱｜任務類型（XX分鐘）
2. ☕ XX:XX ~ XX:XX｜短暫休息（10分鐘）
...
[最後一項的結束時間必須 ≤ {end_str}]

✅ 今日總時長：{available_hours} 小時（必須完全等於可用時間）

⚠️ 未能安排的任務：
[列出今天無法完成的任務，如果全部都能安排則寫"無"]

緊急任務（必須優先安排）：
{format_urgent_tasks(urgent_tasks)}

一般任務：
{format_task_list(normal_tasks)}

記住：
- 每個時段都要標註持續時間（分鐘）
- 時間不要用 24:00 以上的格式，要用隔天的 00:00、01:00 等
- 確保所有活動時間加總 = {available_hours} 小時
- 最後一個活動必須在 {end_str} 或之前結束
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