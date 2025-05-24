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
        model = genai.GenerativeModel("models/gemini-1.5-flash-latest")
        response = model.generate_content(prompt)
        
        # 檢查回應是否有效
        if not response or not response.text:
            raise Exception("Gemini API 回傳空白回應")
            
        return response.text.strip()
    except Exception as e:
        print(f"[Gemini] API 呼叫失敗：{e}")
        # 返回預設值或拋出異常
        raise Exception(f"Gemini API 錯誤：{str(e)}")