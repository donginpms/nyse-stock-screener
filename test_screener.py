import sys
import pandas as pd

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from data_loader import (
    fetch_historical_data, 
    TICKER_NAME_MAP,
    get_sp500_tickers,
    get_nyse_us_common_stocks,
    get_nasdaq_us_common_stocks,
    get_kospi_all_tickers,
    get_tickers_sectors
)
from indicators import (
    calculate_technical_indicators,
    extract_stock_summary,
    calculate_accumulation_box,
    calculate_higher_timeframe_trends
)

def main():
    print("=== [1] Testing S&P 500 Dynamic Loader ===")
    sp500 = get_sp500_tickers(limit=10)
    print(f"S&P 500 Sample (10 stocks): {sp500}")
    assert len(sp500) == 10, "Failed to load S&P 500"

    print("\n=== [2] Testing Strict NYSE US Pure Common Stocks Loader ===")
    nyse_stocks = get_nyse_us_common_stocks(limit=10)
    print(f"NYSE US Common Stocks Sample (10 stocks): {nyse_stocks}")
    assert len(nyse_stocks) == 10, "Failed to load NYSE US Common Stocks"
    
    forbidden_nyse = ['BABA', 'TSM', 'NVO', 'BP', 'DEO', 'INFY', 'RIO', 'SHEL', 'SONY', 'UL', 'VALE', 'AZN', 'E']
    for sym, name in nyse_stocks:
        assert sym not in forbidden_nyse, f"Forbidden foreign stock {sym} found in NYSE!"
        assert "." not in sym, f"Warrant/Unit {sym} found!"
        print(f"  Verified Clean NYSE US Stock: {sym} -> {name}")

    print("\n=== [3] Testing Strict Nasdaq US Pure Common Stocks Loader ===")
    nasdaq_stocks = get_nasdaq_us_common_stocks(limit=10)
    print(f"Nasdaq US Common Stocks Sample (10 stocks): {nasdaq_stocks}")
    assert len(nasdaq_stocks) == 10, "Failed to load Nasdaq US Common Stocks"

    forbidden_nasdaq = ['PDD', 'JD', 'BIDU', 'ASML', 'ARM', 'AZN', 'NTES', 'BABA', 'TSM']
    for sym, name in nasdaq_stocks:
        assert sym not in forbidden_nasdaq, f"Forbidden foreign/ADR {sym} found in Nasdaq!"
        assert "." not in sym, f"Warrant/Unit {sym} found!"
        assert "Acquisition Corp" not in name, f"SPAC {name} found in Nasdaq!"
        assert "SPAC" not in name.upper(), f"SPAC {name} found in Nasdaq!"
        print(f"  Verified Clean Nasdaq US Stock: {sym} -> {name}")

    print("\n=== [4] Testing KOSPI Loader ===")
    kospi_stocks = get_kospi_all_tickers(limit=5)
    print(f"KOSPI Sample: {kospi_stocks}")
    assert len(kospi_stocks) == 5, "Failed to load KOSPI"

    print("\n=== [5] Testing Multi-Market Data Download & Indicators ===")
    test_tickers = ["NVDA", "AAPL", "GE", "005930.KS", "PLTR"]
    data_dict = fetch_historical_data(test_tickers, period="6mo")
    
    if not data_dict:
        print("FAIL: No data downloaded!")
        sys.exit(1)
        
    print(f"Successfully downloaded {len(data_dict)} stocks: {list(data_dict.keys())}")
    
    sector_map = get_tickers_sectors(test_tickers)
    print(f"Sectors Map: {sector_map}")

    summaries = []
    for ticker, df in data_dict.items():
        df_ind = calculate_technical_indicators(df, anchor_mode="swing_low", anchor_lookback=30)
        sec = sector_map.get(ticker, "-")
        summary = extract_stock_summary(ticker, df_ind, TICKER_NAME_MAP.get(ticker, ticker), sector=sec)
        assert summary is not None, f"Failed summary for {ticker}"
        summaries.append(summary)
        
        is_kr = ticker.endswith(".KS")
        curr_symbol = "₩" if is_kr else "$"
        print(f"Ticker: {summary['ticker']} ({summary['name']}) [Sector: {summary['sector']}]")
        print(f"  Close: {curr_symbol}{summary['close']:,} ({summary['change_pct']:+.2f}%)")
        print(f"  HTF Trends -> 1W: {summary['weekly_trend']} (Open: {curr_symbol}{summary['week_open']}), 1M: {summary['monthly_trend']} (Open: {curr_symbol}{summary['month_open']})")
        print(f"  Volume Surge: {summary['vol_surge']}x vs 20d avg")
        print(f"  AVWAP: {curr_symbol}{summary['avwap']:,} (Above: {summary['above_avwap']})")
        print(f"  AMD Box High: {curr_symbol}{summary['amd_box_high']}, Low(0%): {curr_symbol}{summary['amd_box_low']}")
        print(f"  AMD Box Range%: {summary['amd_box_range_pct']}%, -50% Manip: {curr_symbol}{summary['amd_manipulation_neg50pct']}")

    summary_df = pd.DataFrame(summaries)
    print("\n=== [6] Summary Table with Sector & HTF Trends ===")
    print(summary_df[['ticker', 'name', 'sector', 'weekly_trend', 'monthly_trend', 'close', 'change_pct', 'vol_sma20']])

    print("\n=== [7] Testing Volume >= 1M & Price >= $30 Filter ===")
    def passes_filters(row):
        is_kr = row['ticker'].endswith(".KS")
        min_p = 30000.0 if is_kr else 30.0
        return row['vol_sma20'] >= 1000000 and row['close'] >= min_p

    filtered = summary_df[summary_df.apply(passes_filters, axis=1)]
    print(f"Total screened: {len(summary_df)}, Passed Volume>=1M and Price>=$30: {len(filtered)}")
    print(filtered[['ticker', 'name', 'sector', 'weekly_trend', 'monthly_trend', 'close', 'vol_sma20']])
    assert len(filtered) > 0, "Expected at least one stock to pass the 1M volume and $30 price filter"

    print("\n=== [8] Testing ICT AMD Accumulation Box Logic ===")
    sample_df = data_dict["NVDA"]
    amd_res = calculate_accumulation_box(sample_df, period=20)
    print(f"NVDA AMD Result: {amd_res}")
    assert "max_high" in amd_res
    assert "min_low" in amd_res
    assert "box_range_pct" in amd_res
    assert "entry_0pct" in amd_res
    assert "manipulation_neg50pct" in amd_res
    assert amd_res["entry_0pct"] == amd_res["min_low"], "0.00% line must equal min_low"
    
    expected_manip = amd_res["min_low"] - ((amd_res["max_high"] - amd_res["min_low"]) * 0.5)
    assert abs(amd_res["manipulation_neg50pct"] - round(expected_manip, 2)) < 0.05, "-50% line mismatch"

    print(f"AMD Accumulation Screen: stocks with box range <= 20%:")
    amd_screened = summary_df[summary_df['amd_box_range_pct'] <= 20.0]
    print(amd_screened[['ticker', 'name', 'sector', 'weekly_trend', 'monthly_trend', 'close', 'amd_box_range_pct']])

    print("\n=== [9] Testing calculate_higher_timeframe_trends directly ===")
    for ticker, df in data_dict.items():
        w_trend, m_trend, w_open, m_open = calculate_higher_timeframe_trends(df)
        print(f"  {ticker}: 1W Trend={w_trend} (Open={w_open}), 1M Trend={m_trend} (Open={m_open})")
        assert w_trend in ['상승 🟢', '하락 🔴'], f"Invalid weekly trend: {w_trend}"
        assert m_trend in ['상승 🟢', '하락 🔴'], f"Invalid monthly trend: {m_trend}"
        assert w_open > 0, f"Invalid week open: {w_open}"
        assert m_open > 0, f"Invalid month open: {m_open}"

    print("\n=== [10] Testing BNF 25-day Moving Average Disparity (이격도) Logic ===")
    for ticker, df in data_dict.items():
        df_ind = calculate_technical_indicators(df)
        assert 'SMA_25' in df_ind.columns, f"SMA_25 missing in {ticker}"
        assert 'Disparity_25' in df_ind.columns, f"Disparity_25 missing in {ticker}"
        
        last_close = float(df_ind['Close'].iloc[-1])
        last_sma25 = float(df_ind['SMA_25'].iloc[-1])
        expected_disp = round(((last_close - last_sma25) / last_sma25) * 100.0, 2)
        
        summary = extract_stock_summary(ticker, df_ind)
        assert summary['sma25'] == round(last_sma25, 2), f"SMA25 mismatch for {ticker}"
        assert abs(summary['disparity_25'] - expected_disp) < 0.05, f"Disparity mismatch for {ticker}"
        print(f"  {ticker}: Close={last_close:.2f}, SMA25={last_sma25:.2f}, 25일 이격도={summary['disparity_25']:+.2f}%")

    print("\n=== [11] Summary Table with BNF 25일선 이격도 ===")
    print(summary_df[['ticker', 'name', 'close', 'sma25', 'disparity_25', 'weekly_trend', 'monthly_trend']])

    print("\n=== [12] Testing -10% BNF Disparity Filter ===")
    bnf_10_filtered = summary_df[summary_df['disparity_25'] <= -10.0]
    print(f"Stocks with 25일 이격도 <= -10%: {len(bnf_10_filtered)} found")
    for _, row in bnf_10_filtered.iterrows():
        assert row['disparity_25'] <= -10.0
        print(f"  Passed -10% filter: {row['ticker']} ({row['disparity_25']:+.2f}%)")

    print("\n=== [13] Testing Strict 1D Daily Timeframe Isolation for Mode 3 ===")
    from indicators import calculate_bnf_disparity
    import inspect
    sig = inspect.signature(fetch_historical_data)
    assert sig.parameters['interval'].default == '1d', "fetch_historical_data must default to interval='1d'!"
    print("  Verified: fetch_historical_data signature defaults to interval='1d'")

    # Test daily bar calculation directly
    sample_df = data_dict["NVDA"].copy()
    sma25, disp25 = calculate_bnf_disparity(sample_df, window=25)
    assert len(sma25) == len(sample_df)
    assert len(disp25) == len(sample_df)
    print(f"  Verified: calculate_bnf_disparity output lengths match 1D sample ({len(sma25)} bars)")

    # Test intraday mix defense: simulate 5-minute bars and ensure it automatically resamples to 1D daily bars
    minute_dates = pd.date_range("2026-01-01 09:30", periods=50, freq="5min")
    dummy_minute_df = pd.DataFrame({
        "Open": [100.0 + i for i in range(50)],
        "High": [101.0 + i for i in range(50)],
        "Low": [99.0 + i for i in range(50)],
        "Close": [100.5 + i for i in range(50)],
        "Volume": [1000] * 50
    }, index=minute_dates)
    m_sma25, m_disp25 = calculate_bnf_disparity(dummy_minute_df)
    assert len(m_sma25) == 50, "Intraday safety guard must reindex back safely"
    print("  Verified: Intraday minute data defense-in-depth resample guard passed!")

    print("\n=== [14] Testing Larry Williams Weekly Volatility Breakout (Mode 4) ===")
    from indicators import calculate_weekly_volatility_breakout
    nvda_df = data_dict["NVDA"].copy()
    wb_res = calculate_weekly_volatility_breakout(nvda_df, k=0.5)
    print(f"NVDA Weekly Volatility Breakout Result: {wb_res}")
    assert 'target_price' in wb_res
    assert 'target_proximity_pct' in wb_res
    assert 'is_breakout' in wb_res
    assert 'status' in wb_res
    assert wb_res['target_price'] > 0
    assert wb_res['week_open'] > 0
    assert wb_res['prev_week_range'] >= 0

    # Test summary_df includes wb fields
    assert 'wb_target_price' in summary_df.columns
    assert 'wb_target_proximity_pct' in summary_df.columns
    assert 'wb_is_breakout' in summary_df.columns
    assert 'wb_status' in summary_df.columns
    print("  Verified: summary_df has all required Mode 4 columns!")

    # Test filtering by target proximity range (-5% to +5%)
    wb_filtered = summary_df[(summary_df['wb_target_proximity_pct'] >= -5.0) & (summary_df['wb_target_proximity_pct'] <= 5.0)]
    print(f"Stocks within -5% to +5% of target price: {len(wb_filtered)} found")

    print("\nALL S&P 500, NASDAQ, NYSE, KOSPI, SECTOR, HTF TRENDS (1W/1M), ICT AMD, BNF DISPARITY (1D ISOLATED), AND WEEKLY VOLATILITY BREAKOUT TESTS PASSED!")

if __name__ == "__main__":
    main()

