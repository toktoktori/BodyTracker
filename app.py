import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from scipy import stats
from datetime import datetime, timedelta
import os

# 1. 페이지 설정
st.set_page_config(page_title="V-Taper Tracker", layout="wide")
st.title("🔥 Power-Building Slope Tracker : Simple CSV Edition")

# --- [핵심] CSV 파일 관리 함수 ---
CSV_FILE = 'data.csv'

def load_data():
    if not os.path.exists(CSV_FILE):
        return pd.DataFrame(columns=['Date', 'Weight', 'SMM'])
    try:
        df = pd.read_csv(CSV_FILE)
        return df
    except:
        return pd.DataFrame(columns=['Date', 'Weight', 'SMM'])

def save_data(df):
    df.to_csv(CSV_FILE, index=False)

# 초기 데이터 로드
df = load_data()

# 2. 사이드바: 데이터 입력
with st.sidebar:
    st.header("📝 오늘의 기록")
    input_date = st.date_input("날짜", datetime.now())
    input_weight = st.number_input("체중 (kg)", min_value=0.0, step=0.1, format="%.1f")
    input_smm = st.number_input("골격근량 (kg)", min_value=0.0, step=0.1, format="%.1f")
    
    if st.button("💾 데이터 저장하기"):
        date_str = input_date.strftime("%Y-%m-%d")
        new_row = pd.DataFrame({'Date': [date_str], 'Weight': [input_weight], 'SMM': [input_smm]})
        
        # 날짜 중복 체크 (덮어쓰기 로직)
        if not df.empty and date_str in df['Date'].values:
            df = df[df['Date'] != date_str]
        
        df = pd.concat([df, new_row], ignore_index=True)
        save_data(df)
        
        st.success("✅ 저장 완료!")
        st.cache_data.clear()
        st.rerun()

# --- 분석 엔진 ---
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
        "current_weight": recent_df['Weight'].iloc[-1]
    }

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
    tab1, tab2 = st.tabs(["📊 듀얼 분석", "🛠️ 데이터 관리"])
    
    with tab1:
        # 날짜순 정렬 후 그래프 그리기
        plot_df = df.sort_values(by='Date')
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['Weight'], mode='lines+markers', name='체중(kg)', line=dict(color='firebrick')))
        fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['SMM'], mode='lines+markers', name='근육량(kg)', line=dict(color='royalblue')))
        st.plotly_chart(fig, use_container_width=True)
        st.divider()
        col1, col2 = st.columns(2)
        display_analysis(col1, "⏱️ 최근 14일", 14, df)
        display_analysis(col2, "📅 최근 30일", 30, df)

    with tab2:
        st.subheader("🛠️ 데이터 수정 및 삭제")
        # 엑셀처럼 편집 가능한 데이터프레임
        edited_df = st.data_editor(
            df.sort_values(by='Date', ascending=False),
            use_container_width=True,
            num_rows="dynamic",
            key="csv_editor"
        )
        
        if st.button("💾 수정사항 저장하기", type="primary"):
            save_data(edited_df)
            st.success("✅ CSV 파일에 저장되었습니다!")
            st.cache_data.clear()
            st.rerun()
else:
    st.info("👈 왼쪽에서 데이터를 입력해주세요!")
