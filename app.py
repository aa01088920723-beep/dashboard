import pandas as pd
import streamlit as st
import urllib.parse

# 페이지 기본 설정
st.set_page_config(page_title="주간 업무보고 대시보드", layout="wide")

st.title("📊 주간 업무보고 통합 대시보드")
st.caption("버튼(탭)을 클릭하여 각 항목의 현황을 실시간으로 확인하세요.")

# 구글 스프레드시트 ID
DOCUMENT_ID = "1cJEuRJ8Sbgb-PF0-xta0j7J2MqoYlATWXRk907DZPnc"

# 구글 시트 데이터를 안전하게 불러오는 함수 (UTF-8 인코딩 적용)
@st.cache_data(ttl=5)
def load_sheet_data(sheet_name):
    encoded_name = urllib.parse.quote(sheet_name)
    url = f"https://docs.google.com/spreadsheets/d/{DOCUMENT_ID}/gviz/tq?tqx=out:csv&sheet={encoded_name}"
    return pd.read_csv(url, encoding='utf-8')

# 상단 탭(버튼) 구성
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 차주 생산목표 & 완제품 재고", 
    "📋 생산일지", 
    "📦 부품/재고 마스터시트", 
    "⚙️ BOM 현황"
])

# 1. 차주 생산목표 및 완제품 재고 현황 (외부 사이트 임베드/링크)
with tab1:
    st.subheader("차주 생산목표 및 완제품 재고 현황")
    st.info("💡 아래 '페이지 열기' 버튼을 누르시면 해당 페이지로 바로 이동합니다.")
    st.link_button("🔗 완제품 재고 현황 페이지 열기", "https://m.site.naver.com/2a4rF", use_container_width=True)
    
    # 웹페이지 화면을 대시보드 안에 직접 띄우기 (iframe 방식)
    st.components.v1.iframe("https://m.site.naver.com/2a4rF", height=600, scrolling=True)

# 2. 생산일지
with tab2:
    st.subheader("생산일지 현황 (구글 설문지 실시간 연동)")
    try:
        df_prod = load_sheet_data("생산일지")
        st.dataframe(df_prod, use_container_width=True)
    except Exception as e:
        st.error(f"생산일지 데이터를 불러오는 중 오류가 발생했습니다: {e}")

# 3. 부품 및 재고 마스터시트
with tab3:
    st.subheader("부품 및 재고 마스터시트")
    try:
        df_master = load_sheet_data("마스터시트")
        st.dataframe(df_master, use_container_width=True)
    except Exception as e:
        st.error(f"마스터시트 데이터를 불러오는 중 오류가 발생했습니다: {e}")

# 4. BOM 현황
with tab4:
    st.subheader("BOM 현황")
    try:
        df_bom = load_sheet_data("BOM")
        st.dataframe(df_bom, use_container_width=True)
    except Exception as e:
        st.error(f"BOM 데이터를 불러오는 중 오류가 발생했습니다: {e}")