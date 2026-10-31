import re
import requests
from io import StringIO
import yfinance as yf
import pandas as pd
from typing import Dict, List, Tuple, Optional

# --- 1. 기본 내장 프리셋 ---
PRESET_UNIVERSES = {
    "AI & 테크 성장주 (팔란티어, 아이온큐, 삼사라 등)": [
        ("PLTR", "Palantir Technologies"),
        ("IONQ", "IonQ"),
        ("IOT", "Samsara"),
        ("SNOW", "Snowflake"),
        ("NET", "Cloudflare"),
        ("U", "Unity Software"),
        ("CRM", "Salesforce"),
        ("NOW", "ServiceNow"),
        ("PATH", "UiPath"),
        ("AI", "C3.ai"),
        ("SOFI", "SoFi Technologies"),
        ("SHOP", "Shopify"),
        ("UBER", "Uber Technologies"),
        ("APP", "AppLovin"),
        ("CRWD", "CrowdStrike"),
        ("DELL", "Dell Technologies"),
        ("ORCL", "Oracle")
    ],
    "NYSE 대표 우량주 & 산업주 (GE, 캐터필러 등)": [
        ("GE", "GE Aerospace"),
        ("CAT", "Caterpillar"),
        ("BA", "Boeing"),
        ("LMT", "Lockheed Martin"),
        ("DIS", "Walt Disney"),
        ("JPM", "JPMorgan Chase"),
        ("UNH", "UnitedHealth Group"),
        ("XOM", "Exxon Mobil"),
        ("V", "Visa"),
        ("WMT", "Walmart"),
        ("LLY", "Eli Lilly"),
        ("IBM", "IBM"),
        ("RTX", "RTX Corporation"),
        ("GS", "Goldman Sachs"),
        ("KO", "Coca-Cola"),
        ("MCD", "McDonald's"),
        ("PFE", "Pfizer")
    ],
    "KOSPI 주요 종목 (시총 상위 40)": [
        ("005930.KS", "삼성전자"),
        ("000660.KS", "SK하이닉스"),
        ("373220.KS", "LG에너지솔루션"),
        ("207940.KS", "삼성바이오로직스"),
        ("005380.KS", "현대차"),
        ("000270.KS", "기아"),
        ("068270.KS", "셀트리온"),
        ("105560.KS", "KB금융"),
        ("055550.KS", "신한지주"),
        ("035420.KS", "NAVER"),
        ("005490.KS", "POSCO홀딩스"),
        ("012330.KS", "현대모비스"),
        ("035720.KS", "카카오"),
        ("051910.KS", "LG화학"),
        ("006400.KS", "삼성SDI"),
        ("028260.KS", "삼성물산"),
        ("086790.KS", "하나금융지주"),
        ("032830.KS", "삼성생명"),
        ("010130.KS", "고려아연"),
        ("329180.KS", "HD현대중공업"),
        ("042660.KS", "한화오션"),
        ("267260.KS", "HD현대일렉트릭"),
        ("012450.KS", "한화에어로스페이스"),
        ("009150.KS", "삼성전기"),
        ("034730.KS", "SK"),
        ("015760.KS", "한국전력"),
        ("034020.KS", "두산에너빌리티"),
        ("000810.KS", "삼성화재"),
        ("018260.KS", "삼성에스디에스"),
        ("003550.KS", "LG"),
        ("011200.KS", "HMM"),
        ("030200.KS", "KT"),
        ("017670.KS", "SK텔레콤"),
        ("003670.KS", "포스코퓨처엠"),
        ("096770.KS", "SK이노베이션"),
        ("036570.KS", "엔씨소프트"),
        ("259960.KS", "크래프톤"),
        ("000100.KS", "유한양행"),
        ("071050.KS", "한국금융지주"),
        ("402340.KS", "SK스퀘어")
    ]
}

# 티커-기업명 전역 매핑
TICKER_NAME_MAP = {}
for category, items in PRESET_UNIVERSES.items():
    for ticker, name in items:
        TICKER_NAME_MAP[ticker] = name

# 주요 프리셋 종목의 기본 섹터 캐시
TICKER_SECTOR_MAP: Dict[str, str] = {
    "PLTR": "Technology", "IONQ": "Technology", "IOT": "Technology",
    "SNOW": "Technology", "NET": "Technology", "U": "Technology",
    "CRM": "Technology", "NOW": "Technology", "PATH": "Technology",
    "AI": "Technology", "SOFI": "Financial Services", "SHOP": "Technology",
    "UBER": "Technology", "APP": "Technology", "CRWD": "Technology",
    "DELL": "Technology", "ORCL": "Technology", "NVDA": "Technology",
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Communication Services",
    "META": "Communication Services", "TSLA": "Consumer Cyclical",
    "GE": "Industrials", "CAT": "Industrials", "BA": "Industrials",
    "LMT": "Industrials", "DIS": "Communication Services", "JPM": "Financial Services",
    "UNH": "Healthcare", "XOM": "Energy", "V": "Financial Services",
    "WMT": "Consumer Defensive", "LLY": "Healthcare", "IBM": "Technology",
    "RTX": "Industrials", "GS": "Financial Services", "KO": "Consumer Defensive",
    "MCD": "Consumer Cyclical", "PFE": "Healthcare",
    "005930.KS": "Technology", "000660.KS": "Technology", "373220.KS": "Technology",
    "207940.KS": "Healthcare", "005380.KS": "Consumer Cyclical", "000270.KS": "Consumer Cyclical",
    "068270.KS": "Healthcare", "105560.KS": "Financial Services", "055550.KS": "Financial Services",
    "035420.KS": "Communication Services", "005490.KS": "Basic Materials", "012330.KS": "Consumer Cyclical",
    "035720.KS": "Communication Services", "051910.KS": "Basic Materials", "006400.KS": "Technology"
}

def get_tickers_sectors(tickers: List[str]) -> Dict[str, str]:
    """
    여러 티커의 섹터(Sector) 정보를 멀티스레딩(ThreadPoolExecutor)으로 yfinance 객체에서 신속하게 병렬 추출합니다.
    이미 캐시된 종목은 네트워크 호출 없이 즉시 반환됩니다.
    """
    if not tickers:
        return {}

    missing = [t for t in tickers if t not in TICKER_SECTOR_MAP]
    if missing:
        from concurrent.futures import ThreadPoolExecutor

        def _fetch_one_sector(t: str) -> Tuple[str, str]:
            try:
                sec = yf.Ticker(t).info.get('sector')
                return t, str(sec) if sec else '-'
            except Exception:
                return t, '-'

        with ThreadPoolExecutor(max_workers=min(20, len(missing))) as executor:
            results = executor.map(_fetch_one_sector, missing)
            for t, sec in results:
                TICKER_SECTOR_MAP[t] = sec

    return {t: TICKER_SECTOR_MAP.get(t, '-') for t in tickers}


# --- 2. S&P 500 동적 로더 ---
SP500_FALLBACK = [
    ("AAPL", "Apple Inc."), ("MSFT", "Microsoft Corp."), ("NVDA", "NVIDIA Corp."),
    ("AMZN", "Amazon.com Inc."), ("GOOGL", "Alphabet Inc. Class A"), ("META", "Meta Platforms Inc."),
    ("TSLA", "Tesla Inc."), ("BRK-B", "Berkshire Hathaway Inc."), ("AVGO", "Broadcom Inc."),
    ("JPM", "JPMorgan Chase & Co."), ("JNJ", "Johnson & Johnson"), ("V", "Visa Inc."),
    ("PG", "Procter & Gamble Co."), ("XOM", "Exxon Mobil Corp."), ("UNH", "UnitedHealth Group Inc."),
    ("MA", "Mastercard Inc."), ("HD", "Home Depot Inc."), ("COST", "Costco Wholesale Corp."),
    ("MRK", "Merck & Co. Inc."), ("ABBV", "AbbVie Inc."), ("CRM", "Salesforce Inc."),
    ("BAC", "Bank of America Corp."), ("CVX", "Chevron Corp."), ("WMT", "Walmart Inc."),
    ("KO", "Coca-Cola Co."), ("AMD", "Advanced Micro Devices Inc."), ("PEP", "PepsiCo Inc."),
    ("LIN", "Linde plc"), ("ORCL", "Oracle Corp."), ("NFLX", "Netflix Inc."),
    ("TMO", "Thermo Fisher Scientific"), ("ADBE", "Adobe Inc."), ("WFC", "Wells Fargo & Co."),
    ("DIS", "Walt Disney Co."), ("ACN", "Accenture plc"), ("MCD", "McDonald's Corp."),
    ("CSCO", "Cisco Systems Inc."), ("ABT", "Abbott Laboratories"), ("CAT", "Caterpillar Inc."),
    ("GE", "GE Aerospace"), ("IBM", "IBM Corp."), ("INTC", "Intel Corp."),
    ("TXN", "Texas Instruments"), ("QCOM", "Qualcomm Inc."), ("AMAT", "Applied Materials"),
    ("ISRG", "Intuitive Surgical"), ("PLTR", "Palantir Technologies"), ("NOW", "ServiceNow Inc.")
]

def get_sp500_tickers(limit: Optional[int] = None) -> List[Tuple[str, str]]:
    """
    Wikipedia 공식 S&P 500 기업 목록을 동적으로 스크래핑합니다.
    S&P 500은 지수 편입 기준상 100% 미국 본토 국적 보통주(Common Stock)로 구성됩니다.
    동시에 GICS Sector 정보도 추출하여 TICKER_SECTOR_MAP에 캐시합니다.
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        r = requests.get(url, headers=headers, timeout=10)
        tables = pd.read_html(StringIO(r.text))
        df = tables[0]

        tickers = []
        for _, row in df.iterrows():
            sym = str(row['Symbol']).strip().replace('.', '-')
            name = str(row.get('Security', sym)).strip()
            sec = str(row.get('GICS Sector', '-')).strip()
            TICKER_NAME_MAP[sym] = name
            if sec and sec != '-':
                TICKER_SECTOR_MAP[sym] = sec
            tickers.append((sym, name))

        if limit and limit > 0:
            return tickers[:limit]
        return tickers
    except Exception as e:
        print(f"Error fetching Wikipedia S&P 500: {e}")
        for sym, name in SP500_FALLBACK:
            TICKER_NAME_MAP[sym] = name
        return SP500_FALLBACK[:limit] if limit else SP500_FALLBACK


# --- 3. 엄격한 순수 미국 보통주(Common Stock) 정밀 필터링 엔진 ---
# 1) 스팩(SPAC) 및 백지수표 회사 제외 패턴
SPAC_REGEX = re.compile(
    r'(Acquisition Corp|Acquisition Inc|Acquisition Co|Acquisition Group|'
    r'Acquisition Company|Acquisition Corporation|Capital Corp|'
    r'\bSPAC\b|Blank Check|Special Purpose Acquisition)',
    re.IGNORECASE
)

# 2) 비주식 상품(ETF, 펀드, 채권 등) 및 외국 기업 ADR, 영국 plc, 네덜란드 NV, 이탈리아 SpA, 조세회피처 Ordinary Shares 등 완전 배제 패턴
NON_US_OR_NON_COMMON_REGEX = re.compile(
    r'(\bADR\b|\bADS\b|American Depositary|Depositary (Receipt|Share)|'
    r'New York Registry|Registry Share|Ordinary Share|Units?|Warrants?|Rights?|'
    r'Preferred|Debenture|Trust|Fund|Income Fund|Exchange[- ]Traded|'
    r'\bL\.?P\.?\b|\bLLP\b|\bp\.?l\.?c\.?\b|\bN\.?V\.?\b|\bA/?S\b|\bS\.?p\.?A\.?\b|\bS\.?A\.?\b|'
    r'\bAG\b|\bB\.?V\.?\b|\bSE\b|\bLtd\.?\b|\bLimited\b|\bOy\b|\bCva\b|\bSpA\b|\bKGaA\b)',
    re.IGNORECASE
)

def _load_filtered_us_common_stocks_from_nasdaqtrader(exchange_code: str, limit: Optional[int] = None) -> List[Tuple[str, str]]:
    """
    Nasdaq Symbol Directory에서 지정 거래소(NYSE 'N' 또는 Nasdaq 'Q') 상장 종목 중:
    - ETF, 선물, 펀드, 테스트 이슈 제외
    - 복수 클래스/파생 기호('.', '$', '^', '-') 제외
    - 스팩(SPAC), 워런트, 유닛, 라이츠 제외
    - ADR 및 해외 법인격(plc, NV, SpA, SA, AG, Ltd, Ordinary Share) 철저히 배제
    - 순수 미국 국적 보통주(Common Stock)만 엄선하여 반환합니다.
    """
    try:
        url = "http://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"
        df = pd.read_csv(url, sep="|")
        
        # 기본 필터
        sub_df = df[(df['Listing Exchange'] == exchange_code) & (df['ETF'] == 'N') & (df['Test Issue'] == 'N')]
        sub_df = sub_df[~sub_df['Symbol'].str.contains(r'[\.\$\^\-]', regex=True, na=False)]
        
        tickers = []
        for _, row in sub_df.iterrows():
            sym = str(row['Symbol']).strip()
            name = str(row.get('Security Name', sym)).strip()
            
            # 스팩 배제
            if SPAC_REGEX.search(name):
                continue
            # ADR 및 비주식/해외기업 배제
            if NON_US_OR_NON_COMMON_REGEX.search(name):
                continue
            
            # 순수 보통주 명칭 확인
            if 'Common Stock' in name or 'Common Shares' in name or 'Class A' in name or 'Class B' in name:
                TICKER_NAME_MAP[sym] = name
                tickers.append((sym, name))
                
        if limit and limit > 0:
            return tickers[:limit]
        return tickers
    except Exception as e:
        print(f"Error fetching dynamic US Common Stocks for exchange {exchange_code}: {e}")
        return []

def get_nyse_us_common_stocks(limit: Optional[int] = None) -> List[Tuple[str, str]]:
    """NYSE 상장 미국 본토 순수 보통주 목록"""
    stocks = _load_filtered_us_common_stocks_from_nasdaqtrader('N', limit)
    if not stocks:
        return PRESET_UNIVERSES["NYSE 대표 우량주 & 산업주 (GE, 캐터필러 등)"]
    return stocks

def get_nasdaq_us_common_stocks(limit: Optional[int] = None) -> List[Tuple[str, str]]:
    """Nasdaq 상장 미국 본토 순수 보통주 목록"""
    stocks = _load_filtered_us_common_stocks_from_nasdaqtrader('Q', limit)
    if not stocks:
        return [("AAPL", "Apple Inc."), ("MSFT", "Microsoft Corp."), ("NVDA", "NVIDIA Corp."), ("AMZN", "Amazon.com Inc."), ("GOOGL", "Alphabet Inc."), ("META", "Meta Platforms Inc."), ("TSLA", "Tesla Inc.")]
    return stocks


# --- 4. KOSPI 동적 로더 ---
def get_kospi_all_tickers(limit: Optional[int] = None) -> List[Tuple[str, str]]:
    """
    FinanceDataReader를 통해 KOSPI 시장 상장 종목을 시가총액(Marcap) 내림차순으로 로드합니다.
    """
    try:
        import FinanceDataReader as fdr
        df = fdr.StockListing('KOSPI')
        if 'Marcap' in df.columns:
            df = df.sort_values(by='Marcap', ascending=False)
            
        tickers = []
        for _, row in df.iterrows():
            code = str(row['Code']).strip()
            name = str(row.get('Name', code)).strip()
            ticker = f"{code}.KS"
            TICKER_NAME_MAP[ticker] = name
            tickers.append((ticker, name))
            
        if limit and limit > 0:
            return tickers[:limit]
        return tickers
    except Exception as e:
        print(f"Error fetching dynamic KOSPI tickers: {e}")
        return PRESET_UNIVERSES["KOSPI 주요 종목 (시총 상위 40)"]


# --- 5. 대용량 yfinance 병렬 배치 다운로더 ---
def fetch_historical_data(tickers: List[str], period: str = "1y", interval: str = "1d", chunk_size: int = 80) -> Dict[str, pd.DataFrame]:
    """
    yfinance를 활용하여 여러 티커의 데이터를 chunk_size 단위로 배치 분할 수집합니다.
    3번 모드(BNF 25일선 이격도 매매) 및 일봉 분석을 위해 반드시 interval='1d' 일봉 타임프레임으로 철저히 격리되어 수집됩니다.
    """
    if not tickers:
        return {}

    clean_tickers = [t.strip().upper() for t in tickers if t.strip()]
    if not clean_tickers:
        return {}

    # 3번 모드(BNF 25일선 이격도)를 포함한 지표 연산을 위해 일봉(1D) 타임프레임 고정 격리
    safe_interval = "1d" if interval.lower() in ["1d", "daily"] else interval

    result: Dict[str, pd.DataFrame] = {}

    for i in range(0, len(clean_tickers), chunk_size):
        chunk = clean_tickers[i:i + chunk_size]
        try:
            data = yf.download(
                tickers=chunk,
                period=period,
                interval=safe_interval,  # 명시적 interval="1d" 강제 설정
                auto_adjust=False,
                group_by="ticker",
                threads=True,
                progress=False
            )
        except Exception as e:
            print(f"Error downloading chunk {chunk[:3]}...: {e}")
            continue

        if len(chunk) == 1:
            ticker = chunk[0]
            df = data.copy()
            if isinstance(df.columns, pd.MultiIndex):
                if ticker in df.columns.levels[0]:
                    df = df[ticker]
                else:
                    df.columns = df.columns.get_level_values(-1)
            df = df.dropna(subset=['Close', 'Volume'])
            if len(df) > 0:
                result[ticker] = df
        else:
            for ticker in chunk:
                try:
                    if isinstance(data.columns, pd.MultiIndex):
                        if ticker in data.columns.levels[0]:
                            df_ticker = data[ticker].dropna(subset=['Close', 'Volume']).copy()
                            if len(df_ticker) > 0:
                                result[ticker] = df_ticker
                        elif ticker in data.columns:
                            df_ticker = data[[ticker]].dropna().copy()
                            result[ticker] = df_ticker
                    else:
                        result[ticker] = data.copy()
                except Exception as e:
                    print(f"Error parsing ticker {ticker}: {e}")

    return result
