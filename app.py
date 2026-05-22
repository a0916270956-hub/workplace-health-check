import streamlit as st
import google.generativeai as genai
import gspread, json, os, time, tempfile, shutil, requests, pytz
from datetime import datetime

# ==========================================
# 1. 系統設定
# ==========================================
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except:
    st.error("⚠️ 請在 Streamlit Secrets 設定 GOOGLE_API_KEY")
    st.stop()

# ==========================================
# 2. 核心大腦設定 (強制 PDF 檢索)
# ==========================================
SYSTEM_PROMPT = """
你是一位基隆市政府勞動法令顧問。必須優先依照已載入的兩份 PDF 手冊回答。
1. 回答時若 PDF 內有依據，請務必精準引用條文；若無把握則答「建議洽詢主管機關」，嚴禁幻想法規。
2. 結構：【問題概述】、【法令分析】。
3. 必備結語：官方查證連結與基隆市政府諮詢電話 02-24287801。
"""
model = genai.GenerativeModel("gemini-1.5-pro", system_instruction=SYSTEM_PROMPT)

# ==========================================
# 3. 檔案載入系統 (修正路徑與權限)
# ==========================================
if "uploaded_files" not in st.session_state:
    target_files = ["114年勞動基準法規彙編.pdf", "職場工作平權宣導手冊.pdf"]
    uploaded = []
    # 使用絕對路徑以確保讀取成功
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    with st.spinner("⏳ 正在讀取官方手冊並載入 AI 大腦..."):
        for fname in target_files:
            fpath = os.path.join(base_dir, fname)
            if os.path.exists(fpath):
                # 複製到暫存區以繞過路徑權限問題
                tmp_path = os.path.join(tempfile.gettempdir(), fname)
                shutil.copyfile(fpath, tmp_path)
                # 上傳至 Google AI
                f = genai.upload_file(tmp_path)
                while f.state.name == "PROCESSING": time.sleep(2); f = genai.get_file(f.name)
                uploaded.append(f)
            else:
                st.warning(f"⚠️ 找不到檔案: {fname}，請確認 GitHub 檔案名稱是否正確。")
    
    st.session_state.uploaded_files = uploaded
    # 將檔案餵給模型
    history = [{"role": "user", "parts": uploaded + ["請徹底熟讀上述兩份手冊，接下來的所有提問請優先依據手冊內容回答。"]}]
    st.session_state.chat = model.start_chat(history=history)

# ==========================================
# 4. Google Sheets 與 LINE 通知功能
# ==========================================
def log_to_sheets_perfect(user_msg, ai_reply, **kwargs):
    try:
        gc = gspread.service_account_from_dict(json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"]))
        sheet = gc.open("職場健檢_民眾提問紀錄").sheet1
        sheet.append_row([datetime.now(pytz.timezone('Asia/Taipei')).strftime("%Y-%m-%d %H:%M:%S"), 
                          user_msg, ai_reply, kwargs.get('feedback', ''), "已回答", 
                          kwargs.get('name',''), kwargs.get('phone',''), kwargs.get('email',''), kwargs.get('note','')])
    except: pass

def send_line(msg):
    try:
        requests.post("https://api.line.me/v2/bot/message/push", 
                      headers={"Authorization": f"Bearer {st.secrets['LINE_CHANNEL_ACCESS_TOKEN']}"}, 
                      json={"to": st.secrets['LINE_ADMIN_USER_ID'], "messages": [{"type": "text", "text": msg}]})
    except: pass

# ==========================================
# 5. 網頁介面與側邊欄
# ==========================================
st.set_page_config(page_title="職場健檢系統", layout="centered")

with st.sidebar:
    st.markdown("### 🏛️ 官方資源")
    st.markdown("[🔍 勞動部法規查詢](https://laws.mol.gov.tw/)")
    st.markdown("[📖 全國法規資料庫](https://law.moj.gov.tw/)")

st.title("⚖️ 職場友善度 AI 健檢")

for msg in st.session_state.chat.history:
    if hasattr(msg.parts[0], 'text'):
        with st.chat_message("user" if msg.role=="user" else "assistant"):
            st.markdown(msg.parts[0].text)

if prompt := st.chat_input("描述您的職場狀況..."):
    st.chat_message("user").markdown(prompt)
    with st.chat_message("assistant"):
        res = st.session_state.chat.send_message(prompt)
        st.markdown(res.text)
        log_to_sheets_perfect(prompt, res.text)

# 專人服務表單
if st.button("❓ 請求專人協助"): st.session_state.show_form = True
if st.session_state.get("show_form"):
    with st.form("contact"):
        name = st.text_input("姓名")
        val = st.text_input("聯絡方式(電話/Email)")
        if st.form_submit_button("送出申請"):
            send_line(f"新專人請求: {name}, 聯繫: {val}")
            st.success("已受理")
            st.session_state.show_form = False
