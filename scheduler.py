import os
import time
import datetime

from line_utils import get_line_display_name
from firebase_utils import (
    get_add_task_remind_enabled,
    get_add_task_remind_time,
    get_last_add_task_date,
    get_all_user_ids
)
from linebot.v3.messaging import MessagingApi, Configuration, TextMessage
from linebot.v3.messaging import ApiClient


# 表情符號對應表
EMOJI_MAP = {
    'default': '🕘',
    'meal': '🥪',
    'study': '📖',
    'rest': '🧠',
    'coding': '💻',
    'writing': '✍️',
    'reading': '📚',
    'exercise': '🏃',
    'meeting': '👥'
}

configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))

def send_add_task_reminders():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    today = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    users = get_all_user_ids()

    for user_id in users:
        try:
            if get_add_task_remind_enabled(user_id):
                remind_time = get_add_task_remind_time(user_id)
                if remind_time == current_time:
                    last_added = get_last_add_task_date(user_id)
                    if last_added != today:
                        print(f"[提醒] 提醒 {user_id} 新增作業")
                        with ApiClient(configuration) as api_client:
                            MessagingApi(api_client).push_message(
                                to=user_id,
                                messages=[TextMessage(text="📝 記得今天要新增作業唷～")]
                            )
        except Exception as e:
            print(f"[錯誤] 處理 {user_id} 時出錯：{e}")

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

def generate_schedule_prompt(user_id, tasks, habits, today, available_hours):
    """
    生成排程提示詞
    """
    display_name = get_line_display_name(user_id)
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    start_str = get_rounded_start_time()

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

1. 🕘 09:00 ~ 10:30｜任務名稱
2. 🥪 12:00 ~ 13:00｜午餐
3. 📖 13:00 ~ 14:30｜任務名稱
（以此類推）

✅ 今日總時長：X 小時

以下是任務資料（供你安排時間順序使用）：
{format_task_list(tasks)}
"""

    return prompt

def generate_gemini_prompt(user_id, tasks, habits, today, available_hours):
    """
    生成 Gemini 提示詞
    """
    # 格式化任務列表
    task_list = []
    for task in tasks:
        if not task.get("done", False):
            task_list.append(f"- {task['task']}（{task['estimated_time']}小時）")

    # 生成提示詞
    prompt = f"""請幫我安排今天的學習計畫。

目前待辦事項：
{chr(10).join(task_list)}

偏好時段：
- 上午：{habits.get('prefered_morning', '無特別偏好')}
- 下午：{habits.get('prefered_afternoon', '無特別偏好')}

可用時間：{available_hours}小時
日期：{today}

請依照以下格式回覆：
1. 先給一個輕鬆的開場白
2. 接著列出今日排程，格式如下：
   1. 🕘 09:00 ~ 10:30｜英文作業
   2. 10:30 ~ 12:00｜數學作業
   3. 🥪 12:00 ~ 13:00｜午餐
   4. 13:00 ~ 14:30｜物理作業
   5. 🧠 14:30 ~ 14:45｜休息
   6. 💻 14:45 ~ 16:15｜程式作業
3. 最後提醒總時數

注意事項：
1. 時間要連續，不要有空檔
2. 每個任務之間要留 5-15 分鐘的休息時間
3. 用餐時間要固定（12:00-13:00）
4. 每 2 小時要安排一次較長的休息（15-30 分鐘）
5. 根據任務類型選擇適當的時段
6. 總時數不要超過可用時間
7. 使用表情符號來表示不同類型的任務
8. 時間格式統一使用 24 小時制
9. 每個任務都要標註預計時長

請確保回覆格式正確，這樣我才能正確解析排程內容。"""

    return prompt


if __name__ == "__main__":
    print("🟢 新增作業提醒排程已啟動，每分鐘執行一次")
    while True:
        send_add_task_reminders()
        time.sleep(60)