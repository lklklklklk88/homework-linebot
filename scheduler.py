from line_utils import get_line_display_name
import datetime

def generate_gemini_prompt(user_id, tasks, habits, today, available_hours):
    display_name = get_line_display_name(user_id)

    # 動態取得目前時間（假設為台灣時間 UTC+8）
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    current_hour = now.hour

    # 根據目前時間決定可排時間區段
    work_start = max(current_hour, 9)
    work_end = 23
    available_hours = min(available_hours, work_end - work_start)

    prompt = f"""
你是一位擁有規劃能力與人性化口吻的任務助理，請協助 {display_name} 在 {today} 排出最佳工作計劃。

---

📌 安排規則：
- 使用者今天目前時間是 {current_hour} 點，請安排 {available_hours} 小時任務於 {work_start}:00 至 {work_end}:00 之間
- 根據【類別】與【名稱】判斷屬性（高專注型 / 可切割型 / 彈性任務）
- 優先安排今日到期任務與可用時間內可完成者
- 預估時間缺失請註記為「預估」
- 超過時間上限的任務請列入「補做清單」

---

🧠 請用親切助理語氣，先說明你是如何安排今日任務的（大約 2~3 行）

---

📋 【今日任務】請依下列格式生成，每行一項（不要包含這段說明）：
✔️ 任務名稱　emoji（任務屬性, 預估時間）　截止日:日期

---

❌ 【補做清單】請依下列格式列出未安排者與原因（不要包含這段說明）：
- 任務名稱（時間, 屬性）因時間不足 / 缺資料 等原因

---

🕘 建議排程區間：{work_start}:00 ~ {work_end}:00 之間安排任務

📎 建議：每工作 1 小時休息 5~10 分鐘；可用「完成作業」標記進度。

---

📂 以下是今日任務清單（供參考，請勿直接複製）：
"""

    for i, task in enumerate(tasks, 1):
        name = task.get("task", "未命名")
        due = task.get("due", "未設定")
        est = task.get("estimated_time", "未提供")
        category = task.get("category", "未分類")
        prompt += f"{i}. {name}｜D: {due}｜約 {est} 小時｜分類：{category}\n"

    return prompt