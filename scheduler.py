def generate_gemini_prompt(user_id, tasks, habits, today, available_hours):
    prompt = f"""
你是一位智慧任務助理，請幫使用者 {user_id} 排出 {today}（今日）的最佳任務排程。
根據每項任務的：
- 截止日期（due）
- 預估完成時間（estimated_time）
- 類型（category）
- 使用者偏好（上午偏好 {habits.get("prefered_morning", "未提供")}, 下午偏好 {habits.get("prefered_afternoon", "未提供")})

請在 {available_hours} 小時內安排最大化完成的任務。
若有任務缺少預估時間，請列為「預估」。

---

📋 **今日任務總覽**（依完成順序，格式：名稱｜分類 時間 D:）
請用表格排版清楚，像這樣：
✔️ 測驗一      📝 寫作   1.5h   D:5/18
✔️ 程式練習    💻 程式   2.0h   D:5/19
❌ 未完成：
   - AI 大專專題（5h, D:5/28）
   - 背單字（D:5/20）

---

🕘 **上午排程（09:00 - 12:00）**
請列出時間段、任務內容、類型與截止日，例如：
09:00 - 10:30｜📝 測驗一（寫作 1.5h, D:5/18）

🌞 **下午排程（13:00 - 17:00）**
格式同上。

---

📌 **未完成任務清單**（因時間不足）：請簡短條列
- XX 任務（D:xx）
- YY 任務（5h, D:xx）

---

🧠 **備註與建議（條列）**：
- 建議每工作 1 小時休息 5~10 分鐘
- 任務若無預估時間將無法精準排程，建議盡早補充
- 可使用「完成作業」標記進度，或輸入「重新排程」取得最新建議

---

以下是任務清單：
"""
    for i, task in enumerate(tasks, 1):
        name = task.get("task", "未命名")
        due = task.get("due", "未設定")
        est = task.get("estimated_time", "未提供")
        category = task.get("category", "未分類")
        prompt += f"{i}. {name}｜D: {due}｜約 {est} 小時｜分類：{category}\n"

    return prompt


#  這段用來Debug Gemini的
#  
# @app.route("/generate_schedule", methods=["GET"])
# def generate_schedule():
#     user_id = "test123"  # 測試用固定 ID，你之後可改為 LINE 使用者 ID
#     tasks = load_data(user_id)

#     # 模擬習慣資料（未來可存進 Firebase）
#     habits = {
#         "prefered_morning": "閱讀、寫作",
#         "prefered_afternoon": "計算、邏輯"
#     }

#     today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")
#     available_hours = 5

#     prompt = generate_gemini_prompt(user_id, tasks, habits, today, available_hours)
#     return prompt



# @app.route("/generate_schedule_with_ai", methods=["GET"])
# def generate_schedule_with_ai():
#     user_id = "test123"
#     tasks = load_data(user_id)

#     habits = {
#         "prefered_morning": "閱讀、寫作",
#         "prefered_afternoon": "計算、邏輯"
#     }

#     today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")
#     available_hours = 5

#     prompt = generate_gemini_prompt(user_id, tasks, habits, today, available_hours)
#     result = call_gemini_schedule(prompt)

#     return result