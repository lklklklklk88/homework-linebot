import os
import time
import datetime

from firebase_admin import db
from line_utils import get_line_display_name
from firebase_utils import (
    get_all_user_ids,
    get_remind_time,  # 未完成作業
    get_add_task_remind_time,  # 新增作業
    get_task_remind_enabled,
    get_add_task_remind_enabled,
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
