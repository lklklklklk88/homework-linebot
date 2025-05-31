import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# 檢查 API KEY 是否存在
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY 環境變數未設定")

genai.configure(api_key=api_key)

def call_gemini_schedule(prompt):
    try:
        # 使用更嚴格的系統指令
        system_instruction = """
你是一個專業的時間管理助手。在生成排程時，你必須：
1. 嚴格遵守使用者設定的可用時間限制
2. 所有活動（包括作業、休息、用餐）的總時間必須完全等於可用時間，不可超過
3. 使用24小時制，超過24:00要轉換（如25:00→01:00）
4. 每個時段都要標註持續時間（分鐘）
5. 如果任務太多無法在時限內完成，要明確說明哪些任務無法安排
"""
        
        model = genai.GenerativeModel(
            model_name="models/gemini-1.5-flash-latest",
            system_instruction=system_instruction
        )
        
        response = model.generate_content(prompt)
        
        # 檢查回應是否有效
        if not response or not response.text:
            raise Exception("Gemini API 回傳空白回應")
            
        return response.text.strip()
    except Exception as e:
        print(f"[Gemini] API 呼叫失敗：{e}")
        # 返回預設值或拋出異常
        raise Exception(f"Gemini API 錯誤：{str(e)}")