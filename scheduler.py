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
你是一位親切又有效率的任務助理，請針對 {display_name} 在 {today} 安排工作建議。
目前時間為 {now.hour}:{now.minute:02d}，他今天的可支配時間是 {available_hours} 小時。

請你根據任務的【類型】與【名稱】，自行判斷優先順序與安排邏輯，並以親切人性化的語氣，給出不超過 3 行的說明。
**請不要提供任務清單、補做清單或排程表，這些會由程式處理。**

以下是今日任務資料（供參考用，不需列出）：
"""

    for i, task in enumerate(tasks, 1):
        name = task.get("task", "未命名")
        due = task.get("due", "未設定")
        est = task.get("estimated_time", "未提供")
        category = task.get("category", "未分類")
        prompt += f"{i}. {name}｜D: {due}｜約 {est} 小時｜分類：{category}\n"

    return prompt.strip()