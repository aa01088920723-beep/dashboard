import math
import re
import urllib.parse
import sqlite3
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ==========================================
# 1. 페이지 기본 설정 & CSS 커스텀
# ==========================================
st.set_page_config(
    page_title="스마트 공장통합 관제 대시보드",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .main { background-color: #f8f9fa; }
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e9ecef;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    div[data-testid="stMetricValue"] {
        font-size: 28px;
        font-weight: 700;
        color: #1f2937;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# ==========================================
# DB 초기화 (주간 생산목표 & 특이사항 저장용)
# ==========================================
def init_local_db():
    conn = sqlite3.connect("production_data.db")
    cursor = conn.cursor()
    
    # 1) 주간 생산목표 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS production_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_label TEXT,
            item_name TEXT,
            target_qty INTEGER,
            actual_qty INTEGER,
            status_note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 2) 특이사항 및 주요 이벤트 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS issue_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            event_name TEXT,
            progress TEXT,
            action_plan TEXT,
            due_date TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_local_db()

def get_db_connection():
    return sqlite3.connect("production_data.db")

st.title("🏭 스마트 제조 & 재고 통합 관제 대시보드")
st.caption("Real-time Manufacturing & Inventory Intelligence Dashboard")

# 생산/부품 마스터용 문서 ID
DOCUMENT_ID = "1cJEuRJ8Sbgb-PF0-xta0j7J2MqoYlATWXRk907DZPnc"
# 완제품 재고 전용 문서 ID
FINISHED_GOODS_DOC_ID = "1wUFDAk6iutu2433iLxqF5PEVinxZsjXBQ5twqPmwtg0"


# ==========================================
# 2. 데이터 로드 및 날짜 정제 유틸리티 함수
# ==========================================
@st.cache_data(ttl=5)
def load_sheet_data(sheet_name: str, doc_id: str = DOCUMENT_ID) -> pd.DataFrame:
    encoded_name = urllib.parse.quote(sheet_name)
    url = f"https://docs.google.com/spreadsheets/d/{doc_id}/gviz/tq?tqx=out:csv&sheet={encoded_name}"
    try:
        df = pd.read_csv(url, encoding="utf-8")
        df = df.dropna(how="all").dropna(axis=1, how="all")
        return df
    except Exception:
        return pd.DataFrame()


def find_numeric_cols(df):
    return df.select_dtypes(include=[np.number]).columns.tolist()


def clean_date_series(series: pd.Series) -> pd.Series:
    """구글 시트의 다양한 날짜/타임스탬프 한글 형식을 표준 datetime 형태로 안전 변환"""
    s_clean = series.astype(str).str.strip()
    s_clean = s_clean.str.replace("오전", "AM").str.replace("오후", "PM")
    s_clean = s_clean.str.replace(".", "-", regex=False)
    s_clean = s_clean.str.replace("년", "-").str.replace("월", "-").str.replace("일", "")
    return pd.to_datetime(s_clean, errors="coerce")


def get_korean_week_label(dt: pd.Timestamp) -> str:
    """
    수요일이 속한 월을 기준 월로 삼아 N월 M주차 (MM/DD~MM/DD) 형태의 문자열을 반환
    """
    if pd.isna(dt):
        return "미지정"

    monday = dt - pd.Timedelta(days=dt.weekday())  # 월요일 (Mon=0)
    wednesday = monday + pd.Timedelta(days=2)      # 수요일
    friday = monday + pd.Timedelta(days=4)          # 금요일

    target_year = wednesday.year
    target_month = wednesday.month

    first_day_of_month = pd.Timestamp(year=target_year, month=target_month, day=1)
    days_to_first_wed = (2 - first_day_of_month.weekday()) % 7
    first_wednesday = first_day_of_month + pd.Timedelta(days=days_to_first_wed)

    week_num = (wednesday.day - first_wednesday.day) // 7 + 1

    date_range = f"{monday.strftime('%m/%d')}~{friday.strftime('%m/%d')}"
    return f"{target_month}월 {week_num}주차 ({date_range})"


# ==========================================
# 3. 메인 탭 구성
# ==========================================
tab_goal, tab_issue, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "📌 주간 생산목표 관리",
        "🚨 특이사항 & 주요 이벤트",
        "📈 완제품 재고 현황",
        "📋 실시간 생산일지",
        "📦 부품/재고 마스터",
        "🔄 부품 수불 관제 (Flow)",
        "📅 주간/월간 통합 리포트",
        "📅 월별 재고현황",
    ]
)

# ------------------------------------------
# [신규 추가 탭 1] 주간 생산목표 별 실제 생산현황
# ------------------------------------------
with tab_goal:
    st.subheader("📌 주간 생산목표 별 실제 생산현황")
    st.caption("대시보드에서 직접 이번 주 생산 목표 및 실적 수량을 등록하고 관리합니다.")

    conn = get_db_connection()
    df_goals = pd.read_sql_query("SELECT * FROM production_goals ORDER BY id DESC", conn)
    conn.close()

    if not df_goals.empty:
        weeks = df_goals["week_label"].unique().tolist()
        selected_week = st.selectbox("📅 조회할 주차 선택", options=weeks, index=0)
        
        filtered_goals = df_goals[df_goals["week_label"] == selected_week]
        
        st.markdown(f"##### 📊 {selected_week} 생산 달성률 현황")
        m_cols = st.columns(min(len(filtered_goals), 4) if len(filtered_goals) > 0 else 1)
        for idx, (_, row) in enumerate(filtered_goals.iterrows()):
            with m_cols[idx % 4]:
                target = row['target_qty']
                actual = row['actual_qty']
                rate = round((actual / target * 100), 1) if target > 0 else 0
                st.metric(
                    label=f"{row['item_name']}",
                    value=f"{actual:,} EA",
                    delta=f"목표 {target:,} EA ({rate}% 달성)"
                )
        
        st.divider()
        st.markdown("##### 📋 생산목표 상세 현황표")
        st.dataframe(
            filtered_goals[["week_label", "item_name", "target_qty", "actual_qty", "status_note"]],
            column_config={
                "week_label": "주차",
                "item_name": "품목명",
                "target_qty": "생산목표 수량 (EA)",
                "actual_qty": "실제 생산 수량 (EA)",
                "status_note": "비고 / 상태"
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("💡 등록된 주간 생산목표가 없습니다. 아래 입력 폼에서 새 주차 생산 목표를 입력해 주세요.")

    st.divider()
# ==========================================
# ❌ 주간 생산목표 직접 입력 데이터 삭제 기능
# ==========================================
with st.expander("❌ 주간 생산목표 데이터 삭제"):
    # 세션이나 현재 데이터프레임 변수명 확인 (보통 st.session_state에 저장되어 있을 확률이 높습니다)
    # 예시로 df_goals 기준 코드입니다.
    if 'df_goals' in locals() and not df_goals.empty:
        
        # 1. 삭제할 항목 선택 목록 만들기
        delete_options = {
            f"[{i}] {row.get('week_label', '')} | {row.get('item_name', '')} | 수량: {row.get('actual_qty', '')}EA": i
            for i, row in df_goals.iterrows()
        }
        
        selected_label = st.selectbox("삭제할 항목 선택", list(delete_options.keys()), key="del_goal_selectbox")
        target_idx = delete_options[selected_label]
        
        if st.button("선택 항목 삭제", type="primary", key="btn_del_goal_action"):
            # 2. 데이터프레임에서 해당 행 제거 후 인덱스 재정렬
            df_goals = df_goals.drop(target_idx).reset_index(drop=True)
            
            # 3. 만약 데이터를 st.session_state에 저장해서 관리하고 계신다면, 세션도 같이 갱신해줍니다!
            if 'df_goals' in st.session_state:
                st.session_state.df_goals = df_goals
            
            st.success("항목이 성공적으로 삭제되었습니다!")
            st.rerun()
    else:
        st.write("삭제할 데이터가 없습니다.")


# ------------------------------------------
# [신규 추가 탭 2] 특이사항 및 주요 이벤트
# ------------------------------------------
with tab_issue:
    st.subheader("🚨 특이사항 및 주요 이벤트 관제")
    st.caption("부품, GMP, 설비 등 업무 특이사항과 진행상황, 조치 계획을 등록·관리합니다.")

    conn = get_db_connection()
    df_issues = pd.read_sql_query("SELECT * FROM issue_events ORDER BY id DESC", conn)
    conn.close()

    if not df_issues.empty:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            sel_cat = st.multiselect("구분 필터", options=df_issues["category"].unique(), default=df_issues["category"].unique())
        with col_f2:
            sel_status = st.multiselect("상태 필터", options=df_issues["status"].unique(), default=df_issues["status"].unique())

        filtered_issues = df_issues[
            (df_issues["category"].isin(sel_cat)) & 
            (df_issues["status"].isin(sel_status))
        ]

        st.dataframe(
            filtered_issues[["id", "category", "event_name", "progress", "action_plan", "due_date", "status"]],
            column_config={
                "id": "No",
                "category": "구분",
                "event_name": "이벤트",
                "progress": "진행상황",
                "action_plan": "향후 조치 계획",
                "due_date": "완료기한(Due Date)",
                "status": "상태"
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("💡 등록된 특이사항 데이터가 없습니다. 아래 입력 폼에서 등록해 주세요.")

    st.divider()

    with st.expander("➕ 새 특이사항 및 주요 이벤트 등록", expanded=df_issues.empty):
        with st.form("new_issue_form", clear_on_submit=True):
            i_col1, i_col2 = st.columns(2)
            with i_col1:
                i_category = st.selectbox("구분", ["부품", "GMP", "설비", "품질", "기타"])
                i_event = st.text_input("이벤트 제목", placeholder="예: 포장지 공급업체 변경건 / DHR 서류 작성")
                i_progress = st.text_area("진행상황", placeholder="예: 업체 견적문의 완료")
            with i_col2:
                i_plan = st.text_area("향후 조치 계획", placeholder="예: 샘플 수령 후 자체 염료테스트 수행")
                i_due = st.text_input("완료기한 (Due Date)", value="-")
                i_status = st.selectbox("상태", ["🔄 [진행중]", "✅ [완료]", "⏳ [보류/대기]", "🔍 [검토중]"])
            
            submit_i = st.form_submit_button("💾 특이사항 저장하기", use_container_width=True)
            if submit_i:
                if i_event:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO issue_events (category, event_name, progress, action_plan, due_date, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (i_category, i_event, i_progress, i_plan, i_due, i_status))
                    conn.commit()
                    conn.close()
                    st.success("새 특이사항이 저장되었습니다!")
                    st.rerun()
                else:
                    st.warning("이벤트 제목을 입력해 주세요.")


# ------------------------------------------
# [Tab 1] 완제품 재고 현황
# ------------------------------------------
with tab1:
    st.subheader("📈 차주 생산목표 및 완제품 재고 현황")
    col_btn1, col_btn2 = st.columns([3, 1])
    with col_btn1:
        st.info("💡 모바일 반응형 페이지를 대시보드 내부에서 실시간으로 확인합니다.")
    with col_btn2:
        st.link_button(
            "🔗 전체화면으로 보기", "https://m.site.naver.com/2a4rF", use_container_width=True
        )

    st.components.v1.iframe("https://m.site.naver.com/2a4rF", height=680, scrolling=True)


# ------------------------------------------
# [Tab 2] 실시간 생산일지 분석 관제
# ------------------------------------------
with tab2:
    st.subheader("📋 실시간 생산 및 불량 관제 분석")

    with st.spinner("📊 생산 및 불량 데이터를 분석 중입니다..."):
        try:
            df_prod = load_sheet_data("생산일지")
            df_defect = load_sheet_data("불량관리")
            if df_defect.empty:
                df_defect = load_sheet_data("Form_Responses2")

            if not df_prod.empty:
                qty_col_p = None
                lot_col_p = None
                date_col_p = None

                for col in df_prod.columns:
                    col_str = str(col).strip()
                    if "생산수량" in col_str or "수량" in col_str:
                        qty_col_p = col
                    elif "LOT" in col_str or "롯트" in col_str:
                        lot_col_p = col
                    elif "일자" in col_str or "날짜" in col_str or "타임스탬프" in col_str:
                        date_col_p = col

                if not qty_col_p:
                    num_cols_p = find_numeric_cols(df_prod)
                    qty_col_p = num_cols_p[0] if num_cols_p else None

                if qty_col_p:
                    df_prod[qty_col_p] = pd.to_numeric(
                        df_prod[qty_col_p].astype(str).str.replace(',', ''), errors="coerce"
                    ).fillna(0)

                if lot_col_p and qty_col_p:
                    df_unique_lot = df_prod.groupby(lot_col_p)[qty_col_p].max().reset_index()
                    total_qty = df_unique_lot[qty_col_p].sum()
                else:
                    total_qty = df_prod[qty_col_p].sum() if qty_col_p else 0

                total_defect = 0
                defect_qty_col = None
                defect_date_col = None
                defect_item_col = None

                if not df_defect.empty:
                    for col in df_defect.columns:
                        col_str = str(col).strip()
                        if "수량" in col_str:
                            defect_qty_col = col
                        elif "일자" in col_str or "날짜" in col_str or "타임스탬프" in col_str:
                            defect_date_col = col
                        elif "자재" in col_str or "품목" in col_str or "부품" in col_str:
                            defect_item_col = col

                    if defect_qty_col:
                        df_defect[defect_qty_col] = pd.to_numeric(
                            df_defect[defect_qty_col].astype(str).str.replace(',', ''), errors="coerce"
                        ).fillna(0)
                        total_defect = df_defect[defect_qty_col].sum()

                total_output = total_qty + total_defect
                overall_defect_rate = (total_defect / total_output * 100) if total_output > 0 else 0

                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    st.metric("총 생산 기록 건수", f"{len(df_prod):,} 건")
                with m2:
                    st.metric("총 실제 양품 수량", f"{total_qty:,.0f} EA")
                with m3:
                    st.metric(
                        "총 불량 발생 수량",
                        f"{total_defect:,.0f} EA",
                        delta=f"-{total_defect:,.0f}" if total_defect > 0 else "0",
                        delta_color="inverse",
                    )
                with m4:
                    st.metric("전체 공정 불량률", f"{overall_defect_rate:.2f} %")

                st.divider()

                c1, c2 = st.columns([1, 1])

                with c1:
                    st.markdown("##### 📊 품목(제품)별 실제 생산 수량")
                    if lot_col_p and qty_col_p:
                        def extract_item_code(lot_str):
                            lot_str = str(lot_str).strip()
                            parts = re.split(r'[_ ]', lot_str)
                            item_part = parts[0]
                            item_part = re.sub(r'[-_]?\d{6}$', '', item_part)
                            return item_part if item_part else lot_str

                        df_unique_lot["품목코드"] = df_unique_lot[lot_col_p].apply(extract_item_code)
                        grouped_p = df_unique_lot.groupby("품목코드")[qty_col_p].sum().reset_index().sort_values(by=qty_col_p, ascending=False)

                        f_col1, f_col2 = st.columns([2, 1])
                        with f_col2:
                            view_option = st.selectbox(
                                "표시 범위 선택",
                                ["상위 10개", "상위 20개", "전체 품목 보기"],
                                key="prod_view_opt"
                            )

                        if view_option == "상위 10개":
                            display_df = grouped_p.head(10).sort_values(by=qty_col_p, ascending=True)
                        elif view_option == "상위 20개":
                            display_df = grouped_p.head(20).sort_values(by=qty_col_p, ascending=True)
                        else:
                            display_df = grouped_p.sort_values(by=qty_col_p, ascending=True)

                        dynamic_height = max(380, len(display_df) * 35 + 60)

                        fig_bar = px.bar(
                            display_df,
                            x=qty_col_p,
                            y="품목코드",
                            orientation='h',
                            color=qty_col_p,
                            color_continuous_scale="Viridis",
                            text_auto=",d",
                            labels={"품목코드": "품목(제품명)", qty_col_p: "실제 생산수량"},
                        )
                        
                        fig_bar.update_yaxes(type='category', title="")
                        fig_bar.update_xaxes(title="생산수량 (EA)")
                        fig_bar.update_layout(
                            height=dynamic_height,
                            margin=dict(l=150, r=20, t=10, b=40),
                            coloraxis_showscale=False
                        )
                        
                        st.plotly_chart(fig_bar, use_container_width=True)
                    else:
                        st.info("생산일지 분석 데이터를 확인 중입니다.")

                with c2:
                    st.markdown("##### 📉 품목/자재별 불량 발생 비중")
                    if not df_defect.empty and defect_item_col and defect_qty_col:
                        df_defect["정제_품목명"] = df_defect[defect_item_col].astype(str).str.replace(r'^\d+\s*', '', regex=True)
                        grouped_d = df_defect.groupby("정제_품목명")[defect_qty_col].sum().reset_index().sort_values(by=defect_qty_col, ascending=False)

                        fig_defect = px.pie(
                            grouped_d,
                            names="정제_품목명",
                            values=defect_qty_col,
                            hole=0.4,
                            title="자재별 불량 수량 비율",
                            color_discrete_sequence=px.colors.sequential.RdBu,
                        )
                        fig_defect.update_layout(height=380, margin=dict(l=10, r=10, t=40, b=10))
                        st.plotly_chart(fig_defect, use_container_width=True)
                    else:
                        st.info("등록된 불량 데이터가 없습니다.")

                st.divider()

                if not df_defect.empty:
                    st.markdown("##### 📄 자재별 불량 발생 내역 (날짜 및 사유 상세)")
                    
                    display_cols = []
                    col_rename_dict = {}

                    if defect_date_col and defect_date_col in df_defect.columns:
                        display_cols.append(defect_date_col)
                        col_rename_dict[defect_date_col] = "작업일자"

                    if "정제_품목명" in df_defect.columns:
                        display_cols.append("정제_품목명")
                        col_rename_dict["정제_품목명"] = "불량 자재/품목명"

                    if defect_qty_col and defect_qty_col in df_defect.columns:
                        display_cols.append(defect_qty_col)
                        col_rename_dict[defect_qty_col] = "불량 수량"

                    reason_col = None
                    for col in df_defect.columns:
                        if "사유" in col or "특이사항" in col:
                            reason_col = col
                            break
                    if reason_col:
                        display_cols.append(reason_col)
                        col_rename_dict[reason_col] = "주요 불량 사유"

                    worker_col = None
                    for col in df_defect.columns:
                        if "작업자" in col or "담당자" in col:
                            worker_col = col
                            break
                    if worker_col:
                        display_cols.append(worker_col)
                        col_rename_dict[worker_col] = "작업자"

                    df_defect_display = df_defect[display_cols].rename(columns=col_rename_dict)
                    st.dataframe(df_defect_display, use_container_width=True, height=220, hide_index=True)

                st.divider()

                st.markdown("##### 📄 원본 생산일지 상세 데이터")
                st.dataframe(df_prod, use_container_width=True, height=350, hide_index=True)

        except Exception as e:
            st.error(f"생산 및 불량 데이터를 분석하는 중 오류가 발생했습니다: {e}")


# ------------------------------------------
# [Tab 3] 부품 및 재고 마스터시트
# ------------------------------------------
with tab3:
    st.subheader("📦 부품 및 재고 마스터 관리")
    with st.spinner("마스터 데이터를 불러오는 중입니다..."):
        try:
            df_master = load_sheet_data("마스터시트")

            kpi1, kpi2, kpi3 = st.columns(3)
            with kpi1:
                st.metric("총 등록 부품/재고 품목", f"{len(df_master):,} 개")

            num_cols_m = find_numeric_cols(df_master)
            if num_cols_m:
                with kpi2:
                    st.metric("총 재고 보유 수량", f"{df_master[num_cols_m[0]].sum():,} EA")
                with kpi3:
                    st.metric("평균 보유 재고량", f"{df_master[num_cols_m[0]].mean():,.1f} EA")

            st.divider()
            st.markdown("##### 📋 마스터 재고 리스트")
            st.dataframe(df_master, use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"마스터시트 데이터 로드 실패: {e}")


# ------------------------------------------
# [Tab 4] 실시간 부품 수불 및 재고 흐름 관제 (Flow)
# ------------------------------------------
with tab4:
    st.subheader("🔄 실시간 부품 수불 및 재고 흐름 관제")
    st.caption("마스터시트의 실제 초기재고, 불량 누적, 현재고 데이터를 기반으로 실시간 관제합니다.")

    with st.spinner("마스터시트 및 품질 데이터를 정밀 연동 중입니다..."):
        try:
            df_m = load_sheet_data("마스터시트")
            df_d = load_sheet_data("불량관리")
            if df_d.empty:
                df_d = load_sheet_data("Form_Responses2")

            name_col = None
            init_col = None
            curr_col = None

            if not df_m.empty:
                for col in df_m.columns:
                    col_str = str(col).strip()
                    if "이름" in col_str or "부품명" in col_str or "품목명" in col_str:
                        name_col = col
                    elif "초기재고" in col_str or "기초재고" in col_str:
                        init_col = col
                    elif "현재고" in col_str:
                        curr_col = col

            if not name_col and not df_m.empty and len(df_m.columns) >= 2:
                name_col = df_m.columns[1]
            if not init_col and not df_m.empty and len(df_m.columns) >= 6:
                init_col = df_m.columns[5]
            if not curr_col and not df_m.empty and len(df_m.columns) >= 7:
                curr_col = df_m.columns[6]

            item_options = []
            if name_col and not df_m.empty:
                raw_names = df_m[name_col].dropna().astype(str).str.strip().tolist()
                for name in raw_names:
                    if name and not name.endswith("일") and not name.isdigit() and name not in ["nan", "None", "이름", "순번"]:
                        item_options.append(name)

            dropdown_options = ["📦 [전체 부품/자재 요약 보기]"] + sorted(list(set(item_options)))

            selected_item_option = st.selectbox("🔍 관제할 부품/자재를 선택하세요", dropdown_options)

            init_stock = 0
            current_stock = 0
            defect_qty = 0
            used_qty = 0

            if not df_m.empty and name_col and init_col and curr_col:
                df_m[init_col] = pd.to_numeric(df_m[init_col].astype(str).str.replace(',', ''), errors="coerce").fillna(0)
                df_m[curr_col] = pd.to_numeric(df_m[curr_col].astype(str).str.replace(',', ''), errors="coerce").fillna(0)

                if selected_item_option == "📦 [전체 부품/자재 요약 보기]":
                    init_stock = df_m[init_col].sum()
                    current_stock = df_m[curr_col].sum()
                else:
                    df_target = df_m[df_m[name_col].astype(str).str.strip() == selected_item_option]
                    if not df_target.empty:
                        init_stock = df_target[init_col].values[0]
                        current_stock = df_target[curr_col].values[0]

            if not df_d.empty:
                d_qty_col = None
                d_item_col = None
                for col in df_d.columns:
                    col_str = str(col).strip()
                    if "수량" in col_str:
                        d_qty_col = col
                    elif "자재" in col_str or "품목" in col_str or "부품" in col_str:
                        d_item_col = col

                if d_qty_col:
                    df_d[d_qty_col] = pd.to_numeric(df_d[d_qty_col].astype(str).str.replace(',', ''), errors="coerce").fillna(0)
                    if selected_item_option == "📦 [전체 부품/자재 요약 보기]":
                        defect_qty = df_d[d_qty_col].sum()
                    elif d_item_col:
                        df_d["정제자재"] = df_d[d_item_col].astype(str).str.replace(r'^\d+\s*', '', regex=True).str.strip()
                        df_d_target = df_d[df_d["정제자재"] == selected_item_option]
                        if not df_d_target.empty:
                            defect_qty = df_d_target[d_qty_col].sum()

            total_inflow = init_stock
            if total_inflow < current_stock + defect_qty:
                total_inflow = current_stock + defect_qty

            used_qty = max(0, total_inflow - current_stock - defect_qty)

            total_consumed = used_qty + defect_qty
            depletion_rate = (total_consumed / total_inflow * 100) if total_inflow > 0 else 0
            yield_rate = (used_qty / total_consumed * 100) if total_consumed > 0 else 100

            k1, k2, k3, k4 = st.columns(4)
            with k1:
                st.metric("📦 초기/총 확보량", f"{int(total_inflow):,} EA")
            with k2:
                st.metric("⚙️ 정상 생산 소모량", f"{int(used_qty):,} EA")
            with k3:
                st.metric("⚠️ 불량 폐기 누적량", f"{int(defect_qty):,} EA", delta=f"-{int(defect_qty):,}" if defect_qty > 0 else "0", delta_color="inverse")
            with k4:
                st.metric("🏭 창고 현재고량", f"{int(current_stock):,} EA")

            st.divider()

            labels = [
                f"총 확보량 ({int(total_inflow):,})",
                f"정상 생산 소모 ({int(used_qty):,})",
                f"불량 폐기 손실 ({int(defect_qty):,})",
                f"창고 실재고 ({int(current_stock):,})",
            ]

            fig_sankey = go.Figure(
                data=[
                    go.Sankey(
                        node=dict(
                            pad=25,
                            thickness=20,
                            line=dict(color="black", width=0.5),
                            label=labels,
                            color=["#1e88e5", "#43a047", "#e53935", "#fb8c00"],
                        ),
                        link=dict(
                            source=[0, 0, 0],
                            target=[1, 2, 3],
                            value=[max(0.1, used_qty), max(0.1, defect_qty), max(0.1, current_stock)],
                            color=[
                                "rgba(67,160,71,0.3)",
                                "rgba(229,57,53,0.3)",
                                "rgba(251,140,0,0.3)",
                            ],
                        ),
                    )
                ]
            )

            fig_sankey.update_layout(
                title=f"💡 [{selected_item_option}] 자재 수불 및 현재고 파이프라인 흐름",
                height=420,
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig_sankey, use_container_width=True)

            sub1, sub2 = st.columns(2)
            with sub1:
                st.info(f"📊 **부품 총 소진율**: `{depletion_rate:.1f}%` (초기재고 대비 소모/폐기 비율)")
            with sub2:
                st.success(f"✅ **양품 사용율**: `{yield_rate:.1f}%` (소모된 부품 중 양품 비율)")

        except Exception as e:
            st.error(f"수불 관제 파이프라인을 생성하는 중 오류가 발생했습니다: {e}")


# ------------------------------------------
# [Tab 5] 주간 / 월간 생산 & 품질 통합 리포트
# ------------------------------------------
with tab5:
    st.subheader("📅 주간 / 월간 생산 실적 및 품질 분석 리포트")
    st.caption("생산일지 및 품질 불량 데이터를 주기별(주간/월간)로 자동 추적 및 정밀 분석합니다.")

    with st.spinner("생산 및 품질 시상 데이터를 기반으로 통합 리포트를 집계 중입니다..."):
        try:
            df_p = load_sheet_data("생산일지")
            df_d = load_sheet_data("불량관리")
            if df_d.empty:
                df_d = load_sheet_data("Form_Responses2")

            date_col_p, qty_col_p, lot_col_p = None, None, None
            if not df_p.empty:
                for c in df_p.columns:
                    col_str = str(c).strip()
                    if "일자" in col_str or "날짜" in col_str or "타임스탬프" in col_str:
                        date_col_p = c
                    elif "생산수량" in col_str or "수량" in col_str:
                        qty_col_p = c
                    elif "LOT" in col_str or "롯트" in col_str:
                        lot_col_p = c

                if not qty_col_p:
                    nums = find_numeric_cols(df_p)
                    qty_col_p = nums[0] if nums else None

            date_col_d, qty_col_d, item_col_d = None, None, None
            if not df_d.empty:
                for c in df_d.columns:
                    col_str = str(c).strip()
                    if "일자" in col_str or "날짜" in col_str or "타임스탬프" in col_str:
                        date_col_d = c
                    elif "수량" in col_str:
                        qty_col_d = c
                    elif "자재" in col_str or "품목" in col_str or "부품" in col_str:
                        item_col_d = c

            if df_p.empty or not date_col_p or not qty_col_p:
                st.warning("⚠️ 분석할 생산일지 데이터가 존재하지 않거나 일자/수량 항목이 올바르지 않습니다.")
            else:
                df_p[qty_col_p] = pd.to_numeric(
                    df_p[qty_col_p].astype(str).str.replace(',', ''), errors="coerce"
                ).fillna(0)
                df_p["작업일시"] = clean_date_series(df_p[date_col_p])
                df_p = df_p.dropna(subset=["작업일시"]).copy()

                def extract_item(l_str):
                    l_str = str(l_str).strip()
                    if not l_str or l_str.lower() in ["nan", "none"]:
                        return "미지정"
                    parts = re.split(r'[_ ]', l_str)
                    res = re.sub(r'[-_]?\d{6}$', '', parts[0])
                    return res if res else "미지정"

                df_p["품목코드"] = df_p[lot_col_p].apply(extract_item) if lot_col_p else "기본품목"

                if not df_d.empty and date_col_d and qty_col_d:
                    df_d[qty_col_d] = pd.to_numeric(
                        df_d[qty_col_d].astype(str).str.replace(',', ''), errors="coerce"
                    ).fillna(0)
                    df_d["작업일시"] = clean_date_series(df_d[date_col_d])
                    df_d = df_d.dropna(subset=["작업일시"]).copy()
                else:
                    df_d = pd.DataFrame(columns=["작업일시", qty_col_d if qty_col_d else "불량수량"])

                r_col1, r_col2 = st.columns([1, 2])
                with r_col1:
                    period_type = st.radio("📊 분석 주기 선택", ["주간 단위 (Weekly)", "월간 단위 (Monthly)"], horizontal=True)

                if "주간" in period_type:
                    df_p["기간그룹"] = df_p["작업일시"].apply(get_korean_week_label)
                    if not df_d.empty and "작업일시" in df_d.columns:
                        df_d["기간그룹"] = df_d["작업일시"].apply(get_korean_week_label)
                else:
                    df_p["기간그룹"] = df_p["작업일시"].dt.strftime("%Y년 %m월")
                    if not df_d.empty and "작업일시" in df_d.columns:
                        df_d["기간그룹"] = df_d["작업일시"].dt.strftime("%Y년 %m월")

                if lot_col_p:
                    df_p_unique = df_p.groupby(["기간그룹", lot_col_p, "품목코드"])[qty_col_p].max().reset_index()
                else:
                    df_p_unique = df_p

                prod_summary = df_p_unique.groupby("기간그룹")[qty_col_p].sum().reset_index()
                prod_summary.columns = ["기간그룹", "생산수량"]

                if not df_d.empty and "기간그룹" in df_d.columns and qty_col_d in df_d.columns:
                    defect_summary = df_d.groupby("기간그룹")[qty_col_d].sum().reset_index()
                    defect_summary.columns = ["기간그룹", "불량수량"]
                else:
                    defect_summary = pd.DataFrame(columns=["기간그룹", "불량수량"])

                report_df = pd.merge(prod_summary, defect_summary, on="기간그룹", how="left").fillna(0)
                report_df["총출하량"] = report_df["생산수량"] + report_df["불량수량"]
                report_df["불량률(%)"] = np.where(
                    report_df["총출하량"] > 0,
                    (report_df["불량수량"] / report_df["총출하량"]) * 100,
                    0
                )
                report_df = report_df.sort_values(by="기간그룹")

                st.divider()
                tot_p = report_df["생산수량"].sum()
                tot_d = report_df["불량수량"].sum()
                avg_rate = (tot_d / (tot_p + tot_d) * 100) if (tot_p + tot_d) > 0 else 0

                kpi_a, kpi_b, kpi_c, kpi_d = st.columns(4)
                with kpi_a:
                    st.metric("총 분석 기간 수", f"{len(report_df):,} 개 주기")
                with kpi_b:
                    st.metric("기간 총 생산량", f"{int(tot_p):,} EA")
                with kpi_c:
                    st.metric("기간 총 불량량", f"{int(tot_d):,} EA", delta=f"-{int(tot_d):,}" if tot_d > 0 else "0", delta_color="inverse")
                with kpi_d:
                    st.metric("평균 불량률", f"{avg_rate:.2f} %")

                st.divider()

                st.markdown("##### 📈 기간별 생산 실적 및 불량률 추이")
                
                fig_trend = make_subplots(specs=[[{"secondary_y": True}]])
                
                fig_trend.add_trace(
                    go.Bar(
                        x=report_df["기간그룹"],
                        y=report_df["생산수량"],
                        name="생산수량 (EA)",
                        marker_color="#1f77b4",
                        text=report_df["생산수량"].apply(lambda x: f"{int(x):,}"),
                        textposition="inside"
                    ),
                    secondary_y=False,
                )

                fig_trend.add_trace(
                    go.Scatter(
                        x=report_df["기간그룹"],
                        y=report_df["불량률(%)"],
                        name="불량률 (%)",
                        mode="lines+markers+text",
                        line=dict(color="#d62728", width=3),
                        text=report_df["불량률(%)"].apply(lambda x: f"{x:.1f}%"),
                        textposition="top center"
                    ),
                    secondary_y=True,
                )

                fig_trend.update_xaxes(title_text="분석 주기")
                fig_trend.update_yaxes(title_text="생산 수량 (EA)", secondary_y=False)
                fig_trend.update_yaxes(title_text="불량률 (%)", secondary_y=True)
                fig_trend.update_layout(
                    height=400,
                    margin=dict(l=20, r=20, t=30, b=20),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )

                st.plotly_chart(fig_trend, use_container_width=True)

                st.markdown("##### 📦 기간별 품목(제품) 생산 구성 비중")
                item_group = df_p_unique.groupby(["기간그룹", "품목코드"])[qty_col_p].sum().reset_index()

                fig_item = px.bar(
                    item_group,
                    x="기간그룹",
                    y=qty_col_p,
                    color="품목코드",
                    title="주기별 주요 생산 품목 구성",
                    labels={qty_col_p: "생산수량 (EA)", "기간그룹": "분석 주기"},
                    color_discrete_sequence=px.colors.qualitative.Set2
                )
                fig_item.update_layout(height=380, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig_item, use_container_width=True)

                st.markdown("##### 📋 주기별 생산 및 품질 종합 분석표")
                disp_report = report_df.copy()
                disp_report.columns = ["분석 기간", "양품 생산수량 (EA)", "불량 발생수량 (EA)", "총 출하수량 (EA)", "공정 불량률 (%)"]
                
                disp_report["양품 생산수량 (EA)"] = disp_report["양품 생산수량 (EA)"].map("{:,.0f}".format)
                disp_report["불량 발생수량 (EA)"] = disp_report["불량 발생수량 (EA)"].map("{:,.0f}".format)
                disp_report["총 출하수량 (EA)"] = disp_report["총 출하수량 (EA)"].map("{:,.0f}".format)
                disp_report["공정 불량률 (%)"] = disp_report["공정 불량률 (%)"].map("{:.2f}%".format)

                st.dataframe(disp_report, use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"주간/월간 분석 리포트 생성 중 오류가 발생했습니다: {e}")


# ------------------------------------------
# [Tab 6] 월별 재고현황 (완제품 및 부품 재고)
# ------------------------------------------
with tab6:
    st.subheader("📅 월별 재고현황")
    st.caption("경영지원부 보고용 완제품 재고현황 및 부품/자재 재고현황을 기준월별로 조회 및 내보냅니다.")

    with st.spinner("구글 시트의 [완제품재고 관리] 및 [마스터시트] 데이터를 연동 중입니다..."):
        try:
            df_fg_in = load_sheet_data("IN", doc_id=FINISHED_GOODS_DOC_ID)
            df_fg_out = load_sheet_data("OUT", doc_id=FINISHED_GOODS_DOC_ID)
            df_parts = load_sheet_data("마스터시트", doc_id=DOCUMENT_ID)

            if not df_fg_in.empty and "타임스탬프" in df_fg_in.columns:
                df_fg_in["작업일시"] = clean_date_series(df_fg_in["타임스탬프"])
            elif not df_fg_in.empty and len(df_fg_in.columns) > 0:
                df_fg_in["작업일시"] = clean_date_series(df_fg_in.iloc[:, 0])

            if not df_fg_out.empty and "타임스탬프" in df_fg_out.columns:
                df_fg_out["작업일시"] = clean_date_series(df_fg_out["타임스탬프"])
            elif not df_fg_out.empty and len(df_fg_out.columns) > 0:
                df_fg_out["작업일시"] = clean_date_series(df_fg_out.iloc[:, 0])

            available_months = []
            if "작업일시" in df_fg_in.columns and not df_fg_in["작업일시"].dropna().empty:
                df_fg_in["YM"] = df_fg_in["작업일시"].dt.strftime("%Y-%m")
                available_months = sorted(df_fg_in["YM"].dropna().unique(), reverse=True)

            if not available_months:
                available_months = ["2026-09", "2026-08", "2026-07", "2026-06"]

            selected_month = st.selectbox("📅 기준월 선택 (예: 2026-09)", available_months, key="tab6_month_select")

            st.divider()

            st.markdown(f"#### 📈 1. 완제품 재고현황 ({selected_month} 기준)")
            
            if not df_fg_in.empty:
                in_item_col = [c for c in df_fg_in.columns if "제품" in c or "품목" in c]
                in_qty_col = [c for c in df_fg_in.columns if "입고수량" in c or "수량" in c]
                
                c_item = in_item_col[0] if in_item_col else df_fg_in.columns[1]
                c_qty = in_qty_col[0] if in_qty_col else df_fg_in.columns[3]

                df_fg_in[c_qty] = pd.to_numeric(df_fg_in[c_qty].astype(str).str.replace(',', ''), errors="coerce").fillna(0)
                
                if "YM" in df_fg_in.columns:
                    df_in_filtered = df_fg_in[df_fg_in["YM"] <= selected_month]
                else:
                    df_in_filtered = df_fg_in

                fg_in_summary = df_in_filtered.groupby(c_item)[c_qty].sum().reset_index()
                fg_in_summary.columns = ["완제품명", "총 입고수량"]

                fg_out_summary = pd.DataFrame(columns=["완제품명", "총 출하수량"])
                if not df_fg_out.empty:
                    out_item_col = [c for c in df_fg_out.columns if "제품" in c or "품목" in c]
                    out_qty_col = [c for c in df_fg_out.columns if "출고수량" in c or "수량" in c]
                    co_item = out_item_col[0] if out_item_col else df_fg_out.columns[1]
                    co_qty = out_qty_col[0] if out_qty_col else df_fg_out.columns[3]

                    df_fg_out[co_qty] = pd.to_numeric(df_fg_out[co_qty].astype(str).str.replace(',', ''), errors="coerce").fillna(0)
                    
                    if "작업일시" in df_fg_out.columns and not df_fg_out["작업일시"].dropna().empty:
                        df_fg_out["YM"] = df_fg_out["작업일시"].dt.strftime("%Y-%m")
                        df_out_filtered = df_fg_out[df_fg_out["YM"] <= selected_month]
                    else:
                        df_out_filtered = df_fg_out

                    fg_out_summary = df_out_filtered.groupby(co_item)[co_qty].sum().reset_index()
                    fg_out_summary.columns = ["완제품명", "총 출하수량"]

                fg_merged = pd.merge(fg_in_summary, fg_out_summary, on="완제품명", how="outer").fillna(0)
                fg_merged["현재 완제품 재고량"] = fg_merged["총 입고수량"] - fg_merged["총 출하수량"]
                fg_merged = fg_merged.sort_values(by="현재 완제품 재고량", ascending=False)

                fg_display = fg_merged.copy()
                fg_display["총 입고수량"] = fg_display["총 입고수량"].map("{:,.0f}".format)
                fg_display["총 출하수량"] = fg_display["총 출하수량"].map("{:,.0f}".format)
                fg_display["현재 완제품 재고량"] = fg_display["현재 완제품 재고량"].map("{:,.0f}".format)

                st.dataframe(fg_display, use_container_width=True, hide_index=True)

                csv_fg = fg_merged.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label=f"📥 {selected_month} 완제품 재고현황 CSV 다운로드",
                    data=csv_fg,
                    file_name=f"완제품_재고현황_{selected_month}.csv",
                    mime="text/csv",
                    key="dl_fg_csv"
                )
            else:
                st.info("완제품 입출고 데이터를 확인하는 중입니다.")

            st.divider()

            st.markdown(f"#### 📦 2. 부품/자재 재고현황 ({selected_month} 기준)")
            if not df_parts.empty:
                st.dataframe(df_parts, use_container_width=True, hide_index=True)

                csv_parts = df_parts.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label=f"📥 {selected_month} 부품 재고현황 CSV 다운로드",
                    data=csv_parts,
                    file_name=f"부품_재고현황_{selected_month}.csv",
                    mime="text/csv",
                    key="dl_parts_csv"
                )
            else:
                st.info("부품 마스터 재고 데이터를 불러오는 중입니다.")

        except Exception as e:
            st.error(f"월별 재고현황 집계 도중 오류가 발생했습니다: {e}")
