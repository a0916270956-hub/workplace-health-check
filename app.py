import streamlit as st
import google.generativeai as genai
import gspread
import json
from datetime import datetime
import pytz
import requests  # 用於 LINE Messaging API 發送

# ==========================================
# 1. 系統設定與 API 金鑰讀取
# ==========================================
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    st.error("⚠️ 尚未讀取到 API Key！請至 Streamlit Secrets 設定 GOOGLE_API_KEY。")
    st.stop()

# ==========================================
# 2. 安全動態模型選擇 (更新優化版)
# ==========================================
try:
    # 取得可用模型清單
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    
    # 優先選擇 1.5 系列，因為它們目前是 Google 的主流支援版本
    if any('gemini-1.5-flash' in m for m in available_models):
        SELECTED_MODEL = 'gemini-1.5-flash'
    elif any('gemini-1.5-pro' in m for m in available_models):
        SELECTED_MODEL = 'gemini-1.5-pro'
    else:
        # 如果找不到 1.5 系列，則抓取清單中第一個可用的模型名稱
        SELECTED_MODEL = available_models[0].split('/')[-1]
        
except Exception as e:
    # 若 API 無法列出模型，則使用目前最通用的名稱作為保底
    SELECTED_MODEL = "gemini-1.5-flash"

# ==========================================
# 3. 完美版寫入函數 (Google Sheets)
# ==========================================
def log_to_sheets_perfect(user_msg, ai_reply, feedback="", status="已回答", name="", gender="", phone="", email="", note=""):
    try:
        creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
        gc = gspread.service_account_from_dict(creds_dict)
        sheet = gc.open("職場健檢_民眾提問紀錄").sheet1
        tw_tz = pytz.timezone('Asia/Taipei')
        current_time = datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M:%S")
        # 欄位：時間, 提問, 回覆, 評價, 狀態, 姓名, 性別, 電話, Email, 備註
        sheet.append_row([current_time, user_msg, ai_reply, feedback, status, name, gender, phone, email, note])
    except Exception as e:
        print(f"資料庫紀錄異常：{e}")

# ==========================================
# 3.1 LINE Messaging API 通知功能
# ==========================================
def send_line_message(message_text):
    try:
        channel_access_token = st.secrets["LINE_CHANNEL_ACCESS_TOKEN"]
        admin_user_id = st.secrets["LINE_ADMIN_USER_ID"]
        url = "https://api.line.me/v2/bot/message/push"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {channel_access_token}"
        }
        data = {
            "to": admin_user_id,
            "messages": [{"type": "text", "text": message_text}]
        }
        res = requests.post(url, headers=headers, json=data)
        
        # 🎯 如果發送失敗，將錯誤碼顯示在後台 Console
        if res.status_code != 200:
            print(f"LINE 發送失敗，狀態碼：{res.status_code}, 原因：{res.text}")
            
    except Exception as e:
        print(f"LINE 系統異常：{e}")

# ==========================================
# 4. 核心大腦設定 (專家模式 Prompt)
# ==========================================
SYSTEM_PROMPT = """
你是一位精通台灣勞動法令、具備高度專業與同理心的「職場友善度健檢顧問」。
請根據使用者描述的職場狀況，進行客觀分析與評估。

【🚨 回覆結構原則】
1. 直接回覆：首先承接使用者的情緒，給予支持，並「優先直接針對問題給出明確答案」。
2. 問題概述與法令分析：明確標示以下兩個段落：
   - 【問題概述】：簡述民眾遇到的核心爭議。
   - 【法令分析】：僅說明法令依據及具體條文內容。
   - **注意**：僅援引與問題核心直接相關的條文，無關法規不必說明。
3. 法規版本：必須以台灣官方最新發布的勞動法令（如全國法規資料庫、勞動部最新函釋）為準。

【核心守則】
1. 涉及懷孕、育嬰、性別等對待，引用《性別平等工作法》「性別歧視」。
2. 涉及年齡、容貌、身障等，引用《就業服務法》「就業歧視」。
3. 涉及工時、薪資，引用《勞動基準法》。
4. 結語提醒：每一則回答最後一行固定加上：「如仍有疑義歡迎來電02-24287801 基隆市政府關心你」。
"""

try:
    model = genai.GenerativeModel(
        model_name=SELECTED_MODEL,
        system_instruction=SYSTEM_PROMPT
    )
except Exception as e:
    st.error(f"⚠️ 模型建立失敗：{e}")
    st.stop()

# ==========================================
# 5. 網頁介面與美化 (深色模式修正版)
# ==========================================
st.set_page_config(page_title="工作場所融合度 AI 健檢系統", page_icon="⚖️", layout="centered")

st.markdown("""
<style>
    html, body, [class*="st-"] { font-family: '微軟正黑體', sans-serif !important; color: #262730 !important; }
    .stApp { background: linear-gradient(to bottom, #E8F1F8 0%, #FFFFFF 100%) !important; }
    h1 { color: #003366 !important; text-align: center; border-bottom: 3px solid #00509E; padding-bottom: 10px; }
    .stChatMessage { background-color: #FFFFFF !important; border-radius: 15px; border: 1px solid #D1E1F0; box-shadow: 0 4px 8px rgba(0,0,0,0.03); color: #262730 !important; }
    p, .stMarkdown p { color: #262730 !important; }
    div[data-testid="stChatInput"] textarea, input, textarea { background-color: #FFFFFF !important; color: #262730 !important; -webkit-text-fill-color: #262730 !important; }
    ::placeholder { color: #A0A0A0 !important; -webkit-text-fill-color: #A0A0A0 !important; }
    div[data-testid="stButton"] button, div[data-testid="stFormSubmitButton"] button { background-color: #FFFFFF !important; color: #00509E !important; border: 1px solid #00509E !important; font-weight: bold !important; }
    div[data-testid="stButton"] button:hover, div[data-testid="stFormSubmitButton"] button:hover { background-color: #00509E !important; color: #FFFFFF !important; }
</style>
""", unsafe_allow_html=True)

st.title("⚖️ 工作場所融合度 AI 健檢系統")
st.markdown("歡迎使用！請簡單描述您在職場上遇到的狀況。顧問將根據台灣法規，為您進行分析。")

if "chat_session" not in st.session_state:
    st.session_state.chat_session = model.start_chat(history=[])

for message in st.session_state.chat_session.history:
    role = "user" if message.role == "user" else "assistant"
    with st.chat_message(role):
        st.markdown(message.parts[0].text)

if user_input := st.chat_input("請簡單描述您的狀況（請勿在此輸入真實姓名）..."):
    st.chat_message("user").markdown(user_input)
    with st.chat_message("assistant"):
        with st.spinner("顧問分析中..."):
            try:
                response = st.session_state.chat_session.send_message(user_input)
                st.markdown(response.text)
                st.session_state.last_user_msg = user_input
                st.session_state.last_ai_reply = response.text
                log_to_sheets_perfect(user_input, response.text)
            except Exception as e:
                st.error(f"⚠️ 連線錯誤：{e}")

# ==========================================
# 6. 反饋與專人聯繫 (含個資同意與回覆偏好)
# ==========================================
if "last_ai_reply" in st.session_state:
    st.divider()
    st.subheader("📝 您對分析滿意嗎？")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("👍 很有幫助"):
            log_to_sheets_perfect(st.session_state.last_user_msg, st.session_state.last_ai_reply, feedback="滿意", status="結案")
            st.success("感謝您的回饋！")
    with col2:
        if st.button("❓ 需專人補充回復"):
            st.session_state.show_expert_form = True

    if st.session_state.get("show_expert_form", False):
        with st.form("pro_contact"):
            st.info("請填寫聯繫資訊，人員將於上班時間聯繫您。")
            name = st.text_input("您的姓名/稱呼")
            user_gender = st.radio("您的性別", ["男", "女", "其他"], horizontal=True)
            contact_method = st.radio("您希望專人如何回覆您？", ["電話回覆", "Email 回覆"], horizontal=True)
            phone = st.text_input("聯絡電話")
            email = st.text_input("Email 回復")
            note = st.text_area("其他備註說明")
            st.markdown("---")
            consent = st.checkbox("我同意基隆市政府依《個人資料保護法》規定，蒐集、處理及利用上述個人資料，僅限於本次職場健檢諮詢與聯繫使用。")
            
            if st.form_submit_button("送出申請"):
                if not consent:
                    st.error("⚠️ 請勾選同意個資聲明。")
                elif not name or (contact_method == "電話回覆" and not phone) or (contact_method == "Email 回覆" and not email):
                    st.error("請提供姓名與對應的聯繫方式。")
                else:
                    title = "先生" if user_gender == "男" else "女士（小姐）" if user_gender == "女" else ""
                    final_note = f"【偏好：{contact_method}】\n{note}"
                    log_to_sheets_perfect(st.session_state.last_user_msg, st.session_state.last_ai_reply, "需專人服務", "待處理", name, user_gender, phone, email, final_note)
                    # LINE 推播
                    notify_msg = f"\n🚨【專人服務請求】🚨\n民眾：{name} {title}\n電話：{phone}\nEmail：{email}\n偏好：{contact_method}\n備註：{note}"
                    send_line_message(notify_msg)
                    st.success(f"{name} {title} 好，你的申請已送出！專人將儘速與你聯繫。")
                    st.session_state.show_expert_form = False
