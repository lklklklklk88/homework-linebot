from line_utils import get_line_display_name
import datetime

def generate_gemini_prompt(user_id, tasks, habits, today, available_hours):
    display_name = get_line_display_name(user_id)

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    total_minutes = now.hour * 60 + now.minute + 30
    remainder = total_minutes % 60
    rounded_minutes = total_minutes - remainder + (30 if remainder < 30 else 60)
    start_hour = rounded_minutes // 60
    start_minute = rounded_minutes % 60
    start_str = f"{int(start_hour):02d}:{start_minute:02d}"

    prompt = f"""
你是一位親切又有效率的任務助理，請針對 {display_name} 在 {today} 規劃最佳工作排程。

目前時間為 {now.hour}:{now.minute:02d}，可支配時間為 {available_hours} 小時，請從 {start_str} 開始安排。

請先提供一段簡短的說明，解釋你如何安排這些任務，以及為什麼這樣安排。然後再提供具體的時間表。

回覆格式如下：

📝 排程說明：
[在這裡說明你的排程邏輯和建議]

🕘 建議時間表：
13:00 - 14:30 英文報告（1.5 小時）  
14:30 - 15:00 休息  
15:00 - 16:30 數學題目（2 小時）

以下是任務資料（供你安排時間順序使用）：
"""

    for i, task in enumerate(tasks, 1):
        name = task.get("task", "未命名")
        due = task.get("due", "未設定")
        est = task.get("estimated_time", "未提供")
        category = task.get("category", "未分類")
        prompt += f"{i}. {name}｜D: {due}｜約 {est} 小時｜分類：{category}\n"

    return prompt