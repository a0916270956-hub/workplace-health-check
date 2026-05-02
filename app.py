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
# 2. 自動偵測模型 (穩定高配額版：優先使用 1.5-Flash)
# ==========================================
try:
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    
    # 🎯 關鍵修正：優先尋找 1.5-flash，它的免費額度比 2.5 系列多出數十倍
    selected_model = None
    # 第一順位：1.5-flash
    for m in available_models:
        if "gemini-1.5-flash" in m.lower():
            selected_model = m
            break
    
    # 若沒有 1.5，則找任何 flash
    if not selected_model:
        for m in available_models:
            if "flash" in m.lower():
                selected_model = m
                break
                
    # 若連 flash 都沒有，才用第一個
    if not selected_model:
        selected_model = available_models[0]

except Exception as e:
    st.error(f"⚠️ 讀取模型清單時發生錯誤：{e}")
    st.stop()

# ==========================================
# 3. 試算表自動紀錄功能
# ==========================================
def log_to_sheets(user_msg, ai_reply):
    try:
        creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
        gc = gspread.service_account_from_dict(creds_dict)
        sheet = gc.open("職場健檢_民眾提問紀錄").sheet1
        
        tw_tz = pytz.timezone('Asia/Taipei')
        current_time = datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M:%S")
        
        sheet.append_row([current_time, user_msg, ai_reply])
    except Exception as e:
        print(f"資料庫紀錄異常（不影響前端）：{e}")

# ==========================================
# 4. 核心大腦：專業勞動法系統提示詞
# ==========================================
SYSTEM_PROMPT = """
你是一位精通台灣勞動法令、具備高度專業與同理心的「職場友善度健檢顧問」。
請根據使用者描述的職場狀況，進行客觀分析與評估。

【最新修法與函釋重點】(請務必依此最新標準評估)
1. 2026年最新規定：若雇主拒絕提供育嬰留職停薪，裁罰基準已調整。
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
        model_name=selected_model,
        system_instruction=SYSTEM_PROMPT
    )
except Exception as e:
    st.error("⚠️ 模型建立失敗。")
    st.stop()

# ==========================================
# 5. 網頁介面佈局與美化
# ==========================================
st.set_page_config(page_title="工作場所融合度 AI 健檢系統", page_icon="⚖️", layout="centered")

st.markdown("""
<style>
    html, body, [class*="css"] {
        font-family: '微軟正黑體', 'Noto Sans TC', sans-serif !important;
    }
    .stApp {
        background: linear-gradient(to bottom, #E8F1F8 0%, #FFFFFF 100%);
    }
    h1 {
        color: #003366 !important;
        font-weight: 800;
        text-align: center;
        padding-bottom: 15px;
        border-bottom: 3px solid #00509E;
        margin-bottom: 30px;
    }
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stChatMessage {
        background-color: #FFFFFF;
        border: 1px solid #D1E1F0;
        border-radius: 15px;
        padding: 15px;
        margin-bottom: 15px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.03);
    }
</style>
""", unsafe_allow_html=True)

st.title("⚖️ 工作場所融合度 AI 健檢系統")
st.markdown("歡迎使用！請簡單描述您在職場上遇到的狀況。例如：性別平等工作法（申請育嬰留職停薪、職場性騷擾問題等）就業服務法（就業歧視、薪資揭示問題等）、勞動基準法（工時、工資問題等）。顧問將根據台灣法規，為您進行環境友善度評估與法理分析。")


if "chat_session" not in st.session_state:
    st.session_state.chat_session = model.start_chat(history=[])

for message in st.session_state.chat_session.history:
    role = "user" if message.role == "user" else "assistant"
    with st.chat_message(role):
        st.markdown(message.parts[0].text)

if user_input := st.chat_input("請輸入您的職場狀況或疑問..."):
    st.chat_message("user").markdown(user_input)
    
    with st.chat_message("assistant"):
        with st.spinner("顧問法理分析中，請稍候..."):
            try:
                response = st.session_state.chat_session.send_message(user_input)
                st.markdown(response.text)
                log_to_sheets(user_input, response.text)
                
            except Exception as e:
                # 🎯 捕捉 429 錯誤並轉化為友善中文提示
                if "429" in str(e):
                    st.error("🌟 系統目前繁忙中（今日免費諮詢量已達上限）。")
                    st.info("由於免費版 AI 資源有限，請稍等幾分鐘後再試，或於明天再次使用。")
                    st.info("如您有急迫的法律需求，歡迎直接致電基隆市政府諮詢專線：02-24287801。")
                else:
                    st.error(f"⚠️ AI 分析過程發生連線錯誤：{e}")
