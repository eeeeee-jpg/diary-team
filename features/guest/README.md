# 밥때 손님 (`features/guest`)

**담당:** 팀원 C · **PRD:** Epic D (서비스 이름은 가제)

끼니를 기록하면 강아지·고양이 손님이 찾아오고, 만난 손님이 도감 카드로 쌓인다.

## 만들 것
- D-1 손님 방문 (P0): 끼니 기록 시 1마리, 품종은 가중 랜덤, 하루 최대 3회, 수정해도 중복 방문 없음, 희귀도 확률은 설정 파일
- D-2 도감 (P0): 품종 카드 격자, 미발견은 실루엣, 수집률, 개/고양이 필터, 카드 상세
- D-3 연속 일수 (P1), D-4 단골 레벨 (P1)

## 병합 규칙
- `__init__.py`는 `page()`, `ROUTE`, `get_today_summary()`만 내보낸다. `ROUTE = "guest"`
- `st.set_page_config`는 `page()` 안에서 부르지 않는다. 단독 실행 파일 `dev.py`에서만 부른다.
- 위젯 `key`, `st.session_state` 키, 저장소 이름에 `guest_` 접두사를 붙인다.
- 개발 중에는 "끼니 기록됨" 이벤트를 발생시키는 테스트 버튼으로 단독 검증한다. 병합 시 `meal_logged { meal_log_id, slot, date }` 수신으로 교체한다. (발행은 팀원 A, 전달 방식은 PRD 13장 미정)
- 다른 서비스와의 참조는 `GuestVisit.meal_log_id` 하나뿐이다. 병합 전에는 목 ID를 쓴다.
- 확률표와 품종 목록은 설정 파일(`toml`/`json`)로 분리한다.
- 저장 방식은 미정(PRD 13장)이므로 저장 코드는 `storage.py` 한 파일에 모은다.
- 일러스트는 직접 제작하거나 라이선스를 확인한 것만 쓴다. MVP는 품종 20종으로 시작한다.
- 색·글꼴은 `.streamlit/config.toml` 테마와 `shared/` 스타일 헬퍼만 쓰고, 전역 CSS는 넣지 않는다.
- 이 폴더 밖의 파일은 수정하지 않는다.

## 단독 실행
```bash
streamlit run features/guest/dev.py                           # 저장소 루트에서
python -m unittest discover -s features/guest/tests -t .      # 순수 로직 테스트 (표준 라이브러리)
```
사이드바의 "아침/점심/저녁 끼니 기록됨" 버튼이 한 끼 서비스의 `meal_logged` 이벤트를 흉내 낸다. 날짜를 바꿔 여러 날을 기록하면 연속 일수도 확인할 수 있다.

## 파일 구성

| 파일 | 하는 일 |
|---|---|
| `__init__.py` | 병합 단위 (`page()`, `ROUTE`, `get_today_summary()`) |
| `config.toml`, `config.py` | 희귀도 확률(일반 70 / 희귀 25 / 전설 5), 단골 레벨 기준(1·3·7·15회), 품종 20종 |
| `models.py` | `Breed`, `MealLoggedEvent`, `GuestVisit`, `CollectionCard`, `TodaySummary` |
| `logic.py` | 뽑기·단골 레벨·연속 일수·홈 요약 계산 (순수 함수, Streamlit 없음) |
| `storage.py` | 저장 계층. 지금은 `st.session_state`(`guest_visits`, `guest_cards`)에만 저장 → 새로고침하면 사라짐 |
| `events.py` | 한 끼와의 연결 지점. `st.session_state["meal_logged_events"]` 대기열을 읽는다 |
| `service.py` | 이벤트 → 손님 방문 처리, 홈 요약, 분석 이벤트(`guest_visit`, `card_unlocked`, `loyalty_level_up`) |
| `clients/photos.py` | 손님 사진 API. 강아지는 Dog CEO, 고양이는 TheCatAPI (둘 다 키 없음, 타임아웃 5초) |
| `ui.py` | 페이지 화면 (일차·7일 도장판, 도감 진행 막대, 손님 방문 연출, 오늘의 3칸, 도감, 카드 상세) |
| `cards.py` | 트레이딩 카드 HTML/CSS (카드 번호, 희귀도 테두리, 전설 반짝임, NEW 표시, 뒤집기 연출) |
| `illustration.py` | 사진을 못 불러올 때와 못 만난 품종 실루엣에 쓰는 SVG 그림 |
| `meal_photo.py` | 밥상 사진을 긴 변 640px JPEG로 줄인다 (Pillow, Streamlit과 함께 설치됨) |
| `dev.py` | 단독 실행 (여기서만 `st.set_page_config` 호출) |
| `tests/` | `logic.py` 테스트 |

## 팀에 확인할 것

- **이벤트 전달:** 한 끼가 끼니를 기록하면 `st.session_state["meal_logged_events"]` 목록에 `{"meal_log_id", "slot", "date"}`를 넣는 방식을 제안한다(팀원 A와 확정 필요). 바뀌면 `events.py`만 고친다.
- **밥상 사진 (팀원 A에게 요청):** 끼니를 기록할 때 밥상 사진을 함께 올릴 수 있게 하려 한다. 단독 실행(`dev.py`)에서는 이미 된다. 병합 후에도 되려면 한 끼 페이지의 기록 화면에 사진 올리기(`st.file_uploader`, jpg/png/webp)를 넣고, `meal_logged` 이벤트에 `"photo": bytes | None`을 함께 실어 달라고 요청한다. 손님 쪽은 받은 사진을 줄여서 `GuestVisit.meal_photo`에 저장하고, 손님 방문 연출과 오늘의 3칸에 보여 준다. 사진이 없어도 기록은 된다.
- **저장 방식:** 팀 결정 전까지 세션 저장. 정해지면 `storage.py`만 바꾼다. 밥상 사진도 지금은 세션에만 있어 새로고침하면 사라진다.
- **`get_today_summary()`의 `status`:** `"empty" | "in_progress" | "done"`으로 정했다.
- **카드 스타일 (팀 규칙과 다름):** 카드 수집 느낌을 위해 `cards.py`가 `st.html`로 자체 CSS를 넣고 카드 색을 직접 적었다. 모든 클래스에 `guest-` 접두사를 붙여 `body`·`.stApp` 등 다른 화면은 건드리지 않지만, "색 하드코딩 금지·스타일은 `shared/` 헬퍼로만" 규칙과는 다르다. `shared/` 스타일 헬퍼가 나오면 그쪽으로 옮기거나 팀원 A의 허락을 받는다.
- **단골 레벨 테두리(D-4):** 카드 안쪽 테두리가 Lv.2 라벤더 → Lv.3 로즈 → Lv.4 금색 이중선으로 바뀌고, 배지(🎀⭐💖👑)와 칭호도 함께 바뀐다.
- **일차 표시:** "밥때 손님 N일째"는 첫 손님을 만난 날을 1일째로 센다. 최근 7일 도장판은 하루 3칸(●○○)으로 보여 준다.
- **사진 API 사용 (PRD·README와 다름):** 담당자 결정으로 손님 사진을 Dog CEO·TheCatAPI에서 받는다. 팀 문서에는 밥때 손님 외부 데이터가 "—", 일러스트는 "직접 제작 또는 라이선스 확인"으로 되어 있으니 PRD 갱신을 팀원 A에게 요청한다.
  - 두 API 모두 키가 필요 없어 `st.secrets` 설정은 없다.
  - 사진 라이선스: Dog CEO 사진은 Stanford Dogs 데이터셋 기반, TheCatAPI 사진은 사용자 업로드라 상업적 이용 조건이 분명하지 않다. 수업·포트폴리오용으로 쓰고, 출처를 화면이나 README에 밝힌다.
  - TheCatAPI는 키 없이 품종 목록(`/v1/breeds`)이 403이라, 품종별 사진 id를 `config.toml`에 직접 적었다. 고양이는 품종마다 사진이 1장으로 고정된다.
  - API에 없는 품종은 바꿨다: 진돗개 → 치와와, 코리안 숏헤어 → 아메리칸 숏헤어, 러시안 블루 → 아비시니안, 스코티시 폴드 → 노르웨이 숲.
- **의존성:** `streamlit`, `requests`(Streamlit에 포함돼 함께 설치됨). 루트 `requirements.txt`는 팀원 A가 관리하므로 `requests`도 적어 달라고 요청한다.
