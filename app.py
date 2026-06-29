
import streamlit as st
import pandas as pd
from datetime import date, timedelta
import calendar
from pathlib import Path
import base64
import re
from supabase import create_client

st.set_page_config(
    page_title="兒童早療記錄小幫手",
    page_icon="🧸",
    layout="wide"
)

CLINIC_NAME = "右昌聯合醫院 兒童復健中心"
THERAPY_TYPES = ["物理", "職能", "語言", "心理"]
WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
ASSET_DIR = Path("assets")
BACKGROUND_FILE = ASSET_DIR / "kids_rehab_background.svg"

# ========= 介面樣式 =========
def image_to_base64(path):
    if not path.exists():
        return ""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

bg_base64 = image_to_base64(BACKGROUND_FILE)

st.markdown(f"""
<style>
.stApp {{
    background-image:
        linear-gradient(rgba(255, 250, 241, 0.72), rgba(234, 247, 255, 0.78)),
        url("data:image/svg+xml;base64,{bg_base64}");
    background-size: cover;
    background-repeat: no-repeat;
    background-attachment: fixed;
    background-position: center top;
}}
.block-container {{
    -color: rgba(255,255,255,0.76);
    border-radius: 28px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}}
.main-title {{
    background: linear-gradient(90deg, rgba(255,230,167,0.95), rgba(255,214,165,0.93), rgba(202,255,191,0.90));
    padding: 28px;
    border-radius: 24px;
    border: 2px solid #f7c873;
    margin-bottom: 20px;
    box-shadow: 0 6px 18px rgba(120,80,30,0.12);
}}
.main-title h1 {{
    color: #6b3e26;
    margin-bottom: 4px;
}}
.main-title p {{
    color: #9a5b2f;
    font-size: 20px;
}}
.section-card {{
    background-color: rgba(255,255,255,0.88);
    padding: 22px;
    border-radius: 22px;
    border: 1px solid #f3d19c;
    box-shadow: 0 4px 14px rgba(150, 100, 40, 0.08);
    margin-bottom: 18px;
}}
div[data-testid="stMetric"] {{
    background: rgba(255,255,255,0.84);
    border: 1px solid #f3d19c;
    padding: 15px;
    border-radius: 18px;
}}
</style>
""", unsafe_allow_html=True)

# ========= Supabase =========
@st.cache_resource
def get_supabase_client():
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")
    if not url or not key:
        return None
    return create_client(url, key)

supabase = get_supabase_client()

def require_supabase():
    if supabase is None:
        st.error("尚未設定 Supabase。請先在 .streamlit/secrets.toml 填入 SUPABASE_URL 與 SUPABASE_KEY。")
        st.stop()

def restore_session():
    if "access_token" in st.session_state and "refresh_token" in st.session_state:
        try:
            supabase.auth.set_session(
                st.session_state["access_token"],
                st.session_state["refresh_token"]
            )
        except Exception:
            pass

def get_current_user():
    if "user" in st.session_state:
        return st.session_state["user"]
    return None

def ensure_profile(user, parent_name=""):
    try:
        exists = supabase.table("profiles").select("*").eq("id", user.id).execute().data
        if not exists:
            supabase.table("profiles").insert({
                "id": user.id,
                "parent_name": parent_name,
                "email": user.email
            }).execute()
    except Exception:
        pass

def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    for key in ["user", "access_token", "refresh_token"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

# ========= 工具函式 =========
def calculate_age(birth_date, reference_date):
    age = reference_date.year - birth_date.year
    if (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age

def end_of_next_month(input_date):
    if input_date.month == 12:
        next_month_year = input_date.year + 1
        next_month = 1
    else:
        next_month_year = input_date.year
        next_month = input_date.month + 1
    last_day = calendar.monthrange(next_month_year, next_month)[1]
    return date(next_month_year, next_month, last_day)

def calculate_expiry_date(age, first_treatment_date):
    if age < 9:
        return end_of_next_month(first_treatment_date), "9歲以下：首次執行日至次月底"
    return first_treatment_date + timedelta(days=29), "9歲以上：首次執行日起30日，含首次執行日"

def get_weekday_name(input_date):
    return WEEKDAYS[input_date.weekday()]

def display_table(df, hide_id=True):
    show_df = df.copy()
    if hide_id:
        show_df = show_df.drop(columns=[c for c in ["id", "user_id", "child_id", "created_at"] if c in show_df.columns], errors="ignore")
    show_df.index = range(1, len(show_df) + 1)
    st.dataframe(show_df, use_container_width=True)

def display_child_table(df):
    show_df = df.copy()
    show_df = show_df.drop(columns=[c for c in ["id", "user_id", "created_at"] if c in show_df.columns], errors="ignore")
    show_df.index = range(1, len(show_df) + 1)

    def color_expiry(val):
        return "color: red; font-weight: bold;"

    def color_status(val):
        if val == "已到期":
            return "color: red; font-weight: bold;"
        if val == "即將到期":
            return "color: #f77f00; font-weight: bold;"
        if val == "有效":
            return "color: green; font-weight: bold;"
        return "color: #555; font-weight: bold;"

    styled = show_df.style.map(
        color_expiry,
        subset=["療程到期日"] if "療程到期日" in show_df.columns else []
    )
    styled = styled.map(color_status, subset=["狀態"] if "狀態" in show_df.columns else [])
    st.dataframe(styled, use_container_width=True)

def get_status(expiry_date, used_sessions):
    today = date.today()
    expiry = pd.to_datetime(expiry_date).date()
    remaining = max(0, 6 - int(used_sessions))
    if today > expiry:
        return "已到期"
    if remaining <= 0:
        return "已用完"
    if (expiry - today).days <= 7:
        return "即將到期"
    return "有效"

def make_editable_with_delete_checkbox(df):
    edit_df = df.copy().reset_index(drop=True)
    edit_df.insert(0, "刪除", False)
    edit_df.index = range(1, len(edit_df) + 1)
    return edit_df

def split_deleted_rows(edited_df):
    edited_df = edited_df.copy()
    deleted = edited_df[edited_df["刪除"] == True].copy()
    kept = edited_df[edited_df["刪除"] == False].drop(columns=["刪除"]).reset_index(drop=True)
    return kept, deleted

# ========= 資料庫讀寫 =========
def fetch_records(user_id):
    data = supabase.table("treatment_records").select("*").eq("user_id", user_id).order("created_at", desc=True).execute().data
    df = pd.DataFrame(data)
    if len(df) == 0:
        return pd.DataFrame()

    children = fetch_children(user_id)
    if len(children) > 0:
        name_map = dict(zip(children["id"], children["兒童姓名"]))
        df["child_name"] = df["child_id"].map(name_map)

    return df.rename(columns={
        "child_name": "兒童姓名",
        "treatment_code": "療程編號",
        "treatment_date": "治療日期",
        "weekday": "星期",
        "session_number": "療程次數",
        "default_therapy_types": "預設治療類型",
        "actual_therapy_types": "實際治療類型",
    })
    return df.rename(columns=rename)

def fetch_schedule(user_id):
    data = supabase.table("weekly_schedule").select("*").eq("user_id", user_id).order("created_at").execute().data
    df = pd.DataFrame(data)
    if len(df) == 0:
        return pd.DataFrame()
    return df.rename(columns={
        "weekday": "星期",
        "default_therapy_types": "預設治療類型"
    })

def fetch_records(user_id):
    data = supabase.table("treatment_records").select("*").eq("user_id", user_id).order("created_at").execute().data
    df = pd.DataFrame(data)
    if len(df) == 0:
        return pd.DataFrame()    
    children = fetch_children(user_id)
    if len(children) > 0:
        name_map = dict(zip(children["id"], children["兒童姓名"]))
        df["child_name"] = df["child_id"].map(name_map)
        return pd.DataFrame()
    return df.rename(columns={
    "child_name": "兒童姓名",
    "treatment_code": "療程編號",
    "treatment_date": "治療日期",
    "weekday": "星期",
    "session_number": "療程次數",
    "default_therapy_types": "預設治療類型",
    "actual_therapy_types": "實際治療類型",
})

def count_child_records(records_df, child_id):
    if len(records_df) == 0:
        return 0
    return len(records_df[records_df["child_id"] == child_id])

def refresh_child_usage(user_id):
    children = fetch_children(user_id)
    records = fetch_records(user_id)

    if len(children) == 0:
        return

    for _, row in children.iterrows():
        child_id = row["id"]
        used = count_child_records(records, child_id)
        remaining = max(0, 6 - used)
        status = get_status(row["療程到期日"], used)

        supabase.table("children").update({
            "used_sessions": used,
            "remaining_sessions": remaining,
            "status": status,
            "clinic_name": CLINIC_NAME
        }).eq("id", child_id).execute()

def get_next_treatment_code(records_df):
    if len(records_df) == 0 or "療程編號" not in records_df.columns:
        return "TR000001"
    max_num = 0
    for value in records_df["療程編號"].dropna().astype(str):
        match = re.search(r"TR(\d+)", value)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f"TR{max_num + 1:06d}"

def get_default_therapy(schedule_df, child_id, weekday):
    if len(schedule_df) == 0:
        return "未設定"
    matched = schedule_df[(schedule_df["child_id"] == child_id) & (schedule_df["星期"] == weekday)]
    if len(matched) == 0:
        return "未設定"
    val = matched.iloc[0]["預設治療類型"]
    return val if val else "未設定"

# ========= 登入畫面 =========
def show_auth_page():
    st.markdown("""
    <div class="main-title">
    <h1>🧸 兒童早療記錄小幫手</h1>
    <p>請登入後開始記錄孩子的療程</p>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_signup, tab_reset = st.tabs(["登入", "建立帳號", "忘記密碼"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("密碼", type="password")
            submitted = st.form_submit_button("登入")

            if submitted:
                if not email or not password:
                    st.error("請輸入 Email 與密碼")
                else:
                    try:
                        res = supabase.auth.sign_in_with_password({
                            "email": email,
                            "password": password
                        })
                        st.session_state["user"] = res.user
                        st.session_state["access_token"] = res.session.access_token
                        st.session_state["refresh_token"] = res.session.refresh_token
                        ensure_profile(res.user)
                        st.success("登入成功")
                        st.rerun()
                    except Exception as e:
                        st.error(f"登入失敗：{e}")

    with tab_signup:
        with st.form("signup_form"):
            parent_name = st.text_input("家長姓名")
            email = st.text_input("註冊 Email")
            password = st.text_input("註冊密碼", type="password")
            password2 = st.text_input("確認密碼", type="password")
            submitted = st.form_submit_button("建立帳號")

            if submitted:
                if not parent_name or not email or not password:
                    st.error("請完整填寫資料")
                elif password != password2:
                    st.error("兩次密碼不一致")
                elif len(password) < 6:
                    st.error("密碼至少需要 6 個字元")
                else:
                    try:
                        res = supabase.auth.sign_up({
                            "email": email,
                            "password": password
                        })
                        st.success("帳號已建立。若你有開啟 Email 驗證，請先到信箱完成驗證。")
                    except Exception as e:
                        st.error(f"註冊失敗：{e}")

    with tab_reset:
        with st.form("reset_form"):
            email = st.text_input("請輸入 Email")
            submitted = st.form_submit_button("寄送重設密碼信")

            if submitted:
                try:
                    supabase.auth.reset_password_email(email)
                    st.success("已寄出重設密碼信，請檢查信箱。")
                except Exception as e:
                    st.error(f"寄送失敗：{e}")

# ========= 主程式 =========
require_supabase()
restore_session()
user = get_current_user()

if user is None:
    show_auth_page()
    st.stop()

user_id = user.id
refresh_child_usage(user_id)

children_df = fetch_children(user_id)
schedule_df = fetch_schedule(user_id)
records_df = fetch_records(user_id)

st.sidebar.success(f"已登入：{user.email}")
if st.sidebar.button("登出"):
    logout()

st.markdown("""
<div class="main-title">
<h1>🧸 兒童早療記錄小幫手</h1>
<p>用溫暖的方式，陪伴孩子的每一次療程記錄</p>
</div>
""", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)
col1.metric("兒童資料筆數", len(children_df))
col2.metric("最多使用次數", "6 次")
col3.metric("已到期人數", int((children_df["狀態"] == "已到期").sum()) if len(children_df) else 0)
col4.metric("即將到期人數", int((children_df["狀態"] == "即將到期").sum()) if len(children_df) else 0)

st.divider()

st.header("一、新增兒童基本資料")
st.markdown('<div class="section-card">', unsafe_allow_html=True)

with st.form("child_form"):
    child_name = st.text_input("兒童姓名")
    st.text_input("院所名稱", value=CLINIC_NAME, disabled=True)
    birth_date = st.date_input("出生日期", value=date(2018, 1, 1))
    first_register_date = st.date_input("首次掛號日", value=date.today())
    first_treatment_date = st.date_input("首次執行日", value=date.today())

    age_preview = calculate_age(birth_date, first_treatment_date)
    expiry_preview, age_group_preview = calculate_expiry_date(age_preview, first_treatment_date)

    st.info(
        f"目前系統試算：年齡 {age_preview} 歲｜{age_group_preview}｜"
        f"療程期限：{first_treatment_date} 至 {expiry_preview}｜最多使用 6 次"
    )

    submitted = st.form_submit_button("儲存基本資料")

    if submitted:
        if not child_name:
            st.error("請輸入兒童姓名")
        else:
            supabase.table("children").insert({
                "user_id": user_id,
                "child_name": child_name,
                "clinic_name": CLINIC_NAME,
                "birth_date": str(birth_date),
                "age": age_preview,
                "age_group": age_group_preview,
                "first_register_date": str(first_register_date),
                "first_treatment_date": str(first_treatment_date),
                "treatment_start_date": str(first_treatment_date),
                "treatment_expiry_date": str(expiry_preview),
                "max_sessions": 6,
                "used_sessions": 0,
                "remaining_sessions": 6,
                "status": "有效"
            }).execute()
            st.success("已儲存兒童基本資料")
            st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

st.divider()

st.header("二、每週預設療程設定")

if len(children_df) == 0:
    st.info("請先新增兒童基本資料。")
else:
    child_options = dict(zip(children_df["兒童姓名"], children_df["id"]))
    schedule_child_name = st.selectbox("選擇兒童", list(child_options.keys()), key="schedule_child")
    schedule_child_id = child_options[schedule_child_name]

    with st.form("weekly_schedule_form"):
        selected_weekday = st.selectbox("星期", WEEKDAYS)
        default_therapy_list = st.multiselect("預設治療類型，可複選", THERAPY_TYPES)
        schedule_submitted = st.form_submit_button("儲存每週預設療程")

        if schedule_submitted:
            if len(default_therapy_list) == 0:
                st.error("請至少選擇一種預設治療類型。")
            else:
                default_therapy = "、".join(default_therapy_list)
                existing = supabase.table("weekly_schedule").select("*").eq("user_id", user_id).eq("child_id", schedule_child_id).eq("weekday", selected_weekday).execute().data

                if existing:
                    supabase.table("weekly_schedule").update({
                        "default_therapy_types": default_therapy
                    }).eq("id", existing[0]["id"]).execute()
                else:
                    supabase.table("weekly_schedule").insert({
                        "user_id": user_id,
                        "child_id": schedule_child_id,
                        "weekday": selected_weekday,
                        "default_therapy_types": default_therapy
                    }).execute()

                st.success("已儲存每週預設療程")
                st.rerun()

    child_schedule = schedule_df[schedule_df["child_id"] == schedule_child_id] if len(schedule_df) else pd.DataFrame()
    st.subheader("目前每週預設療程")
    if len(child_schedule) == 0:
        st.info("此兒童尚未設定每週預設療程。")
    else:
        display_table(child_schedule)

st.divider()

st.header("三、新增實際治療紀錄")

if len(children_df) == 0:
    st.info("請先新增兒童基本資料。")
else:
    child_options = dict(zip(children_df["兒童姓名"], children_df["id"]))
    record_child_name = st.selectbox("選擇兒童", list(child_options.keys()), key="record_child")
    record_child_id = child_options[record_child_name]

    treatment_date = st.date_input("治療日期", value=date.today())
    weekday = get_weekday_name(treatment_date)
    default_therapy = get_default_therapy(schedule_df, record_child_id, weekday)

    child_row = children_df[children_df["id"] == record_child_id].iloc[0]
    expiry_date = pd.to_datetime(child_row["療程到期日"]).date()
    used = count_child_records(records_df, record_child_id)
    next_number = used + 1
    next_code = get_next_treatment_code(records_df)

    if treatment_date > expiry_date:
        st.error(f"⚠️ 此治療日期已超過療程到期日 {expiry_date}，不可新增治療紀錄。")
    elif used >= 6:
        st.error("⚠️ 此兒童已使用 6 次，無法再新增治療紀錄。")
    else:
        st.info(
            f"治療日期為 {weekday}｜系統預設治療類型：{default_therapy}｜"
            f"本次將記錄為第 {next_number} 次療程｜療程編號：{next_code}"
        )

        default_list = []
        if default_therapy != "未設定":
            default_list = [x for x in default_therapy.split("、") if x in THERAPY_TYPES]

        with st.form("record_form"):
            actual_therapy_list = st.multiselect(
                "實際治療類型，可依臨時狀況修改，可複選",
                THERAPY_TYPES,
                default=default_list
            )
            record_submitted = st.form_submit_button("儲存實際治療紀錄")

            if record_submitted:
                if len(actual_therapy_list) == 0:
                    st.error("請至少選擇一種實際治療類型。")
                else:
                    res = supabase.table("treatment_records").insert({
                    "user_id": user_id,
                    "child_id": record_child_id,
                    "treatment_code": next_code,
                    "treatment_date": str(treatment_date),
                    "weekday": weekday,
                    "session_number": f"第 {next_number} 次",
                    "default_therapy_types": default_therapy,
                    "actual_therapy_types": "、".join(actual_therapy_list)
                }).execute()
                
                refresh_child_usage(user_id)
                
                st.success("已儲存實際治療紀錄，請往下查看目前實際治療紀錄")
                st.rerun()

st.divider()

st.header("四、目前兒童清單")
if len(children_df) == 0:
    st.info("目前尚無資料。")
else:
    display_child_table(children_df)

st.header("五、目前實際治療紀錄")
if len(records_df) == 0:
    st.info("目前尚無治療紀錄。")
else:
    display_table(records_df)

st.divider()

st.header("六、編修與刪除資料")

edit_tab1, edit_tab2, edit_tab3 = st.tabs(["編修兒童資料", "編修每週預設療程", "編修治療紀錄"])

with edit_tab1:
    if len(children_df) == 0:
        st.info("目前尚無兒童資料。")
    else:
        edit_df = make_editable_with_delete_checkbox(children_df)
        edited = st.data_editor(
            edit_df,
            use_container_width=True,
            num_rows="dynamic",
            key="edit_children",
            column_config={
                "id": None,
                "user_id": None,
                "created_at": None
            }
        )
        st.warning(f"目前勾選刪除：{int(edited['刪除'].sum())} 筆")

        if st.button("儲存兒童資料修改／刪除"):
            kept, deleted = split_deleted_rows(edited)

            for _, row in deleted.iterrows():
                supabase.table("children").delete().eq("id", row["id"]).execute()

            for _, row in kept.iterrows():
                birth = pd.to_datetime(row["出生日期"]).date()
                first_treat = pd.to_datetime(row["首次執行日"]).date()
                first_register = pd.to_datetime(row["首次掛號日"]).date()
                age = calculate_age(birth, first_treat)
                expiry, age_group = calculate_expiry_date(age, first_treat)
                used_sessions = count_child_records(records_df, row["id"])
                remaining = max(0, 6 - used_sessions)
                status = get_status(expiry, used_sessions)

                supabase.table("children").update({
                    "child_name": row["兒童姓名"],
                    "clinic_name": CLINIC_NAME,
                    "birth_date": str(birth),
                    "age": age,
                    "age_group": age_group,
                    "first_register_date": str(first_register),
                    "first_treatment_date": str(first_treat),
                    "treatment_start_date": str(first_treat),
                    "treatment_expiry_date": str(expiry),
                    "max_sessions": 6,
                    "used_sessions": used_sessions,
                    "remaining_sessions": remaining,
                    "status": status
                }).eq("id", row["id"]).execute()

            st.success("已儲存兒童資料修改／刪除")
            st.rerun()

with edit_tab2:
    if len(schedule_df) == 0:
        st.info("目前尚無每週預設療程。")
    else:
        edit_df = make_editable_with_delete_checkbox(schedule_df)
        edited = st.data_editor(
            edit_df,
            use_container_width=True,
            num_rows="dynamic",
            key="edit_schedule",
            column_config={
                "id": None,
                "user_id": None,
                "child_id": None,
                "created_at": None
            }
        )
        st.warning(f"目前勾選刪除：{int(edited['刪除'].sum())} 筆")

        if st.button("儲存每週預設療程修改／刪除"):
            kept, deleted = split_deleted_rows(edited)

            for _, row in deleted.iterrows():
                supabase.table("weekly_schedule").delete().eq("id", row["id"]).execute()

            for _, row in kept.iterrows():
                supabase.table("weekly_schedule").update({
                    "weekday": row["星期"],
                    "default_therapy_types": row["預設治療類型"]
                }).eq("id", row["id"]).execute()

            st.success("已儲存每週預設療程修改／刪除")
            st.rerun()

with edit_tab3:
    if len(records_df) == 0:
        st.info("目前尚無治療紀錄。")
    else:
        edit_df = make_editable_with_delete_checkbox(records_df)
        edited = st.data_editor(
            edit_df,
            use_container_width=True,
            num_rows="dynamic",
            key="edit_records",
            column_config={
                "id": None,
                "user_id": None,
                "child_id": None,
                "created_at": None
            }
        )
        st.warning(f"目前勾選刪除：{int(edited['刪除'].sum())} 筆")

        if st.button("儲存治療紀錄修改／刪除"):
            kept, deleted = split_deleted_rows(edited)

            for _, row in deleted.iterrows():
                supabase.table("treatment_records").delete().eq("id", row["id"]).execute()

            for _, row in kept.iterrows():
                supabase.table("treatment_records").update({
                    "treatment_code": row["療程編號"],
                    "treatment_date": str(pd.to_datetime(row["治療日期"]).date()),
                    "weekday": row["星期"],
                    "session_number": row["療程次數"],
                    "default_therapy_types": row["預設治療類型"],
                    "actual_therapy_types": row["實際治療類型"]
                }).eq("id", row["id"]).execute()

            refresh_child_usage(user_id)
            st.success("已儲存治療紀錄修改／刪除")
            st.rerun()

st.divider()

if len(records_df) > 0:
    export_df = records_df.drop(columns=[c for c in ["id", "user_id", "child_id", "created_at"] if c in records_df.columns], errors="ignore")
    csv = export_df.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label="下載治療紀錄 CSV",
        data=csv,
        file_name="兒童早療治療紀錄.csv",
        mime="text/csv"
    )
