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
    # 讀取 Gemini API 與 Google 試算表金鑰
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    st.error("⚠️ 尚未讀取到 API Key！請至 Streamlit Secrets 設定 GOOGLE_API_KEY。")
    st.stop()

# ==========================================
# 2. 自動偵測模型 (穩定免費版：Flash)
# ==========================================
try:
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    if not available_models:
        st.error("⚠️ 您的 API 金鑰目前沒有可用於文字生成的模型權限。")
        st.stop()

    selected_model = available_models[0]
    for m in available_models:
        if "flash" in m.lower():  
            selected_model = m
            break
except Exception as e:
    st.error(f"⚠️ 讀取模型清單時發生錯誤：{e}")
    st.stop()

# ==========================================
# 3. 試算表自動紀錄功能 (寫入函數)
# ==========================================
def log_to_sheets(user_msg, ai_reply):
    try:
        # 從 Secrets 讀取機器人 JSON 金鑰內容
        creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
        
        # 授權登入
        gc = gspread.service_account_from_dict(creds_dict)
        
        # 開啟試算表 (名稱須與您雲端硬碟建立的一致)
        # ⚠️ 請確保已將機器人 Email 加入此試算表的「編輯者」
        sheet = gc.open("職場健檢_民眾提問紀錄").sheet1
        
        # 設定為台灣時間
        tw_tz = pytz.timezone('Asia/Taipei')
        current_time = datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M:%S")
        
        # 寫入資料：時間、民眾提問、AI回覆
        sheet.append_row([current_time, user_msg, ai_reply])
    except Exception as e:
        # 僅在系統後台顯示錯誤，不干擾民眾對話
        print(f"資料庫紀錄異常：{e}")

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
4. 輸出健檢報告：給予 1-100 分綜合評分，並提供蒐證建議與申訴管道。
5. 官方結語提醒：在每一次回答的最後一行，固定加上這句話：「如仍有疑義歡迎來電02-24287801 基隆市政府關心你」。
"""

try:
    model = genai.GenerativeModel(
        model_name=selected_model,
        system_instruction=SYSTEM_PROMPT
    )
except Exception as e:
    st.error("⚠️ 模型建立失敗，請確認 requirements.txt 已正確設定。")
    st.stop()

# ==========================================
# 5. 網頁介面 (UI) 佈局與美化
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

# 對話紀錄初始化
if "chat_session" not in st.session_state:
    st.session_state.chat_session = model.start_chat(history=[])

# 顯示對話歷史
for message in st.session_state.chat_session.history:
    role = "user" if message.role == "user" else "assistant"
    with st.chat_message(role):
        st.markdown(message.parts[0].text)

# 民眾輸入區
if user_input := st.chat_input("請輸入您的職場狀況或疑問..."):
    st.chat_message("user").markdown(user_input)
    
    with st.chat_message("assistant"):
        with st.spinner("顧問法理分析中，請稍候..."):
            try:
                response = st.session_state.chat_session.send_message(user_input)
                st.markdown(response.text)
                
                # 🎯 回答完畢，自動背景同步至 Google 試算表
                log_to_sheets(user_input, response.text)
                
            except Exception as e:
                st.error("⚠️ AI 分析過程發生連線錯誤。")
                st.error(f"錯誤詳細資訊: {e}")
