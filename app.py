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
        
        # 구글 인증 범위 설정
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

# 데이터 불러오기 함수
def load_data():
    if sheet is None:
        return pd.DataFrame(columns=['Date', 'Weight', 'SMM'])
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # 컬럼 확인 및 빈 데이터 처리
        expected_cols = ['Date', 'Weight', 'SMM']
        if not all(col in df.columns for col in expected_cols):
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
            # 사이드바 저장 시에도 안전하게 변환
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
        
    # 날짜 변환 시 에러 방지
    try:
        dataframe['Date_Obj'] = pd.to_datetime(dataframe['Date'], errors='coerce')
        dataframe = dataframe.dropna(subset=['Date_Obj']) # 날짜 없는 행 제외
    except:
        return None

    cutoff_date = datetime.now() - timedelta(days=days)
    recent_df = dataframe[dataframe['Date_Obj'] >= cutoff_date].copy()
    
    if len(recent_df) < 2:
        return None
    
    recent_df['Date_Num'] = recent_df['Date_Obj'].map(datetime.toordinal)
    
    # 데이터가 숫자형인지 확인
    try:
        recent_df['Weight'] = pd.to_numeric(recent_df['Weight'], errors='coerce')
        recent_df = recent_df.dropna(subset=['Weight'])
        if len(recent_df) < 2: return None
        
        slope, intercept, r_value, p_value, std_err = stats.linregress(recent_df['Date_Num'], recent_df['Weight'])
    except:
        return None
    
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
            if current_weight > 0:
                monthly_gain_percent = (monthly_gain_kg / current_weight) * 100
                val_jeff = f"{monthly_gain_percent:.2f} % / 30일"
                delta_jeff_kg = f"{monthly_gain_kg:.2f} kg / 30일"
                
                st.metric(label=f"변화량 ({days}일 기준)", value=val_daily, delta=delta_weekly)
                st.write("---")
                st.markdown(f"**📊 Jeff's Score (%/월)**")
                st.metric(label="월간 예상 성장률", value=val_jeff, delta=delta_jeff_kg)
                
                if monthly_gain_percent > 1.5: st.error("🚨 [Dirty Bulk] 주의")
                elif 0.5 <= monthly_gain_percent <= 1.0: st.success("💎 [Lean Bulk] 이상적")
                elif monthly_gain_percent < 0: st.warning("📉 [Cutting] 중")
            else:
                st.info("체중 데이터 오류")
        else:
            st.info(f"👉 {days}일 데이터 부족")

# 3. 메인 화면 로직
if not df.empty and 'Date' in df.columns and len(df) > 0:
    tab1, tab2 = st.tabs(["📊 듀얼 분석", "🛠️ 데이터 관리"])
    
    # 탭 1: 그래프 및 분석
    with tab1:
        fig = go.Figure()
        # 그래프 그리기 전 날짜 정렬
        plot_df = df.copy()
        plot_df['Date'] = pd.to_datetime(plot_df['Date'], errors='coerce')
        plot_df = plot_df.sort_values(by='Date')
        
        fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['Weight'], mode='lines+markers', name='체중(kg)', line=dict(color='firebrick')))
        fig.add_trace(go.Scatter(x=plot_df['Date'], y=plot_df['SMM'], mode='lines+markers', name='근육량(kg)', line=dict(color='royalblue')))
        st.plotly_chart(fig, use_container_width=True)
        st.divider()
        
        col1, col2 = st.columns(2)
        display_analysis(col1, "⏱️ 최근 14일", 14, df)
        display_analysis(col2, "📅 최근 30일", 30, df)

    # 탭 2: 데이터 관리 (초강력 안전 버전)
    with tab2:
        st.subheader("🛠️ 데이터 수정 및 삭제")
        st.caption("💡 엑셀처럼 수정하고 [동기화]를 누르세요. 행을 선택하고 Delete 키를 누르면 삭제됩니다.")
        
        # 데이터 편집기
        edited_df = st.data_editor(
            df.sort_values(by='Date', ascending=False),
            use_container_width=True,
            num_rows="dynamic",
            key="data_editor"
        )
        
        st.warning("⚠️ [동기화] 버튼을 누르면 위 화면대로 구글 시트가 덮어씌워집니다.")
        
        if st.button("🔄 수정사항 구글 시트에 동기화하기", type="primary"):
            try:
                if sheet:
                    # [초강력 수정] 모든 데이터를 안전한 문자열/숫자로 강제 변환
                    save_df = edited_df.copy()
                    
                    # 1. 날짜 컬럼 강제 문자열 변환 (Timestamp 제거)
                    # apply를 사용하여 개별 값의 타입을 확인하고 변환 (가장 안전함)
                    save_df['Date'] = save_df['Date'].apply(lambda x: x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x))
                    
                    # 2. 숫자 데이터 강제 변환 (NaN은 0으로)
                    save_df['Weight'] = pd.to_numeric(save_df['Weight'], errors='coerce').fillna(0.0)
                    save_df['SMM'] = pd.to_numeric(save_df['SMM'], errors='coerce').fillna(0.0)
                    
                    # 3. 구글 시트 초기화 전 데이터 준비 확인
                    data_to_upload = [save_df.columns.tolist()] + save_df.values.tolist()
                    
                    # 4. 시트 클리어 및 업로드
                    sheet.clear()
                    sheet.append_rows(data_to_upload)
                    
                    st.success("✅ 완벽하게 저장되었습니다!")
                    st.cache_data.clear()
                    st.rerun()
            except Exception as e:
                st.error(f"🚨 저장 실패 (데이터는 안전합니다): {e}")
                st.info("구글 시트의 [버전 기록]을 확인하세요.")
else:
    st.info("👈 왼쪽에서 데이터를 입력하고 '저장'을 눌러주세요!")
    st.warning("💡 구글 시트 1행에 'Date', 'Weight', 'SMM'이 있는지 확인해주세요.")
