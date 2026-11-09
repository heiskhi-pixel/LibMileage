import os
import json
import copy
import random
import hashlib
import sqlite3
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="도서관 장학사업 실시간 점수 조회 포털",
    page_icon="📚",
    layout="wide"
)

DB_FILE = "library_scholarship.db"
CONFIG_FILE = "library_score_config.json"
ALLOWED_DOMAIN = "@pukyong.ac.kr"
ADMIN_PASSWORD = "admin1234"  # 관리자 비밀번호 (실제 운영 시 변경하세요)

# ==================== 이메일(SMTP) 설정 ====================
# [중요] Streamlit Cloud 등 무료 웹 플랫폼 배포 시:
# 1. 아래 SMTP_ENABLED를 True로 변경합니다.
# 2. Gmail 등의 발신 계정과 앱 비밀번호를 입력하거나, 
#    Streamlit Cloud의 'Secrets' 기능에 안전하게 등록하여 사용하세요.
SMTP_ENABLED = False  # True로 변경하면 실제 @pukyong.ac.kr 메일로 인증번호가 발송됩니다.
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "your_library_email@gmail.com"
SMTP_PASSWORD = "your_google_app_password"

DEFAULT_CONFIG = {
    "items": {
        "book": {"score_per_unit": 1.0, "cap": 100.0},
        "ebook": {"score_per_unit": 0.5, "cap": 100.0},
        "culture": {"score_per_unit": 5.0, "cap": 100.0},
        "edu": {"face_score": 5.0, "online_score": 1.5, "cap": 100.0},
        "survey": {"score_per_unit": 3.0, "cap": 100.0},
        "facility": {"vr_score": 5.0, "studio_score": 5.0, "cap": 10.0},
        "club": {"최우수": 70.0, "우수": 60.0, "우량": 50.0, "장려": 40.0},
        "trailer": {"최우수": 25.0, "우수": 20.0, "우량": 15.0, "장려": 10.0},
        "essay": {
            "cap": 130.0,
            "base_tiers": [
                {"min": 20, "score": 100.0}, {"min": 17, "score": 90.0},
                {"min": 14, "score": 80.0}, {"min": 11, "score": 70.0},
                {"min": 8, "score": 60.0}, {"min": 5, "score": 40.0},
                {"min": 2, "score": 20.0}
            ],
            "bonus_tiers": [
                {"min": 20, "score": 30.0}, {"min": 17, "score": 25.0},
                {"min": 14, "score": 20.0}, {"min": 11, "score": 15.0},
                {"min": 8, "score": 10.0}, {"min": 5, "score": 5.0}
            ]
        },
        "sns": {"카드뉴스": 10.0, "숏폼영상": 20.0, "숏폼일반영상": 30.0, "cap": 100.0}
    },
    "awards": [
        {"tier": "1순위", "name": "최우수", "count": 1, "prize": 1000000},
        {"tier": "2순위", "name": "우수", "count": 2, "prize": 800000},
        {"tier": "3순위", "name": "우량", "count": 5, "prize": 500000},
        {"tier": "4순위", "name": "장려(4순위)", "count": 9, "prize": 400000},
        {"tier": "5순위", "name": "장려(5순위)", "count": 21, "prize": 300000}
    ]
}

# ==================== DB 초기화 및 보안 함수 ====================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS members (
            student_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def load_results_from_db():
    if not os.path.exists(DB_FILE):
        return pd.DataFrame()
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql("SELECT * FROM user_scores", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

def save_results_to_db(df):
    conn = sqlite3.connect(DB_FILE)
    df["이용자ID"] = df["이용자ID"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    df["성명"] = df["성명"].astype(str).str.strip()
    df["업데이트일시"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df.to_sql("user_scores", conn, if_exists="replace", index=False)
    conn.close()

def verify_student_identity_before_otp(student_id, name, email):
    """타인 학번 도용 원천 차단: 학번+성명이 장학사업 집계 DB에 존재할 때만 가입 허용"""
    sid = student_id.strip()
    sname = name.strip()
    semail = email.strip().lower()

    if not semail.endswith(ALLOWED_DOMAIN):
        return False, f"반드시 '{ALLOWED_DOMAIN}'로 끝나는 교내 웹메일만 사용할 수 있습니다."

    # 이미 가입된 학번/이메일 체크
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT student_id, email FROM members WHERE student_id = ? OR email = ?", (sid, semail))
    existing = cur.fetchone()
    conn.close()
    if existing:
        return False, "이미 회원가입이 완료된 학번이거나 사용 중인 웹메일 주소입니다."

    # 장학사업 점수 DB(user_scores) 교차 검증
    df_scores = load_results_from_db()
    if df_scores.empty:
        return False, "아직 관리자가 장학사업 대상자 명단을 업로드하지 않았습니다."

    matched = df_scores[
        (df_scores["이용자ID"].astype(str) == sid) &
        (df_scores["성명"].astype(str) == sname)
    ]
    if matched.empty:
        return False, "입력하신 [학번 + 성명] 정보가 도서관 장학사업 집계 명단과 일치하지 않습니다. 타인의 학번으로는 가입할 수 없습니다."

    return True, "본인 확인 완료"

def register_member(student_id, name, email, password):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO members (student_id, name, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (student_id.strip(), name.strip(), email.strip().lower(), hash_password(password), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        return True, "회원가입이 완료되었습니다! [학번 로그인] 탭에서 로그인해 주세요."
    except sqlite3.IntegrityError:
        return False, "이미 가입된 학번이거나 사용 중인 웹메일 주소입니다."
    finally:
        conn.close()

def verify_login(student_id, password):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "SELECT student_id, name, email FROM members WHERE student_id = ? AND password_hash = ?",
        (student_id.strip(), hash_password(password))
    )
    row = cur.fetchone()
    conn.close()
    return row

def send_verification_email(to_email, code):
    if not SMTP_ENABLED:
        return True, f"[테스트 모드] 메일 서버 미연동 상태입니다. 화면 인증번호 [{code}]를 입력해 주세요."
    try:
        msg = MIMEText(
            f"안녕하세요.\n도서관 장학사업 실시간 점수 조회 포털 웹메일 인증번호입니다.\n\n"
            f"인증번호 6자리: [ {code} ]\n\n웹페이지로 돌아가 인증번호를 입력해 주세요.",
            "plain", "utf-8"
        )
        msg["Subject"] = "[도서관] 장학사업 점수 조회 포털 웹메일 인증번호 안내"
        msg["From"] = SMTP_USER
        msg["To"] = to_email

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True, f"{to_email} 주소로 인증번호 6자리를 발송했습니다."
    except Exception as e:
        return False, f"이메일 발송 중 오류가 발생했습니다: {e}"

# 초기 DB 생성
init_db()

# 상단 공통 헤더 및 워터마크
col_h1, col_h2 = st.columns([4, 1])
with col_h1:
    st.title("📚 도서관 장학사업 실시간 점수 조회 포털")
with col_h2:
    st.markdown(
        "<div style='text-align: right; padding-top: 15px; font-weight: bold; color: #1E40AF;'>"
        "도서관 권혁일, 2026.11.04.</div>",
        unsafe_allow_html=True
    )

st.sidebar.title("포털 메뉴")
page_mode = st.sidebar.radio(
    "접속 화면 선택",
    ["🎓 이용자 포털 (로그인 / 회원가입)", "🔒 관리자 백엔드 (담당자 전용)"]
)

# ==================== 1. 이용자 포털 ====================
if page_mode == "🎓 이용자 포털 (로그인 / 회원가입)":
    if "logged_in_user" not in st.session_state:
        st.session_state.logged_in_user = None

    if st.session_state.logged_in_user:
        u_id, u_name, u_email = st.session_state.logged_in_user
        top_c1, top_c2 = st.columns([5, 1])
        with top_c1:
            st.subheader(f"👋 환영합니다, {u_name} ({u_id}) 님!  |  인증 웹메일: {u_email}")
        with top_c2:
            if st.button("로그아웃", use_container_width=True):
                st.session_state.logged_in_user = None
                st.rerun()

        st.markdown("---")
        df_all = load_results_from_db()
        if df_all.empty:
            st.warning("현재 관리자가 장학사업 점수 데이터를 준비 중입니다.")
        else:
            last_updated = df_all["업데이트일시"].iloc[0] if "업데이트일시" in df_all.columns else "-"
            st.caption(f"⏱️ 최근 데이터 업데이트 일시: {last_updated} (전체 집계 인원: {len(df_all)}명)")

            matched = df_all[df_all["이용자ID"].astype(str) == str(u_id)]
            if matched.empty:
                st.info(f"집계 명단에서 학번({u_id})의 데이터를 찾을 수 없습니다.")
            else:
                user_row = matched.iloc[0]
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("나의 최종 총점", f"{float(user_row['최종 총점']):.1f} 점")
                m2.metric("현재 실시간 순위", f"{int(user_row['순위'])} 위", f"전체 {len(df_all)}명 중")
                m3.metric("예상 수상 등급", str(user_row["수상등급"]))
                m4.metric("예상 장학금", f"{int(user_row['지급금액']):,} 원")

                st.markdown("#### 📊 나의 10개 항목별 상세 실적 및 환산 점수")
                detail_data = [
                    {"평가 항목": "1. 단행본대출", "내 실적": f"{int(user_row['단행본(권수)'])} 권", "환산 점수": user_row["단행본(점수)"], "최대 상한(Cap)": 100},
                    {"평가 항목": "2. 전자책대출", "내 실적": f"{int(user_row['전자책(권수)'])} 권", "환산 점수": user_row["전자책(점수)"], "최대 상한(Cap)": 100},
                    {"평가 항목": "3. 문화행사 참여", "내 실적": f"{int(user_row['문화행사(횟수)'])} 회", "환산 점수": user_row["문화행사(점수)"], "최대 상한(Cap)": 100},
                    {"평가 항목": "4. 이용교육 참여", "내 실적": f"대면 {int(user_row['이용교육_대면(횟수)'])} / 비대면 {int(user_row['이용교육_비대면(횟수)'])}", "환산 점수": user_row["이용교육(점수)"], "최대 상한(Cap)": 100},
                    {"평가 항목": "5. 만족도조사", "내 실적": f"{int(user_row['만족도조사(횟수)'])} 회", "환산 점수": user_row["만족도조사(점수)"], "최대 상한(Cap)": 100},
                    {"평가 항목": "6. 시설이용(VR/스튜디오)", "내 실적": f"{int(user_row['시설이용(횟수)'])} 회", "환산 점수": user_row["시설이용(점수)"], "최대 상한(Cap)": 10},
                    {"평가 항목": "7. 독서클럽", "내 실적": user_row["독서클럽(등급)"], "환산 점수": user_row["독서클럽(점수)"], "최대 상한(Cap)": 70},
                    {"평가 항목": "8. 북트레일러", "내 실적": user_row["북트레일러(등급)"], "환산 점수": user_row["북트레일러(점수)"], "최대 상한(Cap)": 25},
                    {"평가 항목": "9. 독서감상문", "내 실적": f"총 {int(user_row['독서감상문_전체(편수)'])}편 (권장 {int(user_row['독서감상문_권장(편수)'])}편)", "환산 점수": user_row["독서감상문(점수)"], "최대 상한(Cap)": 130},
                    {"평가 항목": "10. 도서관SNS서포터즈", "내 실적": user_row["SNS서포터즈(내역)"], "환산 점수": user_row["SNS서포터즈(점수)"], "최대 상한(Cap)": 100},
                ]
                st.table(pd.DataFrame(detail_data))

    else:
        auth_tab1, auth_tab2 = st.tabs(["🔑 학번 로그인", "🛡️ 본인 실명 및 웹메일 인증 회원가입"])

        with auth_tab1:
            st.subheader("학번 로그인")
            with st.form("login_form"):
                login_id = st.text_input("학번 (이용자ID)", placeholder="예: 20261001")
                login_pw = st.text_input("비밀번호", type="password")
                login_submit = st.form_submit_button("로그인하여 내 점수 확인하기", type="primary", use_container_width=True)

            if login_submit:
                user_info = verify_login(login_id, login_pw)
                if user_info:
                    st.session_state.logged_in_user = user_info
                    st.rerun()
                else:
                    st.error("학번 또는 비밀번호가 일치하지 않습니다.")

        with auth_tab2:
            st.subheader("교내 웹메일(@pukyong.ac.kr) 인증 회원가입")
            st.info(
                "🛡️ **보안 안내:** 입력하신 **[학번 + 성명]**이 도서관 장학사업 집계 명단과 일치해야만 "
                "교내 웹메일로 인증번호가 발송됩니다."
            )

            if "otp_code" not in st.session_state:
                st.session_state.otp_code = None
                st.session_state.verified_info = None
                st.session_state.email_verified = False

            c_r1, c_r2, c_r3 = st.columns(3)
            with c_r1:
                reg_id = st.text_input("1. 본인 학번", placeholder="예: 20261001")
            with c_r2:
                reg_name = st.text_input("2. 본인 성명", placeholder="예: 홍길동")
            with c_r3:
                reg_email = st.text_input("3. 교내 웹메일", placeholder="example@pukyong.ac.kr")

            if st.button("📨 실명 확인 및 웹메일 인증번호 발송", use_container_width=True):
                ok_id, msg_id = verify_student_identity_before_otp(reg_id, reg_name, reg_email)
                if not ok_id:
                    st.error(msg_id)
                else:
                    code = str(random.randint(100000, 999999))
                    st.session_state.otp_code = code
                    st.session_state.verified_info = (reg_id.strip(), reg_name.strip(), reg_email.strip().lower())
                    st.session_state.email_verified = False
                    ok_mail, msg_mail = send_verification_email(reg_email.strip().lower(), code)
                    if ok_mail:
                        st.success(msg_mail)
                    else:
                        st.error(msg_mail)

            if st.session_state.otp_code and not st.session_state.email_verified:
                c_v1, c_v2 = st.columns([3, 1])
                with c_v1:
                    input_otp = st.text_input("웹메일로 수신한 6자리 인증번호 입력", max_chars=6)
                with c_v2:
                    st.write("")
                    st.write("")
                    if st.button("✔️ 인증번호 확인", use_container_width=True):
                        if input_otp.strip() == st.session_state.otp_code:
                            st.session_state.email_verified = True
                            st.success("✅ 본인 인증 완료! 아래 비밀번호를 설정해 주세요.")
                        else:
                            st.error("인증번호가 일치하지 않습니다.")

            if st.session_state.email_verified and st.session_state.verified_info:
                v_id, v_name, v_email = st.session_state.verified_info
                st.markdown("---")
                st.write(f"🔒 **인증 완료 계정:** 학번 `{v_id}` | 성명 `{v_name}` | 웹메일 `{v_email}`")
                with st.form("final_reg_form"):
                    reg_pw = st.text_input("사용할 비밀번호 입력", type="password")
                    reg_pw_chk = st.text_input("비밀번호 재입력", type="password")
                    reg_submit = st.form_submit_button("🎉 회원가입 완료", type="primary", use_container_width=True)

                if reg_submit:
                    if not reg_pw or reg_pw != reg_pw_chk:
                        st.error("비밀번호가 비어있거나 서로 일치하지 않습니다.")
                    else:
                        ok, msg = register_member(v_id, v_name, v_email, reg_pw)
                        if ok:
                            st.success(msg)
                            st.session_state.otp_code = None
                            st.session_state.email_verified = False
                        else:
                            st.error(msg)

# ==================== 2. 관리자 백엔드 ====================
elif page_mode == "🔒 관리자 백엔드 (담당자 전용)":
    st.subheader("🔒 도서관 장학사업 관리자 백엔드")

    if "admin_logged_in" not in st.session_state:
        st.session_state.admin_logged_in = False

    if not st.session_state.admin_logged_in:
        pwd = st.text_input("관리자 비밀번호를 입력하세요", type="password")
        if st.button("관리자 로그인", type="primary"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")
        st.stop()

    st.warning("해당 프로그램은 '2026년 장학사업 계획'에 의거하여 만들어진 프로그램으로 최종 결과물에 대한 검수와 책임은 사용자(담당자)에게 있음을 확인합니다.")

    t1, t2, t3 = st.tabs([
        "⚡ 1. 로컬 실행파일(.exe) 결과 엑셀 간편 연동",
        "👥 2. 가입 학생 계정 관리",
        "📊 3. 현재 DB 전체 순위표 확인"
    ])

    with t1:
        st.markdown("#### ⚡ 로컬 PC `도서관점수산정기.exe` 결과 파일 연동")
        st.info(
            "💡 **연동 방법:** 로컬 PC 프로그램에서 산출된 **`도서관_이용자_최종점수_및_순위집계표.xlsx`** "
            "파일을 업로드하면 웹 조회 DB에 즉시 반영됩니다."
        )
        exe_excel = st.file_uploader("최종 결과 엑셀 파일(.xlsx) 업로드", type=["xlsx"])
        if exe_excel and st.button("🚀 웹 조회 DB에 즉시 반영하기", type="primary", use_container_width=True):
            try:
                df_exe = pd.read_excel(exe_excel)
                required_cols = ["이용자ID", "성명", "소속", "최종 총점", "순위", "수상등급", "지급금액"]
                missing = [c for c in required_cols if c not in df_exe.columns]
                if missing:
                    st.error(f"올바른 집계표 파일이 아닙니다. 누락된 열: {missing}")
                else:
                    save_results_to_db(df_exe)
                    st.success(f"✅ 연동 완료! 총 {len(df_exe)}명의 데이터가 웹 포털에 반영되었습니다.")
            except Exception as e:
                st.error(f"오류 발생: {e}")

    with t2:
        conn = sqlite3.connect(DB_FILE)
        df_members = pd.read_sql("SELECT student_id AS 학번, name AS 성명, email AS 인증웹메일, created_at AS 가입일시 FROM members", conn)
        conn.close()
        st.markdown(f"#### 가입 완료 학생 명단 (총 {len(df_members)}명)")
        st.dataframe(df_members, use_container_width=True)

        del_id = st.text_input("초기화할 학생의 학번 입력")
        if st.button("🗑️ 해당 학번 계정 초기화(삭제)"):
            conn = sqlite3.connect(DB_FILE)
            conn.execute("DELETE FROM members WHERE student_id = ?", (del_id.strip(),))
            conn.commit()
            conn.close()
            st.success(f"학번 {del_id} 계정이 초기화되었습니다.")
            st.rerun()

    with t3:
        df_saved = load_results_from_db()
        if df_saved.empty:
            st.info("반영된 점수 데이터가 없습니다.")
        else:
            st.dataframe(df_saved, use_container_width=True)