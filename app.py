import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# ==========================================
# 頁面配置 & 台灣時間
# ==========================================
st.set_page_config(page_title="樹人家商-校園管理整合系統", layout="wide")
tw_time = datetime.utcnow() + timedelta(hours=8)
today_date = tw_time.strftime("%Y-%m-%d")

# ==========================================
# 安全讀取引擎
# ==========================================
def safe_get_dataframe(sheet):
    data = sheet.get_all_values()
    if not data: return pd.DataFrame()
    headers = data[0]
    clean_headers = []
    for i, h in enumerate(headers):
        val = str(h).strip()
        if not val: val = f"未命名欄位_{i}"
        while val in clean_headers: val += "_重複"
        clean_headers.append(val)
    if len(data) > 1: return pd.DataFrame(data[1:], columns=clean_headers)
    return pd.DataFrame(columns=clean_headers)

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
    
    # 確保所需分頁存在
    def ensure_sheet(title, headers):
        try:
            return doc.worksheet(title)
        except:
            ws = doc.add_worksheet(title=title, rows="2000", cols="15")
            ws.append_row(headers)
            return ws

    sheet_leave = ensure_sheet("僑生請假紀錄", ["紀錄日期", "班級", "座號", "學號", "姓名", "類別", "起點日期", "迄止日期", "細節與時間", "外宿地點", "親友/關係/電話", "經辦人"])
    sheet_accounts = ensure_sheet("系統帳號密碼", ["帳號", "密碼", "職務", "姓名", "負責班級"])
    sheet_rewards_db = ensure_sheet("獎懲條文", ["嘉獎", "小功", "大功", "警告", "小過", "大過"])
    sheet_rewards_log = ensure_sheet("獎懲紀錄總表", ["日期", "類別", "學號", "班級", "座號姓名", "獎懲項目", "事由", "建議次數", "導師簽名"])
    
except Exception as e:
    st.error("⚠️ 系統連線失敗，請檢查金鑰設定。")
    st.stop()

# ==========================================
# 讀取資料庫
# ==========================================
def load_data():
    try:
        df_stu = safe_get_dataframe(doc.worksheet("學生名單"))
        for col in ['學號', '姓名', '班級', '座號', '學生手機', '家長聯絡電話']:
            if col not in df_stu.columns: df_stu[col] = ""
        df_stu['學號'] = df_stu['學號'].astype(str).str.strip()
        df_stu['座號'] = df_stu['座號'].astype(str).str.zfill(2)
        
        df_acc = safe_get_dataframe(sheet_accounts)
        if '帳號' in df_acc.columns:
            df_acc['帳號'] = df_acc['帳號'].astype(str).str.strip()
            df_acc['密碼'] = df_acc['密碼'].astype(str).str.strip()
            
        df_rules = safe_get_dataframe(sheet_rewards_db)
        return df_stu, df_acc, df_rules
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_students, df_accounts, df_rules = load_data()
student_db = df_students.set_index('學號').to_dict('index') if not df_students.empty else {}

# 記憶體初始化
for key in ["temp_records", "leave_cart", "reward_cart"]:
    if key not in st.session_state: st.session_state[key] = [] 
if "current_user" not in st.session_state: st.session_state.current_user = None

# ==========================================
# 側邊欄：登入與權限控管
# ==========================================
with st.sidebar:
    st.title("📂 系統選單")
    if st.session_state.current_user is None:
        st.subheader("🔐 人員登入")
        login_user = st.text_input("請輸入帳號")
        login_pwd = st.text_input("請輸入密碼", type="password")
        if st.button("登入系統", type="primary", use_container_width=True):
            if df_accounts.empty:
                st.error("⚠️ 系統尚未讀取到帳號庫。")
            else:
                match = df_accounts[(df_accounts['帳號'] == login_user) & (df_accounts['密碼'] == login_pwd)]
                if not match.empty:
                    user_info = match.iloc[0]
                    st.session_state.current_user = {"role": user_info.get('職務', ''), "name": user_info.get('姓名', ''), "class": user_info.get('負責班級', '全校')}
                    st.rerun()
                else:
                    st.error("❌ 帳號或密碼錯誤！")
    else:
        u = st.session_state.current_user
        st.success(f"✅ 登入成功\n\n👤 {u['name']}\n🏷️ {u['role']}\n📍 {u['class']}")
        if st.button("🔄 登出系統", use_container_width=True):
            st.session_state.current_user = None
            st.rerun()

    st.divider()
    menu_options = []
    if st.session_state.current_user:
        curr_role = st.session_state.current_user["role"]
        if curr_role in ["學務主任", "教務主任", "生輔員", "行政", "管理員"]: menu_options.append("🔭 全校巡查登記")
        if curr_role in ["導師", "管理員"]: 
            menu_options.append("📝 僑生假單申請")
            menu_options.append("🏆 獎懲建議單申請")
        if curr_role == "管理員": menu_options.append("📊 綜合數據中心 (管理員專屬)")
            
    app_mode = st.radio("功能切換", menu_options if menu_options else ["🔒 系統已鎖定"])

# ==========================================
# 模組一：全校巡查登記
# ==========================================
if app_mode == "🔭 全校巡查登記":
    st.header("🔭 全校巡查即時登記")
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
            
        student_id, student_name, seat_num = "-", "-", "-"
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
                selected_class, student_name, seat_num = info.get("班級","-"), info.get("姓名","-"), info.get("座號","-")
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
        if record_type == "個人違規紀錄" and (len(student_id) != 6 or student_name == "-"):
            st.error("⚠️ 請務必輸入正確的學號！")
        else:
            st.session_state.temp_records.append({
                "日期": today_date, "時間": time_period, "對象": "個人" if record_type == "個人違規紀錄" else "班級",
                "班級": selected_class, "座號": seat_num, "學號": student_id, "姓名": student_name, "狀況": status, "得分": score_num,
                "回報人": f"{st.session_state.current_user['name']}"
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
# 模組二：僑生假單申請
# ==========================================
elif app_mode == "📝 僑生假單申請":
    st.header("📝 僑生外散宿申請單 (週報表整合模式)")
    user = st.session_state.current_user
    overseas_classes = ["資訊一孝", "資訊一仁", "觀一孝", "觀一仁", "餐一和", "餐一平", "資訊二孝"]
    target_class = st.selectbox("請選擇要操作的班級", overseas_classes) if user["role"] == "管理員" else user["class"]
    class_students = df_students[df_students["班級"] == target_class].copy()
    
    if class_students.empty:
        st.warning(f"查無 {target_class} 的學生資料。")
    else:
        class_students["顯示名稱"] = class_students["座號"] + "-" + class_students["姓名"]
        with st.expander("第一步：設定假別並加入本週清單", expanded=True):
            selected_display = st.multiselect("選擇本次設定的學生：", class_students["顯示名稱"].tolist())
            selected_data = class_students[class_students["顯示名稱"].isin(selected_display)]
            
            c1, c2 = st.columns(2)
            with c1:
                l_type = st.selectbox("申請項目", ["晚歸", "外宿", "返鄉", "職場實習", "打工", "其他"])
                start_dt = st.date_input("起始日期", value=tw_time)
            with c2:
                end_dt = st.date_input("結束日期", value=tw_time)
                l_time = st.time_input("預計返校時間", value=datetime.strptime("22:00", "%H:%M").time())
            
            stay_info, stay_loc, time_valid = "", "", True
            if l_type == "晚歸" and l_time > datetime.strptime("22:30", "%H:%M").time():
                st.error("❌ 晚歸時間不得超過 22:30！")
                time_valid = False
            elif l_type == "外宿":
                sc1, sc2, sc3, sc4 = st.columns(4)
                with sc1: stay_loc = st.text_input("外宿地點")
                with sc2: rel_name = st.text_input("親友姓名")
                with sc3: rel_type = st.text_input("關係")
                with sc4: rel_tel = st.text_input("親友聯絡電話")
                stay_info = f"親友:{rel_name}({rel_type}) / 電話:{rel_tel}"
                
            reason = st.text_input("事由補充說明")
            
            if st.button("➕ 加入本週整合清單", use_container_width=True) and time_valid:
                if selected_data.empty: st.warning("請至少選擇一位學生！")
                else:
                    for _, s in selected_data.iterrows():
                        st.session_state.leave_cart.append({
                            "班級": target_class, "座號": s.get('座號',''), "學號": s.get('學號',''), "姓名": s.get('姓名',''),
                            "學生手機": s.get('學生手機',''), "家長電話": s.get('家長聯絡電話',''), "類別": l_type, "起訖日期": f"{start_dt} ~ {end_dt}", 
                            "返校時間": "21:00點名" if l_type == "外宿" else l_time.strftime('%H:%M'),
                            "事由與細節": reason + (f" | {stay_loc}" if l_type == "外宿" else ""),
                            "親友資訊": stay_info if l_type == "外宿" else "-",
                            "raw_start": str(start_dt), "raw_end": str(end_dt), "raw_reason": f"返校:{l_time.strftime('%H:%M')} / {reason}", "raw_loc": stay_loc, "raw_info": stay_info
                        })
                    st.success("✅ 已加入清單！")

        if len(st.session_state.leave_cart) > 0:
            st.markdown("### 🛒 假單總表預覽")
            st.dataframe(pd.DataFrame(st.session_state.leave_cart)[["座號", "姓名", "類別", "起訖日期", "返校時間", "事由與細節"]], use_container_width=True)
            col_s, col_c = st.columns(2)
            with col_s:
                if st.button("🚀 確認寫入並產製假單 PDF", type="primary", use_container_width=True):
                    sheet_leave.append_rows([[today_date, r['班級'], r['座號'], r['學號'], r['姓名'], r['類別'], r['raw_start'], r['raw_end'], r['raw_reason'], r['raw_loc'], r['raw_info'], user['name']] for r in st.session_state.leave_cart])
                    rows_html = "".join([f"<tr><td>{r['座號']}</td><td>{r['姓名']}</td><td>{r['類別']}</td><td>{r['起訖日期']}</td><td>{r['返校時間']}</td><td>{r['事由與細節']}<br>{r['親友資訊']}</td><td>{r['學生手機']}</td><td>{r['家長電話']}</td></tr>" for r in st.session_state.leave_cart])
                    st.session_state.print_leave_html = f"""
                    <!DOCTYPE html><html><head><meta charset="utf-8"><style>
                        body {{ font-family: "Microsoft JhengHei", sans-serif; padding: 20px; }}
                        @media print {{ #btn {{ display: none !important; }} @page {{ size: A4 landscape; margin: 15mm; }} }}
                        #btn {{ margin-bottom: 20px; padding: 12px; background: #FF4B4B; color: white; border: none; width: 100%; font-size: 18px; font-weight: bold; cursor: pointer; }}
                        .title {{ text-align: center; font-size: 24px; font-weight: bold; margin-bottom: 20px; border-bottom: 2px solid black; padding-bottom: 10px; }}
                        table {{ width: 100%; border-collapse: collapse; font-size: 13px; }} th, td {{ border: 1px solid black; padding: 8px; text-align: center; }} th {{ background-color: #f2f2f2; }}
                        .sig {{ display: flex; justify-content: space-between; margin-top: 80px; }} .box {{ text-align: center; width: 18%; font-weight: bold; font-size: 16px; }}
                    </style></head><body>
                        <button id="btn" onclick="window.print()">🖨️ 點此列印 (請存為 PDF)</button>
                        <div class="title">樹人家商 {target_class} 僑生外散(宿)集體申請單</div>
                        <table><thead><tr><th>座號</th><th>姓名</th><th>類別</th><th>申請日期</th><th>返校/宿時間</th><th>地點/事由/親友資訊</th><th>學生手機</th><th>家長電話</th></tr></thead><tbody>{rows_html}</tbody></table>
                        <div class="sig"><div class="box">導師<br><br></div><div class="box">生輔組長<br><br></div><div class="box">學務主任<br><br></div><div class="box">國際交流組<br><br></div><div class="box">招生中心<br><br></div></div>
                    </body></html>
                    """
                    st.session_state.leave_cart = [] 
                    st.rerun()
            with col_c:
                if st.button("🗑️ 清空清單", use_container_width=True):
                    st.session_state.leave_cart = []
                    st.rerun()

        if "print_leave_html" in st.session_state:
            st.divider()
            components.html(st.session_state.print_leave_html, height=800, scrolling=True)

# ==========================================
# 模組三：獎懲建議單申請 (全新功能)
# ==========================================
elif app_mode == "🏆 獎懲建議單申請":
    st.header("🏆 獎懲建議單申請作業")
    user = st.session_state.current_user
    
    # 動態抓取獎懲類別與條文
    rules_dict = {}
    if not df_rules.empty:
        for col in df_rules.columns:
            # 過濾掉空白條文
            rules_dict[col] = [r for r in df_rules[col].dropna().tolist() if str(r).strip() != ""]
    
    st.markdown("### 第一步：選擇學生")
    input_mode = st.radio("作業模式", ["📌 本班學生 (下拉勾選)", "🔍 跨班新增 (輸入學號)"], horizontal=True)
    
    selected_students = pd.DataFrame()
    
    if input_mode == "📌 本班學生 (下拉勾選)":
        if user["class"] == "全校":
            st.warning("您目前為全校權限，請使用「跨班新增」模式輸入學號。")
        else:
            class_students = df_students[df_students["班級"] == user["class"]].copy()
            if not class_students.empty:
                class_students["顯示名稱"] = class_students["座號"] + "-" + class_students["姓名"]
                selected_display = st.multiselect("請勾選本班學生：", class_students["顯示名稱"].tolist())
                selected_students = class_students[class_students["顯示名稱"].isin(selected_display)]
            else:
                st.error(f"查無 {user['class']} 學生資料。")
    else:
        search_id = st.text_input("請輸入學生學號 (限6碼)：").strip()
        if len(search_id) == 6:
            if search_id in student_db:
                # 將查到的學生轉成 DataFrame 格式以利後續統一處理
                st.success(f"✅ 查獲學生：{student_db[search_id]['班級']} {student_db[search_id]['姓名']}")
                selected_students = pd.DataFrame([student_db[search_id]])
            else:
                st.error("⚠️ 查無此學號！")

    if not selected_students.empty:
        st.markdown("### 第二步：設定獎懲內容")
        with st.form("reward_form", clear_on_submit=False):
            rc1, rc2, rc3 = st.columns([2, 4, 1])
            with rc1:
                r_type = st.selectbox("獎懲類別", list(rules_dict.keys()) if rules_dict else ["嘉獎", "小功", "警告", "小過"])
            with rc2:
                r_reason = st.selectbox("引用條文/事由", rules_dict.get(r_type, ["無內建法規，請聯絡管理員更新"]))
            with rc3:
                r_count = st.selectbox("建議次數", ["乙次", "兩次", "三次"])
                
            if st.form_submit_button("➕ 加入獎懲建議清單", use_container_width=True):
                for _, s in selected_students.iterrows():
                    st.session_state.reward_cart.append({
                        "類別": "獎勵" if r_type in ["嘉獎", "小功", "大功"] else "懲處",
                        "學號": s['學號'], "班級": s['班級'], "座號姓名": f"{s['座號']}{s['姓名']}",
                        "獎懲項目": r_type, "事由": r_reason, "建議次數": r_count, "導師簽名": user["name"]
                    })
                st.success("✅ 已加入清單！可繼續新增其他學生。")

    if len(st.session_state.reward_cart) > 0:
        st.markdown("### 🛒 待送出之獎懲建議清單")
        df_cart = pd.DataFrame(st.session_state.reward_cart)
        st.dataframe(df_cart, use_container_width=True)
        
        col_s, col_c = st.columns(2)
        with col_s:
            if st.button("🚀 確認無誤，寫入並產製 PDF 建議單", type="primary", use_container_width=True):
                # 寫入資料庫
                upload_rows = [[today_date, r['類別'], r['學號'], r['班級'], r['座號姓名'], r['獎懲項目'], r['事由'], r['建議次數'], r['導師簽名']] for r in st.session_state.reward_cart]
                sheet_rewards_log.append_rows(upload_rows)
                
                # 產製 PDF HTML (依據獎勵或懲處分開顯示標題)
                main_type = "獎勵" if st.session_state.reward_cart[0]['類別'] == "獎勵" else "懲處"
                
                rows_html = ""
                for idx, r in enumerate(st.session_state.reward_cart):
                    rows_html += f"<tr><td>{idx+1}</td><td>{r['學號']}</td><td>{r['班級']}</td><td>{r['座號姓名']}</td><td>{r['獎懲項目']}</td><td style='text-align:left;'>{r['事由']}</td><td>{r['建議次數']}</td><td>{r['導師簽名']}</td></tr>"
                
                st.session_state.print_reward_html = f"""
                <!DOCTYPE html><html><head><meta charset="utf-8"><style>
                    body {{ font-family: "Microsoft JhengHei", sans-serif; padding: 20px; }}
                    @media print {{ #btn {{ display: none !important; }} @page {{ size: A4 portrait; margin: 15mm; }} }}
                    #btn {{ margin-bottom: 20px; padding: 12px; background: #FF4B4B; color: white; border: none; width: 100%; font-size: 18px; font-weight: bold; cursor: pointer; }}
                    .title {{ text-align: center; font-size: 24px; font-weight: bold; margin-bottom: 5px; }}
                    .subtitle {{ text-align: right; font-size: 14px; margin-bottom: 10px; }}
                    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }} 
                    th, td {{ border: 1px solid black; padding: 10px; text-align: center; }} 
                    th {{ background-color: #f2f2f2; }}
                    .sig {{ display: flex; justify-content: space-between; margin-top: 60px; }} 
                    .box {{ text-align: center; width: 22%; font-weight: bold; font-size: 16px; border-top: 1px dotted black; padding-top: 10px; }}
                </style></head><body>
                    <button id="btn" onclick="window.print()">🖨️ 點此列印 {main_type}建議單</button>
                    <div class="title">新北市私立樹人家商{main_type}建議單</div>
                    <div class="subtitle">造冊日期：{today_date}</div>
                    <table><thead><tr><th width="5%">項次</th><th width="12%">學號</th><th width="12%">班級</th><th width="12%">座號姓名</th><th width="10%">類別</th><th width="35%">獎懲事由</th><th width="7%">建議</th><th width="7%">導師</th></tr></thead><tbody>{rows_html}</tbody></table>
                    <div class="sig"><div class="box">簽辦人</div><div class="box">輔導教官</div><div class="box">主任教官</div><div class="box">學務主任</div></div>
                </body></html>
                """
                st.session_state.reward_cart = [] 
                st.rerun()
        with col_c:
            if st.button("🗑️ 清空清單", use_container_width=True):
                st.session_state.reward_cart = []
                st.rerun()

    if "print_reward_html" in st.session_state:
        st.divider()
        components.html(st.session_state.print_reward_html, height=800, scrolling=True)

# ==========================================
# 模組四：綜合數據中心
# ==========================================
elif app_mode == "📊 綜合數據中心 (管理員專屬)":
    st.header("📊 綜合數據中心")
    if "current_user" not in st.session_state or st.session_state.current_user is None: st.stop()
        
    tab1, tab2, tab3 = st.tabs(["🔥 巡查資料庫維護", "✈️ 僑生假單總表", "🏆 獎懲紀錄總表"])
    
    with tab1:
        st.subheader("巡查紀錄維護")
        df_patrol = safe_get_dataframe(sheet_records)
        if not df_patrol.empty:
            edited_df = st.data_editor(df_patrol, num_rows="dynamic", use_container_width=True, height=400)
            if st.button("💾 儲存巡查修改", type="primary"):
                sheet_records.clear()
                sheet_records.update(values=[edited_df.columns.tolist()] + edited_df.values.tolist(), range_name='A1')
                st.success("✅ 資料庫已更新！")
        else: st.info("無紀錄。")
            
    with tab2:
        st.subheader("僑生請假總表")
        df_leave = safe_get_dataframe(sheet_leave)
        if not df_leave.empty:
            edited_leave_df = st.data_editor(df_leave, num_rows="dynamic", use_container_width=True, height=400)
            if st.button("💾 儲存假單修改", type="primary"):
                sheet_leave.clear()
                sheet_leave.update(values=[edited_leave_df.columns.tolist()] + edited_leave_df.values.tolist(), range_name='A1')
                st.success("✅ 資料庫已更新！")
        else: st.info("無紀錄。")

    with tab3:
        st.subheader("全校獎懲建議紀錄表")
        df_rewards = safe_get_dataframe(sheet_rewards_log)
        if not df_rewards.empty:
            edited_rewards_df = st.data_editor(df_rewards, num_rows="dynamic", use_container_width=True, height=400)
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                if st.button("💾 儲存獎懲修改", type="primary"):
                    sheet_rewards_log.clear()
                    sheet_rewards_log.update(values=[edited_rewards_df.columns.tolist()] + edited_rewards_df.values.tolist(), range_name='A1')
                    st.success("✅ 獎懲資料庫已更新！")
            with col_r2:
                csv = edited_rewards_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 下載完整獎懲總表 (CSV)", data=csv, file_name=f"獎懲紀錄總表_{today_date}.csv", use_container_width=True)
        else: st.info("尚無獎懲紀錄。")
