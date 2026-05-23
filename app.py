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
# 1. 系統設定與 API 金鑰讀取
# ==========================================
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    st.error("⚠️ 尚未讀取到 API Key！請至 Streamlit Secrets 設定 GOOGLE_API_KEY。")
    st.stop()

# ==========================================
# 2. 🎯 模型選擇 (修正 404 錯誤)
# ==========================================
# 直接指定穩定且支援 File API 的最新版模型，避免 list_models 抓取到無效字串
SELECTED_MODEL = "gemini-1.5-pro-latest"

# ==========================================
# 3. 完美版寫入函數 (Google Sheets) & LINE 通知
# ==========================================
def log_to_sheets_perfect(user_msg, ai_reply, feedback="", status="已回答", name="", gender="", phone="", email="", note=""):
    try:
        creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
        gc = gspread.service_account_from_dict(creds_dict)
        sheet = gc.open("職場健檢_民眾提問紀錄").sheet1
        tw_tz = pytz.timezone('Asia/Taipei')
        current_time = datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([current_time, user_msg, ai_reply, feedback, status, name, gender, phone, email, note])
    except Exception as e:
        print(f"資料庫紀錄異常：{e}")

def send_line_message(message_text):
    try:
        channel_access_token = st.secrets["LINE_CHANNEL_ACCESS_TOKEN"]
        admin_user_id = st.secrets["LINE_ADMIN_USER_ID"]
        url = "https://api.line.me/v2/bot/message/push"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {channel_access_token}"}
        data = {"to": admin_user_id, "messages": [{"type": "text", "text": message_text}]}
        requests.post(url, headers=headers, json=data)
    except Exception as e:
        print(f"LINE 系統異常：{e}")

# ==========================================
# 4. 核心大腦設定 (⚖️ 融合官方手冊強制檢索)
# ==========================================
SYSTEM_PROMPT = """
你是一位精通台灣勞動法令的「基隆市政府職場友善度健檢顧問」。

【🏆 最高指導原則：官方手冊優先】
對話系統已經向你載入了最新的《114年勞動基準法規彙編》與《職場工作平權宣導手冊》。
當民眾提問時，你必須「優先且絕對」從這兩份官方檔案中搜尋相關條文、函釋與指引來回答。

【🚨 終極防護：精準對症下藥、防幻想與字數限制原則】
1. 嚴格字數限制：每次回覆的「總字數請務必嚴格控制在 500 字以內」。文字需極度精簡、直擊核心，切勿長篇大論。
2. 直接回覆：首先承接使用者的情緒，給予溫暖與支持的回應，並「優先直接針對問題給出明確的答案」。
3. 問題概述與法令分析：接著，請明確標示出【問題概述】與【法令分析】兩個段落。
4. 🎯 精準鎖定法規 (寧缺勿濫)：在內心判斷爭議類型後，懷孕/性別歧視僅限《性別平等工作法》；年齡/身障歧視僅限《就業服務法》；一般勞動條件(薪資/工時/資遣)僅限《勞動基準法》。絕對禁止為了湊字數跨界亂引法條。
5. 🛑 絕對禁止捏造字號：在【法令分析】中，「絕對禁止」自行發明、拼湊或臆測任何具體的「函釋字號」、「文號」、「判決字號」或「發布日期」。除非你在上傳的 PDF 手冊中或大腦知識庫中確實查到該函釋字號，否則一律使用「依據勞動部相關函釋精神」或「依據實務見解」帶過。
6. 🛡️ 寧缺勿濫原則：若民眾描述的情況過於模糊、或你完全無法確定適用的法律條文，請坦承告知：「此情況較為複雜，為求正確與寧缺勿濫，建議您直接向主管機關確認細節。」，絕對不允許強行猜測。
7. 官方結語與查證連結：在每一次回答的最末端，請固定附上以下內容（計入 500 字內）：
   ---
   📚 **官方查證資源：**
   * 勞動部勞動法令查詢系統：https://laws.mol.gov.tw/
   * 全國法規資料庫：https://law.moj.gov.tw/
   
   📞 **如仍有疑義歡迎來電 02-24287801，基隆市政府法制及勞動處關心您。**

【💎 專屬法規知識庫 (精準打擊區)】
- 爭議點：公務機關技工、工友「考績獎金」是否計入平均工資？
- 強制引用：行政院勞工委員會96年6月26日勞動2字第0960071251號函，不列入平均工資計算。

【📖 黃金標準問答範例參考 (機器學習與模仿依據)】
為確保回覆的高品質與可信度，請嚴格模仿以下幾種情境的語氣與邏輯架構來回覆民眾：
[範例：勞基法爭議]
民眾提問：「老闆說我還在試用期，所以明天不用來了，也不給我資遣費，這樣合法嗎？」
標準回覆：「您好！遇到突然失去工作的情況一定很慌張，我們來看看法律怎麼說：
【問題概述】您面臨的是試用期被解雇且未獲資遣費的爭議。
【法令分析】依據勞動部實務見解，我國《勞動基準法》並無「試用期」的明文規定。只要受僱上班，雙方即成立勞動契約。因此，雇主若要單方面終止契約，即使在試用期內，仍必須符合《勞動基準法》第11條或第12條規定，且須依同法第16條及第17條（或勞退條例第12條）給付預告工資與資遣費。雇主的說法已涉嫌違法，建議保留對話截圖作為證據。
---
📚 **官方查證資源：** (略)」
"""

try:
    generation_config = genai.GenerationConfig(temperature=0.0, top_p=0.8)
    model = genai.GenerativeModel(
        model_name=SELECTED_MODEL,
        system_instruction=SYSTEM_PROMPT,
        generation_config=generation_config
    )
except Exception as e:
    st.error(f"⚠️ 模型建立失敗：{e}")
    st.stop()

# ==========================================
# 5. 網頁介面佈局與 📚 官方檔案載入機制 (終極防護版)
# ==========================================
st.set_page_config(page_title="工作場所融合度 AI 健檢系統", page_icon="⚖️", layout="centered")

st.markdown("""
<style>
    html, body, [class*="st-"] { font-family: '微軟正黑體', sans-serif !important; color: #262730 !important; }
    .stApp { background: linear-gradient(to bottom, #E8F1F8 0%, #FFFFFF 100%) !important; }
    h1 { color: #003366 !important; text-align: center; border-bottom: 3px solid #00509E; padding-bottom: 10px; }
    .stChatMessage { background-color: #FFFFFF !important; border-radius: 15px; border: 1px solid #D1E1F0; box-shadow: 0 4px 8px rgba(0,0,0,0.03); color: #262730 !important; }
</style>
""", unsafe_allow_html=True)

# 🎯 側邊欄：實用資源連結
with st.sidebar:
    st.markdown("### 🏛️ 官方實用資源")
    st.markdown("[🔍 勞動部勞動法令查詢系統](https://laws.mol.gov.tw/)")
    st.markdown("[📖 全國法規資料庫](https://law.moj.gov.tw/)")

st.title("⚖️ 工作場所融合度 AI 健檢系統")
st.markdown("歡迎使用！顧問已載入最新《114年勞動基準法規彙編》及《職場工作平權宣導手冊》，為您進行專業法理分析。")

# --- 核心：PDF 檔案上傳至 Gemini 系統大腦 (採用絕對路徑與嚴格攔截網) ---
if "uploaded_files_to_gemini" not in st.session_state:
    files_to_upload = ["114年勞動基準法規彙編.pdf", "職場工作平權宣導手冊.pdf"]
    uploaded_gemini_files = []
    
    with st.spinner("⏳ 正在將官方手冊載入 AI 系統大腦中，初次載入需時約 30 秒，請稍候..."):
        # 取得 app.py 當前所在的絕對資料夾路徑
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        for file_name in files_to_upload:
            file_path = os.path.join(current_dir, file_name)
            
            # 🛡️ 雙重防護第一層：確定檔案真的存在才進行處理
            if os.path.exists(file_path):
                try: 
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                        shutil.copyfile(file_path, tmp_file.name)
                        gemini_file = genai.upload_file(tmp_file.name, mime_type="application/pdf")
                        
                    while gemini_file.state.name == "PROCESSING":
                        time.sleep(2)
                        gemini_file = genai.get_file(gemini_file.name)
                        
                    uploaded_gemini_files.append(gemini_file)
                except Exception as e:
                    print(f"檔案 {file_name} 上傳失敗：{e}")
                    st.warning(f"⚠️ {file_name} 載入程序異常，但系統仍可依照基本法理為您服務。")
            else:
                st.warning(f"⚠️ 尚未在系統資料夾中偵測到「{file_name}」，請確認是否已成功上傳至 GitHub，目前將以基礎法理為您服務。")
                
    st.session_state.uploaded_files_to_gemini = uploaded_gemini_files

# --- 初始化對話紀錄 ---
if "chat_session" not in st.session_state:
    initial_history = []
    
    if st.session_state.uploaded_files_to_gemini:
        parts = st.session_state.uploaded_files_to_gemini + ["請徹底熟讀以上兩份官方手冊。接下來民眾的所有提問，請『絕對優先』依照這兩份手冊內的法規、函釋與指引來進行健檢評估。"]
        initial_history.append({"role": "user", "parts": parts})
        initial_history.append({"role": "model", "parts": ["收到！我已完整讀取並記憶《114年勞動基準法規彙編》與《職場工作平權宣導手冊》。我將嚴格遵守手冊內容為市民解答。"]})
    
    st.session_state.chat_session = model.start_chat(history=initial_history)

# --- 顯示歷史訊息 ---
for message in st.session_state.chat_session.history:
    if message.role == "user" and "請徹底熟讀以上兩份官方手冊" in message.parts[-1].text:
        continue
    if message.role == "model" and "收到！我已完整讀取" in message.parts[0].text:
        continue
        
    role = "user" if message.role == "user" else "assistant"
    with st.chat_message(role):
        st.markdown(message.parts[0].text)

# --- 處理使用者提問 ---
if user_input := st.chat_input("請簡單描述您的狀況（為保護隱私，請勿在此處輸入真實姓名或身分證字號）..."):
    st.chat_message("user").markdown(user_input)
    with st.chat_message("assistant"):
        with st.spinner(f"顧問正翻閱官方手冊深度分析中... 請稍候"):
            try:
                response = st.session_state.chat_session.send_message(user_input)
                st.markdown(response.text)
                
                st.session_state.last_user_msg = user_input
                st.session_state.last_ai_reply = response.text
                
                log_to_sheets_perfect(user_input, response.text)
                
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg:
                    st.error("🌟 系統目前繁忙中（配額暫時已達上限，請重整網頁或稍候片刻再試）。")
                elif "404" in error_msg:
                    st.error("⚠️ 模型連線錯誤 (404)。請嘗試在程式碼第 28 行將 `gemini-1.5-pro-latest` 修改為 `gemini-1.5-flash` 再試一次。")
                else:
                    st.error(f"⚠️ 連線錯誤：{error_msg}")

# ==========================================
# 6. 反饋互動與專人補充表單 
# ==========================================
if "last_ai_reply" in st.session_state:
    st.divider()
    st.subheader("📝 您對本次分析滿意嗎？")
    
    col1, col2 = st.columns(2)
    with col1:
        with st.form("rating_form"):
            st.markdown("**請給予滿意度評分**")
            score = st.slider("(1分為最不滿意，10分為非常滿意)", min_value=1, max_value=10, value=10)
            if st.form_submit_button("送出評分"):
                log_to_sheets_perfect(st.session_state.last_user_msg, st.session_state.last_ai_reply, feedback=f"評分：{score}分", status="結案")
                send_line_message(f"📊【滿意度評分回饋】\n系統收到新評分：{score} 分！")
                st.success(f"感謝您的回饋！您給予了 {score} 分。")
            
    with col2:
        st.markdown("**需要進一步的專人協助嗎？**")
        if st.button("❓ 填寫專人服務表單"):
            st.session_state.show_expert_form = True

    if st.session_state.get("show_expert_form", False):
        st.markdown("---")
        with st.form("pro_contact"):
            st.info("請填寫聯繫資訊，基隆市政府法制及勞動處人員將於上班時間聯繫您。")
            name = st.text_input("您的姓名/稱呼")
            user_gender = st.radio("您的性別", ["男", "女", "其他"], horizontal=True)
            contact_method = st.radio("您希望專人如何回覆您？", ["電話回覆", "Email 回覆"], horizontal=True)
            phone = st.text_input("聯絡電話")
            email = st.text_input("Email 回覆")
            note = st.text_area("其他備註說明")
            st.markdown("---")
            consent = st.checkbox("我同意基隆市政府依個資法蒐集聯繫使用。")
            
            if st.form_submit_button("送出申請"):
                if not consent:
                    st.error("⚠️ 請勾選同意個資聲明！")
                elif contact_method == "電話回覆" and not phone:
                    st.error("⚠️ 請務必填寫聯絡電話。")
                elif contact_method == "Email 回覆" and not email:
                    st.error("⚠️ 請務必填寫 Email。")
                else:
                    title = "先生" if user_gender == "男" else "女士" if user_gender == "女" else ""
                    final_note = f"【希望以 {contact_method}】\n備註: {note}"
                    
                    log_to_sheets_perfect(st.session_state.last_user_msg, st.session_state.last_ai_reply, feedback="專人服務", status="待處理", name=name, gender=user_gender, phone=phone, email=email, note=final_note)
                    send_line_message(f"🚨【專人服務請求】\n民眾：{name} {title}\n偏好：{contact_method}\n請至試算表查看。")
                    st.success("申請已送出！")
                    st.session_state.show_expert_form = False
