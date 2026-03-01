import streamlit as st
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials

st.title("校園巡查登記系統 (全校名單連線版)")
st.divider()

# ==========================================
# 核心升級：連接 Google 試算表與自動抓取名單
# ==========================================
@st.cache_resource
def init_gspread():
    creds_json = json.loads(st.secrets["google_json"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    return gspread.authorize(creds)

try:
    client = init_gspread()
    # 打開學務處的總表
    doc = client.open("全校巡查總資料庫")
    # 第一個分頁：用來存每天的巡查紀錄
    sheet_records = doc.sheet1 
    
    if not sheet_records.row_values(1):
        sheet_records.append_row(["時間", "對象", "班級", "座號", "學號", "姓名", "狀況", "得分", "回報人"])
        
except Exception as e:
    st.error("⚠️ 系統連線 Google 試算表失敗，請聯絡管理員確認金鑰設定。")
    st.stop()

# --- 終極新功能：自動讀取真實學生名單 ---
# @st.cache_data 會讓系統記住名單 10 分鐘，不用每次按按鈕都重新下載，提升系統速度
@st.cache_data(ttl=600)
def load_student_db():
    try:
        # 尋找名為「學生名單」的第二個分頁
        sheet_students = doc.worksheet("學生名單")
        records = sheet_students.get_all_records()
        
        db = {}
        for row in records:
            # 確保學號是文字，並且去除不小心打到的空白鍵
            sid = str(row.get("學號", "")).strip()
            if sid:
                db[sid] = {
                    "姓名": str(row.get("姓名", "未知")),
                    "班級": str(row.get("班級", "未知")),
                    "座號": str(row.get("座號", "未知"))
                }
        return db
    except Exception as e:
        return {} # 如果還沒建立名單分頁，就先回傳空的字典防呆

# 正式將抓下來的雲端資料存入系統字典中
student_db = load_student_db()

# ==========================================
# 系統記憶體初始化
# ==========================================
if "temp_records" not in st.session_state:
    st.session_state.temp_records = []
if "current_user" not in st.session_state:
    st.session_state.current_user = None

# ==========================================
# 1. 綁定回報人員
# ==========================================
st.subheader("👤 巡查人員報到")
if st.session_state.current_user is None:
    col_role, col_name = st.columns(2)
    with col_role:
        role = st.selectbox("請選擇職務", ["生輔員", "管理員", "學務主任", "導師", "其他"])
    with col_name:
        reporter_name = st.text_input("請輸入您的姓名：")
        
    if st.button("🔐 鎖定身分並開始巡查", type="primary"):
        if reporter_name == "":
            st.error("⚠️ 請務必輸入姓名！")
        else:
            st.session_state.current_user = f"{role}-{reporter_name}"
            st.rerun()
else:
    st.success(f"✅ 目前巡查人員：**{st.session_state.current_user}**")
    if st.button("🔄 卸除身分 (換人登入)"):
        st.session_state.current_user = None
        st.rerun()

st.divider()

# ==========================================
# 2. 巡查紀錄填寫
# ==========================================
st.subheader("📝 填寫巡查紀錄")
if st.session_state.current_user is None:
    st.warning("⚠️ 請先在上方完成「巡查人員報到」並鎖定身分，即可解鎖登記系統。")
else:
    time_period = st.selectbox("請選擇巡查時間", [
        "0810-0900 第一節", "0910-1000 第二節", "1010-1100 第三節", "1110-1200 第四節",
        "1230-1300 午休", "1310-1400 第五節", "1410-1500 第六節", "1510-1600 第七節"
    ])
    
    record_type = st.radio("📌 請選擇登記對象", ["班級整體表現", "個人違規紀錄"], horizontal=True)
    
    if record_type == "班級整體表現":
        col1, col2 = st.columns(2)
        with col1:
            grade = st.selectbox("👉 先選年級", ["一年級", "二年級", "三年級"])
        with col2:
            depts = ["餐", "觀", "資訊", "資處", "幼", "美", "商", "電", "影"]
            classes = ["忠", "孝", "仁", "愛", "信", "義", "和", "平"]
            grade_str = grade[0] 
            dynamic_class_list = [f"{d}{grade_str}{c}" for d in depts for c in classes]
            selected_class = st.selectbox("👉 再選班級", dynamic_class_list)
            
        student_id, student_name, seat_num = "無", "無", "無"
        status = st.text_input("請輸入班級巡查狀況：")
    else:
        # 如果尚未載入名單，給予提示
        if not student_db:
            st.warning("⚠️ 尚未偵測到雲端「學生名單」，目前個人違規功能可能無法正常查核學號。")
            
        col_id, col_status = st.columns(2)
        with col_id:
            student_id = st.text_input("請輸入學生學號 (限6碼)：").replace(" ", "")
        with col_status:
            status = st.text_input("請輸入個人巡查狀況：")
        
        if len(student_id) == 6:
            if student_id in student_db:
                info = student_db[student_id]
                selected_class, student_name, seat_num = info["班級"], info["姓名"], info["座號"]
                st.success(f"✅ 查獲學生：{selected_class} {seat_num}號 {student_name}")
            else:
                st.error("⚠️ 雲端名單查無此學號，請確認是否輸入錯誤或尚未更新雲端名單！")
                selected_class, student_name, seat_num = "未知", "未知", "未知"
        else:
            selected_class, student_name, seat_num = "-", "-", "-"
    
    if st.button("➕ 加入下方暫存清單", use_container_width=True):
        if record_type == "個人違規紀錄" and (len(student_id) != 6 or student_name == "未知"):
            st.error("⚠️ 個人紀錄請務必輸入正確且存在於雲端名單的 6 碼學號！")
        else:
            if record_type == "班級整體表現":
                if "午休良好" in status or "導師入班" in status or "三分之二" in status:
                    score_num = 2
                elif "秩序良好" in status:
                    score_num = 1
                elif "午休吵鬧" in status or "未節電" in status or "5人以上" in status:
                    score_num = -1
                else:
                    score_num = 0
            else:
                if "短裙" in status or "便服" in status or "書包" in status:
                    score_num = 0  
                elif "遊蕩" in status or "合作社" in status:
                    score_num = -1 
                else:
                    score_num = 0
                    
            new_record = {
                "時間": time_period,
                "對象": "個人" if record_type == "個人違規紀錄" else "班級",
                "班級": selected_class,
                "座號": seat_num,
                "學號": student_id,
                "姓名": student_name,
                "狀況": status,
                "得分": score_num,
                "回報人": st.session_state.current_user 
            }
            st.session_state.temp_records.append(new_record)

# ==========================================
# 3. 暫存區與批次上傳
# ==========================================
if len(st.session_state.temp_records) > 0:
    st.markdown("### 🛒 待上傳的暫存紀錄")
    st.dataframe(pd.DataFrame(st.session_state.temp_records), use_container_width=True)
    
    col_upload, col_clear = st.columns(2)
    with col_upload:
        if st.button("🚀 確認無誤，全數寫入 Google 試算表", type="primary", use_container_width=True):
            upload_data = []
            for record in st.session_state.temp_records:
                upload_data.append([
                    record["時間"], record["對象"], record["班級"], record["座號"],
                    record["學號"], record["姓名"], record["狀況"], record["得分"], record["回報人"]
                ])
            
            sheet_records.append_rows(upload_data)
            st.session_state.temp_records = []
            st.success("✅ 所有資料已成功寫入學務處專屬 Google 試算表！")
            st.rerun() 
            
    with col_clear:
        if st.button("🗑️ 清空暫存區", use_container_width=True):
            st.session_state.temp_records = []
            st.rerun()

# ==========================================
# 4. 顯示全校共用總表
# ==========================================
st.divider()
st.subheader("📊 全校巡查總資料庫 (即時連線)")

all_data = sheet_records.get_all_records()

if len(all_data) > 0:
    st.dataframe(pd.DataFrame(all_data), use_container_width=True)
else:
    st.info("目前的 Google 試算表尚無任何紀錄。")
