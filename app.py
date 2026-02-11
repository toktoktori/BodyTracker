import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from scipy import stats
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# 1. 페이지 설정
st.set_page_config(page_title="V-Taper Tracker Pro", layout="wide")
st.title("🔥 Power-Building Slope Tracker : Google Sheets Edition")

# --- [핵심] 구글 시트 연결 함수 ---
@st.cache_resource
def get_google_sheet():
    try:
        # Streamlit Secrets에서 키 가져오기
        key_dict = dict(st.secrets["gcp_service_account"])
        
        # [수정됨] 구글 인증 범위 설정 (드라이브 권한 추가!)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
        client = gspread.authorize(creds)
        
        # 시트 열기
        sheet = client.open("V-Taper-Tracker").sheet1
        return sheet
    except Exception as e:
        st.error(f"🚨 연결 에러 발생: {str(e)}")
        return None

# 시트 연결 시도
sheet = get_google_sheet()

# 데이터 불러오기 함수 (에러 방지 강화 버전)
def load_data():
    if sheet is None:
        return pd.DataFrame(columns=['Date', 'Weight', 'SMM'])
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # 만약 시트에 제목이 없어서 컬럼이 다를 경우를 대비
        expected_cols = ['Date', 'Weight', 'SMM']
        if not all(col in df.columns for col in expected_cols):
            # 컬럼명이 일치하지 않으면 빈 데이터프레임 반환 후 안내
            return pd.DataFrame(columns=expected_cols)
            
        return df
    except Exception as e:
        return pd.DataFrame(columns=['Date', 'Weight', 'SMM'])

# 초기 데이터 로드
df = load_data()

# 2. 사이드바: 데이터 입력
with st.sidebar:
    st.header("📝 오늘의 기록")
    input_date = st.date_input("날짜", datetime.now())
    input_weight = st.number_input("체중 (kg)", min_value=0.0, step=0.1, format="%.1f")
    input_smm = st.number_input("골격근량 (kg)", min_value=0.0, step=0.1, format="%.1f")
    
    if st.button("💾 데이터 저장하기"):
        if sheet:
            date_str = input_date.strftime("%Y-%m-%d")
            new_row = [date_str, input_weight, input_smm]
            sheet.append_row(new_row)
            st.success("✅ 구글 시트에 저장 완료!")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("연결이 안 되어 저장할 수 없습니다.")

# --- [핵심 엔진] 기울기 계산 함수 ---
def calculate_slope(dataframe, days):
    if dataframe.empty or 'Date' not in dataframe.columns:
        return None
        
    dataframe['Date_Obj'] = pd.to_datetime(dataframe['Date'])
    cutoff_date = datetime.now() - timedelta(days=days)
    recent_df = dataframe[dataframe['Date_Obj'] >= cutoff_date].copy()
    
    if len(recent_df) < 2:
        return None
    
    recent_df['Date_Num'] = recent_df['Date_Obj'].map(datetime.toordinal)
    slope, intercept, r_value, p_value, std_err = stats.linregress(recent_df['Date_Num'], recent_df['Weight'])
    
    return {
        "slope": slope,
        "r_squared": r_value**2,
        "count": len(recent_df),
        "current_weight": recent_df['Weight'].iloc[-1]
    }

# --- 분석 UI 함수 ---
def display_analysis(col, title, days, dataframe):
    with col:
        st.subheader(f"{title}")
        res = calculate_slope(dataframe, days)
        val_daily, delta_weekly, val_jeff, delta_jeff_kg = "-", None, "-", None
        
        if res:
            slope, current_weight = res['slope'], res['current_weight']
            val_daily = f"{slope:.3f} kg/day"
            delta_weekly = f"{(slope * 7):.2f} kg/week"
            monthly_gain_kg = slope * 30
            monthly_gain_percent = (monthly_gain_kg / current_weight) * 100
            val_jeff = f"{monthly_gain_percent:.2f} % / 30일"
            delta_jeff_kg = f"{monthly_gain_kg:.2f} kg / 30일"

        st.metric(label=f"변화량 ({days}일 기준)", value=val_daily, delta=delta_weekly)
        st.write("---")
        st.markdown(f"**📊 Jeff's Score (%/월)**")
        st.metric(label="월간 예상 성장률", value=val_jeff, delta=delta_jeff_kg)
        
        if res:
            if monthly_gain_percent > 1.5: st.error("🚨 [Dirty Bulk] 주의")
            elif 0.5 <= monthly_gain_percent <= 1.0: st.success("💎 [Lean Bulk] 이상적")
            elif monthly_gain_percent < 0: st.warning("📉 [Cutting] 중")
        else:
            st.info(f"👉 {days}일 데이터 부족")

# 3. 메인 화면 로직 (Tab2 포함 완전체)
if not df.empty and 'Date' in df.columns and len(df) > 0:
    tab1, tab2 = st.tabs(["📊 듀얼 분석", "📋 시트 확인"])
    
    # 탭 1: 그래프 및 분석
    with tab1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['Date'], y=df['Weight'], mode='lines+markers', name='체중(kg)', line=dict(color='firebrick')))
        fig.add_trace(go.Scatter(x=df['Date'], y=df['SMM'], mode='lines+markers', name='근육량(kg)', line=dict(color='royalblue')))
        st.plotly_chart(fig, use_container_width=True)
        st.divider()
        
        col1, col2 = st.columns(2)
        display_analysis(col1, "⏱️ 최근 14일", 14, df)
        display_analysis(col2, "📅 최근 30일", 30, df)

    # 탭 2: 데이터 관리 (수정 및 삭제 기능 추가)
    with tab2:
        st.subheader("🛠️ 데이터 수정 및 삭제")
        st.caption("💡 표에서 값을 직접 더블클릭해 수정하거나, 행을 선택해 삭제(Del 키)할 수 있습니다.")
        
        # 1. 엑셀 같은 편집기 표시 (수정 가능 모드)
        # num_rows="dynamic"을 주면 행 추가/삭제도 가능해집니다.
        edited_df = st.data_editor(
            df.sort_values(by='Date', ascending=False),
            use_container_width=True,
            num_rows="dynamic",
            key="data_editor"
        )
        
        st.warning("⚠️ 수정을 마치면 아래 [동기화] 버튼을 꼭 눌러야 구글 시트에 반영됩니다!")
        
        # 2. 동기화 버튼
        if st.button("🔄 수정사항 구글 시트에 동기화하기", type="primary"):
            try:
                if sheet:
                    # 데이터프레임의 날짜 형식을 문자열로 통일 (오류 방지)
                    save_df = edited_df.copy()
                    save_df['Date'] = save_df['Date'].astype(str)
                    
                    # 구글 시트 싹 비우고 새로 쓰기 (가장 확실한 방법)
                    sheet.clear()
                    
                    # 헤더(제목) 넣기
                    sheet.append_row(save_df.columns.tolist())
                    
                    # 내용물 넣기
                    # 판다스 데이터를 리스트로 변환해서 한 번에 업로드
                    sheet.append_rows(save_df.values.tolist())
                    
                    st.success("✅ 구글 시트가 성공적으로 업데이트되었습니다!")
                    st.cache_data.clear() # 캐시 비우기
                    st.rerun() # 새로고침
            except Exception as e:
                st.error(f"저장 중 오류 발생: {e}")

else:
    # 데이터가 아예 없거나 컬럼명이 틀렸을 때 안내
    st.info("👈 왼쪽에서 데이터를 입력하고 '저장'을 눌러주세요!")
    st.warning("💡 만약 데이터를 넣었는데도 이 메시지가 뜬다면, 구글 시트의 1행이 'Date', 'Weight', 'SMM'으로 되어 있는지 확인해 주세요.")

