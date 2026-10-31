from datetime import datetime
import importlib
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import data_loader
importlib.reload(data_loader)
from data_loader import (
    PRESET_UNIVERSES,
    TICKER_NAME_MAP,
    get_sp500_tickers,
    get_nyse_us_common_stocks,
    get_nasdaq_us_common_stocks,
    get_kospi_all_tickers,
    get_tickers_sectors,
    fetch_historical_data
)

import indicators
importlib.reload(indicators)
from indicators import (
    calculate_technical_indicators,
    extract_stock_summary,
    calculate_accumulation_box,
    calculate_higher_timeframe_trends,
    calculate_bnf_disparity,
    calculate_weekly_volatility_breakout
)

# --- 1. 페이지 설정 및 커스텀 스타일 ---
st.set_page_config(
    page_title="글로벌 모멘텀 주식 스크리너 (S&P 500, Nasdaq, NYSE, KOSPI)",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="auto"  # 모바일/태블릿에서는 화면을 가리지 않도록 반응형 자동 접힘
)

st.markdown("""
<style>
    /* 데스크톱 및 태블릿 기본 카드 */
    .metric-card {
        background-color: #1e222d;
        border-radius: 10px;
        padding: 14px 18px;
        border-left: 5px solid #2962ff;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        margin-bottom: 10px;
    }
    .metric-title {
        color: #9aa0a6;
        font-size: 0.82rem;
        margin-bottom: 4px;
        font-weight: 500;
    }
    .metric-value {
        color: #f8f9fa;
        font-size: 1.5rem;
        font-weight: 700;
        word-break: break-word;
    }
    .metric-sub {
        font-size: 0.8rem;
    }

    /* 모바일 기기(갤럭시 노트 스마트폰 및 세로 화면) 반응형 최적화 */
    @media (max-width: 768px) {
        .metric-card {
            padding: 10px 12px;
            margin-bottom: 8px;
        }
        .metric-title {
            font-size: 0.75rem;
        }
        .metric-value {
            font-size: 1.25rem;
        }
        .metric-sub {
            font-size: 0.72rem;
        }
        /* 모바일 터치 접근성을 위한 다운로드 버튼 높이 및 글자 크기 확보 */
        div[data-testid="stDownloadButton"] button {
            min-height: 46px !important;
            font-size: 0.95rem !important;
            font-weight: 600 !important;
        }
    }

    /* 맞춤형 다크 테마 데이터 테이블 (pyarrow 완전 미사용) */
    .custom-table-container {
        max-height: 430px;
        overflow-y: auto;
        overflow-x: auto;
        border: 1px solid #2a2e39;
        border-radius: 8px;
        background-color: #131722;
        margin-top: 10px;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
    }
    .custom-table-container table {
        width: 100%;
        border-collapse: collapse;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 0.88rem;
        color: #d1d4dc;
        text-align: right;
        white-space: nowrap;
    }
    .custom-table-container th {
        position: sticky;
        top: 0;
        background-color: #1e222d;
        color: #9aa0a6;
        padding: 11px 14px;
        font-weight: 600;
        border-bottom: 2px solid #2a2e39;
        z-index: 2;
        text-align: center;
    }
    .custom-table-container td {
        padding: 9px 14px;
        border-bottom: 1px solid #1e222d;
    }
    .custom-table-container td:first-child,
    .custom-table-container td:nth-child(2) {
        text-align: left;
        font-weight: 600;
    }
    .custom-table-container tr:hover td {
        background-color: #1e222d !important;
    }
</style>
""", unsafe_allow_html=True)


# --- 통화 포맷 헬퍼 ---
def is_korean_stock(ticker: str) -> bool:
    return ticker.endswith(".KS") or ticker.endswith(".KQ")

def format_currency(price: float, ticker: str) -> str:
    if pd.isna(price) or price is None:
        return "-"
    if is_korean_stock(ticker):
        return f"₩{int(round(price)):,}"
    return f"${price:.2f}"


# --- 2. 캐싱 디렉토리 로더 ---
@st.cache_data(ttl=86400, show_spinner=False)
def load_sp500_directory():
    return get_sp500_tickers()

@st.cache_data(ttl=86400, show_spinner=False)
def load_nyse_us_common_directory():
    return get_nyse_us_common_stocks()

@st.cache_data(ttl=86400, show_spinner=False)
def load_nasdaq_us_common_directory():
    return get_nasdaq_us_common_stocks()

@st.cache_data(ttl=86400, show_spinner=False)
def load_kospi_directory():
    return get_kospi_all_tickers()

@st.cache_data(ttl=1800, show_spinner=False)
def load_all_market_data(tickers_tuple, period="1y", interval="1d"):
    """
    3번 모드(BNF 25일선 이격도 매매) 및 지표 연산을 위해 interval='1d' 일봉 타임프레임으로 철저히 격리 호출합니다.
    """
    return fetch_historical_data(list(tickers_tuple), period=period, interval=interval)


# --- 3. 사이드바 컨트롤 ---
st.sidebar.title("🔍 글로벌 주식 스크리너")
st.sidebar.caption("S&P 500 · Nasdaq · NYSE 미국 보통주 · KOSPI 통합 분석")
st.sidebar.markdown("---")

# 1) 유니버스 선택
st.sidebar.subheader("1. 유니버스 선택")
universe_choice = st.sidebar.selectbox(
    "종목군 선택",
    options=[
        "S&P 500 (미국 대표 500대 기업)",
        "Nasdaq 전체 (미국 본토 순수 보통주)",
        "NYSE 전체 (미국 본토 순수 보통주)",
        "KOSPI 주요 종목 (시총 상위 40)",
        "KOSPI 전체 종목 (동적 로드)",
        "AI & 테크 성장주 (팔란티어, 아이온큐, 삼사라 등)",
        "NYSE 대표 우량주 & 산업주 (GE, 캐터필러 등)",
        "사용자 직접 입력 (Custom)"
    ],
    index=0
)

selected_tickers = []

if universe_choice == "S&P 500 (미국 대표 500대 기업)":
    sp500_all = load_sp500_directory()
    total_sp_cnt = len(sp500_all)
    st.sidebar.success(f"🇺🇸 S&P 500 편입 종목: 총 {total_sp_cnt:,}개 (100% 미국 본토 보통주)")
    sp_limit = st.sidebar.slider(
        "스크리닝 대상 수량 (상위 N개)",
        min_value=50,
        max_value=total_sp_cnt,
        value=min(total_sp_cnt, 200),
        step=50,
        help="S&P 500 지수 편입 기준상 전원 미국 본토 국적 보통주(Common Stock)로 구성됩니다."
    )
    selected_tickers = [item[0] for item in sp500_all[:sp_limit]]

elif universe_choice == "Nasdaq 전체 (미국 본토 순수 보통주)":
    nasdaq_all = load_nasdaq_us_common_directory()
    total_nasdaq_cnt = len(nasdaq_all)
    st.sidebar.success(f"🇺🇸 Nasdaq 순수 미국 보통주: 총 {total_nasdaq_cnt:,}개\n\n(※ 스팩(SPAC), ADR, ETF, 펀드, 해외기업 완전 배제)")
    nasdaq_limit = st.sidebar.slider(
        "스크리닝 대상 수량 (상위 N개)",
        min_value=50,
        max_value=min(total_nasdaq_cnt, 2000),
        value=150,
        step=50,
        help="스팩(SPAC), 해외 ADR(ASML, PDD 등), 펀드류를 철저히 배제한 순수 미국 보통주 목록입니다."
    )
    selected_tickers = [item[0] for item in nasdaq_all[:nasdaq_limit]]

elif universe_choice == "NYSE 전체 (미국 본토 순수 보통주)":
    nyse_all = load_nyse_us_common_directory()
    total_nyse_cnt = len(nyse_all)
    st.sidebar.success(f"🇺🇸 NYSE 순수 미국 보통주: 총 {total_nyse_cnt:,}개\n\n(※ 스팩(SPAC), ADR, ETF, 펀드, 해외기업 완전 배제)")
    nyse_limit = st.sidebar.slider(
        "스크리닝 대상 수량 (상위 N개)",
        min_value=50,
        max_value=min(total_nyse_cnt, 1500),
        value=150,
        step=50,
        help="해외 ADR(알리바바, TSMC 등), 스팩, 비주식 펀드류를 엄격히 걸러낸 순수 미국 보통주 목록입니다."
    )
    selected_tickers = [item[0] for item in nyse_all[:nyse_limit]]

elif universe_choice == "KOSPI 전체 종목 (동적 로드)":
    kospi_all = load_kospi_directory()
    total_kospi_cnt = len(kospi_all)
    st.sidebar.info(f"🇰🇷 전체 KOSPI 상장 종목: 총 {total_kospi_cnt:,}개 (시총 상위순 정렬)")
    kospi_limit = st.sidebar.slider(
        "스크리닝 대상 수량 (시총 상위 N개)",
        min_value=30,
        max_value=min(total_kospi_cnt, 1000),
        value=100,
        step=20,
        help="시가총액 및 거래 활성 상위 종목부터 순차적으로 로드합니다."
    )
    selected_tickers = [item[0] for item in kospi_all[:kospi_limit]]

elif universe_choice == "KOSPI 주요 종목 (시총 상위 40)":
    st.sidebar.info("🇰🇷 코스피 시가총액 상위 40대 대표주 프리셋")
    selected_tickers = [item[0] for item in PRESET_UNIVERSES["KOSPI 주요 종목 (시총 상위 40)"]]

elif universe_choice == "사용자 직접 입력 (Custom)":
    custom_default = "NVDA, AAPL, MSFT, PLTR, IONQ, IOT, 005930.KS, 000660.KS, GE, CAT, 035420.KS"
    ticker_input = st.sidebar.text_area(
        "티커 목록 입력 (쉼표 구분, 한국 종목은 .KS)",
        value=custom_default,
        height=100
    )
    selected_tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

else:
    selected_tickers = [item[0] for item in PRESET_UNIVERSES[universe_choice]]

period_choice = st.sidebar.selectbox("데이터 분석 기간", options=["6mo", "1y", "2y"], index=1)

st.sidebar.markdown("---")
# 2) 스크리닝 전략 선택
st.sidebar.subheader("2. 스크리닝 전략 선택")
screener_mode = st.sidebar.radio(
    "스크리닝 전략 선택",
    options=[
        "🚀 상승 돌파 모드", 
        "📦 AMD 박스권 매집 모드", 
        "📉 3. 25일선 이격도 매매",
        "⚡ 4. 변동성 돌파 (Volatility Breakout)"
    ],
    index=0,
    help="'상승 돌파 모드', ICT 'AMD 박스권 매집 모드', BNF '25일선 이격도 매매', 또는 래리 윌리엄스 '4. 변동성 돌파'를 선택합니다."
)

# --- 전략별 파라미터 기본값 사전 초기화 (NameError 원천 방지) ---
wb_k = 0.5
target_proximity_range = (-5.0, 5.0)
wb_breakout_only = False

max_box_range_pct = 15.0
filter_inside_box = True
filter_near_bottom = False

bnf_threshold = -15.0
bnf_tier_filter = "전체 보기"
bnf_filter_choice = "조건 없음"

enable_vol_filter = False
min_vol_surge = 1.5
filter_above_sma20 = False
filter_above_sma50 = False
filter_above_sma200 = False
filter_sma_aligned = False
enable_avwap_filter = False
filter_above_avwap = False
enable_box_filter = False
box_proximity_pct = -3.0
selected_anchor_mode = "swing_low"

if screener_mode == "📦 AMD 박스권 매집 모드":
    max_box_range_pct = st.sidebar.slider(
        "박스권 변동률(%)",
        min_value=0.0,
        max_value=30.0,
        value=15.0,
        step=0.5,
        format="%.1f%%",
        help="최근 20일간 (최고가 - 최저가)/최저가 변동폭이 설정값(기본 15%) 이하인 매집 종목 필터링"
    )
    filter_inside_box = st.sidebar.checkbox(
        "현재가가 박스권 내부(하단~상단)에 위치", 
        value=True,
        help="주가가 박스권 이탈 전 매집 구간 내에 머무르고 있는 종목만 선별"
    )
    filter_near_bottom = st.sidebar.checkbox(
        "0.00% 라인 근접 (하단 5% 이내)",
        value=False,
        help="박스권 하단(0% 라인) 부근에 위치하여 손익비가 우수한 타점 종목 선별"
    )
    selected_anchor_mode = "swing_low"

elif screener_mode == "📉 3. 25일선 이격도 매매":
    st.sidebar.info("💡 **1D(일봉) 타임프레임 엄격 격리**\n\nyfinance `interval='1d'`로 수집된 순수 일봉 데이터만 사용하여 25일 이동평균선(SMA25) 및 이격도를 정밀 산출합니다.")
    bnf_threshold = st.sidebar.slider(
        "25일선 이격도 상한선 (%)",
        min_value=-50.0,
        max_value=0.0,
        value=-15.0,
        step=1.0,
        format="%.0f%%",
        help="25일선 대비 괴리율이 이 값 이하인 낙폭 과대 과매도 종목만 필터링합니다. (음수값이 클수록 더 깊은 하락)"
    )
    bnf_tier_filter = st.sidebar.radio(
        "BNF 타겟 체급별 가이드",
        options=["전체 보기", "대형주 타점 (-10% ~ -18%)", "중형주 타점 (-18% ~ -30%)", "소형·테마주 급락 (-30% 이하)"],
        index=0,
        help="BNF의 주식 체급별(대형주 vs 중소형주) 반등 타점에 맞추어 필터링합니다."
    )
    selected_anchor_mode = "swing_low"

elif screener_mode == "⚡ 4. 변동성 돌파 (Volatility Breakout)":
    st.sidebar.info("💡 **주봉(1W) 기준 래리 윌리엄스 변동성 돌파 전략**\n\n전주 변동폭(고가-저가)에 K값을 곱해 이번 주 시가에 더한 **주봉 목표가**를 기준으로 상향 돌파 또는 근접한 종목을 포착합니다.")
    wb_k = st.sidebar.slider(
        "변동성 돌파 계수 (K값)",
        min_value=0.1,
        max_value=1.0,
        value=0.5,
        step=0.1,
        help="래리 윌리엄스 변동성 돌파 공식: 이번 주 시가 + (전주 변동폭 * K). 기본값 0.5"
    )
    target_proximity_range = st.sidebar.slider(
        "목표가 근접률(%)",
        min_value=-20.0,
        max_value=20.0,
        value=(-5.0, 5.0),
        step=0.5,
        format="%.1f%%",
        help="주봉 목표가 대비 현재가의 괴리율 범위. (예: -5% ~ +5%는 목표가 5% 아래 돌파 임박부터 5% 위 돌파 성공 구간)"
    )
    wb_breakout_only = st.sidebar.checkbox(
        "돌파 완료 종목만 보기 (현재가 >= 목표가)",
        value=False,
        help="목표가 근접률 범위 내 종목 중 이미 주봉 목표가를 돌파한 종목만 필터링"
    )
    selected_anchor_mode = "swing_low"

else:
    selected_anchor_mode = "swing_low"

st.sidebar.markdown("---")
# 3) 유동성 및 주가 필터 (거래량 1M & $30 이상 필터)
st.sidebar.subheader("3. 유동성 및 주가 필터")

enable_min_vol = st.sidebar.checkbox("최소 평균 거래량 필터 (기본 1M 이상)", value=True)
min_avg_vol = st.sidebar.slider(
    "20일 평균 거래량 하한선 (주)",
    min_value=100_000,
    max_value=5_000_000,
    value=1_000_000,
    step=100_000,
    format="%d주",
    help="20일 평균 거래량이 설정값(기본 1,000,000주 = 1M) 이상인 종목만 필터링합니다."
)

enable_min_price = st.sidebar.checkbox("최소 주가 필터 (기본 $30 / ₩30,000 이상)", value=True)
col_p1, col_p2 = st.sidebar.columns(2)
with col_p1:
    min_price_usd = col_p1.number_input(
        "미국 주가 하한선 ($)",
        min_value=1.0,
        max_value=1000.0,
        value=30.0,
        step=5.0,
        help="미국 주식의 최소 종가 기준 (기본 $30)"
    )
with col_p2:
    min_price_krw = col_p2.number_input(
        "한국 주가 하한선 (₩)",
        min_value=1000,
        max_value=1000000,
        value=30000,
        step=5000,
        help="한국 주식의 최소 종가 기준 (기본 ₩30,000)"
    )

if screener_mode in ["🚀 상승 돌파 모드", "📦 AMD 박스권 매집 모드"]:
    st.sidebar.markdown("---")
    # 4) BNF 25일선 이격도 필터 (낙폭 과대)
    st.sidebar.subheader("4. BNF 25일선 이격도 필터 (낙폭 과대)")
    bnf_filter_choice = st.sidebar.selectbox(
        "BNF 25일선 이격도 조건",
        options=[
            "조건 없음",
            "-10% 이하 하락 (이격도 90 이하)",
            "-20% 이하 하락 (이격도 80 이하)",
            "-30% 이하 하락 (이격도 70 이하)",
            "-40% 이하 하락 (이격도 60 이하)"
        ],
        index=0,
        help="BNF의 25일선 이격도 역발상 매매 전략: 25일 이동평균선 대비 현재가의 괴리율(이격도)이 극도로 벌어진 과매도 낙폭 과대 종목을 선별합니다. (대형주 -10%, 중형주 -20%, 소형/테마주 -30% 이상)"
    )
else:
    bnf_filter_choice = "조건 없음"

if screener_mode == "🚀 상승 돌파 모드":
    st.sidebar.markdown("---")
    # 5) 거래량 급증 조건
    st.sidebar.subheader("5. 거래량 급증 (Volume Surge)")
    enable_vol_filter = st.sidebar.checkbox("거래량 급증 필터 적용", value=True)
    min_vol_surge = st.sidebar.slider(
        "20일 평균 대비 거래량 배수 (이상)",
        min_value=1.0,
        max_value=5.0,
        value=1.5,
        step=0.1,
        help="당일 거래량이 직전 20일 평균 거래량의 몇 배 이상인지 필터링합니다."
    )

    st.sidebar.markdown("---")
    # 6) 이동평균선(SMA) 조건
    st.sidebar.subheader("6. 이동평균선 필터")
    filter_above_sma20 = st.sidebar.checkbox("현재가 > 20일선 (SMA 20)", value=True)
    filter_above_sma50 = st.sidebar.checkbox("현재가 > 50일선 (SMA 50)", value=False)
    filter_above_sma200 = st.sidebar.checkbox("현재가 > 200일선 (SMA 200)", value=False)
    filter_sma_aligned = st.sidebar.checkbox("이평선 정배열 (SMA 20 > SMA 50)", value=False)

    st.sidebar.markdown("---")
    # 7) Anchored VWAP 조건
    st.sidebar.subheader("7. Anchored VWAP 필터")
    enable_avwap_filter = st.sidebar.checkbox("Anchored VWAP 조건 적용", value=True)
    avwap_mode = st.sidebar.selectbox(
        "앵커 기준점 (Anchor Point)",
        options=["최근 30일 최저점 (Swing Low)", "최근 30일 최고점 (Swing High)", "조회기간 시작점 (Period Start)"],
        index=0
    )

    anchor_mode_map = {
        "최근 30일 최저점 (Swing Low)": "swing_low",
        "최근 30일 최고점 (Swing High)": "swing_high",
        "조회기간 시작점 (Period Start)": "period_start"
    }
    selected_anchor_mode = anchor_mode_map[avwap_mode]
    filter_above_avwap = st.sidebar.checkbox("현재가 > Anchored VWAP", value=True)

    st.sidebar.markdown("---")
    # 8) 박스권 및 돌파 조건
    st.sidebar.subheader("8. 박스권 돌파 (Box Range)")
    enable_box_filter = st.sidebar.checkbox("박스권 상단 돌파/근접 종목만 보기", value=False)
    box_proximity_pct = st.sidebar.slider(
        "20일 박스권 고점 대비 근접도 (%)",
        min_value=-10.0,
        max_value=5.0,
        value=-3.0,
        step=0.5,
        help="-3%인 경우 최근 20일 최고가에서 3% 이내로 접근했거나 돌파한 종목"
    )

if st.sidebar.button("🔄 캐시 비우기 및 새로고침"):
    st.cache_data.clear()
    st.rerun()


# --- 4. 메인 대시보드 데이터 로드 & 지표 계산 ---
if screener_mode == "🚀 상승 돌파 모드":
    st.title("📈 상승 돌파 주식 스크리너")
    st.caption(f"선택 유니버스: **{universe_choice}** ({len(selected_tickers)}개 종목) | 거래량 급증, 이동평균선 돌파, Anchored VWAP & 박스권 실시간 스크리닝")
elif screener_mode == "📦 AMD 박스권 매집 모드":
    st.title("📦 AMD 박스권 매집 스크리너")
    st.caption(f"선택 유니버스: **{universe_choice}** ({len(selected_tickers)}개 종목) | 1D 일봉 기준 20일 박스권 매집(Accumulation) & 조작(Manipulation) 타점 스크리닝")
elif screener_mode == "📉 3. 25일선 이격도 매매":
    st.title("📉 BNF 25일선 이격도 역발상 스크리너 (1D 일봉 전용)")
    st.caption(f"선택 유니버스: **{universe_choice}** ({len(selected_tickers)}개 종목) | **🔒 1D 일봉(interval='1d') 엄격 격리** | 25일 이동평균선(SMA25) 대비 과매도 낙폭 과대 반등 타점 스크리닝")
else: # "⚡ 4. 변동성 돌파 (Volatility Breakout)"
    st.title("⚡ 래리 윌리엄스 주봉 변동성 돌파 스크리너")
    st.caption(f"선택 유니버스: **{universe_choice}** ({len(selected_tickers)}개 종목) | **주봉(1W) 변동폭(K={wb_k}) 기반 목표가** 실시간 상향 돌파 및 근접 종목 스크리닝")

with st.spinner(f"총 {len(selected_tickers)}개 종목의 시장 데이터를 수집 및 분석 중입니다..."):
    market_data = load_all_market_data(tuple(selected_tickers), period=period_choice, interval="1d")

if not market_data:
    st.error("데이터를 불러오지 못했습니다. 네트워크 연결을 확인하거나 티커를 재설정해주세요.")
    st.stop()

# 종목별 섹터 정보 일괄 조회 (캐시 활용 및 병렬 처리로 지연 시간 최소화)
sectors_map = get_tickers_sectors(selected_tickers)

all_summaries = []
processed_dfs = {}

for ticker, df in market_data.items():
    if df is not None and len(df) >= 20:
        df_calc = calculate_technical_indicators(
            df,
            anchor_mode=selected_anchor_mode,
            anchor_lookback=30
        )
        processed_dfs[ticker] = df_calc
        comp_name = TICKER_NAME_MAP.get(ticker, ticker)
        sec = sectors_map.get(ticker, "-")
        summary = extract_stock_summary(ticker, df_calc, company_name=comp_name, sector=sec)
        if summary:
            all_summaries.append(summary)

if not all_summaries:
    st.warning("분석 가능한 유효 데이터가 없습니다.")
    st.stop()

df_all = pd.DataFrame(all_summaries)

# --- 5. 스크리닝 필터링 로직 ---
df_filtered = df_all.copy()

# 1) 최소 평균 거래량 필터 (기본 1M 이상)
if enable_min_vol:
    df_filtered = df_filtered[df_filtered['vol_sma20'] >= min_avg_vol]

# 2) 최소 주가 필터 (미국: $30 이상, 한국: ₩30,000 이상)
if enable_min_price:
    def check_min_price(row):
        if is_korean_stock(row['ticker']):
            return row['close'] >= min_price_krw
        return row['close'] >= min_price_usd
    df_filtered = df_filtered[df_filtered.apply(check_min_price, axis=1)]

# 3) BNF 25일선 이격도 필터 (낙폭 과대 역발상)
if screener_mode == "📉 3. 25일선 이격도 매매":
    df_filtered = df_filtered[df_filtered['disparity_25'] <= bnf_threshold]
    if bnf_tier_filter == "대형주 타점 (-10% ~ -18%)":
        df_filtered = df_filtered[(df_filtered['disparity_25'] <= -10.0) & (df_filtered['disparity_25'] >= -18.0)]
    elif bnf_tier_filter == "중형주 타점 (-18% ~ -30%)":
        df_filtered = df_filtered[(df_filtered['disparity_25'] <= -18.0) & (df_filtered['disparity_25'] >= -30.0)]
    elif bnf_tier_filter == "소형·테마주 급락 (-30% 이하)":
        df_filtered = df_filtered[df_filtered['disparity_25'] <= -30.0]
elif screener_mode in ["🚀 상승 돌파 모드", "📦 AMD 박스권 매집 모드"]:
    if bnf_filter_choice == "-10% 이하 하락 (이격도 90 이하)":
        df_filtered = df_filtered[df_filtered['disparity_25'] <= -10.0]
    elif bnf_filter_choice == "-20% 이하 하락 (이격도 80 이하)":
        df_filtered = df_filtered[df_filtered['disparity_25'] <= -20.0]
    elif bnf_filter_choice == "-30% 이하 하락 (이격도 70 이하)":
        df_filtered = df_filtered[df_filtered['disparity_25'] <= -30.0]
    elif bnf_filter_choice == "-40% 이하 하락 (이격도 60 이하)":
        df_filtered = df_filtered[df_filtered['disparity_25'] <= -40.0]

if screener_mode == "🚀 상승 돌파 모드":
    # 3) 거래량 급증 필터
    if enable_vol_filter:
        df_filtered = df_filtered[df_filtered['vol_surge'] >= min_vol_surge]

    # 4) 이동평균선 필터
    if filter_above_sma20:
        df_filtered = df_filtered[df_filtered['above_sma20'] == True]

    if filter_above_sma50:
        df_filtered = df_filtered[df_filtered['above_sma50'] == True]

    if filter_above_sma200:
        df_filtered = df_filtered[df_filtered['above_sma200'] == True]

    if filter_sma_aligned:
        df_filtered = df_filtered[df_filtered['sma_aligned'] == True]

    # 5) Anchored VWAP 필터
    if enable_avwap_filter and filter_above_avwap:
        df_filtered = df_filtered[df_filtered['above_avwap'] == True]

    # 6) 박스권 돌파 필터
    if enable_box_filter:
        df_filtered = df_filtered[df_filtered['pct_from_box_high'] >= box_proximity_pct]

elif screener_mode == "📦 AMD 박스권 매집 모드":
    # 박스권 변동률 (Box Range %) 상한선 필터
    df_filtered = df_filtered[df_filtered['amd_box_range_pct'] <= max_box_range_pct]

    # 현재가가 박스권 내에 위치 필터
    if filter_inside_box:
        df_filtered = df_filtered[df_filtered['in_amd_box'] == True]

    # 0.00% 라인 근접 (하단 5% 이내) 필터
    if filter_near_bottom:
        def check_near_bottom(row):
            low = row['amd_box_low']
            return low > 0 and (row['close'] - low) / low <= 0.05 and row['close'] >= low * 0.98
        df_filtered = df_filtered[df_filtered.apply(check_near_bottom, axis=1)]

elif screener_mode == "⚡ 4. 변동성 돌파 (Volatility Breakout)":
    # 4번 모드: 사용자가 선택한 K값을 반영하여 주봉 목표가와 근접률을 정밀 재연산
    if len(df_filtered) > 0:
        def update_wb_k(row):
            target = row['wb_week_open'] + (row['wb_prev_range'] * wb_k)
            prox = ((row['close'] - target) / target * 100.0) if target > 0 else 0.0
            is_bo = bool(row['close'] >= target)
            status_txt = "돌파 성공 ⚡" if is_bo else "돌파 대기 ⏳"
            return pd.Series([round(target, 2), round(prox, 2), is_bo, status_txt])

        wb_updates = df_filtered.apply(update_wb_k, axis=1)
        df_filtered['wb_target_price'] = wb_updates[0]
        df_filtered['wb_target_proximity_pct'] = wb_updates[1]
        df_filtered['wb_is_breakout'] = wb_updates[2]
        df_filtered['wb_status'] = wb_updates[3]

    # 목표가 근접률(%) 양방향 슬라이더 필터링
    min_prox, max_prox = target_proximity_range
    df_filtered = df_filtered[
        (df_filtered['wb_target_proximity_pct'] >= min_prox) & 
        (df_filtered['wb_target_proximity_pct'] <= max_prox)
    ]

    if wb_breakout_only:
        df_filtered = df_filtered[df_filtered['wb_is_breakout'] == True]

latest_date = df_all['date'].max()

# --- 6. 요약 메트릭 카드 ---
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">스크리닝 대상 종목</div>
        <div class="metric-value">{len(df_all)}개</div>
        <div class="metric-sub" style="color: #9aa0a6;">기준일: {latest_date}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    pass_rate = round(len(df_filtered) / len(df_all) * 100, 1) if len(df_all) > 0 else 0
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: #00c853;">
        <div class="metric-title">조건 부합 종목 (통과율)</div>
        <div class="metric-value" style="color: #00c853;">{len(df_filtered)}개</div>
        <div class="metric-sub" style="color: #00c853;">통과율: {pass_rate}%</div>
    </div>
    """, unsafe_allow_html=True)

if screener_mode == "🚀 상승 돌파 모드":
    with col3:
        if len(df_all) > 0:
            top_vol = df_all.sort_values(by="vol_surge", ascending=False).iloc[0]
            st.markdown(f"""
            <div class="metric-card" style="border-left-color: #ff9100;">
                <div class="metric-title">최고 거래량 급증 종목</div>
                <div class="metric-value" style="color: #ff9100;">{top_vol['ticker']}</div>
                <div class="metric-sub" style="color: #ff9100;">20일 대비 {top_vol['vol_surge']}배 급증</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("-")

    with col4:
        if len(df_all) > 0:
            top_gain = df_all.sort_values(by="change_pct", ascending=False).iloc[0]
            price_disp = format_currency(top_gain['close'], top_gain['ticker'])
            st.markdown(f"""
            <div class="metric-card" style="border-left-color: #ff1744;">
                <div class="metric-title">당일 최고 상승 종목</div>
                <div class="metric-value" style="color: #ff1744;">{top_gain['ticker']}</div>
                <div class="metric-sub" style="color: #ff1744;">+{top_gain['change_pct']}% ({price_disp})</div>
            </div>
            """, unsafe_allow_html=True)
elif screener_mode == "📦 AMD 박스권 매집 모드":
    with col3:
        if len(df_filtered) > 0:
            tightest = df_filtered.sort_values(by="amd_box_range_pct", ascending=True).iloc[0]
            st.markdown(f"""
            <div class="metric-card" style="border-left-color: #00e5ff;">
                <div class="metric-title">최고 압축 매집 종목</div>
                <div class="metric-value" style="color: #00e5ff;">{tightest['ticker']}</div>
                <div class="metric-sub" style="color: #00e5ff;">변동률 {tightest['amd_box_range_pct']:.2f}% (최고 수렴)</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("-")

    with col4:
        if len(df_filtered) > 0:
            top_amd_vol = df_filtered.sort_values(by="vol_sma20", ascending=False).iloc[0]
            st.markdown(f"""
            <div class="metric-card" style="border-left-color: #ffd600;">
                <div class="metric-title">매집주 중 거래량 1위</div>
                <div class="metric-value" style="color: #ffd600;">{top_amd_vol['ticker']}</div>
                <div class="metric-sub" style="color: #ffd600;">20일 평균 {top_amd_vol['vol_sma20']:,}주</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("-")
elif screener_mode == "📉 3. 25일선 이격도 매매":
    with col3:
        if len(df_filtered) > 0:
            top_oversold = df_filtered.sort_values(by="disparity_25", ascending=True).iloc[0]
            st.markdown(f"""
            <div class="metric-card" style="border-left-color: #ea80fc;">
                <div class="metric-title">최대 낙폭 과대 종목 (1D)</div>
                <div class="metric-value" style="color: #ea80fc;">{top_oversold['ticker']}</div>
                <div class="metric-sub" style="color: #ea80fc;">25일 이격도 {top_oversold['disparity_25']:+.2f}%</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("-")

    with col4:
        if len(df_filtered) > 0:
            top_bnf_vol = df_filtered.sort_values(by="vol_sma20", ascending=False).iloc[0]
            st.markdown(f"""
            <div class="metric-card" style="border-left-color: #00e5ff;">
                <div class="metric-title">과매도 종목 중 거래량 1위</div>
                <div class="metric-value" style="color: #00e5ff;">{top_bnf_vol['ticker']}</div>
                <div class="metric-sub" style="color: #00e5ff;">20일 평균 {top_bnf_vol['vol_sma20']:,}주</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("-")
else: # "⚡ 4. 변동성 돌파 (Volatility Breakout)"
    with col3:
        if len(df_filtered) > 0:
            bo_count = int(df_filtered['wb_is_breakout'].sum())
            bo_rate = round(bo_count / len(df_filtered) * 100.0, 1) if len(df_filtered) > 0 else 0
            st.markdown(f"""
            <div class="metric-card" style="border-left-color: #ffd600;">
                <div class="metric-title">주봉 목표가 돌파 성공 종목</div>
                <div class="metric-value" style="color: #ffd600;">{bo_count}개</div>
                <div class="metric-sub" style="color: #ffd600;">선별 종목 중 돌파율 {bo_rate}%</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("-")

    with col4:
        if len(df_filtered) > 0:
            top_prox = df_filtered.sort_values(by="wb_target_proximity_pct", ascending=False).iloc[0]
            st.markdown(f"""
            <div class="metric-card" style="border-left-color: #00e676;">
                <div class="metric-title">최고 돌파율 / 근접 종목</div>
                <div class="metric-value" style="color: #00e676;">{top_prox['ticker']}</div>
                <div class="metric-sub" style="color: #00e676;">목표가 대비 {top_prox['wb_target_proximity_pct']:+.2f}%</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("-")

st.markdown("<br>", unsafe_allow_html=True)


# --- 7. 결과 테이블 및 종목 상세 뷰 ---
tab1, tab2 = st.tabs(["📋 스크리닝 결과 리스트", "📊 심층 차트 분석"])

with tab1:
    # 유니버스별 맞춤 파일명 결정
    if "S&P 500" in universe_choice:
        universe_prefix = "SP500"
    elif "Nasdaq" in universe_choice:
        universe_prefix = "Nasdaq"
    elif "NYSE" in universe_choice:
        universe_prefix = "NYSE"
    elif "KOSPI" in universe_choice:
        universe_prefix = "KOSPI"
    elif "AI" in universe_choice or "성장주" in universe_choice:
        universe_prefix = "Tech_Momentum"
    elif "우량주" in universe_choice:
        universe_prefix = "NYSE_Bluechip"
    else:
        universe_prefix = "Custom"

    date_str = str(latest_date).replace("-", "") if latest_date else datetime.now().strftime("%Y%m%d")
    
    if screener_mode == "📦 AMD 박스권 매집 모드":
        csv_filename = f"{universe_prefix}_AMD_Accumulation_{date_str}.csv"
        mode_header = "AMD 박스권 매집 대기 종목"
    elif screener_mode == "📉 3. 25일선 이격도 매매":
        csv_filename = f"{universe_prefix}_BNF_Disparity25_1D_{date_str}.csv"
        mode_header = "BNF 25일선 이격도 매매 종목 (1D 일봉 전용)"
    elif screener_mode == "⚡ 4. 변동성 돌파 (Volatility Breakout)":
        csv_filename = f"{universe_prefix}_VolatilityBreakout_1W_{date_str}.csv"
        mode_header = "래리 윌리엄스 주봉 변동성 돌파 종목"
    else:
        csv_filename = f"{universe_prefix}_screened_stocks_{date_str}.csv"
        mode_header = "상승 돌파 모드 종목"

    # 상단 바: 제목 및 모바일 친화적 즉시 다운로드 버튼
    hcol1, hcol2 = st.columns([3, 2])
    with hcol1:
        st.subheader(f"🎯 {mode_header} ({len(df_filtered)}건)")
    
    if len(df_filtered) == 0:
        if screener_mode == "📦 AMD 박스권 매집 모드":
            st.info(f"💡 현재 설정된 AMD 매집 조건(박스권 변동률 {max_box_range_pct}% 이하, 거래량 {min_avg_vol:,}주 이상, 주가 조건 등)에 부합하는 종목이 없습니다. 사이드바에서 박스권 변동률 상한선을 조정해보세요.")
        elif screener_mode == "📉 3. 25일선 이격도 매매":
            st.info(f"💡 현재 설정된 25일선 이격도 조건(이격도 {bnf_threshold}% 이하, 거래량 {min_avg_vol:,}주 이상 등)에 부합하는 종목이 없습니다. 사이드바에서 이격도 상한선이나 타겟 가이드를 조정해보세요.")
        elif screener_mode == "⚡ 4. 변동성 돌파 (Volatility Breakout)":
            st.info(f"💡 현재 설정된 주봉 변동성 돌파 조건(목표가 근접률 {target_proximity_range[0]:.1f}% ~ {target_proximity_range[1]:.1f}%, K값 {wb_k}, 거래량 {min_avg_vol:,}주 이상 등)에 부합하는 종목이 없습니다. 사이드바에서 근접률 범위나 K값을 조정해보세요.")
        else:
            st.info("💡 현재 설정된 필터 조건(최소 거래량 1M, 최소 주가 $30 등)에 부합하는 종목이 없습니다. 사이드바에서 거래량 하한선이나 주가 조건을 완화해보세요.")
    else:
        display_df = df_filtered.copy()
        display_df['현재가'] = [format_currency(r['close'], r['ticker']) for _, r in display_df.iterrows()]
        display_df['25일 평균선(SMA25)'] = [format_currency(r['sma25'], r['ticker']) if pd.notna(r['sma25']) else '-' for _, r in display_df.iterrows()]
        
        def color_bnf_disparity(val):
            if pd.isna(val) or val is None:
                return ''
            if val <= -30.0:
                return 'background-color: #880e4f; color: #ff80ab; font-weight: bold;'
            elif val <= -20.0:
                return 'background-color: #4a148c; color: #ea80fc; font-weight: bold;'
            elif val <= -10.0:
                return 'color: #ff5252; font-weight: bold;'
            elif val > 0:
                return 'color: #00e676;'
            return ''

        if screener_mode == "📦 AMD 박스권 매집 모드":
            # AMD 요구 컬럼: [티커, 기업명, 현재가, 25일 이격도(%), 25일 평균선(SMA25), 박스권 변동률(%), 박스권 상단, 0.00% 라인(하단), -50% 라인(조작/손절)]
            display_df['박스권 상단'] = [format_currency(r['amd_box_high'], r['ticker']) for _, r in display_df.iterrows()]
            display_df['0.00% 라인(하단)'] = [format_currency(r['amd_entry_0pct'], r['ticker']) for _, r in display_df.iterrows()]
            display_df['-50% 라인(조작/손절)'] = [format_currency(r['amd_manipulation_neg50pct'], r['ticker']) for _, r in display_df.iterrows()]
            
            table_cols = [
                'ticker', 'name', 'sector', 'weekly_trend', 'monthly_trend', '현재가',
                'disparity_25', '25일 평균선(SMA25)',
                'amd_box_range_pct', '박스권 상단', '0.00% 라인(하단)', '-50% 라인(조작/손절)',
                'change_pct', 'vol_sma20'
            ]
            sub_df = display_df[table_cols].copy()
            sub_df.columns = [
                '티커', '기업명', '섹터', '주봉 추세', '월봉 추세', '현재가',
                '25일 이격도(%)', '25일 평균선(SMA25)',
                '박스권 변동률(%)', '박스권 상단', '0.00% 라인(하단)', '-50% 라인(조작/손절)',
                '등락률(%)', '20일 평균거래량'
            ]

            csv_bytes = sub_df.to_csv(index=False).encode('utf-8-sig')

            with hcol2:
                st.download_button(
                    label=f"📥 CSV 다운로드 ({csv_filename})",
                    data=csv_bytes,
                    file_name=csv_filename,
                    mime="text/csv",
                    use_container_width=True,
                    key="btn_csv_download_top"
                )

            sort_col = st.selectbox(
                "정렬 기준 선택", 
                ["25일 이격도(%) (오름차순 - 낙폭 과대)", "박스권 변동률(%) (오름차순 - 최고 압축)", "20일 평균거래량 (내림차순)", "등락률(%) (내림차순)"], 
                index=0
            )
            if "25일 이격도" in sort_col:
                sub_df = sub_df.sort_values(by="25일 이격도(%)", ascending=True)
            elif "박스권 변동률" in sort_col:
                sub_df = sub_df.sort_values(by="박스권 변동률(%)", ascending=True)
            elif "20일 평균거래량" in sort_col:
                sub_df = sub_df.sort_values(by="20일 평균거래량", ascending=False)
            else:
                sub_df = sub_df.sort_values(by="등락률(%)", ascending=False)

            def color_change(val):
                if val > 0:
                    return 'color: #00e676; font-weight: bold;'
                elif val < 0:
                    return 'color: #ff5252; font-weight: bold;'
                return ''

            def highlight_box_range(val):
                if val <= 8.0:
                    return 'background-color: #1b5e20; color: #a5d6a7; font-weight: bold;'
                elif val <= 12.0:
                    return 'background-color: #0d47a1; color: #90caf9;'
                return ''

            def color_htf_trend(val):
                if '상승' in str(val):
                    return 'color: #00e676; font-weight: bold;'
                elif '하락' in str(val):
                    return 'color: #ff5252; font-weight: bold;'
                return ''

            styled_df = sub_df.style\
                .format({
                    '25일 이격도(%)': '{:+.2f}%',
                    '박스권 변동률(%)': '{:.2f}%',
                    '등락률(%)': '{:+.2f}%',
                    '20일 평균거래량': '{:,}'
                })\
                .map(color_change, subset=['등락률(%)'])\
                .map(highlight_box_range, subset=['박스권 변동률(%)'])\
                .map(color_htf_trend, subset=['주봉 추세', '월봉 추세'])\
                .map(color_bnf_disparity, subset=['25일 이격도(%)'])

            # pyarrow 완전 배제 순수 HTML 테이블 렌더링
            table_html = styled_df.hide(axis="index").to_html()
            st.markdown(f'<div class="custom-table-container">{table_html}</div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.download_button(
                label=f"📥 CSV 파일 다운로드 ({csv_filename})",
                data=csv_bytes,
                file_name=csv_filename,
                mime="text/csv",
                use_container_width=True,
                key="btn_csv_download_bottom"
            )

        elif screener_mode == "📉 3. 25일선 이격도 매매":
            # 3번 모드: [티커, 기업명, 섹터, 주봉 추세, 월봉 추세, 현재가, 25일 이격도(%), 25일 평균선(SMA25), 20일선(SMA20), 등락률(%), 당일 거래량, 20일 평균거래량]
            display_df['20일선(SMA20)'] = [format_currency(r['sma20'], r['ticker']) if pd.notna(r['sma20']) else '-' for _, r in display_df.iterrows()]
            
            table_cols = [
                'ticker', 'name', 'sector', 'weekly_trend', 'monthly_trend', '현재가',
                'disparity_25', '25일 평균선(SMA25)', '20일선(SMA20)',
                'change_pct', 'volume', 'vol_sma20'
            ]
            sub_df = display_df[table_cols].copy()
            sub_df.columns = [
                '티커', '기업명', '섹터', '주봉 추세', '월봉 추세', '현재가',
                '25일 이격도(%)', '25일 평균선(SMA25)', '20일선(SMA20)',
                '등락률(%)', '당일 거래량', '20일 평균거래량'
            ]

            csv_bytes = sub_df.to_csv(index=False).encode('utf-8-sig')

            with hcol2:
                st.download_button(
                    label=f"📥 CSV 다운로드 ({csv_filename})",
                    data=csv_bytes,
                    file_name=csv_filename,
                    mime="text/csv",
                    use_container_width=True,
                    key="btn_csv_download_top"
                )

            sort_col = st.selectbox(
                "정렬 기준 선택", 
                ["25일 이격도(%) (오름차순 - 낙폭 과대)", "등락률(%) (오름차순 - 당일 급락)", "20일 평균거래량 (내림차순)", "당일 거래량 (내림차순)"], 
                index=0
            )
            if "25일 이격도" in sort_col:
                sub_df = sub_df.sort_values(by="25일 이격도(%)", ascending=True)
            elif "등락률" in sort_col:
                sub_df = sub_df.sort_values(by="등락률(%)", ascending=True)
            elif "20일 평균거래량" in sort_col:
                sub_df = sub_df.sort_values(by="20일 평균거래량", ascending=False)
            else:
                sub_df = sub_df.sort_values(by="당일 거래량", ascending=False)

            def color_change(val):
                if val > 0:
                    return 'color: #00e676; font-weight: bold;'
                elif val < 0:
                    return 'color: #ff5252; font-weight: bold;'
                return ''

            def color_htf_trend(val):
                if '상승' in str(val):
                    return 'color: #00e676; font-weight: bold;'
                elif '하락' in str(val):
                    return 'color: #ff5252; font-weight: bold;'
                return ''

            styled_df = sub_df.style\
                .format({
                    '25일 이격도(%)': '{:+.2f}%',
                    '등락률(%)': '{:+.2f}%',
                    '당일 거래량': '{:,}',
                    '20일 평균거래량': '{:,}'
                })\
                .map(color_change, subset=['등락률(%)'])\
                .map(color_htf_trend, subset=['주봉 추세', '월봉 추세'])\
                .map(color_bnf_disparity, subset=['25일 이격도(%)'])

            table_html = styled_df.hide(axis="index").to_html()
            st.markdown(f'<div class="custom-table-container">{table_html}</div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.download_button(
                label=f"📥 CSV 파일 다운로드 ({csv_filename})",
                data=csv_bytes,
                file_name=csv_filename,
                mime="text/csv",
                use_container_width=True,
                key="btn_csv_download_bottom"
            )

        elif screener_mode == "⚡ 4. 변동성 돌파 (Volatility Breakout)":
            display_df['주봉 목표가'] = [format_currency(r['wb_target_price'], r['ticker']) if pd.notna(r['wb_target_price']) else '-' for _, r in display_df.iterrows()]
            display_df['이번 주 시가'] = [format_currency(r['wb_week_open'], r['ticker']) if pd.notna(r['wb_week_open']) else '-' for _, r in display_df.iterrows()]
            display_df['전주 변동폭'] = [format_currency(r['wb_prev_range'], r['ticker']) if pd.notna(r['wb_prev_range']) else '-' for _, r in display_df.iterrows()]

            table_cols = [
                'ticker', 'name', 'sector', 'weekly_trend', 'monthly_trend', '현재가',
                '주봉 목표가', 'wb_target_proximity_pct', 'wb_status',
                '이번 주 시가', '전주 변동폭', 'change_pct', 'vol_sma20'
            ]
            sub_df = display_df[table_cols].copy()
            sub_df.columns = [
                '티커', '기업명', '섹터', '주봉 추세', '월봉 추세', '현재가',
                '주봉 목표가', '목표가 근접률(%)', '돌파 상태',
                '이번 주 시가', '전주 변동폭', '등락률(%)', '20일 평균거래량'
            ]

            csv_bytes = sub_df.to_csv(index=False).encode('utf-8-sig')

            with hcol2:
                st.download_button(
                    label=f"📥 CSV 다운로드 ({csv_filename})",
                    data=csv_bytes,
                    file_name=csv_filename,
                    mime="text/csv",
                    use_container_width=True,
                    key="btn_csv_download_top"
                )

            sort_col = st.selectbox(
                "정렬 기준 선택", 
                ["목표가 근접률(%) (내림차순 - 돌파 우세)", "목표가 근접률(%) (오름차순 - 진입 대기)", "등락률(%) (내림차순)", "20일 평균거래량 (내림차순)"], 
                index=0
            )
            if "오름차순" in sort_col:
                sub_df = sub_df.sort_values(by="목표가 근접률(%)", ascending=True)
            elif "내림차순 - 돌파" in sort_col:
                sub_df = sub_df.sort_values(by="목표가 근접률(%)", ascending=False)
            elif "등락률" in sort_col:
                sub_df = sub_df.sort_values(by="등락률(%)", ascending=False)
            else:
                sub_df = sub_df.sort_values(by="20일 평균거래량", ascending=False)

            def color_change(val):
                if val > 0:
                    return 'color: #00e676; font-weight: bold;'
                elif val < 0:
                    return 'color: #ff5252; font-weight: bold;'
                return ''

            def color_proximity(val):
                if pd.isna(val) or val is None:
                    return ''
                if val >= 0:
                    return 'background-color: #1b5e20; color: #a5d6a7; font-weight: bold;'
                elif val >= -3.0:
                    return 'background-color: #e65100; color: #ffe0b2; font-weight: bold;'
                return 'color: #90caf9;'

            def color_breakout_status(val):
                if '성공' in str(val):
                    return 'color: #00e676; font-weight: bold;'
                return 'color: #ffb74d;'

            def color_htf_trend(val):
                if '상승' in str(val):
                    return 'color: #00e676; font-weight: bold;'
                elif '하락' in str(val):
                    return 'color: #ff5252; font-weight: bold;'
                return ''

            styled_df = sub_df.style\
                .format({
                    '목표가 근접률(%)': '{:+.2f}%',
                    '등락률(%)': '{:+.2f}%',
                    '20일 평균거래량': '{:,}'
                })\
                .map(color_change, subset=['등락률(%)'])\
                .map(color_proximity, subset=['목표가 근접률(%)'])\
                .map(color_breakout_status, subset=['돌파 상태'])\
                .map(color_htf_trend, subset=['주봉 추세', '월봉 추세'])

            table_html = styled_df.hide(axis="index").to_html()
            st.markdown(f'<div class="custom-table-container">{table_html}</div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.download_button(
                label=f"📥 CSV 파일 다운로드 ({csv_filename})",
                data=csv_bytes,
                file_name=csv_filename,
                mime="text/csv",
                use_container_width=True,
                key="btn_csv_download_bottom"
            )

        else: # 모멘텀 모드
            display_df['AVWAP'] = [format_currency(r['avwap'], r['ticker']) for _, r in display_df.iterrows()]
            display_df['박스상단'] = [format_currency(r['box_high'], r['ticker']) for _, r in display_df.iterrows()]
            
            table_cols = [
                'ticker', 'name', 'sector', 'weekly_trend', 'monthly_trend', '현재가',
                'disparity_25', '25일 평균선(SMA25)',
                'change_pct', 'volume', 'vol_sma20', 'vol_surge', 
                'above_sma20', 'above_sma50', 'above_avwap', 'pct_from_avwap', 'pct_from_box_high'
            ]
            
            sub_df = display_df[table_cols].copy()
            sub_df.columns = [
                '티커', '기업명', '섹터', '주봉 추세', '월봉 추세', '현재가',
                '25일 이격도(%)', '25일 평균선(SMA25)',
                '등락률(%)', '당일 거래량', '20일 평균거래량', '거래량 급증배율',
                '> SMA20', '> SMA50', '> AVWAP', 'AVWAP 대비(%)', '박스상단 대비(%)'
            ]

            csv_bytes = sub_df.to_csv(index=False).encode('utf-8-sig')

            with hcol2:
                st.download_button(
                    label=f"📥 CSV 다운로드 ({csv_filename})",
                    data=csv_bytes,
                    file_name=csv_filename,
                    mime="text/csv",
                    use_container_width=True,
                    key="btn_csv_download_top"
                )

            sort_col = st.selectbox(
                "정렬 기준 선택", 
                ["거래량 급증배율", "25일 이격도(%) (오름차순 - 낙폭 과대)", "20일 평균거래량", "등락률(%)", "박스상단 대비(%)"], 
                index=0
            )
            if "25일 이격도" in sort_col:
                sub_df = sub_df.sort_values(by="25일 이격도(%)", ascending=True)
            else:
                sub_df = sub_df.sort_values(by=sort_col, ascending=False)

            def color_change(val):
                if val > 0:
                    return 'color: #00e676; font-weight: bold;'
                elif val < 0:
                    return 'color: #ff5252; font-weight: bold;'
                return ''

            def highlight_surge(val):
                if val >= 2.0:
                    return 'background-color: #2e7d32; color: #ffffff; font-weight: bold;'
                elif val >= 1.5:
                    return 'background-color: #1b5e20; color: #e8f5e9;'
                return ''

            def color_htf_trend(val):
                if '상승' in str(val):
                    return 'color: #00e676; font-weight: bold;'
                elif '하락' in str(val):
                    return 'color: #ff5252; font-weight: bold;'
                return ''

            styled_df = sub_df.style\
                .format({
                    '25일 이격도(%)': '{:+.2f}%',
                    '등락률(%)': '{:+.2f}%',
                    '당일 거래량': '{:,}',
                    '20일 평균거래량': '{:,}',
                    '거래량 급증배율': '{:.2f}x',
                    'AVWAP 대비(%)': '{:+.2f}%',
                    '박스상단 대비(%)': '{:+.2f}%'
                })\
                .map(color_change, subset=['등락률(%)'])\
                .map(highlight_surge, subset=['거래량 급증배율'])\
                .map(color_htf_trend, subset=['주봉 추세', '월봉 추세'])\
                .map(color_bnf_disparity, subset=['25일 이격도(%)'])

            table_html = styled_df.hide(axis="index").to_html()
            st.markdown(f'<div class="custom-table-container">{table_html}</div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.download_button(
                label=f"📥 CSV 파일 다운로드 ({csv_filename})",
                data=csv_bytes,
                file_name=csv_filename,
                mime="text/csv",
                use_container_width=True,
                key="btn_csv_download_bottom"
            )


with tab2:
    if screener_mode == "📦 AMD 박스권 매집 모드":
        st.subheader("📦 AMD 박스권 매집(Accumulation) & 조작(Manipulation) 인터랙티브 차트")
    elif screener_mode == "📉 3. 25일선 이격도 매매":
        st.subheader("📉 BNF 25일선 이격도(SMA25) 1D 일봉 인터랙티브 차트")
    elif screener_mode == "⚡ 4. 변동성 돌파 (Volatility Breakout)":
        st.subheader("⚡ 래리 윌리엄스 주봉 변동성 돌파(Volatility Breakout) 인터랙티브 차트")
    else:
        st.subheader("📈 종목별 인터랙티브 캔들스틱 & Anchored VWAP 차트")
    
    available_tickers = df_filtered['ticker'].tolist() if len(df_filtered) > 0 else df_all['ticker'].tolist()
    
    default_ticker = available_tickers[0]
    for pref in ["NVDA", "AAPL", "MSFT", "PLTR", "005930.KS"]:
        if pref in available_tickers:
            default_ticker = pref
            break
            
    selected_chart_ticker = st.selectbox(
        "차트를 확인할 종목을 선택하세요:",
        options=available_tickers,
        index=available_tickers.index(default_ticker) if default_ticker in available_tickers else 0
    )

    stock_df = processed_dfs.get(selected_chart_ticker)
    stock_info = next((item for item in all_summaries if item['ticker'] == selected_chart_ticker), None)

    if stock_df is not None and stock_info is not None:
        curr_price_str = format_currency(stock_info['close'], selected_chart_ticker)
        sma20_str = format_currency(stock_info['sma20'], selected_chart_ticker)
        avwap_str = format_currency(stock_info['avwap'], selected_chart_ticker)
        box_high_str = format_currency(stock_info['amd_box_high'], selected_chart_ticker)
        entry_0pct_str = format_currency(stock_info['amd_entry_0pct'], selected_chart_ticker)
        manip_neg50_str = format_currency(stock_info['amd_manipulation_neg50pct'], selected_chart_ticker)

        # 섹터 및 상위 타임프레임(주봉/월봉) 추세 & BNF 25일선 이격도 요약 배너
        week_open_disp = format_currency(stock_info.get('week_open', 0), selected_chart_ticker)
        month_open_disp = format_currency(stock_info.get('month_open', 0), selected_chart_ticker)
        w_trend = stock_info.get('weekly_trend', '-')
        m_trend = stock_info.get('monthly_trend', '-')
        w_color = "#00e676" if "상승" in w_trend else ("#ff5252" if "하락" in w_trend else "#ffffff")
        m_color = "#00e676" if "상승" in m_trend else ("#ff5252" if "하락" in m_trend else "#ffffff")

        disp_25 = stock_info.get('disparity_25', 0.0)
        sma25_disp = format_currency(stock_info.get('sma25'), selected_chart_ticker)
        bnf_color = "#ff80ab" if disp_25 <= -30.0 else ("#ea80fc" if disp_25 <= -20.0 else ("#ff5252" if disp_25 < 0 else "#00e676"))

        st.markdown(f"""
        <div style="background-color: #1e222d; padding: 12px 18px; border-radius: 8px; margin-bottom: 14px; display: flex; flex-wrap: wrap; gap: 24px; align-items: center; border: 1px solid #2a2e39;">
            <div style="font-size: 0.95rem;">🏷️ <span style="color: #9aa0a6;">섹터:</span> <strong style="color: #ffffff;">{stock_info.get('sector', '-')}</strong></div>
            <div style="font-size: 0.95rem;">📅 <span style="color: #9aa0a6;">주봉(1W) 추세:</span> <span style="color: {w_color}; font-weight: 700;">{w_trend}</span> <span style="color: #9aa0a6; font-size: 0.82rem;">(주초 시가: {week_open_disp})</span></div>
            <div style="font-size: 0.95rem;">🗓️ <span style="color: #9aa0a6;">월봉(1M) 추세:</span> <span style="color: {m_color}; font-weight: 700;">{m_trend}</span> <span style="color: #9aa0a6; font-size: 0.82rem;">(월초 시가: {month_open_disp})</span></div>
            <div style="font-size: 0.95rem;">📉 <span style="color: #9aa0a6;">BNF 25일선 이격도:</span> <strong style="color: {bnf_color};">{disp_25:+.2f}%</strong> <span style="color: #9aa0a6; font-size: 0.82rem;">(25일선: {sma25_disp})</span></div>
        </div>
        """, unsafe_allow_html=True)

        if screener_mode == "📦 AMD 박스권 매집 모드":
            dcol1, dcol2, dcol3, dcol4, dcol5 = st.columns(5)
            dcol1.metric("현재가", curr_price_str, f"{stock_info['change_pct']:+.2f}%")
            dcol2.metric("박스권 변동률(%)", f"{stock_info['amd_box_range_pct']:.2f}%", "수렴 매집 📦")
            dcol3.metric("0.00% 라인(하단)", entry_0pct_str, "1차 진입 타점 🎯")
            dcol4.metric("-50% 라인(조작/손절)", manip_neg50_str, "유동성 스윕 방어선 🛑")
            dcol5.metric("20일 평균거래량", f"{stock_info['vol_sma20']:,}주", f"당일 {stock_info['vol_surge']}배")
        elif screener_mode == "📉 3. 25일선 이격도 매매":
            dcol1, dcol2, dcol3, dcol4, dcol5 = st.columns(5)
            dcol1.metric("현재가 (1D 종가)", curr_price_str, f"{stock_info['change_pct']:+.2f}%")
            dcol2.metric("25일선 이격도", f"{disp_25:+.2f}%", "낙폭 과대 📉")
            dcol3.metric("25일 이동평균선", sma25_disp, "1D SMA25 기준")
            diff_from_sma25 = (stock_info['close'] - stock_info['sma25']) if stock_info.get('sma25') else 0.0
            gap_disp = format_currency(abs(diff_from_sma25), selected_chart_ticker)
            dcol4.metric("25일선과의 격차", f"-{gap_disp}" if diff_from_sma25 < 0 else f"+{gap_disp}", "평균회귀 목표폭")
            dcol5.metric("20일 평균거래량", f"{stock_info['vol_sma20']:,}주", f"당일 {stock_info['vol_surge']}배")
        elif screener_mode == "⚡ 4. 변동성 돌파 (Volatility Breakout)":
            dcol1, dcol2, dcol3, dcol4, dcol5 = st.columns(5)
            dcol1.metric("현재가", curr_price_str, f"{stock_info['change_pct']:+.2f}%")
            wb_target_str = format_currency(stock_info.get('wb_target_price', 0), selected_chart_ticker)
            wb_prox = stock_info.get('wb_target_proximity_pct', 0.0)
            wb_status = stock_info.get('wb_status', '대기')
            dcol2.metric("주봉 목표가", wb_target_str, f"K={wb_k}")
            dcol3.metric("목표가 근접률", f"{wb_prox:+.2f}%", wb_status)
            dcol4.metric("이번 주 시가(Open)", week_open_disp, "주초 시가 기준")
            dcol5.metric("20일 평균거래량", f"{stock_info['vol_sma20']:,}주", f"당일 {stock_info['vol_surge']}배")
        else:
            dcol1, dcol2, dcol3, dcol4, dcol5 = st.columns(5)
            dcol1.metric("현재가", curr_price_str, f"{stock_info['change_pct']:+.2f}%")
            dcol2.metric("거래량 급증율", f"{stock_info['vol_surge']}x", f"평균 {stock_info['vol_sma20']:,}")
            dcol3.metric("SMA 20 위치", sma20_str, "상회 ✅" if stock_info['above_sma20'] else "하회 ❌")
            dcol4.metric("Anchored VWAP", avwap_str, f"{stock_info['pct_from_avwap']:+.2f}%")
            dcol5.metric("20일 박스권 상단", box_high_str, f"{stock_info['pct_from_box_high']:+.2f}%")

        chart_main_title = (
            f"{selected_chart_ticker} - {stock_info['name']} [{stock_info.get('sector', '-')}] 가격 & AMD 지표"
            if screener_mode == "📦 AMD 박스권 매집 모드"
            else (
                f"{selected_chart_ticker} - {stock_info['name']} [{stock_info.get('sector', '-')}] 가격 & BNF 25일선 (1D 일봉 전용)"
                if screener_mode == "📉 3. 25일선 이격도 매매"
                else (
                    f"{selected_chart_ticker} - {stock_info['name']} [{stock_info.get('sector', '-')}] 주봉 변동성 돌파 기준선 (K={wb_k})"
                    if screener_mode == "⚡ 4. 변동성 돌파 (Volatility Breakout)"
                    else f"{selected_chart_ticker} - {stock_info['name']} [{stock_info.get('sector', '-')}] 가격 & 기술적 지표"
                )
            )
        )

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            row_heights=[0.7, 0.3],
            subplot_titles=[
                chart_main_title,
                "거래량 (Volume & 20일 MA)"
            ]
        )

        fig.add_trace(
            go.Candlestick(
                x=stock_df.index,
                open=stock_df['Open'],
                high=stock_df['High'],
                low=stock_df['Low'],
                close=stock_df['Close'],
                name="OHLC",
                increasing_line_color="#26a69a",
                decreasing_line_color="#ef5350"
            ),
            row=1, col=1
        )

        fig.add_trace(
            go.Scatter(
                x=stock_df.index, y=stock_df['SMA_20'],
                mode='lines', name='SMA 20',
                line=dict(color='#ff9800', width=1.5)
            ),
            row=1, col=1
        )
        if 'SMA_25' in stock_df.columns:
            fig.add_trace(
                go.Scatter(
                    x=stock_df.index, y=stock_df['SMA_25'],
                    mode='lines', name='SMA 25 (BNF 기준선)',
                    line=dict(color='#e040fb', width=1.5, dash='dash')
                ),
                row=1, col=1
            )
        fig.add_trace(
            go.Scatter(
                x=stock_df.index, y=stock_df['SMA_50'],
                mode='lines', name='SMA 50',
                line=dict(color='#2196f3', width=1.5)
            ),
            row=1, col=1
        )

        fig.add_trace(
            go.Scatter(
                x=stock_df.index, y=stock_df['Anchored_VWAP'],
                mode='lines', name=f"AVWAP (Anchor: {stock_info['anchor_date']})",
                line=dict(color='#ffd600', width=2.5)
            ),
            row=1, col=1
        )

        # 박스권 상단 라인
        fig.add_trace(
            go.Scatter(
                x=stock_df.index, y=stock_df['Box_High'],
                mode='lines', name='박스권 상단 (Box High)',
                line=dict(color='#00e5ff', width=1.5, dash='dot')
            ),
            row=1, col=1
        )

        # 0.00% 라인 (박스권 하단)
        fig.add_trace(
            go.Scatter(
                x=stock_df.index, y=stock_df['Box_Low'],
                mode='lines', name='0.00% 라인 (하단)',
                line=dict(color='#00e676', width=2.0)
            ),
            row=1, col=1
        )

        # -50.0% 라인 (조작/손절가)
        if 'AMD_Manipulation_50' in stock_df.columns:
            fig.add_trace(
                go.Scatter(
                    x=stock_df.index, y=stock_df['AMD_Manipulation_50'],
                    mode='lines', name='-50% 라인 (조작/손절)',
                    line=dict(color='#ff5252', width=2.0, dash='dash')
                ),
                row=1, col=1
            )

        # 주봉 변동성 돌파 기준선 (K={wb_k})
        current_k = wb_k if ('wb_k' in locals() or 'wb_k' in globals()) else 0.5
        wb_tprice = stock_info.get('wb_target_price')
        if wb_tprice and pd.notna(wb_tprice) and wb_tprice > 0:
            fig.add_trace(
                go.Scatter(
                    x=stock_df.index, y=[wb_tprice] * len(stock_df),
                    mode='lines', name=f'주봉 목표가 (K={current_k})',
                    line=dict(color='#ffd700', width=2.0, dash='dashdot')
                ),
                row=1, col=1
            )

        vol_colors = []
        for surge in stock_df['Vol_Surge_Ratio']:
            if surge >= 2.0:
                vol_colors.append('#ab47bc')
            elif surge >= 1.5:
                vol_colors.append('#00e676')
            else:
                vol_colors.append('#546e7a')

        fig.add_trace(
            go.Bar(
                x=stock_df.index,
                y=stock_df['Volume'],
                marker_color=vol_colors,
                name="Volume"
            ),
            row=2, col=1
        )

        fig.add_trace(
            go.Scatter(
                x=stock_df.index,
                y=stock_df['Vol_SMA_20'],
                mode='lines',
                line=dict(color='#ffab00', width=1.2),
                name="Vol SMA 20"
            ),
            row=2, col=1
        )

        fig.update_layout(
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            height=620,
            margin=dict(l=20, r=20, t=50, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config={
                'responsive': True,
                'scrollZoom': False,
                'displayModeBar': False
            }
        )

        if screener_mode == "📦 AMD 박스권 매집 모드":
            st.markdown(f"#### 🔍 {selected_chart_ticker} ({stock_info['name']}) AMD 전략 기술적 진단")
            st.caption(f"산업 섹터: **{stock_info.get('sector', '-')}** | 주봉 추세: **{stock_info.get('weekly_trend', '-')}** (시가: {week_open_disp}) | 월봉 추세: **{stock_info.get('monthly_trend', '-')}** (시가: {month_open_disp}) | BNF 25일선 이격도: **{disp_25:+.2f}%** (SMA25: {sma25_disp})")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                st.markdown(f"""
                - 📦 **Accumulation (매집 수렴)**: 최근 20일간 변동폭이 **{stock_info['amd_box_range_pct']:.2f}%**로 압축되어 세력(Smart Money)의 매집이 안정적으로 진행 중입니다.
                - 🎯 **0.00% 라인 (하단)**: **{entry_0pct_str}** 지점. 하단 지지 확인 후 진입 시 손익비가 극대화되는 핵심 매수 타점입니다.
                """)
            with col_c2:
                st.markdown(f"""
                - ⚡ **Manipulation (조작 라인 & 손절선)**: -50% 라인인 **{manip_neg50_str}**. 세력의 개미 털기(Stop Hunt/Liquidity Sweep) 시 박스 하단 이탈 한계선이자 최종 손절 기준입니다.
                - 🚀 **Distribution (분배 목표가)**: 박스 상단인 **{box_high_str}** 돌파 시 상승 랠리(Distribution)가 본격화될 가능성이 높습니다.
                """)
        elif screener_mode == "📉 3. 25일선 이격도 매매":
            st.markdown(f"#### 🔍 {selected_chart_ticker} ({stock_info['name']}) BNF 25일선 이격도 전략 진단 (1D 일봉)")
            st.caption(f"산업 섹터: **{stock_info.get('sector', '-')}** | 주봉 추세: **{stock_info.get('weekly_trend', '-')}** (시가: {week_open_disp}) | 월봉 추세: **{stock_info.get('monthly_trend', '-')}** (시가: {month_open_disp}) | BNF 25일선 이격도: **{disp_25:+.2f}%** (SMA25: {sma25_disp})")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                st.markdown(f"""
                - 📉 **25일선 이격도 상태**: 현재가는 25일 이동평균선({sma25_disp}) 대비 **{disp_25:+.2f}%** 괴리 상태입니다. {'(극단적 과매도 패닉셀 구간 🚨)' if disp_25 <= -30 else ('(유효 낙폭 과대 반등 타점 🎯)' if disp_25 <= -15 else '(통상적 조정 범위)')}
                - 🔒 **1D 일봉 격리 보장**: 분봉이나 주봉이 섞이지 않은 **순수 1D 일봉(interval="1d")** 종가 기준으로 산출되어 지표의 신뢰성을 엄격히 유지합니다.
                """)
            with col_c2:
                st.markdown(f"""
                - 🎯 **BNF 역발상 매매 가이드**:
                  * 대형 우량주는 -10%~-15% 이격도에서 1차 분할 매수 고려
                  * 중소형주·테마주는 -20%~-35% 수준의 과매도 투매 출회 후 첫 양봉 출현 시 진입
                - 🛑 **리스크 관리**: 25일선 평균회귀(Mean Reversion) 시 분할 익절하며, 개별 악재(실적 쇼크 등)로 인한 구조적 하락 시 철저한 손절 기준을 준수해야 합니다.
                """)
        elif screener_mode == "⚡ 4. 변동성 돌파 (Volatility Breakout)":
            wb_target_str = format_currency(stock_info.get('wb_target_price', 0), selected_chart_ticker)
            wb_prox = stock_info.get('wb_target_proximity_pct', 0.0)
            wb_is_bo = stock_info.get('wb_is_breakout', False)
            st.markdown(f"#### 🔍 {selected_chart_ticker} ({stock_info['name']}) 래리 윌리엄스 주봉 변동성 돌파 진단")
            st.caption(f"산업 섹터: **{stock_info.get('sector', '-')}** | 주봉 추세: **{stock_info.get('weekly_trend', '-')}** (시가: {week_open_disp}) | 월봉 추세: **{stock_info.get('monthly_trend', '-')}** (시가: {month_open_disp}) | BNF 25일선 이격도: **{disp_25:+.2f}%** (SMA25: {sma25_disp})")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                st.markdown(f"""
                - ⚡ **주봉 돌파 기준가 (K={wb_k})**: **{wb_target_str}** (이번 주 시가 {week_open_disp} + 전주 변동폭 {format_currency(stock_info.get('wb_prev_range', 0), selected_chart_ticker)} × {wb_k})
                - 🎯 **목표가 근접률**: 현재가는 주봉 목표가 대비 **{wb_prox:+.2f}%** 위치입니다. {'(주봉 변동성 돌파 성공! ⚡ 모멘텀 매수 타점)' if wb_is_bo else '(목표가 돌파 대기 중 ⏳)'}
                """)
            with col_c2:
                st.markdown(f"""
                - 📊 **전주 변동폭 (Range)**: 고가 {format_currency(stock_info.get('wb_prev_high', 0), selected_chart_ticker)} ~ 저가 {format_currency(stock_info.get('wb_prev_low', 0), selected_chart_ticker)} (전주 폭: {format_currency(stock_info.get('wb_prev_range', 0), selected_chart_ticker)})
                - 💡 **주봉 변동성 돌파 전략 가이드**:
                  * 주초 시가 대비 전주 Range × K 돌파 시 장중/주간 추세 추종 매수
                  * 주간 보유 후 주말 종가 청산 또는 목표 수익 도달 시 분할 익절하는 스윙 매매에 최적화
                """)
        else:
            st.markdown(f"#### 🔍 {selected_chart_ticker} ({stock_info['name']}) 기술적 분석 진단")
            st.caption(f"산업 섹터: **{stock_info.get('sector', '-')}** | 주봉 추세: **{stock_info.get('weekly_trend', '-')}** (시가: {week_open_disp}) | 월봉 추세: **{stock_info.get('monthly_trend', '-')}** (시가: {month_open_disp}) | BNF 25일선 이격도: **{disp_25:+.2f}%** (SMA25: {sma25_disp})")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                st.markdown(f"""
                - **거래량 상태**: 20일 평균({stock_info['vol_sma20']:,}주) 대비 **{stock_info['vol_surge']}배** {'(급증 신호 포착! 🚀)' if stock_info['vol_surge'] >= 1.5 else '(평이한 수준)'}
                - **이동평균선 배열**: 20일선({sma20_str}) {'상회 ✅' if stock_info['above_sma20'] else '하회 🔻'} / 50일선({format_currency(stock_info['sma50'], selected_chart_ticker)}) {'상회 ✅' if stock_info['above_sma50'] else '하회 🔻'}
                """)
            with col_c2:
                st.markdown(f"""
                - **Anchored VWAP**: 앵커 기준일({stock_info['anchor_date']}) 기준 **{avwap_str}** 대비 **{stock_info['pct_from_avwap']:+.2f}%** {'(AVWAP 지지선 위 ✅)' if stock_info['above_avwap'] else '(AVWAP 저항선 아래 🔻)'}
                - **박스권 위치**: 최근 20일 박스권 [{format_currency(stock_info['box_low'], selected_chart_ticker)} ~ {box_high_str}] 중 고점 대비 **{stock_info['pct_from_box_high']:+.2f}%** {'(돌파 임박/돌파 성공 ⚡)' if stock_info['box_breakout'] else ''}
                """)

