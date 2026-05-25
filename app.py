import streamlit as st
import google.generativeai as genai
import gspread
import json
import os
import time
from datetime import datetime
import pytz
import requests
import tempfile
import shutil

# ==========================================
# 1. 系統設定與 API 金鑰讀取 (終極解決 Dark Mode 字體隱形問題)
# ==========================================
st.set_page_config(page_title="工作場所融合度 AI 健檢系統", page_icon="⚖️", layout="centered")

# 升級版全自動適應 CSS：精準控制對話框與聊天輸入框在深色模式(Dark Mode)下的外觀
st.markdown("""
<style>
    html, body { font-family: '微軟正黑體', sans-serif !important; }
    .stApp { background: linear-gradient(to bottom, #E8F1F8 0%, #FFFFFF 100%) !important; }
    h1 { color: #003366 !important; text-align: center; border-bottom: 3px solid #00509E; padding-bottom: 10px; }
    
    /* === 核心修正：讓聊天輸入框文字、提示字、游標在任何模式下均清晰可見 === */
    .stChatInput p, .stChatInput textarea {
        color: var(--text-color, #262730) !important;
        -webkit-text-fill-color: var(--text-color, #262730) !important;
        caret-color: var(--text-color, #262730) !important; /* 確保游標閃爍可見 */
    }
    
    /* 修正深色模式下輸入框預設提示字的顏色 */
    .stChatInput textarea::placeholder {
        color: #888888 !important;
        -webkit-text-fill-color: #888888 !important;
        opacity: 1 !important;
    }
    
    /* 確保歷史對話框內部的 Markdown 文字不會因深色模式變白而隱形 */
    .stChatMessage { 
        background-color: #FFFFFF !important; 
        border-radius: 15px; 
        border: 1px solid #D1E1F0; 
        box-shadow: 0 4px 8px rgba(0,0,0,0.03); 
    }
    .stChatMessage p, .stChatMessage li, .stChatMessage span, .stChatMessage div {
        color: #262730 !important;
    }
</style>
""", unsafe_allow_html=True)

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    st.error("⚠️ 尚未讀取到 API Key！請至 Streamlit Secrets 設定 GOOGLE_API_KEY。")
    st.stop()

# ==========================================
# 2. 🎯 側邊欄與動態模型選擇 (極速 Flash 優先)
# ==========================================
with st.sidebar:
    st.markdown("### 🏛️ 官方實用資源")
    st.markdown("[🔍 勞動部勞動法令查詢系統](https://laws.mol.gov.tw/)")
    st.markdown("[📖 全國法規資料庫](https://law.moj.gov.tw/)")
    st.divider()
    
    st.markdown("### ⚙️ 系統進階設定")
    st.markdown("若對話時發生錯誤，可從下方選單切換您的金鑰所支援的模型：")
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        if not available_models:
            st.error("⚠️ 您的 API Key 無法存取任何可用的模型！請至 Google AI Studio 確認金鑰狀態。")
            st.stop()
            
        default_index = 0
        flash_priority = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
        
        found = False
        for target_flash in flash_priority:
            for i, m_name in enumerate(available_models):
                if target_flash in m_name:
                    default_index = i
                    found = True
                    break
            if found:
                break
                
        SELECTED_MODEL = st.selectbox("請選擇 AI 模型", available_models, index=default_index)
    except Exception as e:
        st.error(f"讀取模型清單失敗：{e}")
        SELECTED_MODEL = "models/gemini-2.5-flash"

# ==========================================
# 3. 完美版寫入函數 (Google Sheets 同行寫入與多欄位併存更新機制)
# ==========================================
def log_to_sheets_perfect(user_msg, ai_reply, feedback="", status="已回答", name="", gender="", phone="", email="", note=""):
    """ 負責初次寫入提問紀錄，並回傳該筆資料在 Google Sheets 的列號(Row Index) """
    try:
        creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
        gc = gspread.service_account_from_dict(creds_dict)
        sheet = gc.open("職場健檢_民眾提問紀錄").sheet1
        tw_tz = pytz.timezone('Asia/Taipei')
        current_time = datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M:%S")
        
        row_data = [current_time, user_msg, ai_reply, feedback, status, name, gender, phone, email, note]
        sheet.append_row(row_data)
        
        return len(sheet.get_all_values())
    except Exception as e:
        return None

def update_sheets_row(row_index, feedback=None, status=None, name=None, gender=None, phone=None, email=None, note=None):
    """ 依據初次寫入時獲得的列號，精準更新同一行的指定欄位，支援多個欄位同時併存 """
    if not row_index:
        return
    try:
        creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
        gc = gspread.service_account_from_dict(creds_dict)
        sheet = gc.open("職場健檢_民眾提問紀錄").sheet1
        
        # 欄位對應：D=feedback(4), E=status(5), F=name(6), G=gender(7), H=phone(8), I=email(9), J=note(10)
        if feedback is not None: sheet.update_cell(row_index, 4, feedback)
        if status is not None:   sheet.update_cell(row_index, 5, status)
        if name is not None:     sheet.update_cell(row_index, 6, name)
        if gender is not None:   sheet.update_cell(row_index, 7, gender)
        if phone is not None:    sheet.update_cell(row_index, 8, phone)
        if email is not None:    sheet.update_cell(row_index, 9, email)
        if note is not None:     sheet.update_cell(row_index, 10, note)
    except Exception as e:
        pass

def send_line_message(message_text):
    try:
        channel_access_token = st.secrets["LINE_CHANNEL_ACCESS_TOKEN"]
        admin_user_id = st.secrets["LINE_ADMIN_USER_ID"]
        url = "https://api.line.me/v2/bot/message/push"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {channel_access_token}"}
        data = {"to": admin_user_id, "messages": [{"type": "text", "text": message_text}]}
        requests.post(url, headers=headers, json=data)
    except Exception as e:
        pass

# ==========================================
# 4. 核心大腦設定 (⚖️ 融合官方手冊與強制直接引用規範)
# ==========================================
SYSTEM_PROMPT = """
你是一位精通台灣勞動法令的「基隆市政府職場友善度健檢顧問」。

【🏆 最高指導原則：官方手冊優先】
對話系統已經向你載入了最新的《114年勞動基準法規彙編》與《職場工作平權宣導手冊》。
當民眾提問時，你必須「優先且絕對」從這兩份官方檔案中搜尋相關條文、函釋與指引來回答。

【🚨 函釋與法規引用強制規則（核心指令）】
1. 當你需要引用《114年勞動基準法規彙編》或《職場工作平權宣導手冊》內收錄的行政解釋、函釋或實務見解時，請「直接完整引用發文機關、發文日期、發文字號及函釋重點」。
2. 【絕對禁止】在回答中使用頁碼或書籍排版式的糢糊指引。例如，絕對不能回覆類似於：「參照勞動基準法規彙編第403頁『勞工下班未直接返家……』」這樣的格式。你必須將其轉化為具體的機關文號與核心法理。
3. 【歷史機關正名要求】引用歷史函釋或舊公文時，若發文單位為行政院勞工委員會，你在輸出時「必須一律寫為：改制前行政院勞工委員會」；若發文單位為內政部，且屬於處理勞工事務時期，則「必須一律寫為：內政部主管勞工事務時期」。

【🚨 防幻想與字數限制原則】
1. 嚴格字數限制：每次回覆的「總字數請務必嚴格控制在 500 字以內」。文字需極度精簡、直擊核心，切勿長篇大論。
2. 直接回覆：首先承接使用者的情緒，給予溫暖與支持的回應，並「優先直接針對問題給出明確的答案」。
3. 問題概述與法令分析：接著，請明確標示出【問題概述】與【法令分析】兩個段落。
4. 🎯 精準鎖定法規與正名 (寧缺勿濫)：在內心判斷爭議類型後，懷孕/性別歧視僅限《性別平等工作法》；年齡/身障歧視僅限《就業服務法》；一般勞動條件(薪資/工時/資遣)僅限《勞動基準法》。【極度重要】原法規已修法更名，你在回覆中「絕對禁止」輸出舊稱「性別工作平等法」，請務必全面使用最新名稱「性別平等工作法」。絕對禁止為了湊字數跨界亂引法條。
5. 🛑 絕對禁止捏造字號：在【法令分析】中，「絕對禁止」自行發明、拼湊或臆測任何具體的「函釋字號」、「文號」、「判決字號」或「發布日期」。除非你在上傳的 PDF 手冊中或大腦知識庫中確實查到該函釋字號，否則一律使用「依據主管機關相關函釋精神」或「依據實務見解」帶過。
6. 🛡️ 寧缺勿濫原則：若民眾描述的情況過於模糊、或你完全無法確定適用的法律條文，請坦承告知：「此情況較為複雜，為求正確與寧缺勿濫，建議您直接向主管機關確認細節。」，絕對不允許強行猜测。
7. 官方結語與查證連結：在每一次回答的最末端，請固定附上以下內容（計入 500 字內）：
   ---
   📚 **官方查證資源：**
   * 勞動部勞動法令查詢系統：https://laws.mol.gov.tw/
   * 全國法規資料庫：https://law.moj.gov.tw/
   
   📞 **如仍有疑義歡迎來電 02-24287801，基隆市政府法制及勞動處關心您。**

【💎 專屬法規知識庫 (精準打擊區)】
- 爭議點：公務機關技工、工友「考績獎金」是否計入平均工資？
- 強制引用：改制前行政院勞工委員會民國96年6月26日勞動2字第0960071251號函釋要旨不列入平均工資計算。考績獎金：公務機構依年終考核發給之考績獎金，並非勞動契約事先約定之給與。因其發放標準與對象均屬不確定，屬於勞工不可期待之報酬，故難認定為工資，可不計入平均工資。
- 爭議點：女性勞動者因病切除子宮及卵巢（或切除兩者之一）之生理假認定？
- 強制引用：勞動部民國105年2月3日勞動條4字第1040132621號函釋要旨如下：依性別平等工作法第14條規定，女性受僱者因生理日致工作有困難者，每月得請生理假一日。針對女性勞動者因病切除子宮及卵巢（或切除兩者之一）之生理假認定，若經病史、基礎體溫或檢測血中荷爾蒙等適當醫學方法，合理判斷其仍有排卵功能，且於排卵日及原行經之日，仍因荷爾蒙變化而有身體不適致工作困難者，該症狀應屬「廣義生理日」之認定範圍，依法仍得請生理假。另重申，依現行性別平等工作法細則第13條規定，受僱者提出生理假申請時，無需提出證明文件。

【📖 黃金標準問答範例參考】
【問題概述】您面臨的是通勤災害是否認定為職業災害的爭議。
【法令分析】依據改制前行政院勞工委員會（現勞動部）中華民國75年6月23日台內勞字第410301號函釋意旨，勞工於上下班途中，若於適當時間，以適當交通方法，自住宅往返就業場所之轉赴途中發生車禍，其非因故意或重大過失所致者，應屬職業災害。然而，若勞工下班後未直接返家，而是從事與日常居住生活無正當關聯之行為而偏離常軌發生車禍，則難以認定為職業災害。
"""

# ==========================================
# 5. ⚡ 全域快取：官方檔案載入機制 (極速秒開網頁)
# ==========================================
@st.cache_resource(show_spinner=False)
def get_cached_gemini_files():
    files_to_upload = ["114年勞動基準法規彙編.pdf", "職場工作平權宣導手冊.pdf"]
    uploaded_files = []
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    for file_name in files_to_upload:
        file_path = os.path.join(current_dir, file_name)
        if os.path.exists(file_path):
            try: 
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    shutil.copyfile(file_path, tmp_file.name)
                    gemini_file = genai.upload_file(tmp_file.name, mime_type="application/pdf")
                
                while gemini_file.state.name == "PROCESSING":
                    time.sleep(0.5)
                    gemini_file = genai.get_file(gemini_file.name)
                uploaded_files.append(gemini_file)
            except:
                pass
    return uploaded_files

# 執行高速初始化
with st.spinner("⏳ 系統極速初始化中，請稍候..."):
    global_gemini_files = get_cached_gemini_files()

# --- 初始化或切換模型對話紀錄 ---
if "chat_session" not in st.session_state or st.session_state.get("current_model_name") != SELECTED_MODEL:
    try:
        generation_config = genai.GenerationConfig(temperature=0.0, top_p=0.8)
        model = genai.GenerativeModel(
            model_name=SELECTED_MODEL,
            system_instruction=SYSTEM_PROMPT,
            generation_config=generation_config
        )
        
        initial_history = []
        if global_gemini_files:
            parts = global_gemini_files + ["請徹底熟讀以上兩份官方手冊。接下來民眾的所有提問，請『絕對優先』依照這兩份手冊內的法規、函釋與指引來進行健檢評估。"]
            initial_history.append({"role": "user", "parts": parts})
            initial_history.append({"role": "model", "parts": ["收到！我已完整讀取並記憶《114年勞動基準法規彙編》與《職場工作平權宣導手冊》。我將嚴格遵守法規發文日期與文號的引用規則，為市民解答。"]})
        
        st.session_state.chat_session = model.start_chat(history=initial_history)
        st.session_state.current_model_name = SELECTED_MODEL
        
    except Exception as e:
        st.error(f"⚠️ 模型初始化失敗：{e}")
        st.stop()

# --- 顯示歷史訊息 ---
for message in st.session_state.chat_session.history:
    if message.role == "user" and "請徹底熟讀以上兩份官方手冊" in message.parts[-1].text:
        continue
    if message.role == "model" and "收到！我已完整讀取" in message.parts[0].text:
        continue
        
    role = "user" if message.role == "user" else "assistant"
    with st.chat_message(role):
        st.markdown(message.parts[0].text)

# --- 處理使用者提問 (問完即刻寫入試算表同行) ---
if user_input := st.chat_input("請簡單描述您的狀況（為保護隱私，請勿在此處輸入真實姓名或身分證字號）..."):
    st.chat_message("user").markdown(user_input)
    with st.chat_message("assistant"):
        with st.spinner(f"AI顧問正進行深度分析中... 請稍候"):
            try:
                response = st.session_state.chat_session.send_message(user_input)
                st.markdown(response.text)
                
                st.session_state.last_user_msg = user_input
                st.session_state.last_ai_reply = response.text
                
                # 發問完即刻寫入新的一行
                current_row = log_to_sheets_perfect(user_input, response.text, feedback="尚無評分", status="已回答")
                st.session_state.current_row_index = current_row
                
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg:
                    st.error("🌟 系統目前繁忙中（配額暫時已達上限，請重整網頁或稍候片刻再試）。")
                elif "404" in error_msg:
                    st.error(f"⚠️ 模型連線錯誤 (404)。您的 API Key 可能不支援 `{SELECTED_MODEL}` 模型。👉 **請點擊左上角的側邊欄，嘗試切換其他模型！**")
                else:
                    st.error(f"⚠️ 連線錯誤：{error_msg}")

# ==========================================
# 6. 📝 滿意度評分（1-10分滑動條）與專人補充表單 (完美同行併存更新)
# ==========================================
if "last_ai_reply" in st.session_state:
    st.divider()
    st.subheader("📝 您對本次分析滿意嗎？")
    
    col1, col2 = st.columns(2)
    with col1:
        # 評分系統表單
        with st.form("rating_form"):
            st.markdown("**請給予滿意度評分**")
            score = st.slider("(1分為最不滿意，10分為非常滿意)", min_value=1, max_value=10, value=10)
            if st.form_submit_button("送出評分"):
                target_row = st.session_state.get("current_row_index")
                if target_row:
                    # 更新 D欄（反饋評價）與 E欄（處理狀態）使其併存
                    update_sheets_row(target_row, feedback=f"評分：{score}分", status="結案")
                    send_line_message(f"📊【滿意度評分回饋】\n系統收到新評分：{score} 分！")
                    st.success(f"感謝您的回饋！您給予了 {score} 分。")
                else:
                    st.warning("⚠️ 寫入連線可能稍有延遲，請稍後再試。")
            
    with col2:
        st.markdown("**需要進一步的專人協助嗎？**")
        if st.button("❓ 填寫專人服務表單"):
            st.session_state.show_expert_form = True

    # 專人服務表單區塊 (採同行欄位覆蓋更新，D欄與E欄各自獨立倂存)
    if st.session_state.get("show_expert_form", False):
        st.markdown("---")
        with st.form("pro_contact"):
            st.info("請填寫聯繫資訊，基隆市政府法制及勞動處人員將於上班時間聯繫您。")
            name = st.text_input("您的姓名/稱呼")
            user_gender = st.radio("您的性別", ["男", "女", "官方不便透露"], horizontal=True)
            contact_method = st.radio("您希望專人如何回覆您？", ["電話回覆", "Email 回覆"], horizontal=True)
            phone = st.text_input("聯絡電話")
            email = st.text_input("Email 回覆")
            note = st.text_area("其他備註說明")
            st.markdown("---")
            consent = st.checkbox("我同意基隆市政府依《個人資料保護法》規定，蒐集、處理及利用上述個人資料，僅限於本次職場健檢諮詢與聯繫使用。")
            
            if st.form_submit_button("送出申請"):
                if not consent:
                    st.error("⚠️ 請勾選同意個資聲明！")
                elif not name:
                    st.error("⚠️ 請填寫您的姓名/稱呼。")
                elif contact_method == "電話回覆" and not phone:
                    st.error("⚠️ 您選擇了「電話回覆」，請務必填寫聯絡電話。")
                elif contact_method == "Email 回覆" and not email:
                    st.error("⚠️ 您選擇了「Email 回覆」，請務必填寫 Email。")
                else:
                    title = "先生" if user_gender == "男" else "女士（小姐）" if user_gender == "女" else ""
                    final_note = f"【希望以 {contact_method}】\n備註: {note}" if note else f"【希望以 {contact_method}】"
                    
                    # 抓取對話階段生成的同一行列號進行覆蓋更新
                    target_row = st.session_state.get("current_row_index")
                    if target_row:
                        # 更新同一行：D欄改為專人服務狀態，E欄調整為待處理，並補上其餘個資欄位
                        update_sheets_row(
                            target_row, 
                            feedback="需專人服務", 
                            status="待處理",
                            name=name,
                            gender=user_gender,
                            phone=phone,
                            email=email,
                            note=final_note
                        )
                        
                        # LINE 管理員推播通知
                        notify_msg = f"\n🚨【專人服務請求】🚨\n民眾：{name} {title}\n電話：{phone}\nEmail：{email}\n偏好：{contact_method}\n備註：{note}\n請基隆市政府法制及勞動處同仁盡速至試算表查看同一行完整紀錄。"
                        send_line_message(notify_msg)
                        
                        st.success(f"{name} {title} 您好，您的申請已在同筆提問紀錄中完成更新！專人將儘速與您聯繫。")
                        st.session_state.show_expert_form = False
                    else:
                        st.error("❌ 找不到對應的提問列，請重新整理網頁或稍後重試。")
