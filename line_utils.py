from gemini_client import call_gemini_schedule
import json
import re
import datetime

def classify_intent_by_gemini(text: str) -> str:
    """
    使用 Gemini 判斷使用者意圖
    """
    prompt = f"""
你是一個 LINE Bot 的語意理解助手，請閱讀使用者輸入的一句話，判斷它想要執行哪一個功能。

判斷規則：
1. 如果句子中包含新增作業的內容（例如：提到作業名稱、截止日期、時間等），回傳 add_task_natural
2. 如果句子中明確提到要完成某個作業，回傳 complete_task_natural
3. 其他情況按照原有規則判斷

請只回傳以下其中之一（只回傳 intent 代號，不要加句子）：
- add_task_natural：自然語言新增作業（句子包含作業資訊）
- complete_task_natural：自然語言完成作業（明確提到要完成某作業）
- add_task：新增作業（一般指令）
- view_tasks：查看作業
- complete_task：完成作業（一般指令）
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
        "add_task_natural", "complete_task_natural", "add_task", "view_tasks", 
        "complete_task", "set_reminder", "clear_completed", "clear_expired", 
        "show_schedule", "unknown"
    }
    return result if result in valid_intents else "unknown"

def parse_task_info_from_text(text: str) -> dict:
    """
    從自然語言中解析作業資訊
    """
    # 獲取今天的日期作為基準
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    today_str = today.strftime("%Y-%m-%d")
    
    prompt = f"""
你是一個 LINE Bot，負責從使用者輸入的自然語言句子中抽取新增作業所需的資訊。

今天的日期是：{today_str}

請將以下資訊解析為 JSON 格式：
- task：作業名稱（必填，從句子中抽取）
- estimated_time：預估花費時間（單位：小時，數字格式，如果沒提到就設為 null）
- category：任務類型（從句子推斷，如：閱讀、寫作、程式、計算、報告、實驗、練習、研究等，如果無法推斷就設為 null）
- due：截止日期（格式為 YYYY-MM-DD，如果沒提到就設為 null）

時間轉換規則：
- "明天" = 今天日期+1天
- "後天" = 今天日期+2天
- "下週一"、"下周一" = 找到下一個週一的日期
- "這週五"、"本週五" = 找到本週的週五
- "X天後" = 今天日期+X天
- "X月X日" = 今年的該日期（如果已過，則為明年）

範例輸入：「下周一要交作業系統，大概花三小時來寫作業」
預期輸出：{{"task": "作業系統", "estimated_time": 3, "category": "寫作", "due": "2025-06-02"}}

使用者輸入：
「{text}」

請回傳 JSON（確保是有效的 JSON 格式）：
"""
    
    try:
        response = call_gemini_schedule(prompt)
        # 嘗試直接解析
        data = json.loads(response)
        
        # 標記哪些欄位是 AI 自動填寫的
        ai_filled = []
        if data.get("estimated_time") is None:
            ai_filled.append("estimated_time")
        if data.get("category") is None:
            ai_filled.append("category")
        if data.get("due") is None:
            ai_filled.append("due")
            
        data["ai_filled"] = ai_filled
        return data
        
    except Exception as e:
        # 嘗試從回應中提取 JSON
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                
                # 標記 AI 填寫的欄位
                ai_filled = []
                if data.get("estimated_time") is None:
                    ai_filled.append("estimated_time")
                if data.get("category") is None:
                    ai_filled.append("category")
                if data.get("due") is None:
                    ai_filled.append("due")
                    
                data["ai_filled"] = ai_filled
                return data
            except:
                pass
                
        print(f"[錯誤] 解析 Gemini 回傳 JSON 失敗：{response}")
        return None

def parse_complete_task_from_text(text: str, tasks: list) -> dict:
    """
    從自然語言中解析要完成的作業
    """
    # 準備作業列表資訊
    task_list = []
    for i, task in enumerate(tasks):
        if not task.get("done", False):
            task_list.append({
                "index": i,
                "name": task.get("task", "未命名"),
                "category": task.get("category", "未分類"),
                "due": task.get("due", "未設定")
            })
    
    prompt = f"""
你是一個 LINE Bot，負責從使用者輸入的句子中判斷他想要完成哪個作業。

以下是使用者的未完成作業列表：
{json.dumps(task_list, ensure_ascii=False, indent=2)}

請分析使用者的輸入，找出最符合的作業，回傳 JSON 格式：
- task_index：作業的索引值（index）
- task_name：作業名稱
- confidence：信心度（0-1之間，表示匹配的確定程度）
- reason：選擇這個作業的原因

如果找不到明確符合的作業，confidence 設為 0。

使用者輸入：
「{text}」

請回傳 JSON：
"""
    
    try:
        response = call_gemini_schedule(prompt)
        data = json.loads(response)
        return data
    except Exception as e:
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
                
        print(f"[錯誤] 解析完成作業失敗：{response}")
        return None
    
def get_line_display_name(event):
    """
    從 LINE webhook event 取出使用者的顯示名稱。
    注意：需要用 LINE 的 API 取 user profile，event 只會有 user_id。
    """
    user_id = event.source.user_id
    # 這裡需用 MessagingApi 去查 profile，這是範例：
    from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
    import os

    configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
    with ApiClient(configuration) as api_client:
        profile = MessagingApi(api_client).get_profile(user_id)
        return profile.display_name
