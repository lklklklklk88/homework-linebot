from line_utils import get_line_display_name

def generate_gemini_prompt(user_id, tasks, today, available_hours):
    display_name = get_line_display_name(user_id)

    prompt = f"""
你是一位擁有規劃能力與人性化口吻的任務助理，請協助 {display_name} 在 {today} 排出最佳工作計劃。

---

📌 安排規則：
- 根據【類別】與【名稱】判斷屬性（高專注型 / 可切割型 / 彈性任務）
- 優先安排今日到期任務與可用時間（{available_hours} 小時）內可完成者
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

🕘 上午排程（09:00 - 12:00）  
🌞 下午排程（13:00 - 17:00）

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
