from flask import Flask, request, abort
from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.messaging.models import TextMessage, ReplyMessageRequest
from linebot.exceptions import InvalidSignatureError
from linebot.v3.webhook import MessageEvent

import json

app = Flask(__name__)

# LINE 設定（請替換成你自己的）
LINE_CHANNEL_ACCESS_TOKEN = 'XzJXYb1P2VCAbEiyF2ucW/hBWXE1bLyleEhb3hBm7lLauM7yXq+UUQD5Ugxw0Q7QEuXXKlOMBrBOPt8KFYKISvMX7woSIw9k1hClU4V/5nyED3OgAJ9GZlK3FdWEoZzxiFl3Sg2HA47JG05r4mSHkQdB04t89/1O/w1cDnyilFU='
LINE_CHANNEL_SECRET = '0129e7873b7013e19660fa60c28ed6b8'

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 讀取作業資料
def load_data():
    try:
        with open('data.json', 'r') as f:
            return json.load(f)
    except:
        return []

def save_data(data):
    with open('data.json', 'w') as f:
        json.dump(data, f, indent=2)

@app.route("/")
def home():
    return "Bot is running"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent)
def handle_message(event):
    if event.message.type != 'text':
        return

    text = event.message.text.strip()
    data = load_data()

    if text.startswith("新增作業"):
        task = text.replace("新增作業", "").strip()
        data.append({"task": task, "done": False})
        save_data(data)
        reply = f"已新增作業：{task}"

    elif text.startswith("完成作業"):
        try:
            index = int(text.replace("完成作業", "").strip()) - 1
            data[index]["done"] = True
            save_data(data)
            reply = f"已完成第 {index+1} 項作業：{data[index]['task']}"
        except:
            reply = "找不到該作業編號，請確認輸入格式。"

    elif text == "查看作業":
        undone = [f"{i+1}. {d['task']}" for i, d in enumerate(data) if not d["done"]]
        reply = "目前未完成作業：\n" + "\n".join(undone) if undone else "所有作業都完成了，太棒了！"

    else:
        reply = "請使用以下指令：\n1. 新增作業 作業內容\n2. 完成作業 編號\n3. 查看作業"

    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )

if __name__ == "__main__":
    app.run()