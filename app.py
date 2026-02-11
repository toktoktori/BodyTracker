import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from scipy import stats
from datetime import datetime, timedelta
import os

# 1. 페이지 설정
st.set_page_config(page_title="V-Taper Tracker Pro", layout="wide")
st.title("🔥 Power-Building Slope Tracker : Jeff Nippard Edition")

# 2. 데이터 파일 관리
FILE_NAME = 'body_data.csv'

def load_data():
    if os.path.exists(FILE_NAME):
        return pd.read_csv(FILE_NAME)
    else:
        return pd.DataFrame(columns=['Date', 'Weight', 'SMM'])

df = load_data()

# 3. 사이드바: 데이터 입력
with st.sidebar:
    st.header("📝 오늘의 기록")
    input_date = st.date_input("날짜", datetime.now())
    input_weight = st.number_input("체중 (kg)", min_value=0.0, step=0.1, format="%.1f")
    input_smm = st.number_input("골격근량 (kg)", min_value=0.0, step=0.1, format="%.1f")
    
    if st.button("💾 데이터 저장하기"):
        new_data = pd.DataFrame({
            'Date': [input_date],
            'Weight': [input_weight],
            'SMM': [input_smm]
        })
        new_data['Date'] = new_data['Date'].astype(str)
        df = pd.concat([df, new_data], ignore_index=True)
        df = df.sort_values(by='Date')
        df = df.drop_duplicates(subset=['Date'], keep='last')
        df.to_csv(FILE_NAME, index=False)
        st.success("저장 완료!")
        st.rerun()

# --- [핵심 엔진] 기울기 계산 함수 ---
def calculate_slope(dataframe, days):
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

# --- [분석 및 피드백 생성 함수 (UI 유지 버전)] ---
def display_analysis(col, title, days, dataframe):
    with col:
        st.subheader(f"{title}")
        res = calculate_slope(dataframe, days)
        
        val_daily = "-"
        delta_weekly = None
        val_jeff = "-"
        delta_jeff_kg = None
        
        if res:
            slope = res['slope']
            current_weight = res['current_weight']
            val_daily = f"{slope:.3f} kg/day"
            delta_weekly = f"{(slope * 7):.2f} kg/week"
            monthly_gain_kg = slope * 30
            monthly_gain_percent = (monthly_gain_kg / current_weight) * 100
            val_jeff = f"{monthly_gain_percent:.2f} % / 30일"
            delta_jeff_kg = f"{monthly_gain_kg:.2f} kg / 30일 (예상)"

        st.metric(label=f"일일/주간 변화량 ({days}일 기준)", value=val_daily, delta=delta_weekly)
        st.write("---")
        st.markdown(f"**📊 Jeff's Score (체중 대비 월간 성장률)**")
        st.metric(label="월간 예상 성장률 (%)", value=val_jeff, delta=delta_jeff_kg)
        
        if res:
            st.caption(f"데이터: {res['count']}개 | 신뢰도(R²): {res['r_squared']:.2f}")
            if monthly_gain_percent > 1.5:
                st.error("🚨 [Dirty Bulk] 너무 빠릅니다! (지방 증가 주의)")
            elif 1.0 < monthly_gain_percent <= 1.5:
                st.warning("🔥 [Fast Lane] 초급자 속도 (중급자라면 주의)")
            elif 0.5 <= monthly_gain_percent <= 1.0:
                st.success("💎 [Lean Bulk] 이상적인 황금 구간 (중급자 추천)")
            elif 0.25 <= monthly_gain_percent < 0.5:
                st.info("🐢 [Steady] 신중한 증량 (상급자 추천)")
            elif 0 <= monthly_gain_percent < 0.25:
                st.info("⚖️ [Maintenance] 유지보수 구간")
            else:
                st.warning("📉 [Cutting] 체중 감소 중")
        else:
            st.info(f"👉 최근 {days}일 간의 데이터가 2개 이상 필요합니다.")

# 4. 메인 화면 구성
if not df.empty:
    tab1, tab2 = st.tabs(["📊 듀얼 분석 (14vs30)", "📋 데이터 관리 (수정/삭제)"])
    
    with tab1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['Date'], y=df['Weight'], mode='lines+markers', name='체중(kg)', line=dict(color='firebrick', width=3)))
        fig.add_trace(go.Scatter(x=df['Date'], y=df['SMM'], mode='lines+markers', name='골격근량(kg)', line=dict(color='royalblue', width=3)))
        fig.update_layout(title='전체 신체 변화 트렌드', hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
        st.divider()
        col1, col2 = st.columns(2)
        display_analysis(col1, "⏱️ 최근 14일 (단기 컨디션)", 14, df)
        display_analysis(col2, "📅 최근 30일 (장기 성장률)", 30, df)

    with tab2:
        st.subheader("📋 데이터 목록 (엑셀 모드)")
        df_for_edit = df.copy()
        df_for_edit['Date'] = pd.to_datetime(df_for_edit['Date']).dt.date
        edited_df = st.data_editor(
            df_for_edit.sort_values(by='Date', ascending=False),
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Date": st.column_config.DateColumn("날짜", format="YYYY-MM-DD"),
                "Weight": st.column_config.NumberColumn("체중 (kg)", format="%.1f"),
                "SMM": st.column_config.NumberColumn("골격근량 (kg)", format="%.1f")
            },
            key="data_editor"
        )
        if st.button("💾 변경사항 저장하기", type="primary"):
            try:
                edited_df['Date'] = edited_df['Date'].astype(str)
                edited_df = edited_df.sort_values(by='Date')
                edited_df.to_csv(FILE_NAME, index=False)
                st.success("✅ 데이터가 성공적으로 수정되었습니다!")
                st.rerun()
            except Exception as e:
                st.error(f"저장 중 오류가 발생했습니다: {e}")
else:
    st.info("👈 왼쪽 사이드바에서 첫 번째 데이터를 입력해주세요!")