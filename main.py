import os
from flask import Flask, request, abort

from openai import OpenAI
from supabase import create_client, Client

from linebot.v3 import WebhookHandler
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

SYSTEM_VERSION = "v3"


@app.route("/")
def home():
    return f"LINE AI 商業成交系統 {SYSTEM_VERSION} Running"


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
# SUPABASE
# =========================
def get_user(line_user_id):
    res = supabase.table("users").select("*").eq("line_user_id", line_user_id).execute()

    if not res.data:
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


# =========================
# AI ENGINE
# =========================
def ask_gpt(user_message, user):

    system_prompt = f"""
你是「戰將教練 肆伍參平哥AI助理」。

系統版本：{SYSTEM_VERSION}

使用者狀態：
- 階段：{user.get('stage')}
- 週數：{user.get('current_week')}
- 連續打卡：{user.get('streak_days')}

【核心任務】
- 幫助新人 90 天內晉升一星董事
- 只給「一個可執行行動」
- 不講理論、不做長篇分析
- 所有內容要能複製、能成交、能帶人

【風格】
- 像戰略教練，不像客服
- 直接、有壓迫感、有方向
"""

    try:
        response = client.responses.create(
            model="gpt-4o-mini",
            instructions=system_prompt,
            input=user_message[:800],
        )
        return response.output_text

    except Exception as e:
        print("OPENAI ERROR:", e)
        return "系統繁忙，請稍後再試"


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
        print("LINE ERROR:", e)
        abort(400)

    return "OK"


# =========================
# MESSAGE HANDLER
# =========================
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    user_id = event.source.user_id
    user_message = event.message.text[:800]

    print("SYSTEM VERSION:", SYSTEM_VERSION)
    print("USER ID:", user_id)
    print("MESSAGE:", user_message)

    # 1️⃣ user
    user = get_user(user_id)

    # 2️⃣ save user msg
    save_conversation(user_id, "user", user_message)

    # 3️⃣ AI reply
    reply = ask_gpt(user_message, user)

    # 4️⃣ save AI msg
    save_conversation(user_id, "ai", reply)

    # 5️⃣ reply LINE
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
