import math
import re
import urllib.parse
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
    try:
        df = pd.read_csv(url, encoding="utf-8")
        df = df.dropna(how="all").dropna(axis=1, how="all")
        return df
    except Exception:
        return pd.DataFrame()


def find_numeric_cols(df):
    return df.select_dtypes(include=[np.number]).columns.tolist()


# ==========================================
# 3. 메인 탭 구성
# ==========================================
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "📈 완제품 재고 현황",
        "📋 실시간 생산일지",
        "📦 부품/재고 마스터",
        "🔄 부품 수불 관제 (Flow)",
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
                    if "생산수량" in col or "수량" in col:
                        qty_col_p = col
                    elif "LOT" in col or "롯트" in col:
                        lot_col_p = col
                    elif "일자" in col or "날짜" in col or "타임스탬프" in col:
                        date_col_p = col

                if not qty_col_p:
                    num_cols_p = find_numeric_cols(df_prod)
                    qty_col_p = num_cols_p[0] if num_cols_p else None

                if qty_col_p:
                    df_prod[qty_col_p] = pd.to_numeric(df_prod[qty_col_p], errors="coerce").fillna(0)

                # 공정 중복 입력 제거 후 실제 생산 수량 계산
                if lot_col_p and qty_col_p:
                    df_unique_lot = df_prod.groupby(lot_col_p)[qty_col_p].max().reset_index()
                    total_qty = df_unique_lot[qty_col_p].sum()
                else:
                    total_qty = df_prod[qty_col_p].sum() if qty_col_p else 0

                # 불량 수량 집계
                total_defect = 0
                defect_qty_col = None
                defect_date_col = None
                defect_item_col = None

                if not df_defect.empty:
                    for col in df_defect.columns:
                        if "수량" in col:
                            defect_qty_col = col
                        elif "일자" in col or "날짜" in col or "타임스탬프" in col:
                            defect_date_col = col
                        elif "자재" in col or "품목" in col or "부품" in col:
                            defect_item_col = col

                    if defect_qty_col:
                        df_defect[defect_qty_col] = pd.to_numeric(df_defect[defect_qty_col], errors="coerce").fillna(0)
                        total_defect = df_defect[defect_qty_col].sum()

                total_output = total_qty + total_defect
                overall_defect_rate = (total_defect / total_output * 100) if total_output > 0 else 0

                # 상단 KPI 요약 카드
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

                # 시각화 차트 세션
                c1, c2 = st.columns([1, 1])

                with c1:
                    st.markdown("##### 📊 품목(제품)별 실제 생산 수량")
                    if lot_col_p and qty_col_p:
                        # [핵심 수정] LOT 번호에서 품목명 원형을 손상 없이 완벽히 추출하는 정제 함수
                        def extract_item_code(lot_str):
                            lot_str = str(lot_str).strip()
                            # 1. 언더바(_)나 공백( ) 기준으로 구분
                            parts = re.split(r'[_ ]', lot_str)
                            item_part = parts[0]
                            
                            # 2. 하이픈 뒤에 6자리 이상의 날짜/시리얼(예: -261001)만 깔끔하게 제거하고, 
                            # FIX5550S-18 형태의 규격 하이픈은 온전히 유지
                            item_part = re.sub(r'-\d{6,}$', '', item_part)
                            return item_part if item_part else lot_str

                        df_unique_lot["품목코드"] = df_unique_lot[lot_col_p].apply(extract_item_code)
                        grouped_p = df_unique_lot.groupby("품목코드")[qty_col_p].sum().reset_index().sort_values(by=qty_col_p, ascending=False)

                        # --- 보기 범위 선택 필터 (드롭다운) ---
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

                        # 품목 개수에 맞춘 동적 높이 계산 (최소 380px)
                        dynamic_height = max(380, len(display_df) * 35 + 60)

                        # 가로 막대 차트 (orientation='h')
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
                            margin=dict(l=150, r=20, t=10, b=40),  # 품목명이 길어저도 안잘리게 좌측 여백(l=150) 대폭 확장
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

                # 자재별 불량 발생 내역 (날짜 및 사유 상세)
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

                # 원본 생산일지 상세 데이터
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
                    if "수량" in col:
                        d_qty_col = col
                    elif "자재" in col or "품목" in col or "부품" in col:
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
                st.metric("⚠️ 불량 폐기 누적량", f"{int(defect_qty):,} EA", delta=f"-{int(defect_qty):,} EA" if defect_qty > 0 else "0", delta_color="inverse")
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
# [Tab 5] 안전재고 시뮬레이터
# ------------------------------------------
with tab5:
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
