import os
import json
from flask import Flask, request, abort

from openai import OpenAI
from supabase import create_client, Client

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


@app.route("/")
def home():
    return "AI Coach SaaS v3 Running"


# =========================
# ENV
# =========================
LINE_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

line_config = Configuration(access_token=LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_SECRET)

client = OpenAI(api_key=OPENAI_API_KEY)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# =========================
# SUPABASE HELPERS
# =========================
def get_user(line_user_id):
    res = supabase.table("users").select("*").eq("line_user_id", line_user_id).execute()

    if len(res.data) == 0:
        user = {
            "line_user_id": line_user_id,
            "stage": "Starter",
            "current_week": 1,
            "streak_days": 0
        }
        supabase.table("users").insert(user).execute()
        return user

    return res.data[0]


def save_conversation(line_user_id, role, content):
    supabase.table("conversations").insert({
        "line_user_id": line_user_id,
        "role": role,
        "content": content
    }).execute()


def save_checkin(line_user_id, content):
    supabase.table("checkins").insert({
        "line_user_id": line_user_id,
        "content": content
    }).execute()


# =========================
# AI ENGINE
# =========================
def ask_gpt(user_message, user):

    system_prompt = f"""
你是「AI戰將教練」。

使用者狀態：
階段：{user.get('stage')}
週數：{user.get('current_week')}
連續打卡：{user.get('streak_days')}

規則：
- 一次只給一個行動
- 不講理論
- 要可執行
- 幫助成交、帶人、複製
"""

    response = client.responses.create(
        model="gpt-5-mini",
        instructions=system_prompt,
        input=user_message
    )

    return response.output_text


# =========================
# WEBHOOK
# =========================
@app.route("/callback", methods=["POST"])
def callback():
    body = request.get_data(as_text=True)
    signature = request.headers.get("X-Line-Signature")

    try:
        handler.handle(body, signature)
    except Exception as e:
        print("ERROR:", e)
        abort(400)

    return "OK"


# =========================
# MESSAGE HANDLER
# =========================
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    user_id = event.source.user_id
    user_message = event.message.text

    print("USER ID:", user_id)
    print("MESSAGE:", user_message)

    # 1️⃣ 取得 / 建立 user
    user = get_user(user_id)

    # 2️⃣ 存 user message
    save_conversation(user_id, "user", user_message)

    # 3️⃣ AI 回答
    reply = ask_gpt(user_message, user)

    # 4️⃣ 存 AI reply
    save_conversation(user_id, "ai", reply)

    # 5️⃣ LINE 回覆
    with ApiClient(line_config) as api_client:
        line_bot_api = MessagingApi(api_client)

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )
# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
