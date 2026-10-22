# MOIPJI — 개발 명세서

> 오늘 날씨에, 모입지?

- Version: 1.2
- Python: 3.14
- Framework: Streamlit
- Weather API: OpenWeatherMap
- Entry Point: `weather.py`
- Git Branch: `feature/weather`
- 개발 방식: 규칙 기반 추천 (AI API 사용하지 않음)

## 1. 서비스 개요

MOIPJI는 날씨와 사용자가 선택한 패션 스타일을 조합해 오늘의 옷차림을 추천하는 모바일 중심 웹앱이다.

**핵심 UX 콘셉트: 날씨는 숫자로, 옷차림은 말로.**

날씨 수치보다 사용자가 무엇을 입어야 하는지 먼저 알려주고, 위트 있는 UX Writing과 직관적인 코디 카드로 결과를 전달한다.

## 2. 핵심 기능

### F01. 지역별 날씨 조회

- 기본 지역: 서울
- 주요 도시 선택 기능
- 현재 기온, 체감온도, 습도, 풍속, 날씨 상태 표시
- OpenWeatherMap의 실제 데이터 사용
- API 오류 및 데이터 누락 처리

### F02. 시간대별 날씨

오전·오후·저녁 탭으로 구성한다.

| 시간대 | 대표 시각 | 사용자 질문 |
|---|---|---|
| 오전 | 08:00 | 오늘 뭐 입지? |
| 오후 | 13:00 | 지금은 뭐 입지? |
| 저녁 | 19:00 | 저녁엔 뭐 걸치지? |

- 현재 시간대 탭을 기본 선택한다.
- 선택한 시간대와 가장 가까운 실제 예보 데이터를 사용한다.
- 오전·오후·저녁 탭 전환 시 날씨, 추천 아이템, 문구를 함께 변경한다.
- 데이터가 없는 시간대는 안내 메시지를 표시한다.
- 예보 시각은 선택 지역의 현지 시각으로 처리한다.
- 현재 날씨와 미래 예보를 명확하게 구분한다.

### F03. 스타일 선택

사용자가 원하는 코디 스타일을 선택할 수 있다.

| 스타일 | 특징 |
|---|---|
| Simple | 기본 아이템 중심, 깔끔한 조합 |
| Modern | 정돈된 실루엣, 셔츠와 슬랙스 |
| Casual | 편안한 일상복, 데님과 맨투맨 |
| Lovely | 부드러운 색감, 가디건과 스커트 |
| Street | 오버핏, 후드와 와이드 팬츠 |

- 기본 선택값: Simple
- 스타일 변경 시 추천 아이템 및 완성 룩이 함께 변경된다.
- 스타일별 추천 데이터는 별도 파일에서 관리한다.

### F04. 체감온도 기반 코디 추천

| 체감온도 | 기본 추천 |
|---|---|
| 28°C 이상 | 반팔, 반바지, 얇은 소재 |
| 23~27°C | 반팔, 얇은 셔츠, 면바지 |
| 17~22°C | 긴팔, 가디건, 얇은 재킷 |
| 12~16°C | 니트, 재킷, 트렌치코트 |
| 6~11°C | 두꺼운 니트, 코트 |
| 5°C 이하 | 패딩, 목도리, 보온 의류 |

- 체감온도를 기준으로 의류 두께를 결정한다.
- 선택한 스타일에 따라 구체적인 아이템 조합을 변경한다.
- 상의·하의·아우터를 각각 추천한다.
- 아우터가 필요하지 않으면 '아우터 없이도 좋아요'로 표시한다.
- 온도 경계에서 추천이 누락되지 않도록 연속적인 구간으로 구현한다.

**추가 날씨 조건**
- 강수확률 50% 이상: 우산 추천
- 풍속 8m/s 이상: 바람막이 안내
- 일교차 10°C 이상: 겉옷 지참 안내
- 여러 조건이 동시에 발생하면 핵심 안내를 우선 표시한다.

### F05. 개별 아이템 및 완성 룩

추천 결과는 다음 정보를 포함한다.

**개별 아이템**
- 상의: 아이템명 및 추천 이유
- 하의: 아이템명 및 추천 이유
- 아우터: 아이템명 및 추천 이유
- 추가 준비물: 우산, 목도리 등

**완성 룩**
- 추천 코디의 전체 이미지 영역
- 스타일명
- 상의 + 하의 + 아우터 조합
- 한 줄 스타일 설명

이미지와 실제 추천 아이템은 일치해야 한다.

## 3. 이미지 구현

MVP에서는 이미지 표시 영역과 데이터 연결 구조만 구현한다. 실제 이미지는 추후 제작 및 업로드한다.

### 구현 조건

- 코디마다 고유 ID를 부여한다.
- 각 코디 데이터에 이미지 파일 경로를 연결한다.
- 이미지가 없는 경우 플레이스홀더를 표시한다.
- 이미지 파일을 추후 추가하면 해당 경로에서 자동으로 불러온다.
- 개별 아이템 이미지와 완성 룩 이미지를 구분할 수 있도록 데이터 구조를 설계한다.
- 실제 이미지가 없는 상태에서 임의의 이미지를 추천 결과로 표시하지 않는다.
- 이미지 생성 API 및 사용자 이미지 업로드 기능은 구현하지 않는다.

### 이미지 경로 예시

```text
assets/outfits/simple_12_16_01.webp
assets/outfits/modern_12_16_01.webp
assets/outfits/lovely_12_16_01.webp
```

## 4. OpenWeatherMap API

공식 문서: https://openweathermap.org/api

### 4.1 Current Weather API

Endpoint:

`https://api.openweathermap.org/data/2.5/weather`

Parameters:
- `lat`
- `lon`
- `appid`
- `units=metric`
- `lang=kr`

사용 필드:
- `main.temp`
- `main.feels_like`
- `main.humidity`
- `weather[0].description`
- `weather[0].icon`
- `wind.speed`
- `dt`

### 4.2 5 Day / 3 Hour Forecast API

Endpoint:

`https://api.openweathermap.org/data/2.5/forecast`

Parameters:
- `lat`
- `lon`
- `appid`
- `units=metric`
- `lang=kr`

사용 필드:
- `list[].dt`
- `list[].main.temp`
- `list[].main.feels_like`
- `list[].pop`
- `list[].weather`
- `list[].wind.speed`
- `city.timezone`

### 데이터 처리

- 3시간 간격 예보를 오전·오후·저녁으로 분류한다.
- 각 대표 시각에 가장 가까운 예보를 사용한다.
- 당일 예보 중 최고·최저 기온 차이로 일교차를 계산한다.
- 예보 데이터가 부족하면 일교차 안내를 생략한다.
- API 응답 시각을 선택 지역의 현지 시간으로 변환한다.
- 임의의 기상 데이터를 생성하지 않는다.

### API Key 관리

환경변수: `OPENWEATHER_API_KEY`

- 로컬: `.env`
- 배포: Streamlit Secrets 또는 환경변수
- `.env`는 `.gitignore`에 등록
- API Key 하드코딩 금지
- `st.cache_data`로 API 응답 캐싱
- 타임아웃 및 오류 처리 구현

## 5. UX Writing

### 작성 원칙

- 친구처럼 친근하고 재치 있는 말투
- 짧고 명확한 한 줄 메시지
- 과도한 유행어 및 이모지 사용 지양
- 실제 날씨와 모순되는 표현 금지
- 위트 있는 문장 아래 구체적인 추천 아이템 표시
- 문구는 조건별 템플릿으로 관리

### 문구 예시

| 조건 | UX Writing |
|---|---|
| 28°C 이상 | 오늘은 반팔도 더울 각! |
| 23~27°C | 가볍게 입고 나가도 좋겠어. |
| 17~22°C | 반팔만 입기엔 살짝 애매해. |
| 12~16°C | 재킷 하나 걸치면 딱! |
| 6~11°C | 코트 출동할 타이밍. |
| 5°C 이하 | 패딩 안 입으면 후회할지도? |
| 강수확률 높음 | 우산 없이 나갔다간 머리 감기 2회차. |
| 일교차 큼 | 낮에 속지 마. 저녁엔 추워! |

추천 문구는 날씨 조건과 시간대에 따라 변경한다.

## 6. UX/UI 구성

### 정보 위계

1. 오늘의 한 줄 코디 결론
2. 완성 룩 이미지
3. 상의·하의·아우터 추천
4. 날씨 및 추천 근거
5. 추가 준비물

### 화면 구조

**Header**
- MOIPJI 로고
- 슬로건
- 지역 선택

**Weather Summary**
- 현재 날씨 아이콘
- 기온 및 체감온도
- 날씨 상태

**Time Selector**
- 오전 / 오후 / 저녁

**Style Selector**
- Simple / Modern / Casual / Lovely / Street

**Outfit Result**
- 위트 있는 한 줄 메시지
- 완성 룩 이미지 또는 플레이스홀더
- 상의·하의·아우터 아이템 카드
- 추천 이유

**Additional Tips**
- 우산, 겉옷, 바람막이 등 준비물

**Footer**
- OpenWeather 출처
- 데이터 갱신 시각

### UI 원칙

- 모바일 퍼스트 반응형
- 깔끔한 카드형 레이아웃
- 밝은 배경
- 충분한 여백
- 명확한 타이포그래피
- 터치하기 쉬운 컨트롤
- 과도한 장식과 애니메이션 제외
- Streamlit 기본 컴포넌트를 우선 활용

## 7. 프로젝트 구조

```text
features/weather/
├── weather.py
├── weather.md
├── weather_image.md
├── __init__.py
├── requirements.txt
├── .env.example
├── .gitignore
├── data/
│   ├── outfits.json
│   ├── rules.json
│   └── cities.json
├── assets/
│   ├── outfits/
│   └── items/
└── tests/
```

### requirements.txt

```text
streamlit
requests
python-dotenv
```

Python 3.14와 호환되는 패키지 버전을 사용한다.

### 데이터 관리

`outfits.json`에 다음 정보를 저장한다.

- outfit_id
- style
- temperature_range
- top
- bottom
- outer
- accessories
- description
- image_path

코디 데이터와 이미지 경로는 분리하여 관리한다.

## 8. 개발 규칙

1. Python 3.14 환경을 사용한다.
2. OpenWeatherMap API만 연동한다.
3. AI API 및 데이터베이스는 사용하지 않는다.
4. 날씨 조회, 데이터 가공, 코디 추천, 문구 선택을 함수로 분리한다.
5. 코디 추천은 Python 조건문 및 JSON 데이터로 구현한다.
6. 스타일이나 시간대를 변경하면 결과가 함께 갱신되어야 한다.
7. 이미지가 없어도 서비스가 정상 동작해야 한다.
8. 실제 API 데이터가 없으면 임의의 날씨를 생성하지 않는다.
9. API Key를 GitHub에 노출하지 않는다.
10. 팀의 다른 서비스 파일 및 공통 구조는 임의로 수정하지 않는다.

## 9. MVP 완료 기준

- [ ] Python 3.14에서 정상 실행
- [ ] OpenWeatherMap API 연결
- [ ] 지역별 날씨 조회
- [ ] 오전·오후·저녁 시간대 전환
- [ ] 스타일 5종 선택
- [ ] 날씨와 스타일에 따른 코디 추천
- [ ] 상의·하의·아우터 개별 표시
- [ ] 완성 룩 이미지 플레이스홀더
- [ ] 이미지 경로 연결 구조
- [ ] 위트 있는 UX Writing
- [ ] 강수확률·풍속·일교차 안내
- [ ] 모바일 UI 대응
- [ ] API 오류 처리
- [ ] 환경변수 보안 처리

## 10. 실행

```bash
cd features/weather
pip install -r requirements.txt
streamlit run weather.py
```

## 11. 이번 MVP 제외 범위

- OpenAI API 및 이미지 생성 API
- 회원가입 및 로그인
- 데이터베이스
- 사용자 옷장 관리
- 이미지 인식
- 사용자 이미지 업로드
- 코디 저장 및 공유
- 푸시 알림

실제 코디 이미지는 추후 별도로 제작하여 `assets/outfits/`에 추가한다.