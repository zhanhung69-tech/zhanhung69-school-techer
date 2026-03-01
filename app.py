import streamlit as st
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

st.title("校園巡查登記系統 (快捷結算版)")
st.divider()

# ==========================================
# 取得台灣時間的「今天日期」
# ==========================================
tw_time = datetime.utcnow() + timedelta(hours=8)
today_date = tw_time.strftime("%Y-%m-%d")

# ==========================================
# 核心升級：連接 Google 試算表
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
    doc = client.open("全校巡查總資料庫")
    sheet_records = doc.sheet1 
    
    if not sheet_records.row_values(1):
        sheet_records.append_row(["日期", "時間", "對象", "班級", "座號", "學號", "姓名", "狀況", "得分", "回報人"])
except Exception as e:
    st.error("⚠️ 系統連線 Google 試算表失敗，請聯絡管理員確認金鑰設定。")
    st.stop()

@st.cache_data(ttl=600)
def load_student_db():
    try:
        sheet_students = doc.worksheet("學生名單")
        records = sheet_students.get_all_records()
        db = {}
        for row in records:
            sid = str(row.get("學號", "")).strip()
            if sid:
                db[sid] = {
                    "姓名": str(row.get("姓名", "未知")),
                    "班級": str(row.get("班級", "未知")),
                    "座號": str(row.get("座號", "未知"))
                }
        return db
    except Exception as e:
        return {} 

student_db = load_student_db()

# ==========================================
# 系統記憶體與免登入機制
# ==========================================
if "temp_records" not in st.session_state:
    st.session_state.temp_records = []
if "current_user" not in st.session_state:
    st.session_state.current_user = None

# --- 新增：讀取網址專屬綁定參數 ---
if "role" in st.query_params and "name" in st.query_params and st.session_state.current_user is None:
    st.session_state.current_user = f"{st.query_params['role']}-{st.query_params['name']}"

# ==========================================
# 1. 綁定回報人員
# ==========================================
st.subheader("👤 巡查人員報到")
if st.session_state.current_user is None:
    col_role, col_name = st.columns(2)
    with col_role:
        role = st.selectbox("請選擇職務", ["學務主任", "教務主任", "生輔員", "行政"])
    with col_name:
        reporter_name = st.text_input("請輸入您的姓名：")
        
    if st.button("🔐 鎖定身分並開始巡查", type="primary"):
        if reporter_name == "":
            st.error("⚠️ 請務必輸入姓名！")
        else:
            st.session_state.current_user = f"{role}-{reporter_name}"
            st.rerun()
else:
    st.success(f"✅ 目前登入身分：**{st.session_state.current_user}**")
    if st.button("🔄 卸除身分 (換人登入)"):
        st.session_state.current_user = None
        st.query_params.clear() # 清除網址參數
        st.rerun()

st.divider()

# ==========================================
# 2. 巡查紀錄填寫 (快捷選單版)
# ==========================================
st.subheader("📝 填寫巡查紀錄")
if st.session_state.current_user is None:
    st.warning("⚠️ 請先完成登入即可解鎖系統。")
else:
    time_period = st.selectbox("請選擇巡查時間", [
        "0810-0900 第一節", "0910-1000 第二節", "1010-1100 第三節", "1110-1200 第四節",
        "1230-1300 午休", "1310-1400 第五節", "1410-1500 第六節", "1510-1600 第七節"
    ])
    
    record_type = st.radio("📌 請選擇登記對象", ["班級整體表現", "個人違規紀錄"], horizontal=True)
    
    # ---------------- 班級快捷模組 ----------------
    if record_type == "班級整體表現":
        col1, col2 = st.columns(2)
        with col1:
            grade = st.selectbox("👉 先選年級", ["一年級", "二年級", "三年級"])
        with col2:
            depts = ["餐", "觀", "資訊", "資處", "幼", "美", "商", "電", "影"]
            classes = ["忠", "孝", "仁", "愛", "信", "義", "和", "平"]
            dynamic_class_list = [f"{d}{grade[0]}{c}" for d in depts for c in classes]
            selected_class = st.selectbox("👉 再選班級", dynamic_class_list)
            
        student_id, student_name, seat_num = "無", "無", "無"
        
        # 班級常見狀況選單
        class_status_options = [
            "秩序良好 (+1)", "午休良好 (+1)", "導師入班 (+1)", 
            "上課吵鬧/秩序不佳 (-1)", "午休吵鬧 (-1)", "環境髒亂 (-1)", "未節電 (-1)", 
            "其他 (自行輸入)"
        ]
        status_category = st.selectbox("🎯 請選擇班級狀況", class_status_options)
        
        if status_category == "其他 (自行輸入)":
            status = st.text_input("請輸入補充說明：")
            score_action = st.radio("計分方式", ["加 1 分", "扣 1 分", "不計分"], horizontal=True)
            score_num = 1 if score_action == "加 1 分" else (-1 if score_action == "扣 1 分" else 0)
        else:
            status = status_category.split(" (")[0]
            score_num = 1 if "(+1)" in status_category else -1

    # ---------------- 個人快捷模組 ----------------
    else:
        if not student_db:
            st.warning("⚠️ 尚未偵測到雲端「學生名單」。")
            
        col_id, col_status = st.columns(2)
        with col_id:
            student_id = st.text_input("請輸入學生學號 (限6碼)：").replace(" ", "")
            
            if len(student_id) == 6:
                if student_id in student_db:
                    info = student_db[student_id]
                    selected_class, student_name, seat_num = info["班級"], info["姓名"], info["座號"]
                    st.success(f"✅ 查獲：{selected_class} {seat_num}號 {student_name}")
                else:
                    st.error("⚠️ 查無此學號！")
                    selected_class, student_name, seat_num = "未知", "未知", "未知"
            else:
                selected_class, student_name, seat_num = "-", "-", "-"
                
        with col_status:
            # 個人常見狀況選單
            personal_status_options = [
                "服儀違規-書包/短裙/便服 (0)", 
                "上課遊蕩/去合作社 (-0.03)", 
                "遲到/未到/曠課 (-0.03)", 
                "上課滑手機/睡覺 (-0.03)", 
                "熱心服務/表現優良 (+0.03)", 
                "其他 (自行輸入)"
            ]
            status_category = st.selectbox("🎯 請選擇個人狀況", personal_status_options)
            
            if status_category == "其他 (自行輸入)":
                status = st.text_input("請輸入補充說明：")
                score_action = st.radio("計分方式", ["加 0.03 分", "扣 0.03 分", "不計分"], horizontal=True)
                score_num = 0.03 if score_action == "加 0.03 分" else (-0.03 if score_action == "扣 0.03 分" else 0)
            else:
                status = status_category.split(" (")[0]
                if "(+0.03)" in status_category:
                    score_num = 0.03
                elif "(-0.03)" in status_category:
                    score_num = -0.03
                else:
                    score_num = 0
    
    # ---------------- 加入暫存 ----------------
    if st.button("➕ 加入下方暫存清單", use_container_width=True):
        if record_type == "個人違規紀錄" and (len(student_id) != 6 or student_name == "未知"):
            st.error("⚠️ 個人紀錄請務必輸入正確的 6 碼學號！")
        elif status_category == "其他 (自行輸入)" and status == "":
            st.error("⚠️ 請在補充說明欄位輸入狀況！")
        else:
            new_record = {
                "日期": today_date,
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
                    record["日期"], record["時間"], record["對象"], record["班級"], record["座號"],
                    record["學號"], record["姓名"], record["狀況"], record["得分"], record["回報人"]
                ])
            
            sheet_records.append_rows(upload_data)
            st.session_state.temp_records = []
            st.success("✅ 資料寫入成功！")
            st.rerun() 
            
    with col_clear:
        if st.button("🗑️ 清空暫存區", use_container_width=True):
            st.session_state.temp_records = []
            st.rerun()

# ==========================================
# 4. 權限控管與顯示今日總表
# ==========================================
st.divider()

if st.session_state.current_user is not None:
    current_role = st.session_state.current_user.split("-")[0]
    all_data = sheet_records.get_all_records()

    if len(all_data) > 0:
        df = pd.DataFrame(all_data)
        
        if "日期" in df.columns:
            df_today = df[df["日期"] == today_date]
        else:
            df_today = pd.DataFrame() 
        
        if len(df_today) > 0:
            if current_role in ["管理員", "學務主任", "教務主任", "行政"]:
                st.subheader("📊 管理員模式：今日巡查總明細")
                st.dataframe(df_today, use_container_width=True)
                
                # --- 新增：每日班級總分結算表 ---
                st.markdown("### 📈 每日各班成績結算表 (自動統整 1 分與 0.03 分)")
                # 把今天的紀錄依照「班級」分組，並將加扣分加總起來
                summary_df = df_today.groupby("班級")["得分"].sum().reset_index()
                # 四捨五入到小數點第二位，避免電腦浮點數計算誤差 (如 0.02999)
                summary_df["總得分"] = summary_df["得分"].round(2)
                summary_df = summary_df.drop(columns=["得分"])
                
                st.dataframe(summary_df, use_container_width=True)
                
                csv = df_today.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 下載今日巡查明細表 (CSV)",
                    data=csv,
                    file_name=f"{today_date}_今日巡查總表.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.subheader(f"📊 您的今日巡查紀錄")
                df_personal = df_today[df_today["回報人"] == st.session_state.current_user]
                st.dataframe(df_personal, use_container_width=True)
        else:
            st.info("🟢 今日尚無紀錄。")
else:
    st.info("🔒 請先登入。")
