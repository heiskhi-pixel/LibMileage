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
    page_title="국립부경대학교 도서관 장학사업 실시간 점수 조회 포털",
    page_icon="🐋",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_FILE = "library_scholarship.db"
CONFIG_FILE = "library_score_config.json"
ALLOWED_DOMAIN = "@pukyong.ac.kr"
ADMIN_PASSWORD = "admin1234"  # 관리자 비밀번호 (운영 시 변경 가능)

# ==================== 이메일(SMTP) 설정 ====================
SMTP_ENABLED = True
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "library_sender@gmail.com"           # 도서관 대표 Gmail 주소
SMTP_PASSWORD = "your_google_app_password_here"  # 구글 앱 비밀번호 16자리

# ==================== 국립부경대학교 전용 커스텀 CSS 테마 ====================
st.markdown("""
<style>
    /* 전체 배경 및 폰트 */
    .stApp {
        background-color: #F4F7FB;
        font-family: 'Pretendard', '맑은 고딕', sans-serif;
    }

    /* 사이드바 배경 및 접속화면 선택 메뉴 가시성 대폭 강화 */
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

    /* 사이드바 라디오 버튼을 큼직한 카드형 버튼처럼 스타일링 */
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

    /* 상단 PKNU 히어로 배너 */
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

    /* 핵심 KPI 요약 카드 4종 */
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

    /* 섹션 타이틀 배지 */
    .section-header {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 18px;
        font-weight: 800;
        color: #003876;
        margin: 22px 0 12px 0;
    }

    /* 10대 항목 비주얼 프로그레스 카드 */
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

    /* 동점자 우선순위 배너 */
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
    .tie-item {
        text-align: center;
    }
    .tie-title {
        font-size: 12px;
        font-weight: 700;
        color: #475569;
    }
    .tie-score {
        font-size: 20px;
        font-weight: 800;
        color: #003876;
    }

    /* 웹페이지 하단 공식 푸터(Footer) */
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
    .pknu-footer-links a:hover {
        text-decoration: underline;
    }
    .pknu-footer-info {
        color: #94A3B8;
        font-size: 12.5px;
    }
    .pknu-footer-copy {
        color: #64748B;
        font-size: 12px;
        margin-top: 4px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

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
    sid = student_id.strip()
    sname = name.strip()
    semail = email.strip().lower()

    if not semail.endswith(ALLOWED_DOMAIN):
        return False, f"반드시 '{ALLOWED_DOMAIN}'로 끝나는 국립부경대 웹메일만 사용할 수 있습니다."

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT student_id, email FROM members WHERE student_id = ? OR email = ?", (sid, semail))
    existing = cur.fetchone()
    conn.close()
    if existing:
        return False, "이미 회원가입이 완료된 학번이거나 사용 중인 웹메일 주소입니다."

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
        return True, f"[테스트 모드] 인증번호 [{code}]를 입력해 주세요."
    try:
        msg = MIMEText(
            f"안녕하세요.\n국립부경대학교 도서관 장학사업 실시간 점수 조회 포털 인증번호입니다.\n\n"
            f"인증번호 6자리: [ {code} ]\n\n웹페이지로 돌아가 인증번호를 입력해 주세요.",
            "plain", "utf-8"
        )
        msg["Subject"] = "[국립부경대 도서관] 장학사업 점수 조회 포털 웹메일 인증번호 안내"
        msg["From"] = SMTP_USER
        msg["To"] = to_email

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True, f"{to_email} 주소로 6자리 인증번호를 발송했습니다. 메일함을 확인해 주세요."
    except Exception as e:
        return False, f"이메일 발송 중 오류가 발생했습니다: {e}"

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

# ==================== 사이드바 네비게이션 (가시성 강화 & 명칭 변경) ====================
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
            st.markdown(f"#### 👋 반갑습니다, **{u_name}** (`{u_id}`) 님! &nbsp;|&nbsp; 📧 `{u_email}`")
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

                # 1. 상단 4대 핵심 KPI 카드
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

                # 2. 동점자 우선순위 핵심 지표 요약 배너
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

                # 3. 10개 항목별 달성률 게이지 카드 (2열 그리드 배치)
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

                # 4. 기존 데이터 구조를 한눈에 확인하는 원본 데이터 펼침 메뉴
                with st.expander("📋 기존 표(Table) 형태로 전체 데이터 구조 한눈에 보기"):
                    detail_df = pd.DataFrame([
                        {"평가 항목": "1. 단행본대출", "내 실적": f"{int(user_row['단행본(권수)'])} 권", "환산 점수": user_row["단행본(점수)"], "최대 상한(Cap)": 100},
