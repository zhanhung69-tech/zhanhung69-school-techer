import streamlit as st
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# ==========================================
# 頁面配置
# ==========================================
st.set_page_config(page_title="樹人家商-校園管理整合系統", layout="wide")

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
    sheet_records = doc.sheet1  # 第一頁：巡查紀錄
    
    # 檢查或取得請假紀錄分頁
    try:
        sheet_leave = doc.worksheet("僑生請假紀錄")
    except:
        sheet_leave = doc.add_worksheet(title="僑生請假紀錄", rows="2000", cols="12")
        sheet_leave.append_row(["紀錄日期", "班級", "座號", "學號", "姓名", "類別", "起點日期", "迄止日期", "細節與時間", "外宿地點", "親友/關係/電話", "經辦人"])
except Exception as e:
    st.error("⚠️ 系統連線失敗，請檢查金鑰設定。")
    st.stop()

# ==========================================
# 讀取學生名冊
# ==========================================
@st.cache_data(ttl=300)
def load_student_df():
    try:
        sheet_students = doc.worksheet("學生名單")
        df = pd.DataFrame(sheet_students.get_all_records())
        # 防呆：確保需要的欄位存在，若無則補空欄位
        for col in ['學號', '姓名', '班級', '座號', '學生手機', '家長聯絡電話']:
            if col not in df.columns:
                df[col] = ""
        # 將學號轉為字串並去除空白
        df['學號'] = df['學號'].astype(str).str.strip()
        # 確保座號為兩碼字串 (例如 "01", "05")
        df['座號'] = df['座號'].astype(str).str.zfill(2)
        return df
    except:
        return pd.DataFrame()

df_students = load_student_df()

# 轉換為字典供巡查系統快速比對
if not df_students.empty:
    student_db = df_students.set_index('學號').to_dict('index')
else:
    student_db = {}

# 系統記憶體初始化
if "temp_records" not in st.session_state:
    st.session_state.temp_records = []
if "current_user" not in st.session_state:
    st.session_state.current_user = None

# ==========================================
# 側邊欄：嚴格身分與權限綁定
# ==========================================
with st.sidebar:
    st.title("📂 系統選單")
    
    # 網址免登入參數處理
    if "role" in st.query_params and "name" in st.query_params and st.session_state.current_user is None:
        role_param = st.query_params['role']
        st.session_state.current_user = {
            "role": role_param,
            "name": st.query_params['name'],
            "class": st.query_params.get('class', '全校')
        }

    overseas_classes = ["資訊一孝", "資訊一仁", "觀一孝", "觀一仁", "餐一和", "餐一平", "資訊二孝"]

    if st.session_state.current_user is None:
        role = st.selectbox("您的職務", ["學務主任", "教務主任", "生輔員", "行政", "導師", "管理員"])
        
        if role == "導師":
            u_class = st.selectbox("負責班級 (僅限僑生班級)", overseas_classes)
            u_name = st.text_input("老師姓名")
        else:
            u_class = "全校"
            u_name = st.text_input("您的姓名")
            
        if st.button("🔐 登入系統", type="primary"):
            if u_name == "":
                st.error("請輸入姓名！")
            else:
                st.session_state.current_user = {"role": role, "name": u_name, "class": u_class}
                st.rerun()
    else:
        u = st.session_state.current_user
        st.success(f"✅ 已登入身分：\n職務：{u['role']}\n姓名：{u['name']}\n權限區：{u['class']}")
        if st.button("🔄 卸除身分登出"):
            st.session_state.current_user = None
            st.query_params.clear()
            st.rerun()

    st.divider()
    
    # --- 動態選單 (依規定權限控管) ---
    menu_options = []
    if st.session_state.current_user:
        curr_role = st.session_state.current_user["role"]
        
        # 1. 全校巡察登記：排除導師
        if curr_role in ["學務主任", "教務主任", "生輔員", "行政", "管理員"]:
            menu_options.append("🔭 全校巡查登記")
            
        # 2. 僑生請假申請：僅限導師、管理員
        if curr_role in ["導師", "管理員"]:
            menu_options.append("📝 僑生假單申請")
            
        # 3. 數據中心：僅限管理員
        if curr_role == "管理員":
            menu_options.append("📊 綜合數據中心")
            
    app_mode = st.radio("功能切換", menu_options if menu_options else ["🔒 請先登入解鎖系統"])

# ==========================================
# 模組一：全校巡查登記 (完美保留您的完整邏輯)
# ==========================================
if app_mode == "🔭 全校巡查登記":
    st.header("🔭 全校巡查即時登記")
    st.info("💡 系統已連動真實班級選單與 1分/0.03分 自動計分邏輯。")
    
    time_period = st.selectbox("請選擇巡查時間", [
        "0810-0900 第一節", "0910-1000 第二節", "1010-1100 第三節", "1110-1200 第四節",
        "1230-1300 午休", "1310-1400 第五節", "1410-1500 第六節", "1510-1600 第七節"
    ])
    
    record_type = st.radio("📌 請選擇登記對象", ["班級整體表現", "個人違規紀錄"], horizontal=True)
    
    # --- 班級模組 ---
    if record_type == "班級整體表現":
        col1, col2 = st.columns(2)
        with col1:
            grade = st.selectbox("👉 先選年級", ["一年級", "二年級", "三年級"])
        with col2:
            real_class_list = {
                "一年級": ["商一忠", "資處一忠", "觀一忠", "觀一孝", "觀一仁", "餐一忠", "餐一孝", "餐一仁", "餐一愛", "餐一信", "餐一義", "餐一和", "餐一平", "幼一忠", "美一忠", "美一孝", "美一仁", "影一忠", "資訊一忠", "資訊一孝", "資訊一仁"],
                "二年級": ["商二忠", "資處二忠", "資處二孝", "觀二忠", "觀二孝", "餐二忠", "餐二孝", "餐二仁", "餐二愛", "餐二信", "餐二義", "餐二和", "幼二忠", "美二忠", "美二孝", "美二仁", "影二忠", "影二孝", "資訊二忠", "資訊二孝", "資訊二仁"],
                "三年級": ["商三忠", "電三忠", "資處三忠", "資處三孝", "觀三忠", "觀三孝", "觀三仁", "餐三忠", "餐三孝", "餐三仁", "餐三愛", "餐三信", "餐三義", "餐三和", "幼三忠", "幼三孝", "美三忠", "美三孝", "美三仁", "影三忠", "資訊三忠"]
            }
            selected_class = st.selectbox("👉 再選班級", real_class_list[grade])
            
        student_id, student_name, seat_num = "無", "無", "無"
        class_status_options = [
            "秩序良好 (+1)", "午休良好 (+1)", "導師入班 (+1)", 
            "上課吵鬧/秩序不佳 (-1)", "午休吵鬧 (-1)", "環境髒亂 (-1)", "未節電 (-1)", "其他 (自行輸入)"
        ]
        status_category = st.selectbox("🎯 請選擇班級狀況", class_status_options)
        
        if status_category == "其他 (自行輸入)":
            status = st.text_input("請輸入補充說明：")
            score_action = st.radio("計分方式", ["加 1 分", "扣 1 分", "不計分"], horizontal=True)
            score_num = 1 if score_action == "加 1 分" else (-1 if score_action == "扣 1 分" else 0)
        else:
            status = status_category.split(" (")[0]
            score_num = 1 if "(+1)" in status_category else -1

    # --- 個人模組 ---
    else:
        if df_students.empty:
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
            personal_status_options = [
                "服儀違規-書包/短裙/便服 (0)", "上課遊蕩/去合作社 (-0.03)", "遲到/未到/曠課 (-0.03)", 
                "上課滑手機/睡覺 (-0.03)", "熱心服務/表現優良 (+0.03)", "其他 (自行輸入)"
            ]
            status_category = st.selectbox("🎯 請選擇個人狀況", personal_status_options)
            
            if status_category == "其他 (自行輸入)":
                status = st.text_input("請輸入補充說明：")
                score_action = st.radio("計分方式", ["加 0.03 分", "扣 0.03 分", "不計分"], horizontal=True)
                score_num = 0.03 if score_action == "加 0.03 分" else (-0.03 if score_action == "扣 0.03 分" else 0)
            else:
                status = status_category.split(" (")[0]
                if "(+0.03)" in status_category: score_num = 0.03
                elif "(-0.03)" in status_category: score_num = -0.03
                else: score_num = 0
    
    # --- 暫存與上傳區 ---
    if st.button("➕ 加入下方暫存清單", use_container_width=True):
        if record_type == "個人違規紀錄" and (len(student_id) != 6 or student_name == "未知"):
            st.error("⚠️ 個人紀錄請務必輸入正確的 6 碼學號！")
        elif status_category == "其他 (自行輸入)" and status == "":
            st.error("⚠️ 請在補充說明欄位輸入狀況！")
        else:
            new_record = {
                "日期": today_date, "時間": time_period,
                "對象": "個人" if record_type == "個人違規紀錄" else "班級",
                "班級": selected_class, "座號": seat_num, "學號": student_id,
                "姓名": student_name, "狀況": status, "得分": score_num,
                "回報人": f"{st.session_state.current_user['role']}-{st.session_state.current_user['name']}"
            }
            st.session_state.temp_records.append(new_record)

    if len(st.session_state.temp_records) > 0:
        st.markdown("### 🛒 待上傳的暫存紀錄")
        st.dataframe(pd.DataFrame(st.session_state.temp_records), use_container_width=True)
        col_up, col_clr = st.columns(2)
        with col_up:
            if st.button("🚀 確認無誤，全數寫入", type="primary", use_container_width=True):
                upload_data = [[r["日期"], r["時間"], r["對象"], r["班級"], r["座號"], r["學號"], r["姓名"], r["狀況"], r["得分"], r["回報人"]] for r in st.session_state.temp_records]
                sheet_records.append_rows(upload_data)
                st.session_state.temp_records = []
                st.success("✅ 資料寫入成功！")
                st.rerun() 
        with col_clr:
            if st.button("🗑️ 清空暫存區", use_container_width=True):
                st.session_state.temp_records = []
                st.rerun()

# ==========================================
# 模組二：僑生假單申請 (整合版 PDF 產製)
# ==========================================
elif app_mode == "📝 僑生假單申請":
    st.header("📝 僑生外散宿申請單 (週報表整合模式)")
    user = st.session_state.current_user
    
    # 管理員可以幫所有僑生班級代為操作，導師只能看自己的班
    if user["role"] == "管理員":
        target_class = st.selectbox("請選擇要操作的僑生班級", overseas_classes)
    else:
        target_class = user["class"]
        st.info(f"📍 目前負責班級：**{target_class}**")
        
    class_students = df_students[df_students["班級"] == target_class].copy()
    
    if class_students.empty:
        st.warning(f"名單資料庫中查無 {target_class} 的學生資料，請確認「學生名單」試算表是否已更新。")
    else:
        # 新增座號前綴加速尋找
        class_students["顯示名稱"] = class_students["座號"] + "-" + class_students["姓名"]
        
        with st.expander("第一步：勾選本週需申請的學生 (可多選)", expanded=True):
            selected_display = st.multiselect("請選擇學生 (輸入座號可快速搜尋)：", class_students["顯示名稱"].tolist())
            selected_data = class_students[class_students["顯示名稱"].isin(selected_display)]
            
        if not selected_data.empty:
            with st.form("leave_batch_form", clear_on_submit=False):
                st.subheader("第二步：統一填寫假單與外宿細節")
                c1, c2 = st.columns(2)
                with c1:
                    l_type = st.selectbox("申請項目", ["晚歸", "外宿", "返鄉", "職場實習", "打工", "其他"])
                    start_dt = st.date_input("起始日期", value=tw_time)
                with c2:
                    end_dt = st.date_input("結束日期", value=tw_time)
                    l_time = st.time_input("預計返校時間", value=datetime.strptime("22:00", "%H:%M").time())
                
                # 依規定：外宿提醒與晚歸限制
                stay_info = ""
                stay_loc = ""
                time_valid = True
                
                if l_type == "晚歸" and l_time > datetime.strptime("22:30", "%H:%M").time():
                    st.error("❌ 依規定，晚歸時間不得超過 22:30！請修正時間。")
                    time_valid = False
                elif l_type == "外宿":
                    st.info("📌 規定提醒：外宿者請統一於返宿當日 21:00 參加點名。")
                    sc1, sc2, sc3, sc4 = st.columns(4)
                    with sc1: stay_loc = st.text_input("外宿地點")
                    with sc2: rel_name = st.text_input("親友姓名")
                    with sc3: rel_type = st.text_input("關係")
                    with sc4: rel_tel = st.text_input("親友聯絡電話")
                    stay_info = f"親友:{rel_name}({rel_type}) / 電話:{rel_tel}"
                    
                reason = st.text_input("事由補充說明")
                
                submit_btn = st.form_submit_button("🚀 產製一週整合假單並送出", use_container_width=True)
                
                if submit_btn and time_valid:
                    # 存入 Google 試算表
                    all_rows = []
                    for _, s in selected_data.iterrows():
                        all_rows.append([
                            today_date, s['班級'], s['座號'], s['學號'], s['姓名'],
                            l_type, str(start_dt), str(end_dt), f"返校:{l_time.strftime('%H:%M')} / {reason}", 
                            stay_loc if l_type=="外宿" else "", stay_info, user['name']
                        ])
                    sheet_leave.append_rows(all_rows)
                    st.success("✅ 資料已存入雲端！請於下方預覽並列印 PDF。")
                    
                    # 儲存到 session 供 PDF 預覽
                    st.session_state.batch_print = {
                        "class": target_class, "students": selected_data, "type": l_type, 
                        "start": start_dt, "end": end_dt, "time": l_time, "reason": reason, 
                        "stay_loc": stay_loc, "stay_info": stay_info
                    }

            # --- 最終版：排版乾淨的整合式 PDF 預覽 ---
            if "batch_print" in st.session_state:
                p = st.session_state.batch_print
                st.divider()
                st.success("💡 **列印小訣竅：** 請直接按下鍵盤 **Ctrl + P** (或點擊瀏覽器右上角選單 -> 列印)，將目的地選擇為「另存為 PDF」，即可獲得完美格式的假單。")
                
                with st.container(border=True):
                    st.markdown(f"<h2 style='text-align:center;'>樹人家商 {p['class']} 僑生外散(宿)集體申請單</h2>", unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    i_c1, i_c2, i_c3 = st.columns(3)
                    i_c1.markdown(f"**申請類別：** {p['type']}")
                    i_c2.markdown(f"**申請日期：** {p['start']} 至 {p['end']}")
                    if p['type'] == "外宿":
                        i_c3.markdown(f"**返宿時間：** 規定 21:00 參加點名")
                    else:
                        i_c3.markdown(f"**返校時間：** {p['time'].strftime('%H:%M')}")
                    
                    if p['type'] == "外宿":
                        st.markdown(f"**外宿地點：** {p['stay_loc']} 　|　 **親友資訊：** {p['stay_info']}")
                    st.markdown(f"**事由說明：** {p['reason']}")
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # 取出特定欄位印成美觀表格 (拿掉身分證與生日)
                    print_df = p["students"][["座號", "姓名", "學號", "學生手機", "家長聯絡電話"]].copy()
                    # 重設 index 讓畫面更乾淨
                    print_df.reset_index(drop=True, inplace=True)
                    st.table(print_df)
                    
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    
                    # 核章區：拿掉方格，直接職務名稱平排
                    h_cols = st.columns(5)
                    labels = ["導師", "生輔組長", "學務主任", "國際交流組", "招生中心"]
                    for idx, label in enumerate(labels):
                        h_cols[idx].markdown(f"<div style='text-align:center;'><b>{label}</b><br><br><br></div>", unsafe_allow_html=True)

# ==========================================
# 模組三：綜合數據中心 (僅限管理員)
# ==========================================
elif app_mode == "📊 綜合數據中心":
    st.header("📊 管理員專屬：綜合數據中心")
    if "current_user" not in st.session_state or st.session_state.current_user is None:
        st.stop()
        
    tab1, tab2 = st.tabs(["🔥 巡查紀錄與結算", "✈️ 僑生請假總表"])
    
    with tab1:
        st.subheader("全校巡查總表")
        all_patrol = sheet_records.get_all_records()
        if len(all_patrol) > 0:
            df_patrol = pd.DataFrame(all_patrol)
            st.dataframe(df_patrol, use_container_width=True)
        else:
            st.info("尚無巡查紀錄。")
            
    with tab2:
        st.subheader("僑生請假/外散宿總表")
        leave_data = sheet_leave.get_all_records()
        if len(leave_data) > 0:
            df_leave = pd.DataFrame(leave_data)
            st.dataframe(df_leave, use_container_width=True)
            csv = df_leave.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下載完整假單總表 (CSV)", data=csv, file_name=f"僑生請假紀錄總表_{today_date}.csv", use_container_width=True)
        else:
            st.info("尚無請假紀錄。")
