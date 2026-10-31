# 📈 글로벌 모멘텀 주식 스크리너 (S&P 500 · Nasdaq · NYSE · KOSPI)

Streamlit과 `yfinance`, `FinanceDataReader`를 활용하여 미국 및 한국 주요 시장의 유망 종목을 실시간 발굴하는 웹 대시보드입니다.  
스마트폰(갤럭시 노트 등)과 태블릿(갤럭시 패드 등)의 세로/가로 화면에서도 반응형으로 최적화되어 있습니다.

---

## 🌟 핵심 기능

1. **4대 주요 시장 유니버스 완벽 지원**:
   - 🇺🇸 **S&P 500**: Wikipedia 실시간 동적 연동 (100% 미국 본토 보통주 503개)
   - 🇺🇸 **Nasdaq 전체**: 스팩(SPAC), 해외 ADR, ETF, 펀드 철저 배제 (순수 미국 보통주 약 2,250개)
   - 🇺🇸 **NYSE 전체**: 스팩, 해외 ADR, 비주식 펀드 철저 배제 (순수 미국 보통주 약 1,340개)
   - 🇰🇷 **KOSPI 시장**: 시총 상위 40대 대표주 및 전체 940여 개 종목 지원 (원화 ₩ 단위 자동 표기)
   - 🚀 **테마 프리셋 및 커스텀 티커**: AI/테크 모멘텀, 우량 산업주, 사용자 직접 티커 입력

2. **정밀 기술적 지표 & 유동성 필터링 엔진**:
   - **유동성 하한선**: 20일 평균 거래량 $\ge 1\text{M}$ (1,000,000주) 필터 (슬라이더 조절 가능)
   - **최소 주가**: 미국 $\$30$ 이상 / 한국 $₩30,000$ 이상 필터
   - **거래량 급증 (Volume Surge)**: 20일 평균 거래량 대비 1.5배, 2.0배 이상 급증 종목
   - **이동평균선 (SMA)**: 20일/50일/200일선 상회 및 이평선 정배열(SMA20 > SMA50)
   - **Anchored VWAP (AVWAP)**: 최근 스윙 저점/고점/기간시작점 기준 누적 거래량 가중평균가
   - **박스권 (Box Range)**: 최근 20일 박스권 고점 대비 근접도 및 돌파 종목 포착

3. **모바일 & 태블릿 친화적 UI 및 CSV 내보내기**:
   - 상단/하단 원클릭 맞춤형 CSV 다운로드 (`SP500_screened_stocks_YYYYMMDD.csv` 등 유니버스별 자동 명명)
   - 모바일 엑셀 및 구글 스프레드시트 한글 깨짐 방지 (`utf-8-sig` BOM 적용)
   - 터치 스크롤 간섭 방지 반응형 Plotly 인터랙티브 차트

---

## 💻 1. 로컬 환경 실행 방법

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. 대시보드 구동
streamlit run app.py
```
브라우저에서 `http://localhost:8501` 접속 (또는 `run_app.bat` 파일 더블클릭)

---

## ☁️ 2. 클라우드 무료 배포 가이드 (Streamlit Community Cloud)

휴대폰이나 태블릿에서 PC를 켜두지 않고도 **24시간 언제 어디서나 접속**하려면 Streamlit Community Cloud(무료)에 배포하시면 됩니다.

### [1단계] GitHub 저장소에 코드 업로드
1. [GitHub](https://github.com/)에 로그인하고 새로운 저장소(New Repository)를 생성합니다. (예: `stock-screener-dashboard`, Public 권장)
2. 로컬 프로젝트 폴더(`nyse_stock_screener`)에서 터미널을 열고 다음 명령어를 실행합니다:
```bash
git init
git add .
git commit -m "Initial commit for Stock Screener"
git branch -M main
git remote add origin https://github.com/사용자아이디/저장소이름.git
git push -u origin main
```

### [2단계] Streamlit Cloud에서 1클릭 배포
1. [share.streamlit.io](https://share.streamlit.io/)에 접속하여 GitHub 계정으로 로그인합니다.
2. 우측 상단의 **`New app`** 버튼을 클릭합니다.
3. 방금 올린 저장소를 선택합니다:
   - **Repository**: `사용자아이디/저장소이름`
   - **Branch**: `main`
   - **Main file path**: `app.py`
4. **`Deploy!`** 버튼을 누르면 1~2분 안에 전 세계 어디서나 접속 가능한 고유 URL이 발급됩니다. (예: `https://my-stock-screener.streamlit.app`)

---

## 📱 3. 갤럭시 노트(스마트폰) & 갤럭시 패드(태블릿) 홈 화면에 앱처럼 추가하기

생성된 대시보드 웹 주소를 스마트폰과 패드에 추가하면 별도의 앱 설치 없이도 일반 앱처럼 탭하여 전체 화면으로 실행할 수 있습니다.

### 삼성 인터넷(Samsung Internet) 브라우저 사용 시:
1. 갤럭시 노트 또는 패드에서 대시보드 URL에 접속합니다.
2. 브라우저 우측 하단의 **메뉴(≡)** 아이콘을 탭합니다.
3. **`현재 페이지 추가`** -> **`홈 화면`**을 선택합니다.
4. 홈 화면에 '주식 스크리너' 아이콘이 생성되어, 터치 시 상단 주소창 없이 앱처럼 깔끔하게 구동됩니다.

### 크롬(Chrome) 브라우저 사용 시:
1. 갤럭시 노트 또는 패드에서 대시보드 URL에 접속합니다.
2. 우측 상단의 **더보기(⋮)** 아이콘을 탭합니다.
3. **`홈 화면에 추가`** 또는 **`앱 설치`**를 선택합니다.
4. 이제 홈 화면에서 터치 한 번으로 실시간 스크리닝 및 CSV 다운로드가 가능합니다.
