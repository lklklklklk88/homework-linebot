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

請根據以下原則安排任務：
1. 優先考慮截止日期
2. 根據任務類型安排適合的時段（例如：早上安排需要高專注的任務）
3. 在任務之間安排適當的休息時間
4. 總時數不要超過 7 小時

回覆格式如下：

📝 排程說明：
[用輕鬆的語氣說明今天的排程重點，例如：
"今天幫你排了 X 小時的任務，上午安排高專注內容，下午放鬆一點"]

💡 溫馨提醒：
任務完成後，記得到【完成作業】選單回報喔！

📅 今日排程

1. 🕘 09:00 ~ 12:30｜快點完成（210 分鐘）
2. 🥪 12:30 ~ 13:00｜午餐（30 分鐘）
3. 📖 13:00 ~ 14:00｜作業系統｜閱讀
4. 🧠 14:00 ~ 14:15｜休息（15 分鐘）
5. 💻 14:15 ~ 15:15｜AI Agent｜寫程式
6. 🧠 15:15 ~ 15:30｜休息（15 分鐘）
7. 💻 15:30 ~ 16:30｜AI Agent｜寫程式

✅ 今日總時長：X 小時

以下是任務資料（供你安排時間順序使用）：
"""

    for i, task in enumerate(tasks, 1):
        name = task.get("task", "未命名")
        due = task.get("due", "未設定")
        est = task.get("estimated_time", "未提供")
        category = task.get("category", "未分類")
        prompt += f"{i}. {name}｜D: {due}｜約 {est} 小時｜分類：{category}\n"

    return prompt

def generate_schedule_prompt(tasks, current_time, available_time):
    """
    生成排程提示詞
    """
    prompt = f"""你是一位專業的排程助手。請根據以下任務和時間安排，生成一個合理的今日排程。

當前時間：{current_time}
可用時間：{available_time}

待辦任務：
"""
    
    # 添加任務列表
    for i, task in enumerate(tasks, 1):
        prompt += f"{i}. {task['task']}（預計 {task['estimated_time']} 小時，截止：{task['due']}）\n"
    
    prompt += """
請根據以下原則安排任務：
1. 優先安排截止日期較近的任務
2. 考慮任務類型和專注度需求
3. 在適當時間安排休息
4. 避免過度密集的安排

請用以下格式回覆：
1. 先給一個輕鬆的開場白
2. 然後列出建議的排程（使用以下格式）：
   1. 🕘 09:00 ~ 10:30｜任務名稱
   2. 🥪 12:00 ~ 13:00｜午餐
   3. 📖 13:00 ~ 14:30｜任務名稱
   （以此類推）
3. 最後加上總時數提醒

注意：
- 使用表情符號來表示不同類型的活動
- 時間格式使用 24 小時制
- 每個任務之間要留適當的休息時間
- 如果總時數超過 7 小時，請提醒使用者注意休息
"""
    
    return prompt