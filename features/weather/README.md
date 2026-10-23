# 날씨 + 오늘 코디 — MOIPJI (`features/weather`)
R
**담당:** 팀원 E · **PRD:** Epic F · **명세:** [weather.md](./weather.md) · **이미지 명세:** [weather_image.md](./weather_image.md)

> 오늘 날씨에, 모입지?

외출할 시간의 날씨와 고른 스타일로 옷차림을 추천하고, 그 코디를 입은 도트 캐릭터(미니미)로 보여 준다. 준비물을 챙기고 코디를 옷장에 저장할 수 있다. 날씨 조회 함수는 홈과 오늘의 한 끼도 가져다 쓴다.

## 실행

```bash
cd features/weather
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt   # macOS·Linux: .venv/bin/python
copy .env.example .env                                     # OPENWEATHER_API_KEY=발급받은 키
.venv\Scripts\python -m streamlit run weather.py
.venv\Scripts\python -m pytest tests                       # 로직 테스트 (실제 API는 호출하지 않음)
```

- Python 3.14, Streamlit 1.66.1
- API 키는 `OPENWEATHER_API_KEY` 또는 `WEATHER_KEY`를 `st.secrets` → 환경변수(`.env`) 순서로 찾는다
- `features/weather` 폴더에서 실행해야 `.streamlit/config.toml` 테마가 적용된다

## 주요 기능

- 들어올 때마다 게임처럼 한 단계에 하나씩(닉네임 → 성별 → 지역 → 꾸미기 → 시작) 내 정보를 받는다. 진행 단계를 표시하고, 큰 안내 캐릭터가 말하고 손 흔들고 박수치며 말을 건다. 이번 접속에만 저장해서 새로고침하면 처음 화면으로 돌아간다. 맨 위 톱니바퀴에서 고치면 고른 아이템·색·챙긴 준비물은 초기화된다
- 다이어리 옆 GNB(JOOYOU·guest·meal·reading·MOIPJI)로 팀 서비스로 이동. 좁은 화면은 톱니바퀴 오른쪽 '=' 메뉴
- 국가 → 도시 선택 (대한민국 16곳 + 몰디브·필리핀·태국·일본·중국·대만·미국), 오늘 0시~내일 21시(48시간, 3시간 간격) 외출 시간 여러 칸 선택 후 확정, 날씨 새로고침
- 브라이트/어두움 모드 (맨 위 오른쪽)
- 외출 중 가장 추운 때 기준 코디 추천 (성별마다 스타일 5종 × 체감 구간 6개 = 30개, 여성 Lovely / 남성 Dandy)
- 준비물: 우산·마스크(미세먼지 나쁨)·핫팩·귀마개·물·여벌 가디건·바람막이·양산·선글라스 + 코디 소품 (준비물마다 색 선택)
- 미니미: 내 성별·키·체격에 맞춘 체형으로 추천 코디(고른 색 포함)를 입고 챙긴 준비물을 든 도트 캐릭터, 날씨별 바깥 풍경, 말풍선
- "다른 아이템 둘러보기"를 누르면 스타일 안에서 상의·하의·원피스·세트·아우터·기타(준비물·소품)를 하나씩 "선택"하고 색도 고른다. 안경/선글라스·모자·우산/양산은 하나만, 가디건류·자켓류도 하나씩. 아우터에 가죽 자켓·숏 경량 패딩 (얇은 셔츠는 상의로도), 색상 선택 팔레트, 챙길 것 카드, 옷장(이름·태그, 리스트/썸네일)
- 미니미 포즈: 우산을 들어 올려 쓰고, 물·핫팩은 몸 앞에 든다. 챙길 때 동작을 한 번 보여 주고, 배경의 구름·비·눈·별이 계속 움직인다

자세한 동작과 기준값은 [weather.md](./weather.md)를 본다.

## 파일

| 파일 | 내용 |
|---|---|
| `weather.py` | 날씨 조회·가공, 추천, 옷장 저장, 화면(진입점) |
| `minimi.py` | 도트 그림: 미니미·풍경(`render_scene`), 옷 아이콘(`render_garment`), 준비물 아이콘(`render_supply`) |
| `theme.py` | 싸이월드 다이어리 외곽 프레임과 팀 서비스 GNB (화면 바깥 레이어만) |
| `__init__.py` | 병합용 내보내기 |
| `data/outfits.json` | 스타일, 컬러 팔레트, 아이템(도트 모양 포함), 코디 30개 |
| `data/rules.json` | 체감 구간, 시간대, 문구, 준비물 조건·문장, 말풍선, 기본 태그, 기준값 |
| `data/cities.json` | 지역 좌표 |
| `.streamlit/config.toml` | 단독 실행용 테마 |
| `tests/test_weather.py` | pytest |
| `.local/wardrobe.json` | 옷장 저장 파일 (`.gitignore`, 커밋하지 않음) |

문구·기준값·코디는 코드 수정 없이 `data/*.json`에서 고친다.

## 병합 시 쓰는 것 (`__init__.py`)

```python
from features.weather import page, ROUTE, get_today_summary, get_weather

ROUTE                     # "weather"
page()                    # 페이지 그리기. st.set_page_config를 부르지 않는다
get_today_summary()       # {"title": "MOIPJI", "value": "13°C · 재킷 하나 걸치면 딱!", "status": "ok" | "error"}
get_weather(lat, lng)     # 아래 형태, 실패하면 WeatherError
```

`get_weather` 반환 형태 (반환 형태를 바꿀 때는 팀원 A와 먼저 합의):

```python
{
    "temp": 13.2, "feels_like": 11.4,                      # ℃
    "precip": {"type": "none" | "rain" | "snow", "probability": 0.0 ~ 1.0 | None},
    "min": 8.0, "max": 16.0,                                # 오늘
    "hourly": [{"time": "ISO 8601", "temp": ..., "feels_like": ..., "pop": ...}, ...],  # 3시간 × 8
}
```

- 날씨 응답은 `st.cache_data(ttl=600)`로 캐시돼 홈·한 끼가 같이 불러도 중복 호출이 없다
- 위젯 `key`, `st.session_state` 키, 캐시 함수 이름에는 `weather_` 접두사를 붙였다
- 페이지 CSS는 `.stApp:has(.st-key-weather_root)`처럼 MOIPJI 화면이 있을 때만 적용되도록 범위를 좁혔다

## 팀 템플릿과 다른 점

병합 담당자가 알아야 할 차이다.

- 단독 실행 파일은 `dev.py`가 아니라 `weather.py` 자체다 (`if __name__ == "__main__"`에서만 `st.set_page_config` 호출)
- API 호출 코드는 `clients/`로 나누지 않고 `weather.py` 안에 있다
- 의존성은 이 폴더의 `requirements.txt`에 있다 (루트 `requirements.txt`에 합쳐야 함)
- 페이지 배경 그라데이션·글꼴을 바꾸는 CSS를 넣는다 (위 범위 제한 적용)
- 옷장을 로컬 파일(`.local/wardrobe.json`)에 저장한다. 배포 환경에서는 모든 방문자가 같은 옷장을 쓰게 되므로 저장 방식을 정해야 한다
