import math
import urllib.parse
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ==========================================
# 1. 페이지 기본 설정 & CSS 커스텀 (대시보드 룩앤필)
# ==========================================
st.set_page_config(
    page_title="스마트 공장통합 관제 대시보드",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 고급스러운 대시보드 스타일 지정을 위한 CSS Inject
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

st.title("🏭 스마트 제조 & 재고 통합 관제 대시보드")
st.caption("Real-time Manufacturing & Inventory Intelligence Dashboard")

DOCUMENT_ID = "1cJEuRJ8Sbgb-PF0-xta0j7J2MqoYlATWXRk907DZPnc"


# ==========================================
# 2. 데이터 로드 함수
# ==========================================
@st.cache_data(ttl=5)
def load_sheet_data(sheet_name: str) -> pd.DataFrame:
    encoded_name = urllib.parse.quote(sheet_name)
    url = f"https://docs.google.com/spreadsheets/d/{DOCUMENT_ID}/gviz/tq?tqx=out:csv&sheet={encoded_name}"
    df = pd.read_csv(url, encoding="utf-8")
    # 완전히 비어있는 행/열 제거
    df = df.dropna(how="all").dropna(axis=1, how="all")
    return df


# 수량/숫자 컬럼 자동으로 찾는 유틸리티 함수
def find_numeric_cols(df):
    return df.select_dtypes(include=[np.number]).columns.tolist()


# ==========================================
# 3. 메인 탭 구성
# ==========================================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "📈 완제품 재고 현황",
        "📋 실시간 생산일지",
        "📦 부품/재고 마스터",
        "⚙️ BOM 관리",
        "🔄 디지털 트윈 (Flow)",
        "🛡️ 안전재고 시뮬레이터",
    ]
)

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
# [Tab 2] 실시간 생산일지 (그럴듯한 요약 & 차트 추가)
# ------------------------------------------
with tab2:
    st.subheader("📋 실시간 생산일지 분석 관제")

    with st.spinner("📊 생산 데이터를 분석 중입니다..."):
        try:
            df_prod = load_sheet_data("생산일지")

            if not df_prod.empty:
                num_cols = find_numeric_cols(df_prod)

                # --- 1. 상단 KPI 요약 카드 ---
                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    st.metric("총 기록 건수", f"{len(df_prod):,} 건")

                # 수량 데이터가 있는 컬럼이 있다면 합계/평균 산출
                qty_col = num_cols[0] if num_cols else None
                if qty_col:
                    total_qty = df_prod[qty_col].sum()
                    avg_qty = df_prod[qty_col].mean()
                    with m2:
                        st.metric("총 실적 수량", f"{total_qty:,.0f} EA")
                    with m3:
                        st.metric("평균 생산량", f"{avg_qty:,.1f} EA")
                else:
                    with m2:
                        st.metric("데이터 상태", "정상 연동됨")
                    with m3:
                        st.metric("실시간 업데이트", "ON")

                with m4:
                    st.metric("최근 업데이트", "방금 전")

                st.divider()

                # --- 2. 시각화 차트 세션 ---
                c1, c2 = st.columns([1, 1])

                # 수량 컬럼 및 문자열(품목/담당자) 컬럼 추출
                str_cols = df_prod.select_dtypes(include=["object"]).columns.tolist()

                with c1:
                    st.markdown("##### 📊 항목별 생산 현황")
                    if str_cols and qty_col:
                        cat_col = str_cols[0]
                        grouped = (
                            df_prod.groupby(cat_col)[qty_col]
                            .sum()
                            .reset_index()
                            .sort_values(by=qty_col, ascending=False)
                        )
                        fig_bar = px.bar(
                            grouped.head(10),
                            x=cat_col,
                            y=qty_col,
                            color=qty_col,
                            color_continuous_scale="Viridis",
                            text_auto=",d",
                            title=f"주요 {cat_col}별 생산 수량",
                        )
                        fig_bar.update_layout(height=350, margin=dict(l=10, r=10, t=40, b=10))
                        st.plotly_chart(fig_bar, use_container_width=True)
                    else:
                        st.info("시각화를 위한 수량/항목 데이터 컬럼을 분석 중입니다.")

                with c2:
                    st.markdown("##### 📈 기록 분포 & 비율")
                    if str_cols and qty_col and len(str_cols) > 1:
                        pie_col = str_cols[1] if len(str_cols) > 1 else str_cols[0]
                        fig_pie = px.pie(
                            df_prod,
                            names=pie_col,
                            values=qty_col,
                            hole=0.4,
                            title=f"{pie_col}별 점유율",
                        )
                        fig_pie.update_layout(height=350, margin=dict(l=10, r=10, t=40, b=10))
                        st.plotly_chart(fig_pie, use_container_width=True)
                    elif qty_col:
                        fig_hist = px.histogram(
                            df_prod, x=qty_col, title="생산량 분포도", color_discrete_sequence=["#2b5c8f"]
                        )
                        fig_hist.update_layout(height=350, margin=dict(l=10, r=10, t=40, b=10))
                        st.plotly_chart(fig_hist, use_container_width=True)

                # --- 3. 정돈된 상세 데이터 테이블 ---
                st.markdown("##### 📄 원본 생산일지 상세 데이터")

                # 숫자형 컬럼에 데이터 바(Data Bar) 효과 적용
                if qty_col:
                    st.dataframe(
                        df_prod.style.background_gradient(subset=[qty_col], cmap="Blues"),
                        use_container_width=True,
                        height=400,
                    )
                else:
                    st.dataframe(df_prod, use_container_width=True, height=400)

        except Exception as e:
            st.error(f"생산일지 데이터를 불러오거나 분석하는 중 오류가 발생했습니다: {e}")


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

            # 수량 항목 강조 표시
            if num_cols_m:
                st.dataframe(
                    df_master.style.highlight_max(subset=[num_cols_m[0]], color="#e8f5e9"),
                    use_container_width=True,
                )
            else:
                st.dataframe(df_master, use_container_width=True)

        except Exception as e:
            st.error(f"마스터시트 데이터 로드 실패: {e}")


# ------------------------------------------
# [Tab 4] BOM 현황
# ------------------------------------------
with tab4:
    st.subheader("⚙️ BOM (Bill of Materials) 구조 현황")
    with st.spinner("BOM 구조 분석 중..."):
        try:
            df_bom = load_sheet_data("BOM")

            b1, b2 = st.columns(2)
            with b1:
                st.metric("BOM 등록 구성요소", f"{len(df_bom):,} 개")

            st.divider()
            st.dataframe(df_bom, use_container_width=True, height=500)

        except Exception as e:
            st.error(f"BOM 데이터 로드 실패: {e}")


# ------------------------------------------
# [Tab 5] 디지털 트윈 (재고 & 공정 파이프라인 흐름)
# ------------------------------------------
with tab5:
    st.subheader("🔄 자재 ➔ WIP ➔ 완제품 ➔ 출고 디지털 트윈 파이프라인")
    st.caption("실시간 자재 투입량 및 공정 손실, 보유 재고 흐름을 시각적으로 모니터링합니다.")

    # 컨트롤 파널
    st.markdown("##### 🎛️ 공정별 수량 시뮬레이션 입력")
    col_in1, col_in2, col_in3, col_in4 = st.columns(4)
    with col_in1:
        raw_mat = st.number_input("1. 원자재 입고량 (EA)", value=10000, step=500)
    with col_in2:
        wip_qty = st.number_input("2. 공정 투입 (WIP) (EA)", value=8500, step=500)
    with col_in3:
        finished_goods = st.number_input("3. 완제품 입고 (EA)", value=8000, step=500)
    with col_in4:
        shipped_goods = st.number_input("4. 최종 출고 (EA)", value=6800, step=500)

    # 파이프라인 유량 계산
    unprocessed_raw = max(0, raw_mat - wip_qty)
    wip_loss = max(0, wip_qty - finished_goods)
    fg_stock = max(0, finished_goods - shipped_goods)

    labels = [
        f"원자재 입고 ({raw_mat:,})",
        f"공정 투입 WIP ({wip_qty:,})",
        f"완제품 검사완료 ({finished_goods:,})",
        f"최종 출고 ({shipped_goods:,})",
        f"공정 손실/불량 ({wip_loss:,})",
        f"원자재 미투입 재고 ({unprocessed_raw:,})",
        f"완제품 보관 재고 ({fg_stock:,})",
    ]

    fig = go.Figure(
        data=[
            go.Sankey(
                node=dict(
                    pad=20,
                    thickness=20,
                    line=dict(color="black", width=0.5),
                    label=labels,
                    color=[
                        "#1e88e5",
                        "#fb8c00",
                        "#43a047",
                        "#8e24aa",
                        "#e53935",
                        "#90a4ae",
                        "#6d4c41",
                    ],
                ),
                link=dict(
                    source=[0, 0, 1, 1, 2, 2],
                    target=[1, 5, 2, 4, 3, 6],
                    value=[
                        wip_qty,
                        unprocessed_raw,
                        finished_goods,
                        wip_loss,
                        shipped_goods,
                        fg_stock,
                    ],
                    color=[
                        "rgba(30,136,229,0.3)",
                        "rgba(144,164,174,0.3)",
                        "rgba(251,140,0,0.3)",
                        "rgba(229,57,53,0.3)",
                        "rgba(67,160,71,0.3)",
                        "rgba(109,76,65,0.3)",
                    ],
                ),
            )
        ]
    )

    fig.update_layout(height=480, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)


# ------------------------------------------
# [Tab 6] 안전재고 시뮬레이터
# ------------------------------------------
with tab6:
    st.subheader("🛡️ 최적 안전재고(Safety Stock) & 재발주점(ROP) 시뮬레이터")

    s_col1, s_col2 = st.columns([1, 1])

    with s_col1:
        st.markdown("##### 🎛️ 변수 설정")
        service_level = st.select_slider(
            "목표 서비스 수준 (품절 방지율 %)",
            options=[80, 85, 90, 95, 98, 99, 99.9],
            value=95,
        )
        z_dict = {80: 0.84, 85: 1.04, 90: 1.28, 95: 1.65, 98: 2.05, 99: 2.33, 99.9: 3.09}
        z_score = z_dict[service_level]

        avg_demand = st.slider("일평균 출고량 (D)", 10, 2000, 250, 10)
        std_demand = st.slider("일 출고량 변동성 (σd)", 0, 500, 50, 5)
        lead_time = st.number_input("입고 리드타임 (L - 일)", 1, 60, 7)
        std_lt = st.number_input("리드타임 지연 변동성 (σL)", 0.0, 10.0, 1.0, 0.5)

    with s_col2:
        safety_stock = round(
            z_score * math.sqrt((lead_time * (std_demand**2)) + ((avg_demand**2) * (std_lt**2)))
        )
        lt_demand = avg_demand * lead_time
        rop = lt_demand + safety_stock

        st.markdown("##### 📈 산출 결과")
        r1, r2 = st.columns(2)
        with r1:
            st.metric("🛡️ 권장 안전재고", f"{safety_stock:,} EA", delta=f"Z-Score {z_score}")
        with r2:
            st.metric("🔔 목표 재발주점 (ROP)", f"{rop:,} EA", delta="이 수치 도달 시 발주")

        fig_rop = go.Figure(
            data=[
                go.Bar(name="리드타임 소요량", x=["ROP"], y=[lt_demand], marker_color="#1e88e5"),
                go.Bar(
                    name="안전재고(방어용)", x=["ROP"], y=[safety_stock], marker_color="#e53935"
                ),
            ]
        )
        fig_rop.update_layout(
            barmode="stack",
            height=220,
            margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_rop, use_container_width=True)
