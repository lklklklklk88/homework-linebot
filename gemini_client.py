import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def call_gemini_schedule(prompt):
    model = genai.GenerativeModel("models/gemini-1.5-flash-latest")  # 實際為 2.5 Flash
    response = model.generate_content(prompt)
    return response.text.strip()
