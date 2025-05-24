# task_parser.py
import json, re
from gemini_client import call_gemini_schedule

def parse_task_from_text(text: str):
    prompt = f"""
你是一個 LINE Bot，負責從使用者輸入的自然語言句子中抽取新增作業所需的資訊。

請將以下資訊解析為 JSON 格式（key 使用英文）：
- task：作業名稱
- estimated_time：預估花費時間（單位：小時，數字格式）
- category：任務類型（如：閱讀、寫作、程式）
- due：截止日期（格式為 YYYY-MM-DD，如果句子中有「下週一」、「明天」這類模糊時間，請轉換為明確日期）

使用者輸入：
「{text}」

請回傳 JSON：
"""
    response = call_gemini_schedule(prompt)
    # ↘ 先直接嘗試；若失敗就抓第一個 {...}
    try:
        return json.loads(response)
    except Exception:
        match = re.search(r'\{.*\}', response, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        print(f"[錯誤] 解析 Gemini 回傳 JSON 失敗：{response}")
        return None