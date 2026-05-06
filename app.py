import streamlit as st
import google.generativeai as genai
import gspread
import json
from datetime import datetime
import pytz
import requests

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
# 2. 🎯 安全動態模型選擇 (解決 404 找不到模型)
# ==========================================
try:
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    
    if 'models/gemini-1.5-flash-latest' in available_models:
        SELECTED_MODEL = 'gemini-1.5-flash-latest'
    elif 'models/gemini-1.5-flash' in available_models:
        SELECTED_MODEL = 'gemini-1.5-flash'
    elif 'models/gemini-1.5-pro' in available_models:
        SELECTED_MODEL = 'gemini-1.5-pro'
    elif 'models/gemini-pro' in available_models:
        SELECTED_MODEL = 'gemini-pro'
    else:
        SELECTED_MODEL = available_models[0].replace("models/", "")
        
except Exception as e:
    SELECTED_MODEL = "gemini-1.5-pro"

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
        
        # 寫入順序：A(時間), B(提問), C(回覆), D(評價), E(狀態), F(姓名), G(性別), H(電話), I(Email), J(備註)
        sheet.append_row([current_time, user_msg, ai_reply, feedback, status, name, gender, phone, email, note])
    except Exception as e:
        print(f"資料庫紀錄異常：{e}")

# ==========================================
# 3.1 LINE Messaging API 強化通知功能
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
        
        if res.status_code != 200:
            st.warning(f"⚠️ LINE 通知無法送達，錯誤代碼：{res.status_code}。請檢查金鑰或權限設定。")
            print(f"LINE 發送失敗：{res.text}")
            
    except Exception as e:
        print(f"LINE 系統異常：{e}")

# ==========================================
# 4. 核心大腦設定 (⚖️ 強制防幻想機制)
# ==========================================
SYSTEM_PROMPT = """
你是一位精通台灣勞動法令、具備高度專業與同理心的「職場友善度健檢顧問」。
請根據使用者描述的職場狀況，進行客觀分析與評估。

【🚨 絕對防幻想與專業查證原則】
1. 直接回覆：首先承接使用者的情緒，給予溫暖與支持的回應，並「優先直接針對問題給出明確的答案」。
2. 問題概述與法令分析：接著，請明確標示出【問題概述】與【法令分析】兩個段落。
   - ⚠️ 防護機制啟動：在【法令分析】中，若要引用勞動部函釋或法院判決，**必須是你資料庫中真實存在的日期與文號**。若你不確定確切的函釋字號，請直接回答「依據勞動部相關函釋精神...」，**絕對禁止自行發明、捏造或拼湊不存在的函釋文號或法規條次！** 無關之法規切勿贅述。
3. 最新法規：請務必以台灣官方最新發布的勞動法令（如全國法規資料庫、勞動部最新函釋）為準。不知道確切法規時，請建議民眾由專人協助查證。

【核心守則】
1. 嚴格區分歧視類型：
   - 若涉及懷孕、育嬰留停、性別、性傾向等不利對待，歸類為違反《性別平等工作法》的「性別歧視」。
   - 若涉及年齡、容貌、身心障礙等因素，歸類為違反《就業服務法》的「就業歧視」。
2. 勞動條件檢核：涉及工時、工資問題請引用《勞動基準法》及相關勞動法令。
3. 輸出健檢報告：給予 1-100 分綜合評分，並提供具體蒐證建議與申訴管道。
4. 官方結語提醒：在每一次回答的最後一行，固定加上這句話：「如仍有疑義歡迎來電02-24287801 基隆市政府關心你」。
"""

try:
    # 加入 generation_config，將 temperature 調低 (0.1)，大幅降低幻想與胡編亂造的機率
    generation_config = genai.GenerationConfig(
        temperature=0.1,
        top_p=0.8,
    )
    model = genai.GenerativeModel(
        model_name=SELECTED_MODEL,
        system_instruction=SYSTEM_PROMPT,
        generation_config=generation_config
    )
except Exception as e:
    st.error(f"⚠️ 模型建立失敗：{e}")
    st.stop()

# ==========================================
# 5. 網頁介面佈局與深色模式防呆美化
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
st.markdown("歡迎使用！請簡單描述您在職場上遇到的狀況，顧問將根據台灣法規，為您進行環境友善度評估與法理分析。")

if "chat_session" not in st.session_state:
    st.session_state.chat_session = model.start_chat(history=[])

for message in st.session_state.chat_session.history:
    role = "user" if message.role == "user" else "assistant"
    with st.chat_message(role):
        st.markdown(message.parts[0].text)

if user_input := st.chat_input("請簡單描述您的狀況（為保護隱私，請勿在此處輸入真實姓名或身分證字號）..."):
    st.chat_message("user").markdown(user_input)
    with st.chat_message("assistant"):
        with st.spinner(f"顧問分析中... (查證法規中，請稍候)"):
            try:
                response = st.session_state.chat_session.send_message(user_input)
                st.markdown(response.text)
                
                st.session_state.last_user_msg = user_input
                st.session_state.last_ai_reply = response.text
                
                log_to_sheets_perfect(user_input, response.text)
                
            except Exception as e:
                if "429" in str(e):
                    st.error("🌟 系統目前繁忙中（配額暫時已達上限，請稍候片刻再試）。")
                    st.info("如您有急迫法律需求，歡迎致電基隆市政府諮詢專線：02-24287801。")
                else:
                    st.error(f"⚠️ 連線錯誤：{e}")

# ==========================================
# 6. 反饋互動與專人補充表單 
# ==========================================
if "last_ai_reply" in st.session_state:
    st.divider()
    st.subheader("📝 您對本次分析滿意嗎？")
    
    col1, col2 = st.columns(2)
    
    # 🎯 左側：滿意度 1-10 分評分區塊
    with col1:
        with st.form("rating_form"):
            st.markdown("**請給予滿意度評分**")
            score = st.slider("(1分為最不滿意，10分為非常滿意)", min_value=1, max_value=10, value=10)
            if st.form_submit_button("送出評分"):
                # 寫入試算表
                log_to_sheets_perfect(st.session_state.last_user_msg, st.session_state.last_ai_reply, feedback=f"評分：{score}分", status="結案")
                # 發送 LINE 通知給管理員
                send_line_message(f"📊【滿意度評分回饋】\n系統剛收到一筆新評分：{score} 分！\n民眾提問概要：{st.session_state.last_user_msg[:30]}...")
                st.success(f"感謝您的回饋！您給予了 {score} 分。")
            
    # 🎯 右側：專人服務請求按鈕
    with col2:
        st.markdown("**需要進一步的專人協助嗎？**")
        if st.button("❓ 填寫專人服務表單"):
            st.session_state.show_expert_form = True

    # 🎯 專人服務表單區塊
    if st.session_state.get("show_expert_form", False):
        st.markdown("---")
        with st.form("pro_contact"):
            st.info("請填寫聯繫資訊，基隆市政府人員將於上班時間聯繫您。")
            
            name = st.text_input("您的姓名/稱呼")
            user_gender = st.radio("您的性別", ["男", "女", "其他"], horizontal=True)
            
            # 🎯 修正：移除 LINE 回覆，僅保留電話與 Email
            contact_method = st.radio("您希望專人如何回覆您？", ["電話回覆", "Email 回覆"], horizontal=True)
            
            phone = st.text_input("聯絡電話")
            email = st.text_input("Email 回復")
            note = st.text_area("其他備註說明")
            
            st.markdown("---")
            consent = st.checkbox("我同意基隆市政府依《個人資料保護法》規定，蒐集、處理及利用上述個人資料，僅限於本次職場健檢諮詢與聯繫使用。")
            
            if st.form_submit_button("送出申請"):
                if not consent:
                    st.error("⚠️ 請勾選同意個資聲明，我們才能依法為您服務喔！")
                elif not name:
                    st.error("請提供您的姓名或稱呼。")
                elif contact_method == "電話回覆" and not phone:
                    st.error("⚠️ 您選擇了「電話回覆」，請務必填寫聯絡電話。")
                elif contact_method == "Email 回覆" and not email:
                    st.error("⚠️ 您選擇了「Email 回覆」，請務必填寫 Email。")
                else:
                    title = "先生" if user_gender == "男" else "女士（小姐）" if user_gender == "女" else ""
                    
                    final_note = f"【希望以 {contact_method}】\n"
                    if note:
                        final_note += f"備註: {note}"
                    
                    log_to_sheets_perfect(
                        st.session_state.last_user_msg, 
                        st.session_state.last_ai_reply, 
                        feedback="需專人服務", 
                        status="待處理",
                        name=name,        
                        gender=user_gender, 
                        phone=phone,      
                        email=email,      
                        note=final_note   
                    )
                    
                    # 傳送 LINE 即時推播通知
                    notify_msg = f"\n🚨【專人服務請求】🚨\n民眾：{name} {title}\n偏好：{contact_method}\n"
                    if contact_method == "電話回覆": notify_msg += f"電話：{phone}\n"
                    elif contact_method == "Email 回覆": notify_msg += f"Email：{email}\n"
                    notify_msg += f"備註：{note}\n請勞資關係科同仁盡速至試算表查看。"
                    
                    send_line_message(notify_msg)
                    
                    st.success(f"{name} {title} 好，您的申請已成功送出！專人將儘速與您聯繫。")
                    st.session_state.show_expert_form = False
