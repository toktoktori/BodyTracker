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
        # .to_dict()를 사용하여 확실하게 딕셔너리로 변환
        key_dict = dict(st.secrets["gcp_service_account"])
        
        # 구글 인증 범위 설정
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
        client = gspread.authorize(creds)
        
        # 시트 열기
        sheet = client.open("V-Taper-Tracker").sheet1
        return sheet
    except Exception as e:
        st.error(f"🚨 연결 에러 발생: {str(e)}")
        # 디버깅용 힌트 (보안상 키 전체 노출 금지)
        if "private_key" in str(e):
             st.error("힌트: Private Key 형식이 잘못되었습니다.")
        return None

# 시트 연결 시도
sheet = get_google_sheet()

# 데이터 불러오기 함수
def load_data():
    if sheet is None:
        return pd.DataFrame(columns=['Date', 'Weight', 'SMM'])
    try:
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=['Date', 'Weight', 'SMM'])
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"데이터 읽기 에러: {e}")
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

# 3. 메인 화면
if not df.empty:
    tab1, tab2 = st.tabs(["📊 듀얼 분석", "📋 시트 확인"])
    with tab1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['Date'], y=df['Weight'], mode='lines+markers', name='체중(kg)', line=dict(color='firebrick')))
        fig.add_trace(go.Scatter(x=df['Date'], y=df['SMM'], mode='lines+markers', name='근육량(kg)', line=dict(color='royalblue')))
        st.plotly_chart(fig, use_container_width=True)
        st.divider()
        col1, col2 = st.columns(2)
        display_analysis(col1, "⏱️ 최근 14일", 14, df)
        display_analysis(col2, "📅 최근 30일", 30, df)
    with tab2:
        st.subheader("📋 구글 시트 실시간 데이터")
        st.dataframe(df.sort_values(by='Date', ascending=False), use_container_width=True)
        if st.button("🔄 새로고침"):
            st.cache_data.clear()
            st.rerun()
else:
    if sheet:
        st.info("👈 데이터를 입력해주세요! (구글 시트에 저장됩니다)")
    else:
        st.error("서버 연결에 실패했습니다. Secrets 설정을 확인해주세요.")
