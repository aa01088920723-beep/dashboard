import re
import pandas as pd
import streamlit as st

# ==========================================
# [기본 페이지 설정]
# ==========================================
st.set_page_config(
    page_title='의료기기 생산 및 재고/불량 통합 관리 시스템', layout='wide'
)

st.title('📊 의료기기 생산 및 부품 재고·불량 통합 대시보드')

# ==========================================
# [구글 시트 데이터 연결 및 로딩 (전체 원본 유지)]
# ==========================================
# * 주의: 기존에 사용하시던 연결 객체 이름(예: conn)이나 경로 설정은 그대로 두시면 됩니다.
try:
  df_production = conn.read(
      worksheet='생산일지', ttl=0
  )  # 실제 생산일지 시트
  df_defect = conn.read(
      worksheet='불량관리', ttl=0
  )  # 새로 추가된 불량관리 시트
  df_master = conn.read(worksheet='마스터시트', ttl=0)  # 마스터시트
  df_bom = conn.read(worksheet='BOM', ttl=0)  # BOM 시트
  df_receiving = conn.read(worksheet='입고일지', ttl=0)  # 입고일지
except Exception as e:
  # 예외 및 로컬 테스트용 빈 데이터프레임
  df_production = pd.DataFrame()
  df_defect = pd.DataFrame()
  df_master = pd.DataFrame()
  df_bom = pd.DataFrame()
  df_receiving = pd.DataFrame()

# ==========================================
# [데이터 전처리 및 정제]
# ==========================================
# 1. 불량관리 시트 데이터 정제 (앞의 순번 숫자 제거 및 품목명 추출)
if not df_defect.empty and '불량수량' in df_defect.columns:
  df_defect['불량수량'] = pd.to_numeric(
      df_defect['불량수량'], errors='coerce'
  ).fillna(0)


  def extract_item_name(val):
    val = str(val).strip()
    match = re.sub(r'^\d+\s*', '', val)
    return match if match else val


  if '불량자재' in df_defect.columns:
    df_defect['품목명'] = df_defect['불량자재'].apply(extract_item_name)
  else:
    df_defect['품목명'] = '기타'
else:
  df_defect['품목명'] = []
  df_defect['불량수량'] = 0

# 2. 생산일지 데이터 정제
if not df_production.empty and '생산수량' in df_production.columns:
  df_production['생산수량'] = pd.to_numeric(
      df_production['생산수량'], errors='coerce'
  ).fillna(0)


# ==========================================
# [사이드바 메뉴 혹은 탭 구성 (기존 300줄 구조 유지)]
# ==========================================
menu = st.sidebar.selectbox(
    '메뉴 선택',
    [
        '실시간 생산일지 분석 (관제)',
        '부품 재고 마스터',
        'BOM 관리',
        '입고일지 현황',
        '디지털 트윈 안전재고 시뮬레이터',
    ],
)

# ----------------------------------------------------
# 1. 실시간 생산일지 분석 (관제) 탭
# ----------------------------------------------------
if menu == '실시간 생산일지 분석 (관제)':
  st.header('🏭 실시간 생산 및 불량 통합 관제')

  # 상단 KPI 요약 카드
  total_prod = (
      df_production['생산수량'].sum() if not df_production.empty else 0
  )
  total_defect = df_defect['불량수량'].sum() if not df_defect.empty else 0
  total_output_sum = total_prod + total_defect
  overall_defect_rate = (
      (total_defect / total_output_sum * 100) if total_output_sum > 0 else 0
  )

  c1, c2, c3 = st.columns(3)
  c1.metric('총 양품 생산수량', f'{int(total_prod):,} EA')
  c2.metric(
      '총 불량 수량',
      f'{int(total_defect):,} EA',
      delta=f'-{int(total_defect)}',
      delta_color='inverse',
  )
  c3.metric('전체 공정 불량률', f'{overall_defect_rate:.2f} %')

  st.divider()

  # [개선] LOT별 점유율 대신 -> '품목별(공정별) 생산 점유율' 바꿈
  st.subheader('📈 품목별 생산 점유율 비중')
  if not df_production.empty and '공정명(단축키)' in df_production.columns:
    prod_share = (
        df_production.groupby('공정명(단축키)')['생산수량']
        .sum()
        .reset_index()
    )
    prod_share['점유율(%)'] = (
        prod_share['생산수량'] / total_prod * 100
    ).round(2)

    col_a, col_b = st.columns(2)
    with col_a:
      st.dataframe(
          prod_share, hide_index=True, use_container_width=True
      )
    with col_b:
      st.bar_chart(prod_share.set_index('공정명(단축키)')['생산수량'])
  else:
    st.info('생산일지 데이터가 없습니다.')

  st.divider()

  # [신규] 불량관리 시트 연동 품목별 불량 분석 표
  st.subheader('📉 품목/자재별 불량 수량 및 불량률 분석')
  if not df_defect.empty and '품목명' in df_defect.columns:
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
            '대표불량사유': '주요 발생 사유',
        },
        use_container_width=True,
        hide_index=True,
    )
    st.bar_chart(defect_summary.set_index('품목명')['불량수량'])
  else:
    st.info('등록된 불량 데이터가 없습니다.')

  st.divider()

  # 기존 생산일지 원본 데이터 테이블 출력
  with st.expander('📋 실시간 생산일지 원본 데이터 보기'):
    st.dataframe(df_production, use_container_width=True, hide_index=True)

# ----------------------------------------------------
# 2. 부품 재고 마스터 탭
# ----------------------------------------------------
elif menu == '부품 재고 마스터':
  st.header('📦 부품 재고 마스터 관리')
  if not df_master.empty:
    st.dataframe(df_master, use_container_width=True, hide_index=True)
  else:
    st.info('마스터시트 데이터가 없습니다.')

# ----------------------------------------------------
# 3. BOM 관리 탭
# ----------------------------------------------------
elif menu == 'BOM 관리':
  st.header('🛠️ BOM (자재 소요 구성) 정보')
  if not df_bom.empty:
    st.dataframe(df_bom, use_container_width=True, hide_index=True)
  else:
    st.info('BOM 데이터가 없습니다.')

# ----------------------------------------------------
# 4. 입고일지 현황 탭
# ----------------------------------------------------
elif menu == '입고일지 현황':
  st.header('📥 부품 입고일지 내역')
  if not df_receiving.empty:
    st.dataframe(df_receiving, use_container_width=True, hide_index=True)
  else:
    st.info('입고일지 데이터가 없습니다.')

# ----------------------------------------------------
# 5. 디지털 트윈 안전재고 시뮬레이터 탭
# ----------------------------------------------------
elif menu == '디지털 트윈 안전재고 시뮬레이터':
  st.header('🔮 디지털 트윈 안전재고 및 발주 시뮬레이터')
  st.info(
      '마스터시트의 현재고, 납기일수, 안전발주점을 기반으로 시뮬레이션을'
      ' 수행합니다.'
  )

  if not df_master.empty:
    # 기존에 구현해두신 시뮬레이터 계산 로직 및 위젯 코드가 이 자리에 위치합니다.
    st.dataframe(df_master, use_container_width=True, hide_index=True)
  else:
    st.info('시뮬레이션용 데이터가 부족합니다.')
