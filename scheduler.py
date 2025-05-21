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

📅 今日排程

1. 🕘 09:00 ~ 12:30｜快點完成（210 分鐘）
2. 🥪 12:30 ~ 13:00｜午餐（30 分鐘）
3. 📖 13:00 ~ 14:00｜作業系統｜閱讀
4. 🧠 14:00 ~ 14:15｜休息（15 分鐘）
5. 💻 14:15 ~ 15:15｜AI Agent｜寫程式
6. 🧠 15:15 ~ 15:30｜休息（15 分鐘）
7. 💻 15:30 ~ 16:30｜AI Agent｜寫程式

✅ 今日總時長：X 小時

💡 溫馨提醒：
任務完成後，記得到【完成作業】選單回報喔！

以下是任務資料（供你安排時間順序使用）：
"""

    for i, task in enumerate(tasks, 1):
        name = task.get("task", "未命名")
        due = task.get("due", "未設定")
        est = task.get("estimated_time", "未提供")
        category = task.get("category", "未分類")
        prompt += f"{i}. {name}｜D: {due}｜約 {est} 小時｜分類：{category}\n"

    return prompt