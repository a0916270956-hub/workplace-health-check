import streamlit as st
import google.generativeai as genai
import gspread
import json
from datetime import datetime
import pytz

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
# 2. 模型偵測：優先使用 1.5-Flash 以換取最高免費額度
# ==========================================
try:
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    selected_model = next((m for m in available_models if "gemini-1.5-flash" in m.lower()), available_models[0])
except Exception as e:
    st.error(f"⚠️ 模型讀取錯誤：{e}")
    st.stop()

# ==========================================
# 3. 完美版寫入函數：支援反饋與專人聯繫資訊
# ==========================================
def log_to_sheets_perfect(user_msg, ai_reply, feedback="", status="已回答", name="", phone="", email="", note=""):
    try:
        creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
        gc = gspread.service_account_from_dict(creds_dict)
        sheet = gc.open("職場健檢_民眾提問紀錄").sheet1
        
        tw_tz = pytz.timezone('Asia/Taipei')
        current_time = datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M:%S")
        
        # 依照標題列順序寫入資料
        sheet.append_row([current_time, user_msg, ai_reply, feedback, status, name, phone, email, note])
    except Exception as e:
        print(f"資料庫紀錄異常（不影響前端）：{e}")

# ==========================================
# 4. 專業法律大腦提示詞
# ==========================================
SYSTEM_PROMPT = """
你是一位精通台灣勞動法令、具備高度專業與同理心的「職場友善度健檢顧問」。
請根據使用者描述的職場狀況，進行客觀分析與評估。

【核心守則】
1. 展現同理心：首先承接使用者的情緒。
2. 嚴格區分歧視：
   - 涉及性別、懷孕、育嬰留停者，歸類為《性別平等工作法》之「性別歧視」。
   - 涉及年齡、身心障礙者，歸類為《就業服務法》之「就業歧視」。
3. 官方結語：在每一則回答最後一行，固定加上「如仍有疑義歡迎來電02-24287801 基隆市政府關心你」。
"""

model = genai.GenerativeModel(model_name=selected_model, system_instruction=SYSTEM_PROMPT)

# ==========================================
# 5. UI 美化與互動邏輯
# ==========================================
st.set_page_config(page_title="工作場所融合度 AI 健檢系統", page_icon="⚖️", layout="centered")

# 介面美化
st.markdown("""
<style>
    html, body, [class*="css"] { font-family: '微軟正黑體', sans-serif !important; }
    .stApp { background: linear-gradient(to bottom, #E8F1F8 0%, #FFFFFF 100%); }
    h1 { color: #003366 !important; text-align: center; border-bottom: 3px solid #00509E; }
    .stChatMessage { background-color: #FFFFFF; border-radius: 15px; border: 1px solid #D1E1F0; box-shadow: 0 4px 8px rgba(0,0,0,0.03); }
</style>
""", unsafe_allow_html=True)

st.title("⚖️ 工作場所融合度 AI 健檢系統")
st.info("歡迎使用！請描述您的職場狀況，顧問將根據台灣法規為您進行分析。")

if "chat_session" not in st.session_state:
    st.session_state.chat_session = model.start_chat(history=[])

# 渲染對話歷史
for message in st.session_state.chat_session.history:
    role = "user" if message.role == "user" else "assistant"
    with st.chat_message(role):
        st.markdown(message.parts[0].text)

# 民眾輸入區
if user_input := st.chat_input("請輸入您的職場狀況或疑問..."):
    st.chat_message("user").markdown(user_input)
    with st.chat_message("assistant"):
        with st.spinner("顧問分析中..."):
            try:
                response = st.session_state.chat_session.send_message(user_input)
                st.markdown(response.text)
                
                # 暫存以便後續反饋使用
                st.session_state.last_user_msg = user_input
                st.session_state.last_ai_reply = response.text
                
                # 初始紀錄
                log_to_sheets_perfect(user_input, response.text)
                
            except Exception as e:
                if "429" in str(e):
                    st.error("🌟 系統目前繁忙中（配額已達上限）。")
                    st.info("如您有急迫法律需求，歡迎致電基隆市政府諮詢專線：02-24287801。")
                else:
                    st.error(f"⚠️ 連線錯誤：{e}")

# ==========================================
# 6. 反饋與專人補充互動表單
# ==========================================
if "last_ai_reply" in st.session_state:
    st.divider()
    st.subheader("📝 您對分析滿意嗎？")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("👍 很有幫助"):
            log_to_sheets_perfect(st.session_state.last_user_msg, st.session_state.last_ai_reply, feedback="滿意", status="結案")
            st.success("感謝回饋！")
            
    with col2:
        if st.button("❓ 仍有疑惑/需專人回覆"):
            st.session_state.show_expert_form = True

    if st.session_state.get("show_expert_form", False):
        with st.form("pro_contact"):
            st.warning("請填寫聯繫資訊，人員將於上班時間回覆您。")
            name = st.text_input("稱呼")
            phone = st.text_input("聯絡電話")
            email = st.text_input("Email 回復")
            note = st.text_area("其他備註")
            
            if st.form_submit_button("送出申請"):
                if not name or not (phone or email):
                    st.error("請填寫姓名與至少一種聯繫方式。")
                else:
                    log_to_sheets_perfect(
                        st.session_state.last_user_msg, 
                        st.session_state.last_ai_reply, 
                        feedback="需專人服務", 
                        status="待處理",
                        name=name, phone=phone, email=email, note=note
                    )
                    st.success("申請已送出，專人將儘速聯繫您。")
                    st.session_state.show_expert_form = False
