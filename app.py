import streamlit as st
import streamlit.components.v1 as components
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
    sheet_records = doc.sheet1  
    
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
        for col in ['學號', '姓名', '班級', '座號', '學生手機', '家長聯絡電話']:
            if col not in df.columns:
                df[col] = ""
        df['學號'] = df['學號'].astype(str).str.strip()
        df['座號'] = df['座號'].astype(str).str.zfill(2)
        return df
    except:
        return pd.DataFrame()

df_students = load_student_df()
if not df_students.empty:
    student_db = df_students.set_index('學號').to_dict('index')
else:
    student_db = {}

# 系統記憶體初始化
if "temp_records" not in st.session_state:
    st.session_state.temp_records = []
if "leave_cart" not in st.session_state:
    st.session_state.leave_cart = [] # 假單專用的購物車
if "current_user" not in st.session_state:
    st.session_state.current_user = None

# ==========================================
# 側邊欄：嚴格身分與權限綁定
# ==========================================
with st.sidebar:
    st.title("📂 系統選單")
    
    if "role" in st.query_params and "name" in st.query_params and st.session_state.current_user is None:
        st.session_state.current_user = {
            "role": st.query_params['role'],
            "name": st.query_params['name'],
            "class": st.query_params.get('class', '全校')
        }

    overseas_classes = ["資訊一孝", "資訊一仁", "觀一孝", "觀一仁", "餐一和", "餐一平", "資訊二孝"]

    if st.session_state.current_user is None:
        role = st.selectbox("您的職務", ["學務主任", "教務主任", "生輔員", "行政", "導師", "管理員"])
        
        if role == "導師":
            u_class = st.selectbox("負責班級", overseas_classes)
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
    
    menu_options = []
    if st.session_state.current_user:
        curr_role = st.session_state.current_user["role"]
        if curr_role in ["學務主任", "教務主任", "生輔員", "行政", "管理員"]:
            menu_options.append("🔭 全校巡查登記")
        if curr_role in ["導師", "管理員"]:
            menu_options.append("📝 僑生假單申請")
        if curr_role == "管理員":
            menu_options.append("📊 綜合數據中心")
            
    app_mode = st.radio("功能切換", menu_options if menu_options else ["🔒 請先登入解鎖系統"])

# ==========================================
# 模組一：全校巡查登記
# ==========================================
if app_mode == "🔭 全校巡查登記":
    st.header("🔭 全校巡查即時登記")
    # (此處完美保留您的巡查邏輯，因為字數限制不在此重複貼出，請保留您原本這段 `if app_mode == "🔭 全校巡查登記":` 的全部內容)
    # [註：實務上請將上一版的巡查模組貼回這裡]
    time_period = st.selectbox("請選擇巡查時間", ["0810-0900 第一節", "0910-1000 第二節", "1010-1100 第三節", "1110-1200 第四節", "1230-1300 午休", "1310-1400 第五節", "1410-1500 第六節", "1510-1600 第七節"])
    record_type = st.radio("📌 請選擇登記對象", ["班級整體表現", "個人違規紀錄"], horizontal=True)
    
    if record_type == "班級整體表現":
        col1, col2 = st.columns(2)
        with col1: grade = st.selectbox("👉 先選年級", ["一年級", "二年級", "三年級"])
        with col2:
            real_class_list = {
                "一年級": ["商一忠", "資處一忠", "觀一忠", "觀一孝", "觀一仁", "餐一忠", "餐一孝", "餐一仁", "餐一愛", "餐一信", "餐一義", "餐一和", "餐一平", "幼一忠", "美一忠", "美一孝", "美一仁", "影一忠", "資訊一忠", "資訊一孝", "資訊一仁"],
                "二年級": ["商二忠", "資處二忠", "資處二孝", "觀二忠", "觀二孝", "餐二忠", "餐二孝", "餐二仁", "餐二愛", "餐二信", "餐二義", "餐二和", "幼二忠", "美二忠", "美二孝", "美二仁", "影二忠", "影二孝", "資訊二忠", "資訊二孝", "資訊二仁"],
                "三年級": ["商三忠", "電三忠", "資處三忠", "資處三孝", "觀三忠", "觀三孝", "觀三仁", "餐三忠", "餐三孝", "餐三仁", "餐三愛", "餐三信", "餐三義", "餐三和", "幼三忠", "幼三孝", "美三忠", "美三孝", "美三仁", "影三忠", "資訊三忠"]
            }
            selected_class = st.selectbox("👉 再選班級", real_class_list[grade])
            
        student_id, student_name, seat_num = "無", "無", "無"
        status_category = st.selectbox("🎯 請選擇班級狀況", ["秩序良好 (+1)", "午休良好 (+1)", "導師入班 (+1)", "上課吵鬧/秩序不佳 (-1)", "午休吵鬧 (-1)", "環境髒亂 (-1)", "未節電 (-1)", "其他 (自行輸入)"])
        
        if status_category == "其他 (自行輸入)":
            status = st.text_input("請輸入補充說明：")
            score_action = st.radio("計分方式", ["加 1 分", "扣 1 分", "不計分"], horizontal=True)
            score_num = 1 if score_action == "加 1 分" else (-1 if score_action == "扣 1 分" else 0)
        else:
            status = status_category.split(" (")[0]
            score_num = 1 if "(+1)" in status_category else -1
    else:
        col_id, col_status = st.columns(2)
        with col_id:
            student_id = st.text_input("請輸入學生學號 (限6碼)：").replace(" ", "")
            if len(student_id) == 6 and student_id in student_db:
                info = student_db[student_id]
                selected_class, student_name, seat_num = info["班級"], info["姓名"], info["座號"]
                st.success(f"✅ 查獲：{selected_class} {seat_num}號 {student_name}")
            else:
                selected_class, student_name, seat_num = "-", "-", "-"
                if len(student_id) == 6: st.error("⚠️ 查無此學號！")
                
        with col_status:
            status_category = st.selectbox("🎯 請選擇個人狀況", ["服儀違規-書包/短裙/便服 (0)", "上課遊蕩/去合作社 (-0.03)", "遲到/未到/曠課 (-0.03)", "上課滑手機/睡覺 (-0.03)", "熱心服務/表現優良 (+0.03)", "其他 (自行輸入)"])
            if status_category == "其他 (自行輸入)":
                status = st.text_input("請輸入補充說明：")
                score_action = st.radio("計分方式", ["加 0.03 分", "扣 0.03 分", "不計分"], horizontal=True)
                score_num = 0.03 if score_action == "加 0.03 分" else (-0.03 if score_action == "扣 0.03 分" else 0)
            else:
                status = status_category.split(" (")[0]
                if "(+0.03)" in status_category: score_num = 0.03
                elif "(-0.03)" in status_category: score_num = -0.03
                else: score_num = 0

    if st.button("➕ 加入下方暫存清單", use_container_width=True):
        if record_type == "個人違規紀錄" and (len(student_id) != 6 or student_name == "未知"):
            st.error("⚠️ 個人紀錄請務必輸入正確的 6 碼學號！")
        else:
            st.session_state.temp_records.append({
                "日期": today_date, "時間": time_period, "對象": "個人" if record_type == "個人違規紀錄" else "班級",
                "班級": selected_class, "座號": seat_num, "學號": student_id, "姓名": student_name, "狀況": status, "得分": score_num,
                "回報人": f"{st.session_state.current_user['role']}-{st.session_state.current_user['name']}"
            })

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
# 模組二：僑生假單申請 (升級版：購物車機制 + 完美 PDF)
# ==========================================
elif app_mode == "📝 僑生假單申請":
    st.header("📝 僑生外散宿申請單 (週報表整合模式)")
    user = st.session_state.current_user
    
    target_class = st.selectbox("請選擇要操作的僑生班級", overseas_classes) if user["role"] == "管理員" else user["class"]
    class_students = df_students[df_students["班級"] == target_class].copy()
    
    if class_students.empty:
        st.warning(f"名單資料庫中查無 {target_class} 的學生資料。")
    else:
        class_students["顯示名稱"] = class_students["座號"] + "-" + class_students["姓名"]
        
        # --- 步驟 1：不斷加入購物車 ---
        with st.expander("第一步：設定假別並加入本週清單 (可重複分批加入)", expanded=True):
            selected_display = st.multiselect("選擇本次要設定的學生 (可多選)：", class_students["顯示名稱"].tolist())
            selected_data = class_students[class_students["顯示名稱"].isin(selected_display)]
            
            c1, c2 = st.columns(2)
            with c1:
                l_type = st.selectbox("申請項目", ["晚歸", "外宿", "返鄉", "職場實習", "打工", "其他"])
                start_dt = st.date_input("起始日期", value=tw_time)
            with c2:
                end_dt = st.date_input("結束日期", value=tw_time)
                l_time = st.time_input("預計返校時間", value=datetime.strptime("22:00", "%H:%M").time())
            
            stay_info = ""
            stay_loc = ""
            time_valid = True
            
            if l_type == "晚歸" and l_time > datetime.strptime("22:30", "%H:%M").time():
                st.error("❌ 依規定，晚歸時間不得超過 22:30！請修正時間。")
                time_valid = False
            elif l_type == "外宿":
                st.info("📌 提醒：外宿者請統一於返宿當日 21:00 參加點名。")
                sc1, sc2, sc3, sc4 = st.columns(4)
                with sc1: stay_loc = st.text_input("外宿地點")
                with sc2: rel_name = st.text_input("親友姓名")
                with sc3: rel_type = st.text_input("關係")
                with sc4: rel_tel = st.text_input("親友聯絡電話")
                stay_info = f"親友:{rel_name}({rel_type}) / 電話:{rel_tel}"
                
            reason = st.text_input("事由補充說明")
            
            if st.button("➕ 將以上設定加入本週整合清單", use_container_width=True) and time_valid:
                if selected_data.empty:
                    st.warning("請至少選擇一位學生！")
                else:
                    for _, s in selected_data.iterrows():
                        record = {
                            "班級": target_class, "座號": s['座號'], "學號": s['學號'], "姓名": s['姓名'],
                            "學生手機": s['學生手機'], "家長電話": s['家長聯絡電話'],
                            "類別": l_type, "起訖日期": f"{start_dt} ~ {end_dt}", 
                            "返校時間": "21:00點名" if l_type == "外宿" else l_time.strftime('%H:%M'),
                            "事由與細節": reason + (f" | {stay_loc}" if l_type == "外宿" else ""),
                            "親友資訊": stay_info if l_type == "外宿" else "-",
                            # 用於寫入資料庫的原始欄位
                            "raw_start": str(start_dt), "raw_end": str(end_dt), "raw_reason": f"返校:{l_time.strftime('%H:%M')} / {reason}",
                            "raw_loc": stay_loc, "raw_info": stay_info
                        }
                        st.session_state.leave_cart.append(record)
                    st.success(f"✅ 已成功將 {len(selected_data)} 位學生加入清單！可繼續選擇其他學生設定不同假別。")

        # --- 步驟 2：預覽購物車與正式送出 ---
        if len(st.session_state.leave_cart) > 0:
            st.markdown("### 🛒 本週申請總表預覽")
            
            # 整理要顯示在網頁上的 DataFrame
            df_cart = pd.DataFrame(st.session_state.leave_cart)
            display_cols = ["座號", "姓名", "類別", "起訖日期", "返校時間", "事由與細節", "親友資訊"]
            st.dataframe(df_cart[display_cols], use_container_width=True)
            
            col_send, col_clear = st.columns(2)
            with col_send:
                if st.button("🚀 全班確認無誤，送出寫入並產製 PDF", type="primary", use_container_width=True):
                    # 1. 寫入 GSheets
                    upload_rows = []
                    for r in st.session_state.leave_cart:
                        upload_rows.append([
                            today_date, r['班級'], r['座號'], r['學號'], r['姓名'],
                            r['類別'], r['raw_start'], r['raw_end'], r['raw_reason'], 
                            r['raw_loc'], r['raw_info'], user['name']
                        ])
                    sheet_leave.append_rows(upload_rows)
                    
                    # 2. 產製純淨 HTML 列印版
                    html_table_rows = ""
                    for r in st.session_state.leave_cart:
                        html_table_rows += f"<tr><td>{r['座號']}</td><td>{r['姓名']}</td><td>{r['類別']}</td><td>{r['起訖日期']}</td><td>{r['返校時間']}</td><td>{r['事由與細節']}<br>{r['親友資訊']}</td><td>{r['學生手機']}</td><td>{r['家長電話']}</td></tr>"
                    
                    html_content = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="utf-8">
                        <style>
                            body {{ font-family: "Microsoft JhengHei", sans-serif; color: black; background: white; padding: 20px; }}
                            @media print {{
                                #print-btn {{ display: none !important; }}
                                @page {{ size: A4 landscape; margin: 15mm; }}
                            }}
                            #print-btn {{ margin-bottom: 20px; padding: 12px 24px; background: #FF4B4B; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 18px; font-weight: bold; width: 100%; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                            #print-btn:hover {{ background: #ff3333; }}
                            .title {{ text-align: center; font-size: 24px; font-weight: bold; margin-bottom: 20px; border-bottom: 2px solid black; padding-bottom: 10px; }}
                            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; }}
                            th, td {{ border: 1px solid black; padding: 8px; text-align: center; vertical-align: middle; }}
                            th {{ background-color: #f2f2f2; }}
                            .sig-container {{ display: flex; justify-content: space-between; margin-top: 80px; }}
                            .sig-box {{ text-align: center; width: 18%; font-weight: bold; font-size: 16px; }}
                        </style>
                    </head>
                    <body>
                        <button id="print-btn" onclick="window.print()">🖨️ 點此開啟列印 (請選擇另存為 PDF)</button>
                        <div class="title">樹人家商 {target_class} 僑生外散(宿)集體申請單</div>
                        <table>
                            <thead>
                                <tr><th>座號</th><th>姓名</th><th>類別</th><th>申請日期</th><th>返校/宿時間</th><th>地點/事由/親友資訊</th><th>學生手機</th><th>家長電話</th></tr>
                            </thead>
                            <tbody>
                                {html_table_rows}
                            </tbody>
                        </table>
                        <div class="sig-container">
                            <div class="sig-box">導師<br><br><br></div>
                            <div class="sig-box">生輔組長<br><br><br></div>
                            <div class="sig-box">學務主任<br><br><br></div>
                            <div class="sig-box">國際交流組<br><br><br></div>
                            <div class="sig-box">招生中心<br><br><br></div>
                        </div>
                    </body>
                    </html>
                    """
                    st.session_state.print_html = html_content
                    st.session_state.leave_cart = [] # 送出後清空購物車
                    st.success("✅ 資料已成功寫入資料庫！")
                    st.rerun()
                    
            with col_clear:
                if st.button("🗑️ 清空清單，重新設定", use_container_width=True):
                    st.session_state.leave_cart = []
                    st.rerun()

        # --- 步驟 3：渲染純淨的 PDF 列印畫面 ---
        if "print_html" in st.session_state:
            st.divider()
            st.success("🎉 **產製成功！** 請點擊下方紅色按鈕，系統會彈出一個乾淨的列印視窗，不會印到任何網頁側邊欄！(強烈建議版面設定為**橫向**)")
            # 使用 iframe 技術隔絕 Streamlit 本身的 UI
            components.html(st.session_state.print_html, height=800, scrolling=True)

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
            st.dataframe(pd.DataFrame(all_patrol), use_container_width=True)
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
