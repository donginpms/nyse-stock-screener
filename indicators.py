import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple

__all__ = [
    "calculate_technical_indicators",
    "calculate_accumulation_box",
    "calculate_bnf_disparity",
    "calculate_higher_timeframe_trends",
    "calculate_weekly_volatility_breakout",
    "extract_stock_summary"
]

def calculate_bnf_disparity(df: pd.DataFrame, window: int = 25) -> Tuple[pd.Series, pd.Series]:
    """
    BNF의 25일선 이격도 매매(3번 모드) 전용 지표 계산 함수.
    반드시 일봉(1D, interval='1d') OHLCV 데이터프레임 기준으로만 작동하며,
    주봉이나 분봉 데이터 혼입을 원천 방지하고 순수 25일 이동평균선(SMA25) 및 25일 이격도(%)를 반환합니다.
    - 25일 이동평균선 (SMA25): Close의 25영업일 단순 이동평균
    - 25일 이격도 (%): ((현재가 - SMA25) / SMA25) * 100.0 (음수일수록 25일선 대비 낙폭 과대)
    """
    if df is None or len(df) == 0:
        return pd.Series(dtype='float64'), pd.Series(dtype='float64')

    work_df = df
    # 1D 일봉 타임프레임 엄격 격리: 혹시 인트라데이(분봉) 데이터가 유입되었을 경우 일별 1D 일봉으로 리샘플링하여 격리
    if isinstance(work_df.index, pd.DatetimeIndex) and len(work_df) > 1:
        diffs = work_df.index.to_series().diff().dropna()
        if not diffs.empty and (diffs < pd.Timedelta(hours=20)).any():
            work_df = work_df.resample('1D').agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }).dropna()

    sma_25 = work_df['Close'].rolling(window=window, min_periods=1).mean()
    disparity_25 = np.where(sma_25 > 0, ((work_df['Close'] - sma_25) / sma_25) * 100.0, 0.0)
    
    # 원본 인덱스에 정렬하여 반환
    res_sma = sma_25.reindex(df.index) if len(work_df) != len(df) else sma_25
    res_disp = pd.Series(disparity_25, index=work_df.index).reindex(df.index) if len(work_df) != len(df) else pd.Series(disparity_25, index=df.index)
    return res_sma, res_disp

def calculate_weekly_volatility_breakout(df: pd.DataFrame, k: float = 0.5) -> Dict[str, Any]:
    """
    주봉 기준 래리 윌리엄스 변동성 돌파 (Larry Williams Weekly Volatility Breakout, 4번 모드) 지표 계산.
    1D(일봉) 데이터로부터 이번 주(1W)와 직전 주(전주)를 정확히 그룹핑하여 계산합니다:
    - 직전 주(전주) 변동폭(Range) = 전주 고가(High) - 전주 저가(Low)
    - 이번 주 매수 목표가(Target Price) = 이번 주 시가(Open) + (전주 변동폭 * K)
    - 목표가 근접률(%) = ((현재가 - 주봉 목표가) / 주봉 목표가) * 100.0 (양수면 돌파 완료, 음수면 돌파 대기)
    - 돌파 여부 = 현재가 >= 주봉 목표가
    """
    if df is None or len(df) == 0:
        return {
            "week_open": 0.0,
            "prev_week_high": 0.0,
            "prev_week_low": 0.0,
            "prev_week_range": 0.0,
            "target_price": 0.0,
            "target_proximity_pct": 0.0,
            "is_breakout": False,
            "breakout_status": "데이터 부족",
            "status": "데이터 부족"
        }

    current_price = float(df['Close'].iloc[-1])
    idx = pd.to_datetime(df.index)
    iso_cal = idx.isocalendar()

    df_iso = df.copy()
    df_iso['iso_year'] = iso_cal.year.values
    df_iso['iso_week'] = iso_cal.week.values

    # 주차 목록을 순서대로 그룹화
    week_groups = df_iso.groupby(['iso_year', 'iso_week'], sort=False)
    unique_weeks = list(week_groups.groups.keys())

    if len(unique_weeks) < 2:
        week_open = float(df['Open'].iloc[0])
        range_val = float(df['High'].max() - df['Low'].min())
        target = week_open + (range_val * k)
        prox = ((current_price - target) / target * 100.0) if target > 0 else 0.0
        is_breakout = bool(current_price >= target)
        status_str = "돌파 성공 ⚡" if is_breakout else "돌파 대기 ⏳"
        return {
            "week_open": round(week_open, 2),
            "prev_week_high": round(float(df['High'].max()), 2),
            "prev_week_low": round(float(df['Low'].min()), 2),
            "prev_week_range": round(range_val, 2),
            "target_price": round(target, 2),
            "target_proximity_pct": round(prox, 2),
            "is_breakout": is_breakout,
            "breakout_status": status_str,
            "status": status_str
        }

    # 이번 주 데이터 (Current Week)
    curr_week_key = unique_weeks[-1]
    curr_slice = week_groups.get_group(curr_week_key)
    curr_open = float(curr_slice['Open'].iloc[0])

    # 직전 주 데이터 (Previous Week)
    prev_week_key = unique_weeks[-2]
    prev_slice = week_groups.get_group(prev_week_key)
    prev_high = float(prev_slice['High'].max())
    prev_low = float(prev_slice['Low'].min())
    prev_range = prev_high - prev_low

    target_price = curr_open + (prev_range * k)
    target_proximity_pct = ((current_price - target_price) / target_price * 100.0) if target_price > 0 else 0.0
    is_breakout = bool(current_price >= target_price)
    status_str = "돌파 성공 ⚡" if is_breakout else "돌파 대기 ⏳"

    return {
        "week_open": round(curr_open, 2),
        "prev_week_high": round(prev_high, 2),
        "prev_week_low": round(prev_low, 2),
        "prev_week_range": round(prev_range, 2),
        "target_price": round(target_price, 2),
        "target_proximity_pct": round(target_proximity_pct, 2),
        "is_breakout": is_breakout,
        "breakout_status": status_str,
        "status": status_str
    }


def calculate_technical_indicators(df: pd.DataFrame, 
                                  anchor_mode: str = "swing_low", 
                                  anchor_lookback: int = 30,
                                  custom_anchor_date: Optional[str] = None) -> pd.DataFrame:
    """
    주어진 종목의 OHLCV 데이터프레임에 보조지표(이동평균선, 거래량 지표, Anchored VWAP, 박스권, BNF 25일 이격도)를 추가 계산합니다.
    (모든 계산은 반드시 1D 일봉 타임프레임 데이터 기준으로 격리 연산됩니다.)
    """
    if df is None or len(df) < 5:
        return df

    df = df.copy()
    
    # 1. 이동평균선 (SMA 20, 25, 50, 200) 및 BNF 25일선 이격도 (반드시 일봉 1D 기준 격리)
    df['SMA_20'] = df['Close'].rolling(window=20, min_periods=1).mean()
    df['SMA_25'], df['Disparity_25'] = calculate_bnf_disparity(df, window=25)
    df['SMA_50'] = df['Close'].rolling(window=50, min_periods=1).mean()
    if len(df) >= 200:
        df['SMA_200'] = df['Close'].rolling(window=200, min_periods=1).mean()
    else:
        df['SMA_200'] = np.nan

    # 2. 거래량 이동평균 및 서지(Surge) 비율
    df['Vol_SMA_20'] = df['Volume'].rolling(window=20, min_periods=1).mean()
    df['Vol_Surge_Ratio'] = np.where(df['Vol_SMA_20'] > 0, df['Volume'] / df['Vol_SMA_20'], 1.0)

    # 3. 박스권 (최근 20일 기준 최고가/최저가)
    box_window = 20
    df['Box_High'] = df['High'].rolling(window=box_window, min_periods=5).max()
    df['Box_Low'] = df['Low'].rolling(window=box_window, min_periods=5).min()
    df['Box_Width_Pct'] = (df['Box_High'] - df['Box_Low']) / df['Box_Low'] * 100.0

    # 4. Typical Price
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3.0
    tp_vol = typical_price * df['Volume']

    # 5. Anchored VWAP 계산
    # 앵커 기준일(Anchor Index) 결정
    anchor_idx = 0
    if custom_anchor_date:
        try:
            target_dt = pd.to_datetime(custom_anchor_date)
            # anchor_date 이후 첫 번째 유효 인덱스 탐색
            mask = df.index >= target_dt
            if mask.any():
                anchor_idx = df.index.get_indexer_for(df.index[mask])[0]
        except Exception:
            anchor_idx = 0
    elif anchor_mode == "swing_low":
        # 최근 anchor_lookback 일간의 최저점 날짜
        lookback_slice = df.tail(anchor_lookback)
        min_date = lookback_slice['Low'].idxmin()
        anchor_idx = df.index.get_loc(min_date)
    elif anchor_mode == "swing_high":
        lookback_slice = df.tail(anchor_lookback)
        max_date = lookback_slice['High'].idxmax()
        anchor_idx = df.index.get_loc(max_date)
    elif anchor_mode == "period_start":
        anchor_idx = 0

    # AVWAP 누적 계산
    avwap_series = pd.Series(index=df.index, dtype='float64')
    sub_tp_vol = tp_vol.iloc[anchor_idx:]
    sub_vol = df['Volume'].iloc[anchor_idx:]

    cum_tp_vol = sub_tp_vol.cumsum()
    cum_vol = sub_vol.cumsum()

    sub_avwap = np.where(cum_vol > 0, cum_tp_vol / cum_vol, np.nan)
    avwap_series.iloc[anchor_idx:] = sub_avwap

    df['Anchored_VWAP'] = avwap_series
    df['Anchor_Date'] = df.index[anchor_idx]
    
    # 6. ICT AMD 박스권 매집 지표 (최근 20일 기준)
    df['AMD_Box_High'] = df['High'].rolling(window=20, min_periods=5).max()
    df['AMD_Box_Low'] = df['Low'].rolling(window=20, min_periods=5).min()
    box_diff = df['AMD_Box_High'] - df['AMD_Box_Low']
    df['AMD_Box_Range_Pct'] = np.where(df['AMD_Box_Low'] > 0, (box_diff / df['AMD_Box_Low']) * 100.0, 0.0)
    df['AMD_Entry_0pct'] = df['AMD_Box_Low']
    df['AMD_Manipulation_50'] = df['AMD_Box_Low'] - (box_diff * 0.5)

    # 7. 주봉 변동성 돌파 (Larry Williams Weekly Volatility Breakout) 지표
    wb_info = calculate_weekly_volatility_breakout(df, k=0.5)
    df['Weekly_Target_Price'] = wb_info['target_price']
    df['Weekly_Open'] = wb_info['week_open']

    return df



def calculate_accumulation_box(df: pd.DataFrame, period: int = 20) -> Dict[str, float]:
    """
    ICT AMD (Accumulation, Manipulation, Distribution) 전략의 박스권 매집(Accumulation) 지표 계산.
    1D(일봉) 기준 최근 period(기본 20일) 동안의 최고가, 최저가, 박스권 변동률(%),
    0.00% 진입라인(박스권 하단) 및 -50% 조작라인(손절가/유동성 스윕 기준선)을 반환합니다.
    """
    if df is None or len(df) < 5:
        return {
            "max_high": 0.0,
            "min_low": 0.0,
            "box_range_pct": 0.0,
            "entry_0pct": 0.0,
            "manipulation_neg50pct": 0.0,
            "period": period
        }
    
    actual_period = min(period, len(df))
    tail_df = df.tail(actual_period)
    max_high = float(tail_df['High'].max())
    min_low = float(tail_df['Low'].min())
    
    box_range_pct = ((max_high - min_low) / min_low * 100.0) if min_low > 0 else 0.0
    entry_0pct = min_low
    manipulation_neg50pct = min_low - ((max_high - min_low) * 0.5)

    return {
        "max_high": round(max_high, 2),
        "min_low": round(min_low, 2),
        "box_range_pct": round(box_range_pct, 2),
        "entry_0pct": round(entry_0pct, 2),
        "manipulation_neg50pct": round(manipulation_neg50pct, 2),
        "period": actual_period
    }



def calculate_higher_timeframe_trends(df: pd.DataFrame) -> Tuple[str, str, float, float]:
    """
    일봉(1D) 데이터셋으로부터 이번 주(1W) 및 이번 달(1M) 시가(Open)를 역추적하여
    현재가와의 상대적 위치를 비교, 주봉/월봉 추세를 판별합니다.
    (yfinance 추가 네트워크 호출 0건으로 초고속 연산 보장)
    - 주봉 추세: 현재가 >= 이번 주 시가(Open) -> '상승 🟢', 미만 -> '하락 🔴'
    - 월봉 추세: 현재가 >= 이번 달 시가(Open) -> '상승 🟢', 미만 -> '하락 🔴'
    """
    if df is None or len(df) == 0:
        return "-", "-", 0.0, 0.0

    current_price = float(df['Close'].iloc[-1])
    
    # 인덱스 날짜 변환 보장
    idx = pd.to_datetime(df.index)
    last_dt = idx[-1]

    # 1. 이번 주 시가 (주간 첫 거래일 Open)
    iso_year, iso_week, _ = last_dt.isocalendar()
    is_same_week = (idx.isocalendar().year == iso_year) & (idx.isocalendar().week == iso_week)
    week_slice = df[is_same_week]
    if not week_slice.empty:
        week_open = float(week_slice['Open'].iloc[0])
        weekly_trend = '상승 🟢' if current_price >= week_open else '하락 🔴'
    else:
        week_open = current_price
        weekly_trend = '-'

    # 2. 이번 달 시가 (월간 첫 거래일 Open)
    is_same_month = (idx.year == last_dt.year) & (idx.month == last_dt.month)
    month_slice = df[is_same_month]
    if not month_slice.empty:
        month_open = float(month_slice['Open'].iloc[0])
        monthly_trend = '상승 🟢' if current_price >= month_open else '하락 🔴'
    else:
        month_open = current_price
        monthly_trend = '-'

    return weekly_trend, monthly_trend, week_open, month_open


def extract_stock_summary(ticker: str, df: pd.DataFrame, company_name: str = "", sector: str = "-") -> Optional[Dict[str, Any]]:
    """
    가장 최근 거래일 기준의 스크리닝 요약 정보 추출 (모멘텀, ICT AMD 지표 및 주봉/월봉 추세, 섹터 포함)
    """
    if df is None or len(df) < 20:
        return None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    close_price = float(last['Close'])
    prev_close = float(prev['Close'])
    change_pct = ((close_price - prev_close) / prev_close) * 100.0 if prev_close > 0 else 0.0

    current_vol = float(last['Volume'])
    vol_sma20 = float(last['Vol_SMA_20']) if 'Vol_SMA_20' in last and pd.notna(last['Vol_SMA_20']) else current_vol
    vol_surge = float(last['Vol_Surge_Ratio']) if 'Vol_Surge_Ratio' in last and pd.notna(last['Vol_Surge_Ratio']) else 1.0

    sma20 = float(last['SMA_20']) if pd.notna(last.get('SMA_20')) else None
    sma25 = float(last['SMA_25']) if pd.notna(last.get('SMA_25')) else None
    sma50 = float(last['SMA_50']) if pd.notna(last.get('SMA_50')) else None
    sma200 = float(last['SMA_200']) if pd.notna(last.get('SMA_200')) else None

    # BNF 25일선 이격도 (%) = ((현재가 - SMA25) / SMA25) * 100
    disparity_25 = float(((close_price - sma25) / sma25) * 100.0) if (sma25 and sma25 > 0) else 0.0

    avwap = float(last['Anchored_VWAP']) if pd.notna(last.get('Anchored_VWAP')) else None
    anchor_date = str(last.get('Anchor_Date'))[:10] if pd.notna(last.get('Anchor_Date')) else "N/A"

    box_high = float(last['Box_High']) if pd.notna(last.get('Box_High')) else close_price
    box_low = float(last['Box_Low']) if pd.notna(last.get('Box_Low')) else close_price
    box_width = float(last['Box_Width_Pct']) if pd.notna(last.get('Box_Width_Pct')) else 0.0

    # 거리 계산
    pct_from_avwap = ((close_price - avwap) / avwap * 100.0) if avwap else 0.0
    pct_from_box_high = ((close_price - box_high) / box_high * 100.0) if box_high else 0.0

    # 조건 플래그
    above_sma20 = (close_price > sma20) if sma20 else False
    above_sma50 = (close_price > sma50) if sma50 else False
    above_sma200 = (close_price > sma200) if sma200 else False
    sma_aligned = (above_sma20 and above_sma50 and (sma20 > sma50)) if (sma20 and sma50) else False
    above_avwap = (close_price > avwap) if avwap else False
    box_breakout = (close_price >= box_high * 0.99) # 박스 상단 1% 이내 또는 상향 돌파

    # ICT AMD 박스권 매집 지표 계산
    amd_box = calculate_accumulation_box(df, period=20)
    amd_high = amd_box["max_high"]
    amd_low = amd_box["min_low"]
    amd_range_pct = amd_box["box_range_pct"]
    amd_entry = amd_box["entry_0pct"]
    amd_manipulation = amd_box["manipulation_neg50pct"]
    in_amd_box = (amd_low <= close_price <= amd_high) if (amd_low > 0 and amd_high > 0) else False

    # 주봉 및 월봉 상위 타임프레임 추세 계산
    weekly_trend, monthly_trend, week_open, month_open = calculate_higher_timeframe_trends(df)

    # 래리 윌리엄스 주봉 변동성 돌파 (4번 모드) 계산
    wb = calculate_weekly_volatility_breakout(df, k=0.5)

    return {
        "ticker": ticker,
        "name": company_name or ticker,
        "sector": sector or "-",
        "weekly_trend": weekly_trend,
        "monthly_trend": monthly_trend,
        "week_open": round(week_open, 2),
        "month_open": round(month_open, 2),
        "date": str(df.index[-1])[:10],
        "close": round(close_price, 2),
        "change_pct": round(change_pct, 2),
        "volume": int(current_vol),
        "vol_sma20": int(vol_sma20),
        "vol_surge": round(vol_surge, 2),
        "sma20": round(sma20, 2) if sma20 else None,
        "sma25": round(sma25, 2) if sma25 else None,
        "disparity_25": round(disparity_25, 2),
        "sma50": round(sma50, 2) if sma50 else None,
        "sma200": round(sma200, 2) if sma200 else None,
        "above_sma20": above_sma20,
        "above_sma50": above_sma50,
        "above_sma200": above_sma200,
        "sma_aligned": sma_aligned,
        "avwap": round(avwap, 2) if avwap else None,
        "above_avwap": above_avwap,
        "pct_from_avwap": round(pct_from_avwap, 2),
        "anchor_date": anchor_date,
        "box_high": round(box_high, 2),
        "box_low": round(box_low, 2),
        "box_width_pct": round(box_width, 1),
        "pct_from_box_high": round(pct_from_box_high, 2),
        "box_breakout": box_breakout,
        # ICT AMD 지표
        "amd_box_high": amd_high,
        "amd_box_low": amd_low,
        "amd_box_range_pct": amd_range_pct,
        "amd_entry_0pct": amd_entry,
        "amd_manipulation_neg50pct": amd_manipulation,
        "in_amd_box": in_amd_box,
        # 래리 윌리엄스 주봉 변동성 돌파 (4번 모드)
        "wb_target_price": wb["target_price"],
        "wb_target_proximity_pct": wb["target_proximity_pct"],
        "wb_is_breakout": wb["is_breakout"],
        "wb_status": wb["breakout_status"],
        "wb_prev_range": wb["prev_week_range"],
        "wb_prev_high": wb["prev_week_high"],
        "wb_prev_low": wb["prev_week_low"],
        "wb_week_open": wb["week_open"]
    }

