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
# 🔥 新人入口（ONBOARDING）
# =========================
def new_user_onboarding():
    return (
        "🚀 【90天新人加速器·最高指導原則】\n"
        "1. 快速篩選優選客戶（PC+）\n"
        "2. 複製二星經理\n"
        "3. 目標一星董事\n\n"

        "===SPLIT===\n"
        "🎯 第一階段：【第1月·快速篩選 PC+ 愛用池】\n"
        "💡 核心：累積 10-20 個 PC+ 自動送貨愛用池。\n"
        "👉 輸入【第1月】即可解鎖第1-4週任務\n\n"

        "===SPLIT===\n"
        "🎯 第二階段：【第2月·複製二星經理】\n"
        "💡 核心：建立幹部線，複製二星經理\n"
        "🔒 輸入【解鎖第二月+密碼】\n\n"

        "🎯 第三階段：【第3月·一星董事系統】\n"
        "💡 核心：建廠插旗 + 六大獎金\n"
        "🔒 輸入【解鎖第三月+密碼】"
    )


# =========================
# AI ENGINE
# =========================
def ask_ai(user_message, user):

    system_prompt = f"""
你是【AI戰將教練 v3】。

你在運作一個商業成交系統，而不是聊天機器人。

系統版本：{SYSTEM_VERSION}

使用者狀態：
- 階段：{user.get("stage")}
- 週數：{user.get("current_week")}
- 連續打卡：{user.get("streak_days")}

【核心規則】
1. 一次只給一個行動
2. 不講大道理
3. 必須導向成交或下一步行動
4. 永遠要有下一步指令
5. 簡短、可複製
6. 用繁體中文

【商業目標】
- PC / PC+ 成交
- BP 夥伴轉換
- 複製二星經理
- 一星董事系統化
"""

    try:
        response = client.responses.create(
            model="gpt-4o-mini",
            instructions=system_prompt,
            input=user_message[:800]
        )
        return response.output_text.strip()

    except Exception as e:
        print("OPENAI ERROR:", e)
        return "先做一件事：找出3個有健康需求的人。"

# =========================
# FLOW CONTROLLER
# =========================
def flow_response(mode, msg):

    if mode == "L1":
        return "🚀 輸入【第1月】開始90天系統"

    if mode == "UNLOCK_L2":
        return "🔓 第二階段已解鎖，輸入【第2月大盤】"

    if mode == "UNLOCK_L3":
        return "🔓 第三階段已解鎖，輸入【第3月大盤】"

    if mode == "L2":
        return "🔥 第二階段執行中，輸入 W5~W8"

    if mode == "L3":
        return "🔥 第三階段執行中，輸入 W9~W12"

    return None



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

    # 1️⃣ 取得 user
    user = get_user(user_id)

    # 🔥 2️⃣ 新人直接進 onboarding（重點）
    if user.get("stage") == "Starter":
        reply = new_user_onboarding()
    else:
        # 3️⃣ AI 回覆
        reply = ask_ai(user_message, user)

    # 4️⃣ 存紀錄
    save_conversation(user_id, "user", user_message)

    # 5️⃣ 回覆 LINE
    with ApiClient(Configuration(access_token=LINE_ACCESS_TOKEN)) as api_client:
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
