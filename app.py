import streamlit as st
import google.generativeai as genai

# ==========================================
# 1. 系統設定與 AI 大腦初始化
# ==========================================
# 請替換成您申請的 Gemini API Key
GOOGLE_API_KEY = "AIzaSyA5wbhSQwwwL5Wo1UjZ9knVwJ2vsmWYWUM" 
genai.configure(api_key=GOOGLE_API_KEY)

# 定義專業的系統提示詞 (System Prompt)
SYSTEM_PROMPT = """
你是一位熟悉台灣勞動法規的「職場友善度健檢顧問」。
請根據使用者描述的職場狀況，進行客觀分析與評估。

【核心守則】
1. 展現同理心：先承接使用者的情緒，給予溫暖的回應。
2. 精準法規分類：在涉及歧視案件時，必須嚴格區分並指明是屬於《性別平等工作法》的「性別歧視」（如孕產、育嬰留停、性別氣質受不利對待），還是屬於《就業服務法》範疇的一般「就業歧視」。分類務必精確，不可混淆。
3. 評估報告：最後請給出「綜合友善度評分（1-100分）」，並提供具體的自我保護或申訴建議。
"""

# 建立模型實例
model = genai.GenerativeModel(
    model_name="gemini-1.5-pro",  # 改用這個更進階且穩定的名稱
    system_instruction=SYSTEM_PROMPT
)

# ==========================================
# 2. 網頁介面 (UI) 佈局
# ==========================================
st.set_page_config(page_title="職場友善度 AI 健檢", page_icon="⚖️", layout="centered")
st.title("⚖️ 職場友善度 AI 健檢顧問")
st.markdown("歡迎！請簡單描述您在職場上遇到的狀況（例如：工時問題、請假被拒、升遷疑慮等），AI 將為您進行初步的環境友善度評估。")

# ==========================================
# 3. 聊天紀錄狀態管理 (Session State)
# ==========================================
# 確保網頁重新整理時，對話紀錄不會消失
if "chat_session" not in st.session_state:
    st.session_state.chat_session = model.start_chat(history=[])

# 在畫面上渲染過去的對話紀錄
for message in st.session_state.chat_session.history:
    role = "user" if message.role == "user" else "assistant"
    with st.chat_message(role):
        st.markdown(message.parts[0].text)

# ==========================================
# 4. 接收使用者輸入與生成回應
# ==========================================
# 網頁下方的對話輸入框
if user_input := st.chat_input("請輸入您的職場狀況或疑問..."):
    # 顯示使用者的訊息
    st.chat_message("user").markdown(user_input)
    
    # 呼叫 AI 生成回覆 (顯示載入中的動畫)
    with st.chat_message("assistant"):
        with st.spinner("顧問分析中，請稍候..."):
            response = st.session_state.chat_session.send_message(user_input)
            st.markdown(response.text)
