import os
import json
from flask import Flask, request, abort

from openai import OpenAI

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent


# =========================
# APP INIT
# =========================
app = Flask(__name__)

# ===== Render 健康檢查 =====
@app.route("/")
def home():
    return "AI Coach v2.1 Running"

# ===== LINE Webhook =====
@app.route("/callback", methods=["POST"])
def callback():
    pass
    
LINE_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

line_config = Configuration(access_token=LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_SECRET)

client = OpenAI(api_key=OPENAI_API_KEY)

MEMORY_FILE = "memory.json"


# =========================
# MEMORY SYSTEM
# =========================
def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {}
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_memory(data):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user_memory(user_id):
    memory = load_memory()

    if user_id not in memory:
        memory[user_id] = {
            "stage": "Starter",
            "last_action": None,
            "history": []
        }

    return memory[user_id], memory


def update_memory(user_id, user_memory, user_message, reply, full_memory):
    user_memory["last_action"] = user_message

    user_memory["history"].append({
        "user": user_message,
        "ai": reply
    })

    user_memory["history"] = user_memory["history"][-10:]

    full_memory[user_id] = user_memory
    save_memory(full_memory)


def build_context(memory):
    return f"""
【使用者狀態】
階段：{memory['stage']}
最近行動：{memory['last_action']}

【最近對話】
{memory['history'][-1] if memory['history'] else '無'}
"""


# =========================
# AI ENGINE
# =========================
def ask_gpt(user_message, memory, mode="COACH"):

    system_prompt = """
你是「平哥AI戰將教練」。

你的任務：
協助使用者建立行動力、成交能力、團隊複製能力，並在90天內成長。

規則：
1. 使用繁體中文
2. 一次只給一個重點
3. 必須提供可執行行動
4. 禁止空話與理論
5. 依照使用者階段調整內容（Starter / Builder / Leader）
"""

    context = build_context(memory)

    response = client.responses.create(
        model="gpt-5",
        instructions=system_prompt + "\n\n" + context,
        input=user_message,
        temperature=0.7
    )

    return response.output_text


# =========================
# ROUTER
# =========================
def ai_router(user_message: str):

    msg = user_message.strip().upper()

    if msg in ["90天新人加速器", "起盤藍圖"]:
        return "MENU"

    if msg.startswith("W"):
        return "WEEK"

    if any(x in user_message for x in ["怎麼", "如何", "為什麼", "教我"]):
        return "COACH"

    if any(x in user_message for x in ["團隊", "帶人", "董事", "複製"]):
        return "LEADER"

    return "COACH"


# =========================
# LINE WEBHOOK
# =========================
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


# =========================
# MESSAGE HANDLER
# =========================
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    user_id = event.source.user_id
    user_message = event.message.text

    memory, full_memory = get_user_memory(user_id)

    mode = ai_router(user_message)

    # ===== 指令系統 =====
    if mode == "MENU":
        reply = "90天系統主選單：請輸入 W1-W12 或 問我任何問題"

    elif mode == "WEEK":
        reply = f"{user_message} 任務內容（可在此擴充）"

    else:
        reply = ask_gpt(user_message, memory, mode)

    update_memory(user_id, memory, user_message, reply, full_memory)

    with ApiClient(line_config) as api_client:
        line_bot_api = MessagingApi(api_client)

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )


# =========================
# RUN SERVER
# =========================
if __name__ == "__main__":
    app.run(port=5000, debug=True)
