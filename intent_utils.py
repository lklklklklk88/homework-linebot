# intent_utils.py
from gemini_client import call_gemini_schedule

def classify_intent_by_gemini(text: str) -> str:
    prompt = f"""
你是一個 LINE Bot 的語意理解助手，請閱讀使用者輸入的一句話，判斷它想要執行哪一個功能，回傳對應的英文指令代碼（小寫）。

請只回傳下列其中之一：
- add_task：使用者想新增作業
- view_task：使用者想查看作業
- complete_task：使用者想標記某個作業為完成
- set_reminder：使用者想設定提醒時間
- unknown：無法辨識的指令

使用者輸入的句子是：
「{text}」

請回覆：
"""

    result = call_gemini_schedule(prompt).lower().strip()
    valid_intents = {"add_task", "view_task", "complete_task", "set_reminder", "unknown"}
    return result if result in valid_intents else "unknown"
