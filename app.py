import os
import ssl
import json
import copy
import random
import secrets
import hashlib
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="국립부경대학교 도서관 장학사업 실시간 점수 조회 포털",
    page_icon="🐋",
    layout="wide",
    initial_sidebar_state="expanded"
)

def get_secret(key, default):
    """Streamlit Cloud Secrets가 설정되어 있으면 우선 읽고, 없으면 코드 기본값 사용"""
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return default

DB_FILE = "library_scholarship.db"
APP_BASE_URL = get_secret("APP_BASE_URL", "https://libmileage-hlipayy4kja247wjvnthrg.streamlit.app/")
ALLOWED_DOMAIN = "@pukyong.ac.kr"  # 화면 노출용 대표 도메인
ALLOWED_DOMAINS = ("@pukyong.ac.kr", "@pknu.ac.kr")  # 실제 내부 허용 도메인 (화면 비노출)
ADMIN_PASSWORD = get_secret("ADMIN_PASSWORD", "admin1234")  # 관리자 비밀번호

# ==================== 이메일(SMTP) 발송 설정 ====================
# Streamlit Cloud의 Secrets에 등록하면 GitHub에 비밀번호를 노출하지 않고 안전하게 발송할 수 있습니다.
# Secrets를 사용하지 않을 경우에만 아래 두 줄의 따옴표 안을 실제 발신 계정과 16자리 앱 비밀번호로 수정하세요.
SMTP_ENABLED = get_secret("SMTP_ENABLED", True)
SMTP_SERVER = get_secret("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(get_secret("SMTP_PORT", 465))
SMTP_USER = get_secret("SMTP_USER", "여기에_발신용_구글이메일_입력@gmail.com")
SMTP_PASSWORD = get_secret("SMTP_PASSWORD", "여기에_구글_16자리_앱비밀번호_입력")

# ==================== 국립부경대학교 전용 커스텀 CSS 테마 ====================
st.markdown("""
<style>
    .stApp {
        background-color: #F4F7FB;
        font-family: 'Pretendard', '맑은 고딕', sans-serif;
    }

    section[data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 2px solid #E2E8F0;
    }
    .sidebar-menu-box {
        background: linear-gradient(135deg, #003876 0%, #005BAC 100%);
        color: #FFFFFF;
        padding: 16px 18px;
        border-radius: 14px;
        margin-bottom: 14px;
        box-shadow: 0 6px 16px rgba(0, 56, 118, 0.15);
    }
    .sidebar-menu-title {
        font-size: 17px;
        font-weight: 800;
        margin: 0;
        color: #FFFFFF;
        letter-spacing: -0.3px;
    }
    .sidebar-menu-desc {
        font-size: 12px;
        color: #DCEBFA;
        margin-top: 4px;
    }

    section[data-testid="stSidebar"] div[role="radiogroup"] {
        gap: 10px !important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label {
        background-color: #F1F5F9 !important;
        border: 2px solid #CBD5E1 !important;
        border-radius: 12px !important;
        padding: 14px 16px !important;
        width: 100% !important;
        transition: all 0.2s ease !important;
        cursor: pointer !important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        border-color: #005BAC !important;
        background-color: #EBF3FC !important;
        transform: translateY(-1px);
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label[data-checked="true"],
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
        background: linear-gradient(90deg, #003876 0%, #005BAC 100%) !important;
        border-color: #003876 !important;
        box-shadow: 0 4px 12px rgba(0, 56, 118, 0.22) !important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label p {
        font-size: 15.5px !important;
        font-weight: 800 !important;
        color: #1E293B !important;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p {
        color: #FFFFFF !important;
    }

    .pknu-hero {
        background: linear-gradient(135deg, #003876 0%, #005BAC 60%, #0080C6 100%);
        padding: 26px 32px;
        border-radius: 18px;
        color: white;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 10px 25px rgba(0, 56, 118, 0.16);
        margin-bottom: 24px;
    }
    .pknu-hero-title {
        font-size: 26px;
        font-weight: 800;
        letter-spacing: -0.5px;
        margin: 0;
        color: #FFFFFF;
    }
    .pknu-hero-sub {
        font-size: 14px;
        color: #DCEBFA;
        margin-top: 6px;
    }

    .kpi-card {
        background: #FFFFFF;
        border-radius: 16px;
        padding: 22px 20px;
        box-shadow: 0 4px 15px rgba(0, 56, 118, 0.06);
        border-top: 5px solid #003876;
        transition: transform 0.15s ease;
        height: 100%;
    }
    .kpi-card.ocean { border-top-color: #0080C6; }
    .kpi-card.gold { border-top-color: #D97706; }
    .kpi-card.teal { border-top-color: #0D9488; }

    .kpi-label {
        font-size: 13px;
        font-weight: 700;
        color: #64748B;
        margin-bottom: 8px;
    }
    .kpi-value {
        font-size: 30px;
        font-weight: 800;
        color: #003876;
        line-height: 1.1;
    }
    .kpi-sub {
        font-size: 12px;
        font-weight: 600;
        color: #0080C6;
        margin-top: 8px;
    }

    .section-header {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 18px;
        font-weight: 800;
        color: #003876;
        margin: 22px 0 12px 0;
    }

    .item-card {
        background: #FFFFFF;
        border-radius: 14px;
        padding: 16px 18px;
        margin-bottom: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.03);
    }
    .item-card-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }
    .item-title {
        font-size: 15px;
        font-weight: 800;
        color: #1E293B;
    }
    .item-score-badge {
        background: #EBF3FC;
        color: #003876;
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 13px;
        font-weight: 800;
    }
    .item-meta {
        font-size: 12.5px;
        color: #64748B;
        margin-bottom: 8px;
    }
    .progress-track {
        width: 100%;
        height: 10px;
        background-color: #E2E8F0;
        border-radius: 999px;
        overflow: hidden;
    }
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #003876 0%, #0080C6 100%);
        border-radius: 999px;
    }

    .tie-banner {
        background: linear-gradient(90deg, #EBF3FC 0%, #F0F9FF 100%);
        border-left: 5px solid #005BAC;
        padding: 16px 20px;
        border-radius: 12px;
        margin: 14px 0;
        display: flex;
        justify-content: space-around;
        align-items: center;
        flex-wrap: wrap;
        gap: 12px;
    }
    .tie-item { text-align: center; }
    .tie-title { font-size: 12px; font-weight: 700; color: #475569; }
    .tie-score { font-size: 20px; font-weight: 800; color: #003876; }

    .pknu-footer {
        margin-top: 64px;
        padding: 28px 32px;
        background-color: #1E293B;
        color: #CBD5E1;
        border-radius: 14px;
        font-size: 13px;
        line-height: 1.7;
    }
    .pknu-footer-links {
        display: flex;
        gap: 20px;
        margin-bottom: 12px;
        padding-bottom: 12px;
        border-bottom: 1px solid #334155;
        flex-wrap: wrap;
    }
    .pknu-footer-links a {
        color: #FFFFFF !important;
        font-weight: 700;
        text-decoration: none;
        font-size: 13.5px;
    }
    .pknu-footer-links a.privacy-link {
        color: #38BDF8 !important;
        font-weight: 800;
    }
    .pknu-footer-links a:hover { text-decoration: underline; }
    .pknu-footer-info { color: #94A3B8; font-size: 12.5px; }
    .pknu-footer-copy { color: #64748B; font-size: 12px; margin-top: 4px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ==================== DB 초기화 및 보안·토큰 관리 함수 ====================
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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pw_tokens (
            token TEXT PRIMARY KEY,
            otp_code TEXT NOT NULL,
            student_id TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            purpose TEXT NOT NULL,
            expires_at TEXT NOT NULL
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

def create_password_setup_token(student_id, name, email, purpose="register"):
    """15분 유효한 비밀번호 설정 링크 토큰과 6자리 인증번호 동시 발급"""
    token = secrets.token_urlsafe(24)
    otp_code = str(random.randint(100000, 999999))
    expires_at = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM pw_tokens WHERE student_id = ? AND purpose = ?", (student_id.strip(), purpose))
    cur.execute(
        "INSERT INTO pw_tokens (token, otp_code, student_id, name, email, purpose, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (token, otp_code, student_id.strip(), name.strip(), email.strip().lower(), purpose, expires_at)
    )
    conn.commit()
    conn.close()
    return token, otp_code

def get_valid_token_info(token=None, student_id=None, otp_code=None, purpose=None):
    """링크 토큰 또는 6자리 인증번호 유효성 확인"""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("DELETE FROM pw_tokens WHERE expires_at < ?", (now_str,))
    conn.commit()

    if token:
        cur.execute(
            "SELECT token, otp_code, student_id, name, email, purpose, expires_at FROM pw_tokens WHERE token = ?",
            (token.strip(),)
        )
    else:
        cur.execute(
            "SELECT token, otp_code, student_id, name, email, purpose, expires_at FROM pw_tokens WHERE student_id = ? AND otp_code = ? AND purpose = ?",
            (student_id.strip(), otp_code.strip(), purpose)
        )
    row = cur.fetchone()
    conn.close()
    return row

def delete_token(token):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM pw_tokens WHERE token = ?", (token,))
    conn.commit()
    conn.close()

def verify_student_for_register(student_id, name, email):
    sid = student_id.strip()
    sname = name.strip().replace(" ", "")
    semail = email.strip().lower()

    if not any(semail.endswith(domain) for domain in ALLOWED_DOMAINS):
        return False, f"반드시 '{ALLOWED_DOMAIN}'로 끝나는 국립부경대 웹메일만 사용할 수 있습니다."

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT student_id, email FROM members WHERE student_id = ? OR email = ?", (sid, semail))
    existing = cur.fetchone()
    conn.close()
    if existing:
        return False, "이미 회원가입이 완료된 학번이거나 사용 중인 웹메일 주소입니다. 비밀번호를 잊으셨다면 [비밀번호 재설정] 탭을 이용해 주세요."

    df_scores = load_results_from_db()
    if df_scores.empty:
        return False, "아직 관리자가 장학사업 대상자 명단을 업로드하지 않았습니다."

    matched = df_scores[
        (df_scores["이용자ID"].astype(str).str.strip() == sid) &
        (df_scores["성명"].astype(str).str.replace(" ", "", regex=False) == sname)
    ]
    if matched.empty:
        return False, "입력하신 [학번 + 성명] 정보가 도서관 장학사업 집계 명단과 일치하지 않습니다."

    return True, "본인 확인 완료"

def verify_student_for_reset(student_id, name, email):
    sid = student_id.strip()
    sname = name.strip().replace(" ", "")
    semail = email.strip().lower()

    if not any(semail.endswith(domain) for domain in ALLOWED_DOMAINS):
        return False, f"반드시 '{ALLOWED_DOMAIN}'로 끝나는 국립부경대 웹메일을 입력해 주세요."

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT student_id, name, email FROM members WHERE student_id = ?", (sid,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return False, "가입된 이력이 없는 학번입니다. 먼저 회원가입을 진행해 주세요."

    db_id, db_name, db_email = row
    if db_name.replace(" ", "") != sname or db_email.lower() != semail:
        return False, "가입 시 등록한 성명 또는 교내 웹메일 정보와 일치하지 않습니다."

    return True, "가입 정보 확인 완료"

def save_member_password(student_id, name, email, password, purpose="register"):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    pw_hash = hash_password(password)
    try:
        if purpose == "reset":
            cur.execute("UPDATE members SET password_hash = ? WHERE student_id = ?", (pw_hash, student_id.strip()))
            if cur.rowcount == 0:
                return False, "해당 학번 계정을 찾을 수 없습니다."
            conn.commit()
            return True, "비밀번호가 성공적으로 변경되었습니다! [학번 로그인] 탭에서 새 비밀번호로 로그인해 주세요."
        else:
            cur.execute(
                "INSERT INTO members (student_id, name, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                (student_id.strip(), name.strip(), email.strip().lower(), pw_hash, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
            return True, "비밀번호 설정 및 회원가입이 완료되었습니다! [학번 로그인] 탭에서 로그인해 주세요."
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

def send_password_setup_email(to_email, name, token, otp_code, purpose="register"):
    """SSL 컨텍스트 보강 및 465/587 상세 진단 로그 포함 메일 발송 함수"""
    base_url = APP_BASE_URL.rstrip("/")
    setup_link = f"{base_url}/?pw_token={token}"

    if not SMTP_ENABLED:
        return True, f"[테스트 모드] 인증번호 [{otp_code}] 입력 또는 링크({setup_link})로 비밀번호를 설정하세요."

    clean_user = str(SMTP_USER).strip()
    clean_pw = str(SMTP_PASSWORD).replace(" ", "").strip()

    if ("여기에_" in clean_user) or ("여기에_" in clean_pw) or (not clean_user) or (not clean_pw):
        return False, "app.py 상단(또는 Streamlit Secrets)의 SMTP_USER와 SMTP_PASSWORD에 실제 발신 이메일과 16자리 앱 비밀번호를 입력해 주세요."

    # Gmail / 부경대 구글 워크스페이스 계정이면 서버 주소를 smtp.gmail.com 으로 자동 고정
    if clean_user.lower().endswith(("@gmail.com", "@pukyong.ac.kr")):
        target_server = "smtp.gmail.com"
    else:
        target_server = str(SMTP_SERVER).strip()

    action_label = "회원가입 비밀번호 설정" if purpose == "register" else "비밀번호 재설정"
    subject = f"[국립부경대 도서관] 장학사업 포털 {action_label} 안내"
    body = (
        f"안녕하세요, {name} 님.\n"
        f"국립부경대학교 도서관 장학사업 실시간 점수 조회 포털입니다.\n\n"
        f"아래 두 가지 방법 중 편한 방법으로 15분 이내에 비밀번호를 설정해 주세요.\n\n"
        f"[방법 1] 비밀번호 설정 바로가기 링크 클릭\n"
        f"{setup_link}\n\n"
        f"[방법 2] 열려 있는 웹페이지에 인증번호 6자리 직접 입력\n"
        f"인증번호: [ {otp_code} ]\n\n"
        f"※ 본인이 요청하지 않은 메일이라면 무시하셔도 됩니다.\n"
        f"국립부경대학교 도서관 드림"
    )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((str(Header("국립부경대 도서관", "utf-8")), clean_user))
    msg["To"] = to_email.strip()

    ctx = ssl.create_default_context()
    errors = []

    # 1순위: SSL 465 포트
    try:
        with smtplib.SMTP_SSL(target_server, 465, timeout=15, context=ctx) as server:
            server.ehlo()
            server.login(clean_user, clean_pw)
            server.send_message(msg)
        return True, "입력하신 교내 웹메일로 비밀번호 설정 메일(설정 링크 및 6자리 인증번호)을 발송했습니다. 메일함(스팸함 포함)을 확인해 주세요."
    except Exception as e:
        errors.append(f"465(SSL): {type(e).__name__} - {e}")

    # 2순위: STARTTLS 587 포트
    try:
        with smtplib.SMTP(target_server, 587, timeout=15) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.ehlo()
            server.login(clean_user, clean_pw)
            server.send_message(msg)
        return True, "입력하신 교내 웹메일로 비밀번호 설정 메일(설정 링크 및 6자리 인증번호)을 발송했습니다. 메일함(스팸함 포함)을 확인해 주세요."
    except Exception as e:
        errors.append(f"587(TLS): {type(e).__name__} - {e}")

    return False, f"이메일 발송 실패 [서버: {target_server} | 발신: {clean_user}] -> " + " / ".join(errors)

def render_item_card(title, raw_text, score, cap):
    score_val = float(score)
    cap_val = float(cap)
    pct = min(max((score_val / cap_val) * 100.0 if cap_val > 0 else 0, 0), 100)
    st.markdown(f"""
    <div class="item-card">
        <div class="item-card-top">
            <span class="item-title">{title}</span>
            <span class="item-score-badge">{score_val:g} / {cap_val:g} 점 ({pct:.0f}%)</span>
        </div>
        <div class="item-meta">📌 내 인정 실적: <b>{raw_text}</b></div>
        <div class="progress-track">
            <div class="progress-fill" style="width: {pct}%;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_footer():
    st.markdown("""
    <div class="pknu-footer">
        <div class="pknu-footer-links">
            <a href="https://www.pknu.ac.kr/main/168" target="_blank" class="privacy-link">개인정보처리방침</a>
            <span style="color:#475569;">|</span>
            <a href="https://libweb.pknu.ac.kr/nospam/" target="_blank">이메일무단수집금지</a>
        </div>
        <div class="pknu-footer-info">
            48513 부산광역시 남구 용소로 45(대연동) &nbsp;|&nbsp; FAX: 051-629-6917
        </div>
        <div class="pknu-footer-copy">
            COPYRIGHT(C) 2016 PUKYONG NATIONAL UNIVERSITY LIBRARY. ALL RIGHTS RESERVED.
        </div>
    </div>
    """, unsafe_allow_html=True)

init_db()

# ==================== 상단 국립부경대 시그니처 히어로 배너 ====================
st.markdown("""
<div class="pknu-hero">
    <div>
        <div class="pknu-hero-title">🐋 국립부경대학교 도서관 장학사업 실시간 점수 조회 포털</div>
        <div class="pknu-hero-sub">PKNU Library Mileage & Scholarship Dashboard | 나의 독서·문화·학습 활동 마일리지 및 실시간 순위 분석</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ==================== 이메일 링크(?pw_token=...) 접속 시 비밀번호 설정 전용 화면 ====================
raw_token = st.query_params.get("pw_token", None)
if isinstance(raw_token, list):
    raw_token = raw_token[0] if raw_token else None

if raw_token:
    token_row = get_valid_token_info(token=raw_token)
    c_tk1, c_tk2, c_tk3 = st.columns([1, 2, 1])
    with c_tk2:
        if not token_row:
            st.error("유효하지 않거나 만료된 비밀번호 설정 링크입니다. (유효시간 15분) 포털에서 다시 메일을 요청해 주세요.")
            if st.button("🏠 로그인 화면으로 돌아가기", type="primary", use_container_width=True):
                st.query_params.clear()
                st.rerun()
        else:
            tk_val, _, tk_sid, tk_name, tk_email, tk_purpose, _ = token_row
            title_txt = "🔐 회원가입 비밀번호 설정" if tk_purpose == "register" else "🔄 새 비밀번호 재설정"
            st.markdown(f"### {title_txt}")
            st.info(f"🔒 **본인 확인 완료 계정:** 학번 `{tk_sid}` | 성명 `{tk_name}`")

            with st.form("link_pw_setup_form"):
                new_pw = st.text_input("새 비밀번호 입력 (4자 이상)", type="password")
                new_pw_chk = st.text_input("새 비밀번호 재입력", type="password")
                save_pw_btn = st.form_submit_button("✅ 비밀번호 설정 완료", type="primary", use_container_width=True)

            if save_pw_btn:
                if len(new_pw) < 4:
                    st.error("비밀번호는 4자 이상 입력해 주세요.")
                elif new_pw != new_pw_chk:
                    st.error("비밀번호가 서로 일치하지 않습니다.")
                else:
                    ok, msg = save_member_password(tk_sid, tk_name, tk_email, new_pw, purpose=tk_purpose)
                    if ok:
                        delete_token(tk_val)
                        st.success(msg)
                        if st.button("🔑 로그인 화면으로 이동", type="primary", use_container_width=True):
                            st.query_params.clear()
                            st.rerun()
                    else:
                        st.error(msg)
    render_footer()
    st.stop()

# ==================== 사이드바 네비게이션 ====================
with st.sidebar:
    st.markdown("""
    <div class="sidebar-menu-box">
        <div class="sidebar-menu-title">🧭 접속 화면 선택</div>
        <div class="sidebar-menu-desc">원하시는 서비스 메뉴를 선택하세요</div>
    </div>
    """, unsafe_allow_html=True)

    page_mode = st.radio(
        "접속 화면 선택 메뉴",
        ["🎓 본인 점수 확인(학생용)", "⚙️ 관리자페이지"],
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.markdown("#### 🏆 수상 기준 요약 (총 38명)")
    st.caption(
        "- **1위 (최우수 1명):** 1,000,000원\n"
        "- **2~3위 (우수 2명):** 800,000원\n"
        "- **4~8위 (우량 5명):** 500,000원\n"
        "- **9~17위 (장려 9명):** 400,000원\n"
        "- **18~38위 (장려 21명):** 300,000원"
    )

# ==================== 1. 본인 점수 확인(학생용) ====================
if page_mode == "🎓 본인 점수 확인(학생용)":
    if "logged_in_user" not in st.session_state:
        st.session_state.logged_in_user = None

    if st.session_state.logged_in_user:
        u_id, u_name, u_email = st.session_state.logged_in_user
        top_c1, top_c2 = st.columns([5, 1])
        with top_c1:
            st.markdown(f"#### 👋 반갑습니다, **{u_name}** (`{u_id}`) 님!")
        with top_c2:
            if st.button("로그아웃", use_container_width=True):
                st.session_state.logged_in_user = None
                st.rerun()

        df_all = load_results_from_db()
        if df_all.empty:
            st.warning("현재 관리자가 장학사업 점수 데이터를 준비 중입니다.")
        else:
            last_updated = df_all["업데이트일시"].iloc[0] if "업데이트일시" in df_all.columns else "-"
            matched = df_all[df_all["이용자ID"].astype(str) == str(u_id)]

            if matched.empty:
                st.info(f"집계 명단에서 학번({u_id})의 데이터를 찾을 수 없습니다.")
            else:
                user_row = matched.iloc[0]
                my_score = float(user_row["최종 총점"])
                my_rank = int(user_row["순위"])
                my_grade = str(user_row["수상등급"])
                my_prize = int(user_row["지급금액"])
                total_users = len(df_all)

                cutoff_row = df_all[df_all["순위"] <= 38].tail(1)
                cutoff_score = float(cutoff_row["최종 총점"].iloc[0]) if not cutoff_row.empty else 0.0
                rank_badge = "🎉 장학금 수상권 진입!" if my_rank <= 38 else f"수상권(38위)까지 +{max(cutoff_score - my_score, 0):.1f}점 필요"

                k1, k2, k3, k4 = st.columns(4)
                with k1:
                    st.markdown(f"""
                    <div class="kpi-card">
                        <div class="kpi-label">나의 최종 총점 (최대 835점)</div>
                        <div class="kpi-value">{my_score:.1f} <span style="font-size:16px;font-weight:600;">점</span></div>
                        <div class="kpi-sub">⏱️ 기준: {last_updated}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with k2:
                    st.markdown(f"""
                    <div class="kpi-card ocean">
                        <div class="kpi-label">현재 실시간 순위</div>
                        <div class="kpi-value">{my_rank} <span style="font-size:16px;font-weight:600;">위 / {total_users}명</span></div>
                        <div class="kpi-sub">상위 {(my_rank/total_users)*100:.1f}%</div>
                    </div>
                    """, unsafe_allow_html=True)
                with k3:
                    st.markdown(f"""
                    <div class="kpi-card gold">
                        <div class="kpi-label">예상 수상 등급</div>
                        <div class="kpi-value" style="color:#B45309;">{my_grade if my_grade != '-' else '미수상권'}</div>
                        <div class="kpi-sub" style="color:#D97706;">{rank_badge}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with k4:
                    st.markdown(f"""
                    <div class="kpi-card teal">
                        <div class="kpi-label">예상 지급 장학금</div>
                        <div class="kpi-value" style="color:#0F766E;">{my_prize:,} <span style="font-size:16px;font-weight:600;">원</span></div>
                        <div class="kpi-sub" style="color:#0D9488;">소속: {user_row['소속']}</div>
                    </div>
                    """, unsafe_allow_html=True)

                tie1 = float(user_row.get("동점1순위(독서지원합)", float(user_row["독서클럽(점수)"]) + float(user_row["독서감상문(점수)"])))
                tie2 = float(user_row.get("동점2순위(자료이용합)", float(user_row["단행본(점수)"]) + float(user_row["전자책(점수)"])))
                tie3 = float(user_row.get("동점3순위(서포터즈)", float(user_row["SNS서포터즈(점수)"])))

                st.markdown(f"""
                <div class="tie-banner">
                    <div style="font-weight:800; color:#003876; font-size:14px;">⚖️ 동점자 우위 판정 지표</div>
                    <div class="tie-item">
                        <div class="tie-title">1순위: 독서지원 부문 (클럽+감상문)</div>
                        <div class="tie-score">{tie1:g} 점 <span style="font-size:12px;color:#64748B;">/ 200점</span></div>
                    </div>
                    <div class="tie-item">
                        <div class="tie-title">2순위: 자료이용 부문 (단행본+전자책)</div>
                        <div class="tie-score">{tie2:g} 점 <span style="font-size:12px;color:#64748B;">/ 200점</span></div>
                    </div>
                    <div class="tie-item">
                        <div class="tie-title">3순위: 도서관 서포터즈 부문</div>
                        <div class="tie-score">{tie3:g} 점 <span style="font-size:12px;color:#64748B;">/ 100점</span></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown('<div class="section-header">📊 10대 평가 항목별 달성률 및 상세 실적 카탈로그</div>', unsafe_allow_html=True)

                col_left, col_right = st.columns(2)
                with col_left:
                    render_item_card("📚 1. 단행본 대출", f"{int(user_row['단행본(권수)'])} 권 (1권당 1점)", user_row["단행본(점수)"], 100)
                    render_item_card("📱 2. 전자책 대출", f"{int(user_row['전자책(권수)'])} 권 (1권당 0.5점)", user_row["전자책(점수)"], 100)
                    render_item_card("🎭 3. 문화행사 참여", f"{int(user_row['문화행사(횟수)'])} 회 (1회당 5점)", user_row["문화행사(점수)"], 100)
                    render_item_card("🎓 4. 이용교육 참여", f"대면 {int(user_row['이용교육_대면(횟수)'])}회 / 비대면 {int(user_row['이용교육_비대면(횟수)'])}회", user_row["이용교육(점수)"], 100)
                    render_item_card("📝 5. 만족도조사 참여", f"{int(user_row['만족도조사(횟수)'])} 회 (1회당 3점)", user_row["만족도조사(점수)"], 100)

                with col_right:
                    render_item_card("🥽 6. 시설이용 (VR/스튜디오)", f"{int(user_row['시설이용(횟수)'])} 회 (1회당 5점)", user_row["시설이용(점수)"], 10)
                    render_item_card("👥 7. 독서클럽 활동", f"수상 등급: {user_row['독서클럽(등급)']}", user_row["독서클럽(점수)"], 70)
                    render_item_card("🎬 8. 북트레일러 공모", f"수상 등급: {user_row['북트레일러(등급)']}", user_row["북트레일러(점수)"], 25)
                    render_item_card("✍️ 9. 독서감상문 제출", f"전체 {int(user_row['독서감상문_전체(편수)'])}편 (권장도서 {int(user_row['독서감상문_권장(편수)'])}편)", user_row["독서감상문(점수)"], 130)
                    render_item_card("📢 10. 도서관 SNS 서포터즈", f"활동 내역: {user_row['SNS서포터즈(내역)']}", user_row["SNS서포터즈(점수)"], 100)

                with st.expander("📋 기존 표(Table) 형태로 전체 데이터 구조 한눈에 보기"):
                    detail_df = pd.DataFrame([
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
                    ])
                    st.dataframe(
                        detail_df,
                        column_config={
                            "환산 점수": st.column_config.ProgressColumn(
                                "환산 점수 (상한 대비)",
                                format="%f 점",
                                min_value=0,
                                max_value=130,
                            )
                        },
                        hide_index=True,
                        use_container_width=True
                    )

    else:
        auth_tab1, auth_tab2, auth_tab3 = st.tabs([
            "🔑 학번 로그인",
            "🛡️ 회원가입 (@pukyong.ac.kr 인증)",
            "🔄 비밀번호 재설정 (메일 발송)"
        ])

        # 1) 학번 로그인 탭
        with auth_tab1:
            c_login1, c_login2, c_login3 = st.columns([1, 2, 1])
            with c_login2:
                st.markdown("#### 🔑 학번 로그인")
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

        # 2) 회원가입 (비밀번호 설정 메일 발송) 탭
        with auth_tab2:
            st.markdown("#### 🛡️ 교내 웹메일(@pukyong.ac.kr) 인증 회원가입")
            st.info("입력하신 **[학번 + 성명]**이 장학사업 집계 명단과 일치하면 교내 웹메일(@pukyong.ac.kr)로 **비밀번호 설정 링크 및 6자리 인증번호**가 발송됩니다.")

            if "reg_sent_sid" not in st.session_state:
                st.session_state.reg_sent_sid = None
                st.session_state.reg_verified_token = None

            c_r1, c_r2, c_r3 = st.columns(3)
            with c_r1:
                reg_id = st.text_input("1. 본인 학번", placeholder="예: 20261001", key="reg_id")
            with c_r2:
                reg_name = st.text_input("2. 본인 성명", placeholder="예: 홍길동", key="reg_name")
            with c_r3:
                reg_email = st.text_input("3. 교내 웹메일(@pukyong.ac.kr)", placeholder="example@pukyong.ac.kr", key="reg_email")

            if st.button("📨 본인 확인 및 비밀번호 설정 메일 발송", use_container_width=True):
                ok_id, msg_id = verify_student_for_register(reg_id, reg_name, reg_email)
                if not ok_id:
                    st.error(msg_id)
                else:
                    token, otp_code = create_password_setup_token(reg_id, reg_name, reg_email, purpose="register")
                    ok_mail, msg_mail = send_password_setup_email(reg_email.strip().lower(), reg_name.strip(), token, otp_code, purpose="register")
                    if ok_mail:
                        st.session_state.reg_sent_sid = reg_id.strip()
                        st.session_state.reg_verified_token = None
                        st.success(msg_mail)
                    else:
                        st.error(msg_mail)

            if st.session_state.reg_sent_sid and not st.session_state.reg_verified_token:
                st.caption("메일 안의 **비밀번호 설정 링크**를 클릭하거나, 아래에 **6자리 인증번호**를 직접 입력해 진행할 수 있습니다.")
                c_v1, c_v2 = st.columns([3, 1])
                with c_v1:
                    input_otp = st.text_input("웹메일로 수신한 6자리 인증번호 입력", max_chars=6, key="reg_otp")
                with c_v2:
                    st.write("")
                    st.write("")
                    if st.button("✔️ 인증번호 확인", use_container_width=True, key="reg_otp_btn"):
                        row = get_valid_token_info(student_id=st.session_state.reg_sent_sid, otp_code=input_otp, purpose="register")
                        if row:
                            st.session_state.reg_verified_token = row
                            st.success("✅ 본인 인증 완료! 아래에서 비밀번호를 설정해 주세요.")
                        else:
                            st.error("인증번호가 일치하지 않거나 만료되었습니다.")

            if st.session_state.reg_verified_token:
                tk_val, _, v_id, v_name, v_email, _, _ = st.session_state.reg_verified_token
                st.markdown("---")
                st.write(f"🔒 **인증 완료 계정:** 학번 `{v_id}` | 성명 `{v_name}`")
                with st.form("final_reg_form"):
                    reg_pw = st.text_input("사용할 비밀번호 입력 (4자 이상)", type="password")
                    reg_pw_chk = st.text_input("비밀번호 재입력", type="password")
                    reg_submit = st.form_submit_button("🎉 비밀번호 설정 및 회원가입 완료", type="primary", use_container_width=True)

                if reg_submit:
                    if len(reg_pw) < 4:
                        st.error("비밀번호는 4자 이상 입력해 주세요.")
                    elif reg_pw != reg_pw_chk:
                        st.error("비밀번호가 서로 일치하지 않습니다.")
                    else:
                        ok, msg = save_member_password(v_id, v_name, v_email, reg_pw, purpose="register")
                        if ok:
                            delete_token(tk_val)
                            st.success(msg)
                            st.session_state.reg_sent_sid = None
                            st.session_state.reg_verified_token = None
                        else:
                            st.error(msg)

        # 3) 비밀번호 재설정 (메일 발송) 탭
        with auth_tab3:
            st.markdown("#### 🔄 비밀번호 분실 시 재설정 메일 발송")
            st.info("가입하신 **학번, 성명, 교내 웹메일(@pukyong.ac.kr)**을 입력하시면 비밀번호를 새로 설정할 수 있는 메일을 보내드립니다.")

            if "rst_sent_sid" not in st.session_state:
                st.session_state.rst_sent_sid = None
                st.session_state.rst_verified_token = None

            c_rs1, c_rs2, c_rs3 = st.columns(3)
            with c_rs1:
                rst_id = st.text_input("1. 가입한 학번", placeholder="예: 20261001", key="rst_id")
            with c_rs2:
                rst_name = st.text_input("2. 성명", placeholder="예: 홍길동", key="rst_name")
            with c_rs3:
                rst_email = st.text_input("3. 가입한 교내 웹메일(@pukyong.ac.kr)", placeholder="example@pukyong.ac.kr", key="rst_email")

            if st.button("📧 비밀번호 재설정 메일 발송", use_container_width=True):
                ok_rst, msg_rst = verify_student_for_reset(rst_id, rst_name, rst_email)
                if not ok_rst:
                    st.error(msg_rst)
                else:
                    token, otp_code = create_password_setup_token(rst_id, rst_name, rst_email, purpose="reset")
                    ok_mail, msg_mail = send_password_setup_email(rst_email.strip().lower(), rst_name.strip(), token, otp_code, purpose="reset")
                    if ok_mail:
                        st.session_state.rst_sent_sid = rst_id.strip()
                        st.session_state.rst_verified_token = None
                        st.success(msg_mail)
                    else:
                        st.error(msg_mail)

            if st.session_state.rst_sent_sid and not st.session_state.rst_verified_token:
                st.caption("메일 안의 **비밀번호 설정 링크**를 클릭하거나, 아래에 **6자리 인증번호**를 입력해 새 비밀번호를 설정할 수 있습니다.")
                c_rv1, c_rv2 = st.columns([3, 1])
                with c_rv1:
                    rst_otp = st.text_input("웹메일로 수신한 6자리 인증번호 입력", max_chars=6, key="rst_otp")
                with c_rv2:
                    st.write("")
                    st.write("")
                    if st.button("✔️ 인증번호 확인", use_container_width=True, key="rst_otp_btn"):
                        row = get_valid_token_info(student_id=st.session_state.rst_sent_sid, otp_code=rst_otp, purpose="reset")
                        if row:
                            st.session_state.rst_verified_token = row
                            st.success("✅ 본인 인증 완료! 새 비밀번호를 입력해 주세요.")
                        else:
                            st.error("인증번호가 일치하지 않거나 만료되었습니다.")

            if st.session_state.rst_verified_token:
                tk_val, _, v_id, v_name, v_email, _, _ = st.session_state.rst_verified_token
                st.markdown("---")
                st.write(f"🔒 **재설정 대상 계정:** 학번 `{v_id}` | 성명 `{v_name}`")
                with st.form("final_reset_form"):
                    new_pw = st.text_input("새 비밀번호 입력 (4자 이상)", type="password")
                    new_pw_chk = st.text_input("새 비밀번호 재입력", type="password")
                    rst_submit = st.form_submit_button("✅ 새 비밀번호 저장", type="primary", use_container_width=True)

                if rst_submit:
                    if len(new_pw) < 4:
                        st.error("비밀번호는 4자 이상 입력해 주세요.")
                    elif new_pw != new_pw_chk:
                        st.error("비밀번호가 서로 일치하지 않습니다.")
                    else:
                        ok, msg = save_member_password(v_id, v_name, v_email, new_pw, purpose="reset")
                        if ok:
                            delete_token(tk_val)
                            st.success(msg)
                            st.session_state.rst_sent_sid = None
                            st.session_state.rst_verified_token = None
                        else:
                            st.error(msg)

# ==================== 2. 관리자페이지 ====================
elif page_mode == "⚙️ 관리자페이지":
    if "admin_logged_in" not in st.session_state:
        st.session_state.admin_logged_in = False

    if not st.session_state.admin_logged_in:
        c_adm1, c_adm2, c_adm3 = st.columns([1, 2, 1])
        with c_adm2:
            st.markdown("#### 🔒 관리자페이지 로그인")
            st.caption("담당자 전용 메뉴입니다. 관리자 비밀번호를 입력한 뒤 엔터(Enter) 또는 로그인 버튼을 눌러주세요.")
            with st.form("admin_login_form"):
                pwd = st.text_input("관리자 비밀번호", type="password", placeholder="비밀번호를 입력하세요")
                adm_submit = st.form_submit_button("🔑 관리자 로그인", type="primary", use_container_width=True)

            if adm_submit:
                if pwd.strip() == ADMIN_PASSWORD:
                    st.session_state.admin_logged_in = True
                    st.rerun()
                else:
                    st.error("비밀번호가 올바르지 않습니다.")
    else:
        top_adm1, top_adm2 = st.columns([5, 1])
        with top_adm1:
            st.info("🛡️ 해당 프로그램은 '2026년 장학사업 계획'에 의거하여 만들어진 프로그램으로 최종 결과물에 대한 검수와 책임은 사용자(담당자)에게 있음을 확인합니다.")
        with top_adm2:
            if st.button("관리자 로그아웃", use_container_width=True):
                st.session_state.admin_logged_in = False
                st.rerun()

        df_saved = load_results_from_db()
        conn = sqlite3.connect(DB_FILE)
        df_members = pd.read_sql("SELECT student_id AS 학번, name AS 성명, email AS 인증웹메일, created_at AS 가입일시 FROM members", conn)
        conn.close()

        if not df_saved.empty:
            total_cnt = len(df_saved)
            avg_scr = float(df_saved["최종 총점"].mean())
            max_scr = float(df_saved["최종 총점"].max())
            total_prize = int(df_saved["지급금액"].sum())

            a1, a2, a3, a4 = st.columns(4)
            with a1:
                st.markdown(f'<div class="kpi-card"><div class="kpi-label">총 집계 대상 인원</div><div class="kpi-value">{total_cnt:,} 명</div><div class="kpi-sub">웹포털 가입자: {len(df_members)}명</div></div>', unsafe_allow_html=True)
            with a2:
                st.markdown(f'<div class="kpi-card ocean"><div class="kpi-label">전체 평균 점수 / 최고점</div><div class="kpi-value">{avg_scr:.1f} 점</div><div class="kpi-sub">1위 최고점: {max_scr:.1f}점</div></div>', unsafe_allow_html=True)
            with a3:
                st.markdown(f'<div class="kpi-card gold"><div class="kpi-label">장학금 배정 인원</div><div class="kpi-value" style="color:#B45309;">{(df_saved["지급금액"] > 0).sum()} 명</div><div class="kpi-sub" style="color:#D97706;">기준: 1위 ~ 38위</div></div>', unsafe_allow_html=True)
            with a4:
                st.markdown(f'<div class="kpi-card teal"><div class="kpi-label">총 장학금 집행 예산</div><div class="kpi-value" style="color:#0F766E;">{total_prize:,} 원</div><div class="kpi-sub" style="color:#0D9488;">자동 산출 완료</div></div>', unsafe_allow_html=True)
            st.write("")

        t1, t2, t3 = st.tabs([
            "⚡ 1. 로컬 실행파일(.exe) 결과 엑셀 간편 연동",
            "📊 2. 실시간 순위 대시보드 및 게이지 표",
            "👥 3. 가입 학생 계정 및 비밀번호 메일 관리"
        ])

        with t1:
            st.markdown("#### ⚡ 로컬 PC `도서관점수산정기.exe` 결과 파일 연동")
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
                        st.success(f"✅ 연동 완료! 총 {len(df_exe)}명의 데이터가 웹 대시보드에 즉시 반영되었습니다.")
                        st.rerun()
                except Exception as e:
                    st.error(f"오류 발생: {e}")

        with t2:
            if df_saved.empty:
                st.info("반영된 점수 데이터가 없습니다.")
            else:
                st.markdown("#### 🏆 전체 이용자 순위 및 시각적 점수 게이지 표 (데이터 구조 100% 보존)")
                max_total = max(float(df_saved["최종 총점"].max()), 100.0)
                st.dataframe(
                    df_saved,
                    column_config={
                        "순위": st.column_config.NumberColumn("🏆 순위", format="%d 위"),
                        "최종 총점": st.column_config.ProgressColumn(
                            "최종 총점 (시각화 게이지)",
                            format="%.1f 점",
                            min_value=0,
                            max_value=max_total,
                        ),
                        "지급금액": st.column_config.NumberColumn("💰 지급 장학금", format="%d 원"),
                        "단행본(점수)": st.column_config.ProgressColumn("단행본(점수)", format="%d", min_value=0, max_value=100),
                        "전자책(점수)": st.column_config.ProgressColumn("전자책(점수)", format="%.1f", min_value=0, max_value=100),
                        "독서감상문(점수)": st.column_config.ProgressColumn("독서감상문(점수)", format="%d", min_value=0, max_value=130),
                    },
                    hide_index=True,
                    use_container_width=True,
                    height=520
                )

        with t3:
            st.markdown(f"#### 👥 가입 완료 학생 명단 (총 {len(df_members)}명)")
            st.dataframe(df_members, use_container_width=True, hide_index=True)

            st.markdown("---")
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.markdown("##### 📧 학생에게 비밀번호 재설정 메일 직접 발송")
                reset_target_id = st.text_input("비밀번호 재설정 메일을 보낼 학번 입력", key="adm_rst_id")
                if st.button("📨 해당 학생에게 비밀번호 재설정 메일 발송", use_container_width=True):
                    conn = sqlite3.connect(DB_FILE)
                    cur = conn.cursor()
                    cur.execute("SELECT student_id, name, email FROM members WHERE student_id = ?", (reset_target_id.strip(),))
                    target_row = cur.fetchone()
                    conn.close()
                    if not target_row:
                        st.error("가입된 회원 목록에서 해당 학번을 찾을 수 없습니다.")
                    else:
                        t_sid, t_name, t_email = target_row
                        token, otp_code = create_password_setup_token(t_sid, t_name, t_email, purpose="reset")
                        ok_mail, msg_mail = send_password_setup_email(t_email, t_name, token, otp_code, purpose="reset")
                        if ok_mail:
                            st.success(f"✅ {t_name}({t_sid}) 학생의 등록 메일로 비밀번호 재설정 메일을 발송했습니다.")
                        else:
                            st.error(msg_mail)

            with col_m2:
                st.markdown("##### 🗑️ 학생 계정 초기화(삭제)")
                del_id = st.text_input("초기화할 학생의 학번 입력", key="adm_del_id")
                if st.button("🗑️ 해당 학번 계정 초기화(삭제)", use_container_width=True):
                    conn = sqlite3.connect(DB_FILE)
                    conn.execute("DELETE FROM members WHERE student_id = ?", (del_id.strip(),))
                    conn.commit()
                    conn.close()
                    st.success(f"학번 {del_id} 계정이 초기화되었습니다.")
                    st.rerun()

            with st.expander("🧪 이메일 발송(SMTP) 설정 정상 작동 테스트"):
                test_email = st.text_input("테스트 메일을 받아볼 주소 입력", placeholder="본인 이메일 주소 입력")
                if st.button("🚀 테스트 메일 1통 발송해보기"):
                    if not test_email.strip():
                        st.warning("수신할 이메일 주소를 입력해 주세요.")
                    else:
                        ok_t, msg_t = send_password_setup_email(test_email.strip(), "담당자", "TEST_TOKEN_SAMPLE", "123456", purpose="reset")
                        if ok_t:
                            st.success(f"✅ 테스트 메일 발송 성공! ({test_email.strip()} 메일함을 확인해 보세요)")
                        else:
                            st.error(msg_t)

# ==================== 전체 화면 최하단 공식 푸터 렌더링 ====================
render_footer()
