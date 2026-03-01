import streamlit as st
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

st.set_page_config(page_title="校園管理整合系統", layout="wide")

# ==========================================
# 取得台灣時間
# ==========================================
tw_time = datetime.utcnow() + timedelta(hours=8)
today_date = tw_time.strftime("%Y-%m-%d")

# ==========================================
# 連接 Google 試算表
# ==========================================
@st.cache_resource
def init_gspread():
    creds_json = json.loads(st.secrets["google_json"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    return gspread.authorize(creds)

try:
    client = init_gspread()
    doc = client.open("全校巡查總資料庫")
    sheet_records = doc.sheet1  # 預設第一頁是巡查紀錄
    
    # 檢查或取得請假紀錄分頁
    try:
        sheet_leave = doc.worksheet("僑生請假紀錄")
    except:
        # 如果不存在則建立
        sheet_leave = doc.add_worksheet(title="僑生請假紀錄", rows="1000", cols="10")
        sheet_leave.append_row(["紀錄日期", "學號", "姓名", "班級", "請假類別", "起點日期", "迄止日期", "原因備註", "經辦人"])

except Exception as e:
    st.error("⚠️ 系統連線失敗，請檢查金鑰設定。")
    st.stop()

# 讀取學生名冊 (用於自動帶出姓名)
@st.cache_data(ttl=600)
def load_student_db():
    try:
        sheet_students = doc.worksheet("學生名單")
        records = sheet_students.get_all_records()
        return {str(r["學號"]).strip(): r for r in records if "學號" in r}
    except:
        return {}

student_db = load_student_db()

# ==========================================
# 側邊欄：功能選單與身分綁定
# ==========================================
with st.sidebar:
    st.title("📂 功能選單")
    app_mode = st.radio("請選擇作業項目", ["🔭 全校巡查登記", "📝 僑生請假紀錄", "📊 數據管理中心"])
    st.divider()
    
    # 免登入參數處理
    if "role" in st.query_params and "name" in st.query_params and "current_user" not in st.session_state:
        st.session_state.current_user = f"{st.query_params['role']}-{st.query_params['name']}"
    
    if "current_user" not in st.session_state or st.session_state.current_user is None:
        role = st.selectbox("您的職務", ["學務主任", "教務主任", "生輔員", "行政"])
        name = st.text_input("您的姓名")
        if st.button("確認綁定"):
            st.session_state.current_user = f"{role}-{name}"
            st.rerun()
    else:
        st.success(f"目前身分：\n{st.session_state.current_user}")
        if st.button("解除綁定"):
            st.session_state.current_user = None
            st.rerun()

# ==========================================
# 功能一：全校巡查登記 (保留原本邏輯)
# ==========================================
if app_mode == "🔭 全校巡查登記":
    st.header("🔭 全校巡查即時登記")
    # (此處保留先前已優化的巡查程式碼，包含班級選單、快捷狀況、自動得分...)
    st.info("系統已連動真實班級選單與 1分/0.03分 自動計分邏輯。")
    # ... 原有巡查邏輯程式碼 ... (為節省長度，此處僅示意，實際執行時請與先前代碼合併)

# ==========================================
# 功能二：僑生請假紀錄 (全新加入)
# ==========================================
elif app_mode == "📝 僑生請假紀錄":
    st.header("📝 僑生請假登記專區")
    
    if "current_user" not in st.session_state or st.session_state.current_user is None:
        st.warning("請先於側邊欄完成身分綁定。")
    else:
        with st.form("leave_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                l_sid = st.text_input("輸入僑生學號 (6碼)").strip()
                l_type = st.selectbox("請假類別", ["病假", "事假", "公假", "喪假", "回國省親", "其他"])
            
            with col2:
                # 日期選擇
                start_date = st.date_input("請假起始日", value=tw_time)
                end_date = st.date_input("請假結束日", value=tw_time)
            
            l_reason = st.text_area("請假原因備註")
            
            # 自動查驗
            student_info = student_db.get(l_sid)
            if student_info:
                st.success(f"確認學生：{student_info.get('班級')} - {student_info.get('姓名')}")
            
            submit_leave = st.form_submit_button("提交請假申請", use_container_width=True)
            
            if submit_leave:
                if not student_info:
                    st.error("學號錯誤或不在名冊內，無法提交。")
                else:
                    new_leave = [
                        today_date, l_sid, student_info.get('姓名'), student_info.get('班級'),
                        l_type, str(start_date), str(end_date), l_reason, st.session_state.current_user
                    ]
                    sheet_leave.append_row(new_leave)
                    st.balloons()
                    st.success("請假紀錄已成功同步至雲端資料庫！")

# ==========================================
# 功能三：數據管理中心 (權限控管)
# ==========================================
elif app_mode == "📊 數據管理中心":
    st.header("📊 綜合數據中心")
    if "current_user" not in st.session_state:
        st.stop()
        
    user_role = st.session_state.current_user.split("-")[0]
    
    if user_role in ["學務主任", "管理員", "行政"]:
        tab1, tab2 = st.tabs(["🔥 今日巡查結算", "✈️ 僑生請假統計"])
        
        with tab1:
            st.subheader("今日巡查即時結算 (班級/個人)")
            # 呈現今日巡查的 groupby 結算表...
            
        with tab2:
            st.subheader("僑生請假總表")
            leave_data = sheet_leave.get_all_records()
            if leave_data:
                df_leave = pd.DataFrame(leave_data)
                st.dataframe(df_leave, use_container_width=True)
                csv = df_leave.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 下載請假紀錄清冊", data=csv, file_name=f"僑生請假紀錄_{today_date}.csv")
            else:
                st.write("目前尚無請假紀錄。")
    else:
        st.warning("您的權限僅限於登記，如需檢視總表請聯絡管理員。")
