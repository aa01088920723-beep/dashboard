import pandas as pd
import streamlit as st
import urllib.parse

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="주간 업무보고 대시보드 (TV전용)",
    page_icon="📊",
    layout="wide"
)

# 2. TV 최적화 스타일 (스크롤 최소화 & 대형 폰트)
st.markdown("""
    <style>
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 0rem !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 2.5rem !important;
        font-weight: 800 !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 1.2rem !important;
        font-weight: 700 !important;
    }
    button[data-baseweb="tab"] {
        font-size: 20px !important;
        font-weight: bold !important;
    }
    </style>
""", unsafe_allow_html=True)

DOCUMENT_ID = "1cJEuRJ8Sbgb-PF0-xta0j7J2MqoYlATWXRk907DZPnc"

@st.cache_data(ttl=5)
def load_sheet_data(sheet_name):
    encoded_name = urllib.parse.quote(sheet_name)
    url = f"https://docs.google.com/spreadsheets/d/{DOCUMENT_ID}/gviz/tq?tqx=out:csv&sheet={encoded_name}"
    return pd.read_csv(url, encoding='utf-8')

st.title("🖥️ 주간 업무보고 핵심 요약 대시보드")

# 탭 구성
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 생산일지 요약", 
    "📦 주요 재고 현황", 
    "⚙️ BOM 현황",
    "📈 완제품 재고 현황"
])

# 1. 생산일지 요약 (차트 + 최근 10건)
with tab1:
    try:
        df_prod = load_sheet_data("생산일지")
        df_prod['생산수량'] = pd.to_numeric(df_prod['생산수량'], errors='coerce').fillna(0)
        df_prod['불량수량'] = pd.to_numeric(df_prod['불량수량'], errors='coerce').fillna(0)

        # 상단 요약 KPI
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 생산량", f"{int(df_prod['생산수량'].sum()):,} EA")
        c2.metric("총 불량수량", f"{int(df_prod['불량수량'].sum()):,} EA")
        c3.metric("최근 작업일", str(df_prod['제조일자'].iloc[-1]) if '제조일자' in df_prod.columns else "-")
        c4.metric("누적 등록건수", f"{len(df_prod)} 건")

        st.divider()

        # 좌우 split: 좌측 차트 / 우측 최근 10건 표
        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.markdown("##### 📊 주요 공정별 생산량")
            if '공정명단축키)' in df_prod.columns:
                group_df = df_prod.groupby('공정명단축키)')['생산수량'].sum()
                st.bar_chart(group_df, height=350)

        with col_right:
            st.markdown("##### ⏱️ 최근 생산일지 기록 (최신 10건)")
            recent_df = df_prod.tail(10).iloc[::-1]
            st.dataframe(recent_df, use_container_width=True, height=350)

    except Exception as e:
        st.error(f"생산일지 불러오기 실패: {e}")

# 2. 재고 마스터시트 요약
with tab2:
    try:
        df_master = load_sheet_data("마스터시트")
        st.markdown("##### 📦 부품 및 재고 마스터 현황")
        st.dataframe(df_master, use_container_width=True, height=500)
    except Exception as e:
        st.error(f"마스터시트 불러오기 실패: {e}")

# 3. BOM 현황
with tab3:
    try:
        df_bom = load_sheet_data("BOM")
        st.markdown("##### ⚙️ BOM 현황")
        st.dataframe(df_bom, use_container_width=True, height=500)
    except Exception as e:
        st.error(f"BOM 불러오기 실패: {e}")

# 4. 외부 링크
with tab4:
    st.components.v1.iframe("https://m.site.naver.com/2a4rF", height=600, scrolling=True)
