import datetime

def generate_gemini_prompt(user_id, tasks, habits, today, available_hours):
    prompt = f"""你是一位作業規劃助理，請幫使用者 {user_id} 規劃今天 {today} 的最佳工作分配表。
請根據使用者習慣、各作業的截止日與預估時間，安排一份不超過 {available_hours} 小時的工作計畫。
若時間不夠，請明確指出哪些任務將無法完成。

🧠 使用者偏好：
- 上午：{habits.get('prefered_morning', '未提供')}
- 下午：{habits.get('prefered_afternoon', '未提供')}

📋 作業清單：
"""
    for i, task in enumerate(tasks, 1):
        name = task.get("task", "未命名")
        due = task.get("due", "未設定")
        est = task.get("estimated_time", "未知時間")
        category = task.get("category", "未分類")
        prompt += f"{i}. {name}｜截止日：{due}｜預估時間：{est} 小時｜類型：{category}\n"

    prompt += "\n請給出：\n1. 今日的任務排程（含時間段與順序）\n2. 若任務無法完成請註明\n3. 如有必要，建議休息時間"
    return prompt
