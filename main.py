import os
from flask import Flask, request, abort

from openai import OpenAI
from supabase import create_client, Client

from business_engine import BusinessEngine   

engine = BusinessEngine()                   

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


def update_user_stage(line_user_id, stage):
    supabase.table("users").update({"stage": stage}).eq("line_user_id", line_user_id).execute()


def save_conversation(line_user_id, role, content):
    supabase.table("conversations").insert({
        "line_user_id": line_user_id,
        "role": role,
        "content": content
    }).execute()


# =========================
# 🔥 ONBOARDING（只顯示一次）
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
        "👉 輸入【第1月】開始任務\n\n"

        "===SPLIT===\n"
        "🎯 第二階段：【第2月·複製二星經理】\n"
        "🔒 輸入【解鎖第二月+密碼】\n\n"

        "🎯 第三階段：【第3月·一星董事系統】\n"
        "🔒 輸入【解鎖第三月+密碼】"
    )


# =========================
# AI ENGINE
# =========================
def ask_ai(user_message, user):

    system_prompt = f"""
你是【AI戰將教練 v3】。

系統版本：{SYSTEM_VERSION}

使用者狀態：
- 階段：{user.get("stage")}
- 週數：{user.get("current_week")}
- 連續打卡：{user.get("streak_days")}

規則：
1. 一次只給一個行動
2. 不講大道理
3. 必須導向成交或下一步
4. 簡短、可複製
5. 用繁體中文
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
    print("USER:", user_id)
    print("MSG:", user_message)

    user = get_user(user_id)

    save_conversation(user_id, "user", user_message)

    mode = route_message(user_message)

    if mode == "BUSINESS":
    pc_count = extract_pc_count(user_message)  # 可先簡化
    result = engine.quick_preview(pc_count)
    reply = f"""
💰 商業試算結果

PC數：{result['pc_count']}
週收入：{result['weekly_income']}
QDV：{result['qdv']}
BV：{result['bv']}
"""
    
    # =========================
    # ⭐ 修正重點：只在第一次顯示 onboarding
    # =========================
    if user.get("stage") == "Starter" and user_message in ["hi", "哈囉", "你好", "start"]:
        reply = new_user_onboarding()

        # 👉 更新狀態，避免一直卡 onboarding
        update_user_stage(user_id, "Active")

    else:
        reply = ask_ai(user_message, user)

    save_conversation(user_id, "ai", reply)

    # LINE 回覆
    with ApiClient(Configuration(access_token=LINE_ACCESS_TOKEN)) as api_client:
        line_bot_api = MessagingApi(api_client)

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )

    # =========================
    # 📊 商業計算類（→ Business Engine）
    # =========================
def route_message(msg: str):

    msg = msg.strip()

    # 📊 商業計算類（→ Business Engine）
    if any(word in msg for word in ["收入", "賺多少", "QDV", "BV", "獎金", "週薪", "利潤"]):
        return "BUSINESS"

    # 📦 系統流程類
    if msg in ["第1月", "W1", "W2", "W3", "W4"]:
        return "FLOW_L1"

    if "解鎖第二月" in msg:
        return "UNLOCK_L2"

    if msg in ["W5", "W6", "W7", "W8"]:
        return "FLOW_L2"

    return "AI"


# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
