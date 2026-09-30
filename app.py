import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="주간 업무 보고 대시보드", layout="wide")

# ---------------------------------------------------------
# 0. 구글 시트 데이터 연결 (st.connection)
# ---------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

# 데이터 불러오기 (캐싱 주기 설정: ttl=60)
df_production = conn.read(worksheet="생산목표", ttl=60)
df_inventory = conn.read(worksheet="부품재고", ttl=60)
df_issues = conn.read(worksheet="특이사항", ttl=60)

st.title("📋 주간 업무 보고 대시보드")
st.caption(f"기준일자: {pd.Timestamp.now().strftime('%Y.%m.%d')}")

# ---------------------------------------------------------
# 1. 주간 목표 / 생산 / 차주 목표 현황
# ---------------------------------------------------------
st.header("1. 주간 목표 / 생산 / 차주 생산 목표")

col1, col2 = st.columns(2)

with col1:
    st.subheader("🎯 금주 생산 목표 및 실적")
    st.dataframe(df_production[['주차', '품목', '목표수량', '생산수량', '상태']], use_container_width=True)

with col2:
    st.subheader("📅 차주 생산 목표 및 완제품 재고")
    # 차주 생산목표 데이터 표출
    st.dataframe(df_production[df_production['주차'] == '차주목표'][['품목', '목표수량']], use_container_width=True)

st.divider()

# ---------------------------------------------------------
# 2. 생산일지 및 부품재고 현황
# ---------------------------------------------------------
st.header("2. 생산일지 및 부품재고 현황")

tab1, tab2 = st.tabs(["📦 주요 부품/완제품 재고", "📜 상세 생산일지"])

with tab1:
    st.dataframe(df_inventory, use_container_width=True)

with tab2:
    st.info("💡 실시간 생산일지 상세 내역입니다.")
    # 필요시 추가 상세 표출

st.divider()

# ---------------------------------------------------------
# 3. 특이사항 및 주요 이벤트 (대시보드 상에서 바로 수정/등록)
# ---------------------------------------------------------
st.header("3. 특이사항 및 주요 이벤트")
st.write("주간 발생 이슈, GMP, 멸균, 부품 변경 등의 특이사항을 아래 표에서 직접 수정 및 추가할 수 있습니다.")

# Streamlit data_editor를 통한 실시간 편집
edited_df = st.data_editor(
    df_issues,
    num_rows="dynamic", # 행 추가/삭제 가능
    column_config={
        "No": st.column_config.NumberColumn("No", disabled=True),
        "구분": st.column_config.SelectboxColumn("구분", options=["부품", "GMP", "멸균", "생산", "기타"]),
        "이벤트": st.column_config.TextColumn("이벤트"),
        "진행상황": st.column_config.TextColumn("진행상황"),
        "향후 조치 계획": st.column_config.TextColumn("향후 조치 계획"),
        "완료기한": st.column_config.TextColumn("완료기한(Due Date)"),
        "상태": st.column_config.SelectboxColumn("상태", options=["🔄 [진행중]", "✅ [완료]", "⏸️ [보류]"])
    },
    use_container_width=True,
    key="issue_editor"
)

# 저장 버튼 클릭 시 구글 시트로 변경사항 업데이트
if st.button("💾 특이사항 저장 및 업데이트"):
    try:
        conn.update(worksheet="특이사항", data=edited_df)
        st.success("성공적으로 저장되었습니다!")
        st.rerun()
    except Exception as e:
        st.error(f"저장 중 오류가 발생했습니다: {e}")
