import re
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title='의료기기 생산 및 재고/불량 통합 대시보드', layout='wide'
)

st.title('📊 의료기기 생산 및 부품 재고·불량 통합 대시보드')

# ==========================================
# 1. 구글 시트 전체 데이터 로딩 (기존 기능 유지)
# ==========================================
try:
  # 기존에 사용 중이신 연결 세션을 통해 각 시트 데이터를 모두 불러옵니다.
  df_production = conn.read(worksheet='생산일지', ttl=0)  # 생산일지 (Form_Responses)
  df_defect = conn.read(worksheet='불량관리', ttl=0)  # 불량관리 (Form_Responses2)
  df_master = conn.read(worksheet='마스터시트', ttl=0)  # 마스터시트
  df_bom = conn.read(worksheet='BOM', ttl=0)  # BOM 시트
  df_receiving = conn.read(worksheet='입고일지', ttl=0)  # 입고일지
except Exception as e:
  # 로컬 테스트 및 예외 처리용 빈 데이터프레임
  df_production = pd.DataFrame()
  df_defect = pd.DataFrame()
  df_master = pd.DataFrame()
  df_bom = pd.DataFrame()
  df_receiving = pd.DataFrame()

# ==========================================
# 2. 데이터 전처리 및 정제
# ==========================================
# (1) 불량 데이터 전처리 ('불량관리' 시트)
if not df_defect.empty:
  df_defect['불량수량'] = pd.to_numeric(
      df_defect['불량수량'], errors='coerce'
  ).fillna(0)


  # '33 18G-110 주사침' 형태에서 숫자 순번을 제외하고 자재/품목명만 추출
  def extract_item_name(val):
    val = str(val).strip()
    match = re.sub(r'^\d+\s*', '', val)
    return match if match else val


  df_defect['품목명'] = df_defect['불량자재'].apply(extract_item_name)
else:
  df_defect['품목명'] = []
  df_defect['불량수량'] = 0

# (2) 생산일지 데이터 전처리
if not df_production.empty:
  df_production['생산수량'] = pd.to_numeric(
      df_production['생산수량'], errors='coerce'
  ).fillna(0)

# ==========================================
# 3. 상단 통합 요약 지표 (양품 / 불량 / 전체 불량률)
# ==========================================
total_prod = df_production['생산수량'].sum() if not df_production.empty else 0
total_defect = df_defect['불량수량'].sum() if not df_defect.empty else 0
total_output_sum = total_prod + total_defect
overall_defect_rate = (
    (total_defect / total_output_sum * 100) if total_output_sum > 0 else 0
)

col1, col2, col3 = st.columns(3)
col1.metric('총 양품 생산수량', f'{int(total_prod):,} EA')
col2.metric(
    '총 불량 수량',
    f'{int(total_defect):,} EA',
    delta=f'-{int(total_defect)}',
    delta_color='inverse',
)
col3.metric('전체 공정 불량률', f'{overall_defect_rate:.2f} %')

st.divider()

# ==========================================
# 4. 실시간 생산일지 분석 및 품목별 생산 비중 (LOT별 점유율 대체)
# ==========================================
st.subheader('📈 품목별 생산 점유율 현황')

if not df_production.empty and '공정명(단축키)' in df_production.columns:
  prod_share = (
      df_production.groupby('공정명(단축키)')['생산수량']
      .sum()
      .reset_index()
  )
  prod_share['점유율(%)'] = (
      prod_share['생산수량'] / total_prod * 100
  ).round(2)

  col_a, col_b = st.columns([1, 1])
  with col_a:
    st.dataframe(
        prod_share, hide_index=True, use_container_width=True
    )
  with col_b:
    st.bar_chart(prod_share.set_index('공정명(단축키)')['생산수량'])
else:
  st.info('생산일지 데이터가 없습니다.')

st.divider()

# ==========================================
# 5. 품목/자재별 불량 현황 및 불량률 분석 (신규 추가)
# ==========================================
st.subheader('📉 자재/품목별 불량 발생 분석')

if not df_defect.empty:
  defect_summary = (
      df_defect.groupby('품목명')
      .agg(
          불량수량=('불량수량', 'sum'),
          대표불량사유=(
              '불량 사유 및 특이사항',
              lambda x: ', '.join(x.dropna().unique()),
          ),
      )
      .reset_index()
  )

  defect_summary = defect_summary.sort_values(
      by='불량수량', ascending=False
  )
  defect_summary['불량 비중(%)'] = (
      defect_summary['불량수량'] / total_defect * 100
  ).round(2)

  st.dataframe(
      defect_summary,
      column_config={
          '품목명': '자재/부품명',
          '불량수량': st.column_config.NumberColumn(
              '불량 수량(EA)', format='%d'
          ),
          '불량 비중(%)': st.column_config.NumberColumn(
              '전체 불량 대비 비중', format='%.2f %%'
          ),
          '대표불량사유': '주요 불량 사유',
      },
      use_container_width=True,
      hide_index=True,
  )

  st.bar_chart(defect_summary.set_index('품목명')['불량수량'])
else:
  st.info('등록된 불량 데이터가 없습니다.')

st.divider()

# ==========================================
# 6. 마스터시트 및 부품 재고 현황 (기존 유지)
# ==========================================
st.subheader('📦 부품 마스터 및 현재고 현황')
if not df_master.empty:
  st.dataframe(df_master, use_container_width=True, hide_index=True)
else:
  st.info('마스터시트 데이터가 없습니다.')
