import streamlit as st
import google.generativeai as genai

# ==========================================
# 1. 系統設定與 API 金鑰讀取 (安全讀取版)
# ==========================================
try:
    # 這裡只能寫 "GOOGLE_API_KEY" 這個標籤名稱，讓程式去雲端保險箱抓密碼
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    st.error("⚠️ 尚未讀取到 API Key！請確認您已在 Streamlit Cloud 後台的 Settings > Secrets 中設定了 GOOGLE_API_KEY。")
    st.stop()

# ==========================================
# 2. 自動偵測模型 (終極防 404 機制)
# ==========================================
try:
    # 自動向 Google 詢問您的金鑰支援哪些模型
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    
    if not available_models:
        st.error("⚠️ 您的 API 金鑰目前沒有可用於文字生成的模型權限，可能金鑰已失效。")
        st.stop()

    # 優先選擇最新且穩定的 flash 模型
    selected_model = available_models[0]
    for m in available_models:
        if "1.5-flash" in m:
            selected_model = m
            break
            
    # 在側邊欄顯示狀態，若看到這行代表連線與套件都正常
    st.sidebar.success(f"✅ AI 核心連線成功！\n\n目前使用模型：\n`{selected_model}`")

except Exception as e:
    # 若出現 403 錯誤，通常是因為金鑰被 Google 發現寫在公開網頁而封鎖了
    if "403" in str(e) or "leaked" in str(e).lower():
        st.error("🚨 嚴重錯誤：您的 API 金鑰已因外洩被 Google 封鎖！")
        st.info("💡 解決步驟：\n1. 請至 Google AI Studio 申請一把全新的金鑰。\n2. 前往 Streamlit 後台 (Manage app > Settings > Secrets)。\n3. 將新金鑰填入 `GOOGLE_API_KEY = \"新金鑰\"` 並儲存。")
    else:
        st.error(f"⚠️ 讀取模型清單時發生連線錯誤：{e}")
    st.stop()

# ==========================================
# 3. 核心大腦：專業勞動法系統提示詞
# ==========================================
SYSTEM_PROMPT = """
你是一位精通台灣勞動法令、具備高度專業與同理心的「職場友善度健檢顧問」。
...（原本的指令）...

【最新修法與函釋重點】(請務必依此最新標準評估)
1. 2026年最新規定：若雇主拒絕提供育嬰留職停薪，裁罰基準已調整為...
2. 針對性別歧視之認定，近期勞動部函釋指出...
3. 雇主若未依法設置哺集乳室，可依《性別平等工作法》第...條開罰。

【核心守則】
1. 展現同理心：首先承接使用者的情緒，給予溫暖與支持的回應。
2. 嚴格區分歧視類型（法理重點）：若案件涉及不平等待遇，你必須精確判斷並使用正確法規名詞：
   - 若涉及懷孕、育嬰留停、性別、性傾向或性別氣質受不利對待，請明確歸類為違反《性別平等工作法》的「性別歧視」。
   - 若涉及年齡、容貌、階級、身心障礙等因素，請明確歸類為違反《就業服務法》的「就業歧視」。
   - 兩者的法源與地方政府的處理程序完全不同，絕不可混淆。
3. 勞動條件檢核：若涉及工時、加班費、請假權益受損，請引用《勞動基準法》相關概念進行評估。
4. 輸出健檢報告：給予 1-100 分綜合評分，並提供具體實用的行政救濟與蒐證建議（如：向地方勞動主管機關申訴、準備出勤證據）。
"""

# 建立模型實例
try:
    model = genai.GenerativeModel(
        model_name=selected_model,
        system_instruction=SYSTEM_PROMPT
    )
except Exception as e:
    st.error("⚠️ 模型建立失敗，這通常是 requirements.txt 內套件版本未設定正確所致。")
    st.stop()

# ==========================================
# 4. 網頁介面 (UI) 佈局與對話邏輯
# ==========================================
st.set_page_config(page_title="職場友善度 AI 健檢系統", page_icon="⚖️", layout="centered")
st.title("⚖️ 職場友善度 AI 健檢系統")
st.markdown("歡迎使用！請簡單描述您在職場上遇到的狀況（例如：申請育嬰留停的遭遇、工時問題等）。顧問將根據台灣法規，為您進行環境友善度評估與法理分析。")

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
            except Exception as e:
                st.error("⚠️ AI 分析過程發生連線錯誤。")
                st.error(f"錯誤詳細資訊: {e}")