from gemini_client import call_gemini_schedule

def classify_intent_by_gemini(text: str) -> str:
    prompt = f"""
你是一個 LINE Bot 的語意理解助手，請閱讀使用者輸入的一句話，判斷它想要執行哪一個功能，回傳對應的英文指令代碼（小寫）。

請只回傳以下其中之一（只回傳 intent 代號，不要加句子）：
- add_task：新增作業
- view_task：查看作業
- complete_task：完成作業
- set_reminder：設定提醒時間
- clear_completed：清除已完成作業
- clear_expired：清除已截止作業
- show_schedule：查看今日排程
- unknown：無法辨識的指令

使用者輸入的句子是：
「{text}」

請回覆：
"""

    result = call_gemini_schedule(prompt).lower().strip()
    valid_intents = {
        "add_task", "view_task", "complete_task", "set_reminder",
        "clear_completed", "clear_expired", "show_schedule", "unknown"
    }
    return result if result in valid_intents else "unknown"
