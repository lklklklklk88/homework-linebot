def generate_gemini_prompt(user_id, tasks, habits, today, available_hours):
    prompt = f"""你是一位智能任務助理，請幫使用者 {user_id} 規劃 {today}（今日）最佳工作排程。

目標：根據任務的【截止日】、【類型】與【預估時間】安排時間表，考量以下條件：

- 🧠 上午（09:00 - 12:00）：偏好 {habits.get("prefered_morning", "未提供")}
- 🧠 下午（13:00 - 17:00）：偏好 {habits.get("prefered_afternoon", "未提供")}
- ⏰ 可用時間：{available_hours} 小時
- 任務欄位包含：「名稱、截止日、預估時間、類型」，有缺則請推測或列為【預估】

---

📋 請輸出格式如下：

1️⃣ **今日任務概覽**（依照順序列出，含 emoji 與耗時）：
✔️ 英文報告（📝 寫作, 1.5h, D:5/19）
✔️ 程式作業（💻 程式, 2h, D:5/18）
✖️ 未完成：AI Project（5h）

2️⃣ **上午時段（9:00 - 12:00）**
* 09:00 - 10:30：✏️ 英文報告（寫作，1.5h, D:5/19）

3️⃣ **下午時段（13:00 - 17:00）**
* 13:30 - 15:30：💻 程式作業（2h, D:5/18）

4️⃣ **未能完成的任務**（因時間不足）：
- AI Project（5h）

5️⃣ **備註與建議：**
- 若任務耗時僅為預估，請視實際進度調整
- 建議每小時工作後安排 5~10 分鐘休息
- 可透過「完成作業」指令更新進度，或輸入「重新排程」獲得新建議

---

📚 請注意內容排版清晰、分類明確，使用者將直接看到這段文字於 LINE Bot 中。
"""
    prompt += "\n---\n📂 以下是作業清單：\n"
    for i, task in enumerate(tasks, 1):
        name = task.get("task", "未命名")
        due = task.get("due", "未設定")
        est = task.get("estimated_time", "未提供")
        category = task.get("category", "未分類")
        prompt += f"{i}. {name}｜D: {due}｜約 {est} 小時｜分類：{category}\n"
    return prompt
