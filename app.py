import streamlit as st
import google.generativeai as genai
import gspread
import json
from datetime import datetime
import pytz

# ==========================================
# 1. 系統設定與 API 金鑰
# ==========================================
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    st.error("⚠️ 尚未讀取到 API Key！請至 Streamlit Secrets 設定。")
    st.stop()

# 直接指定模型，減少 API 偵測開銷
SELECTED_MODEL = "gemini-1.5-flash"

# ==========================================
# 2. 完美版寫入函數 (A-I 欄位)
# ==========================================
def log_to_sheets_final(user_msg, ai_reply, feedback="", status="已回答", name="", phone="", email="", note=""):
    try:
        creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
        gc = gspread.service_account_from_dict(creds_dict)
        # 務必確保試算表名稱與此一致
        sheet = gc.open("職場健檢_民眾提問紀錄").sheet1
        
        tw_tz = pytz.timezone('Asia/Taipei')
        current_time = datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M:%S")
        
        # 順序：時間, 提問, 回覆, 評價, 狀態, 姓名, 電話, Email, 備註
        sheet.append_row([current_time, user_msg, ai_reply, feedback, status, name, phone, email, note])
    except Exception as e:
        print(f"資料庫紀錄異常：{e}")

# ==========================================
# 3. 核心大腦設定
# ==========================================
SYSTEM_PROMPT = """你是一位精通台灣勞動法令的「職場友善度健檢顧問」。
請根據法規客觀分析，並在最後一行加上「如仍有疑義歡迎來電02-24287801 基隆市政府關心你」。"""

model = genai.GenerativeModel(model_name=SELECTED_MODEL, system_instruction=SYSTEM_PROMPT)

# ==========================================
# 4. 介面與對話邏輯
# ==========================================
st.set_page_config(page_title="工作場所融合度 AI 健檢系統", page_icon="⚖️")

# (CSS 美化區塊請保留您原本的版本)

st.title("⚖️ 工作場所融合度 AI 健檢系統")
st.markdown("歡迎使用！請簡單描述您在職場上遇到的狀況。例如：性別平等工作法（申請育嬰留職停薪、性別歧視及職場性騷擾問題等）就業服務法（就業歧視、薪資揭示問題等）、勞動基準法（工時、工資問題等）。顧問將根據台灣法規，為您進行環境友善度評估與法理分析。")

if "chat_session" not in st.session_state:
    st.session_state.chat_session = model.start_chat(history=[])

# 顯示對話歷史
for message in st.session_state.chat_session.history:
    role = "user" if message.role == "user" else "assistant"
    with st.chat_message(role):
        st.markdown(message.parts[0].text)

# 民眾提問
if user_input := st.chat_input("請輸入您的職場狀況..."):
    st.chat_message("user").markdown(user_input)
    with st.chat_message("assistant"):
        with st.spinner("顧問分析中..."):
            try:
                response = st.session_state.chat_session.send_message(user_input)
                st.markdown(response.text)
                
                # 存入 Session 供反饋區使用
                st.session_state.last_user_msg = user_input
                st.session_state.last_ai_reply = response.text
                
                # 初始紀錄寫入
                log_to_sheets_final(user_input, response.text)
                
            except Exception as e:
                if "429" in str(e):
                    st.error("🌟 系統繁忙（免費配額已達上限），請稍等一分鐘後再試。")
                else:
                    st.error(f"連線錯誤：{e}")

# ==========================================
# 5. 反饋互動與專人補充區
# ==========================================
if "last_ai_reply" in st.session_state:
    st.divider()
    st.subheader("📝 您的評價與專人服務申請")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("👍 分析很有幫助"):
            log_to_sheets_final(st.session_state.last_user_msg, st.session_state.last_ai_reply, feedback="滿意", status="結案")
            st.success("感謝回饋！")
            
    with col2:
        if st.button("❓ 需專人補充回復"):
            st.session_state.ask_expert = True

    if st.session_state.get("ask_expert", False):
        with st.form("expert_form"):
            st.info("請填寫聯繫資訊，勞資關係科人員將於上班時間聯繫您。")
            name = st.text_input("姓名")
            phone = st.text_input("電話")
            email = st.text_input("Email")
            note = st.text_area("備註")
            
            if st.form_submit_button("提交申請"):
                if name and (phone or email):
                    log_to_sheets_final(
                        st.session_state.last_user_msg, 
                        st.session_state.last_ai_reply, 
                        feedback="需專人服務", 
                        status="待處理",
                        name=name, phone=phone, email=email, note=note
                    )
                    st.success("已收到申請，專人將儘速與您聯絡。")
                    st.session_state.ask_expert = False
                else:
                    st.error("請填寫姓名與至少一種聯絡方式。")
