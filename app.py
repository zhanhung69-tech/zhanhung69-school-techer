import streamlit as st
import pandas as pd
import os

st.title("校園巡查登記系統 (實務進化版)")
st.divider()

# ==========================================
# 核心資料庫與暫存區設定
# ==========================================
DB_FILE = "school_master_records.csv"

if not os.path.exists(DB_FILE):
    pd.DataFrame(columns=["時間", "對象", "班級", "座號", "學號", "姓名", "狀況", "得分", "回報人"]).to_csv(DB_FILE, index=False, encoding='utf-8-sig')

student_db = {
    "112001": {"姓名": "王小明", "班級": "餐一忠", "座號": "01"},
    "112002": {"姓名": "李小華", "班級": "資處一孝", "座號": "05"},
    "111003": {"姓名": "陳大毛", "班級": "觀二忠", "座號": "12"},
    "110005": {"姓名": "林小芳", "班級": "影三年", "座號": "33"}
}

if "temp_records" not in st.session_state:
    st.session_state.temp_records = []

# --- 新增：身分記憶體 ---
if "current_user" not in st.session_state:
    st.session_state.current_user = None

# ==========================================
# 1. 綁定回報人員 (登入鎖定機制)
# ==========================================
st.subheader("👤 巡查人員報到")

# 如果記憶體裡「沒有」登入資料，就顯示輸入框
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
            # 把身分存進記憶體，並重新整理網頁
            st.session_state.current_user = f"{role}-{reporter_name}"
            st.rerun()
            
# 如果記憶體裡「有」登入資料，就顯示歡迎詞和登出按鈕
else:
    st.success(f"✅ 目前巡查人員：**{st.session_state.current_user}**")
    if st.button("🔄 卸除身分 (換人登入)"):
        st.session_state.current_user = None # 清空記憶體
        st.rerun()

st.divider()

# ==========================================
# 2. 巡查紀錄填寫
# ==========================================
st.subheader("📝 填寫巡查紀錄 (批次輸入區)")

# 防呆：如果還沒鎖定身分，就不給填寫資料
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
                st.error("⚠️ 資料庫查無此學號！")
                selected_class, student_name, seat_num = "未知", "未知", "未知"
        else:
            selected_class, student_name, seat_num = "-", "-", "-"
    
    # ==========================================
    # 3. 暫存與批次上傳邏輯
    # ==========================================
    if st.button("➕ 加入下方暫存清單", use_container_width=True):
        if record_type == "個人違規紀錄" and (len(student_id) != 6 or student_name == "未知"):
            st.error("⚠️ 個人紀錄請務必輸入正確且存在於資料庫的 6 碼學號！")
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
                "回報人": st.session_state.current_user # 直接使用鎖定好的身分
            }
            st.session_state.temp_records.append(new_record)

# ==========================================
# 顯示暫存區 (購物車概念)
# ==========================================
if len(st.session_state.temp_records) > 0:
    st.markdown("### 🛒 待上傳的暫存紀錄 (請確認無誤後上傳)")
    temp_df = pd.DataFrame(st.session_state.temp_records)
    st.dataframe(temp_df, use_container_width=True)
    
    col_upload, col_clear = st.columns(2)
    with col_upload:
        if st.button("🚀 確認無誤，全數寫入總資料庫", type="primary", use_container_width=True):
            master_df = pd.read_csv(DB_FILE)
            updated_df = pd.concat([master_df, temp_df], ignore_index=True)
            updated_df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
            st.session_state.temp_records = []
            st.success("✅ 所有資料已成功寫入！")
            st.rerun() 
            
    with col_clear:
        if st.button("🗑️ 清空暫存區 (重新輸入)", use_container_width=True):
            st.session_state.temp_records = []
            st.rerun()

st.divider()
st.subheader("📊 全校巡查總資料庫")
try:
    master_df = pd.read_csv(DB_FILE)
    if len(master_df) > 0:
        st.dataframe(master_df, use_container_width=True)
    else:
        st.info("目前總資料庫尚無紀錄。")
except Exception as e:
    st.error("讀取資料庫時發生錯誤。")