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
# 2. 核心設定與模型初始化
# ==========================================
SYSTEM_PROMPT = """
你是一位基隆市政府勞動法令顧問。必須優先依照載入的 PDF 內容回答。
1. 若 PDF 內有依據，務必精準引用；無把握則答「需洽主管機關」。
2. 結構：【問題概述】、【法令分析】。
3. 必備結語：附官方連結與市府諮詢電話 02-24287801。
"""
model = genai.GenerativeModel("gemini-1.5-pro", system_instruction=SYSTEM_PROMPT)

# ==========================================
# 3. 檔案載入區 (放在這裡最安全，確保執行前已載入)
# ==========================================
if "uploaded_files" not in st.session_state:
    target_files = ["114年勞動基準法規彙編.pdf", "職場工作平權宣導手冊.pdf"]
    uploaded = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    with st.spinner("⏳ 正在載入官方手冊..."):
        for fname in target_files:
            fpath = os.path.join(base_dir, fname)
            if os.path.exists(fpath):
                tmp_path = os.path.join(tempfile.gettempdir(), fname)
                shutil.copyfile(fpath, tmp_path)
                f = genai.upload_file(tmp_path)
                while f.state.name == "PROCESSING": time.sleep(2); f = genai.get_file(f.name)
                uploaded.append(f)
    st.session_state.uploaded_files = uploaded
    st.session_state.chat = model.start_chat(history=[{"role": "user", "parts": uploaded + ["請依此手冊回答。"]}])

# ==========================================
# 4. 功能函式 (紀錄與通知)
# ==========================================
def log_to_sheets(user_msg, ai_reply, **kwargs):
    try:
        gc = gspread.service_account_from_dict(json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"]))
        sheet = gc.open("職場健檢_民眾提問紀錄").sheet1
        sheet.append_row([datetime.now(pytz.timezone('Asia/Taipei')).strftime("%Y-%m-%d %H:%M:%S"), 
                          user_msg, ai_reply, kwargs.get('feedback', ''), "已回答", 
                          kwargs.get('name',''), kwargs.get('phone',''), kwargs.get('email','')])
    except: pass

# ==========================================
# 5. 網頁介面 (聊天室 + 專人服務表單)
# ==========================================
st.set_page_config(page_title="職場健檢系統", layout="centered")

st.title("⚖️ 職場友善度 AI 健檢")

# 顯示對話
for msg in st.session_state.chat.history:
    if hasattr(msg.parts[0], 'text'):
        with st.chat_message("user" if msg.role=="user" else "assistant"):
            st.markdown(msg.parts[0].text)

# 使用者輸入與回應
if prompt := st.chat_input("描述您的職場狀況..."):
    st.chat_message("user").markdown(prompt)
    with st.chat_message("assistant"):
        res = st.session_state.chat.send_message(prompt)
        st.markdown(res.text)
        log_to_sheets(prompt, res.text)

# 專人服務表單 (放在最下方，不會擋住聊天室)
if st.button("❓ 請求專人協助"): st.session_state.show_form = True
if st.session_state.get("show_form"):
    with st.form("contact_form"):
        name = st.text_input("您的姓名")
        contact = st.text_input("聯繫電話或 Email")
        if st.form_submit_button("送出申請"):
            st.success("已受理，將由專人聯繫您。")
            st.session_state.show_form = False
