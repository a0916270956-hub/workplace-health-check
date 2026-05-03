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
# 2. 🎯 終極修正：安全動態模型選擇 (自動降級機制)
# ==========================================
try:
    # 取得您這把 API Key 真正能看見的所有可用模型
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    
    # 依序尋找可用的模型：1.5-flash -> 1.5-pro -> 1.0-pro -> gemini-pro
    if 'models/gemini-1.5-flash' in available_models:
        SELECTED_MODEL = 'gemini-1.5-flash'
    elif 'models/gemini-1.5-pro' in available_models:
        SELECTED_MODEL = 'gemini-1.5-pro'
    elif 'models/gemini-1.0-pro' in available_models:
        SELECTED_MODEL = 'gemini-1.0-pro'
    elif 'models/gemini-pro' in available_models:
        SELECTED_MODEL = 'gemini-pro'
    else:
        # 如果都沒有，就硬抓第一個能用的
        SELECTED_MODEL = available_models[0].replace("models/", "")
        
except Exception as e:
    # 最壞情況下的絕對保底模型
    SELECTED_MODEL = "gemini-pro"

# ==========================================
# 3. 完美版寫入函數：支援姓名與性別交換位置
# ==========================================
def log_to_sheets_perfect(user_msg, ai_reply, feedback="", status="已回答", name="", gender="", phone="", email="", note=""):
    try:
        creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
        gc = gspread.service_account_from_dict(creds_dict)
        sheet = gc.open("職場健檢_民眾提問紀錄").sheet1
        
        tw_tz = pytz.timezone('Asia/Taipei')
        current_time = datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M:%S")
        
        # 依照標題列順序寫入資料：姓名(F)、性別(G)
        sheet.append_row([current_time, user_msg, ai_reply, feedback, status, name, gender, phone, email, note])
    except Exception as e:
        print(f"資料庫紀錄異常：{e}")

# ==========================================
# 4. 核心大腦設定
# ==========================================
SYSTEM_PROMPT = """
你是一位精通台灣勞動法令、具備高度專業與同理心的「職場友善度健檢顧問」。
請根據使用者描述的職場狀況，進行客觀分析與評估。

【最新修法與函釋重點】(請務必依此最新標準評估)
1. 2026年最新規定：若雇主拒絕提供育嬰留職停薪，裁罰基準已調高並強化執行。
2. 針對性別歧視之認定，應參考勞動部最新函釋標準。
3. 雇主若未依法設置哺集乳室，可依《性別平等工作法》開罰。

【核心守則】
1. 展現同理心：首先承接使用者的情緒，給予溫暖與支持的回應。
2. 嚴格區分歧視類型：
   - 若涉及懷孕、育嬰留停、性別、性傾向等不利對待，請歸類為違反《性別平等工作法》的「性別歧視」。
   - 若涉及年齡、容貌、身心障礙等因素，請歸類為違反《就業服務法》的「就業歧視」。
3. 勞動條件檢核：涉及工時、工資問題請引用《勞動基準法》。
4. 輸出健檢報告：給予 1-100 分綜合評分，並提供具體蒐證建議與申訴管道。
5. 官方結語提醒：在每一次回答的最後一行，固定加上這句話：「如仍有疑義歡迎來電02-24287801 基隆市政府關心你」。
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
# 5. 網頁介面佈局
# ==========================================
st.set_page_config(page_title="工作場所融合度 AI 健檢系統", page_icon="⚖️", layout="centered")

# 介面美化
st.markdown("""
<style>
    html, body, [class*="css"] { font-family: '微軟正黑體', sans-serif !important; }
    .stApp { background: linear-gradient(to bottom, #E8F1F8 0%, #FFFFFF 100%); }
    h1 { color: #003366 !important; text-align: center; border-bottom: 3px solid #00509E; padding-bottom: 10px; }
    .stChatMessage { background-color: #FFFFFF; border-radius: 15px; border: 1px solid #D1E1F0; box-shadow: 0 4px 8px rgba(0,0,0,0.03); }
</style>
""", unsafe_allow_html=True)

st.title("⚖️ 工作場所融合度 AI 健檢系統")
st.markdown("歡迎使用！請簡單描述您在職場上遇到的狀況。例如：性別平等工作法（申請育嬰留職停薪、性別歧視及職場性騷擾問題等）就業服務法（就業歧視、薪資揭示問題等）、勞動基準法（工時、工資問題等）。顧問將根據台灣法規，為您進行環境友善度評估與法理分析。")

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
        with st.spinner(f"顧問分析中... (目前使用模型: {SELECTED_MODEL})"):
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
# 6. 反饋互動與專人補充表單
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
            
            # 順序：姓名在前，性別在後
            name = st.text_input("您的姓名/稱呼")
            user_gender = st.radio("您的性別", ["男", "女", "其他"], horizontal=True)
            
            phone = st.text_input("聯絡電話")
            email = st.text_input("Email 回復")
            note = st.text_area("其他備註說明")
            
            if st.form_submit_button("送出申請"):
                if not name or not (phone or email):
                    st.error("請提供姓名與至少一種聯繫方式（電話或 Email）。")
                else:
                    # 稱謂優化邏輯
                    title = ""
                    if user_gender == "男":
                        title = "先生"
                    elif user_gender == "女":
                        title = "女士（小姐）"
                    
                    log_to_sheets_perfect(
                        st.session_state.last_user_msg, 
                        st.session_state.last_ai_reply, 
                        feedback="需專人服務", 
                        status="待處理",
                        name=name,        
                        gender=user_gender, 
                        phone=phone,      
                        email=email,      
                        note=note         
                    )
                    st.success(f"{name} {title} 好你的申請已送出！專人將儘速與你聯繫。")
                    st.session_state.show_expert_form = False
