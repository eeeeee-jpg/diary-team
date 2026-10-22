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
- 일러스트는 직접 제작하거나 라이선스를 확인한 것만 쓴다. 품종은 40종(개 20 + 고양이 20)이다. PRD의 MVP 초안(20종)보다 늘렸으므로 팀 확정이 필요하다 (아래 "팀에 확인할 것").
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
| `config.toml`, `config.py` | 희귀도 확률(일반 70 / 희귀 25 / 전설 5), 단골 레벨 기준(1·3·7·15회), 품종 40종 (일반 22 · 희귀 14 · 전설 4) |
| `models.py` | `Breed`, `MealLoggedEvent`, `GuestVisit`, `CollectionCard`, `TodaySummary` |
| `logic.py` | 뽑기·단골 레벨·연속 일수·홈 요약 계산 (순수 함수, Streamlit 없음) |
| `storage.py` | 저장 계층. 지금은 `st.session_state`(`guest_visits`, `guest_cards`)에만 저장 → 새로고침하면 사라짐 |
| `events.py` | 한 끼와의 연결 지점. `st.session_state["meal_logged_events"]` 대기열을 읽는다 |
| `service.py` | 이벤트 → 손님 방문 처리, 홈 요약, 분석 이벤트(`guest_visit`, `card_unlocked`, `loyalty_level_up`) |
| `clients/photos.py` | 손님 사진 API. 강아지는 Dog CEO, 고양이는 TheCatAPI (둘 다 키 없음, 타임아웃 5초) |
| `ui.py` | 페이지 흐름 (오늘의 일기 탭, 카드 앨범 탭, 앨범에 붙이기 버튼, 카드 고르기) |
| `diary.py` | 다이어리 모양 HTML/CSS: 노트 한 권(`guest_book` 컨테이너: 스프링 구멍·마스킹 테이프·인덱스 탭), N일째 도장, 7일 스티커, 폴라로이드, 방문 일기(손님이 다가오는 연출·카드 뿅·테이프 모양 버튼), 앨범, 카드 메모 |
| `cards.py` | 트레이딩 카드 HTML/CSS (카드 번호, 희귀도 테두리, 홀로그램·기울기, NEW 표시, 뒤집기 연출) |
| `illustration.py` | 사진을 못 불러올 때와 못 만난 품종 실루엣에 쓰는 SVG 얼굴, 방문 연출용 정면 2등신 스티커 캐릭터(`guest_walker_svg`, 품종 색·귀 모양으로 칠함)와 발자국 |
| `meal_photo.py` | 밥상 사진을 긴 변 640px JPEG로 줄인다 (Pillow, Streamlit과 함께 설치됨) |
| `dev.py` | 단독 실행 (여기서만 `st.set_page_config` 호출). 맨 위 "오늘 뭐 먹었어?" 메모지에서 끼니·날짜·먹은 메뉴·밥상 사진을 골라 기록한다 |
| `tests/` | `logic.py` 테스트 |

## 팀에 확인할 것

- **이벤트 전달:** 한 끼가 끼니를 기록하면 `st.session_state["meal_logged_events"]` 목록에 `{"meal_log_id", "slot", "date"}`를 넣는 방식을 제안한다(팀원 A와 확정 필요). 바뀌면 `events.py`만 고친다.
- **밥상 사진 (팀원 A에게 요청):** 끼니를 기록할 때 밥상 사진을 함께 올릴 수 있게 하려 한다. 단독 실행(`dev.py`)에서는 이미 된다. 병합 후에도 되려면 한 끼 페이지의 기록 화면에 사진 올리기(`st.file_uploader`, jpg/png/webp)를 넣고, `meal_logged` 이벤트에 `"photo": bytes | None`을 함께 실어 달라고 요청한다. 손님 쪽은 받은 사진을 줄여서 `GuestVisit.meal_photo`에 저장하고, 손님 방문 연출과 오늘의 3칸에 보여 준다. 사진이 없어도 기록은 된다.
- **먹은 메뉴 글 (팀원 A에게 요청):** 끼니를 기록할 때 쓴 메뉴 글(예: "김치찌개, 계란말이")을 `meal_logged` 이벤트에 `"menu": str | None`으로 함께 넣어 달라고 요청한다. 손님 쪽은 `logic.clean_menu()`로 공백을 정리하고 30자까지만 `GuestVisit.menu`에 저장해, 방문 일기 제목("김치찌개 냄새를 맡고 손님이 찾아왔다!")과 오늘의 폴라로이드 아래 줄에 보여 준다. 없으면 지금처럼 끼니 이름만 쓴다.
- **저장 방식:** 팀 결정 전까지 세션 저장. 정해지면 `storage.py`만 바꾼다. 밥상 사진도 지금은 세션에만 있어 새로고침하면 사라진다.
- **`get_today_summary()`의 `status`:** `"empty" | "in_progress" | "done"`으로 정했다.
- **카드 스타일 (팀 규칙과 다름):** 카드 수집 느낌을 위해 `cards.py`가 `st.html`로 자체 CSS를 넣고 카드 색을 직접 적었다. 모든 클래스에 `guest-` 접두사를 붙여 `body`·`.stApp` 등 다른 화면은 건드리지 않지만, "색 하드코딩 금지·스타일은 `shared/` 헬퍼로만" 규칙과는 다르다. `shared/` 스타일 헬퍼가 나오면 그쪽으로 옮기거나 팀원 A의 허락을 받는다.
- **폰트:** 제목·도장·탭·버튼은 Jua, 날짜·캡션·말풍선 같은 작은 손글씨 줄은 Poor Story, 본문은 Gowun Dodum (모두 Google Fonts, SIL Open Font License). 처음 쓴 Gaegu는 가독성이 낮아 바꿨다. `diary.py`·`dev.py`에서 Google Fonts로 불러온다. 팀 공통 폰트가 정해지면 맞춘다.
- **카드 홀로그램 (JavaScript 사용):** 마우스를 올리면 카드가 기울고 희귀도별 홀로그램·반사광이 움직이도록 `st.html(..., unsafe_allow_javascript=True)`로 작은 스크립트(`cards.TILT_JS`)를 넣었다. 스크립트는 `.guest-card`에만 이벤트를 붙이고, HTML에 들어가는 값은 `config.toml`과 API 사진 주소뿐이며 모두 `escape()`를 거친다. "움직임 줄이기" 설정이 켜져 있으면 동작하지 않는다.
- **단골 레벨 테두리(D-4):** 카드 안쪽 테두리가 Lv.2 라벤더 → Lv.3 로즈 → Lv.4 금색 이중선으로 바뀌고, 배지(🎀⭐💖👑)와 칭호도 함께 바뀐다.
- **일차 표시:** "밥때 손님 N일째"는 첫 손님을 만난 날을 1일째로 센다. 최근 7일 도장판은 하루 3칸(●○○)으로 보여 준다.
- **사진 API 사용 (PRD·README와 다름):** 담당자 결정으로 손님 사진을 Dog CEO·TheCatAPI에서 받는다. 팀 문서에는 밥때 손님 외부 데이터가 "—", 일러스트는 "직접 제작 또는 라이선스 확인"으로 되어 있으니 PRD 갱신을 팀원 A에게 요청한다.
  - 두 API 모두 키가 필요 없어 `st.secrets` 설정은 없다.
  - 사진 라이선스: Dog CEO 사진은 Stanford Dogs 데이터셋 기반, TheCatAPI 사진은 사용자 업로드라 상업적 이용 조건이 분명하지 않다. 수업·포트폴리오용으로 쓰고, 출처를 화면이나 README에 밝힌다.
  - TheCatAPI는 키 없이 품종 목록(`/v1/breeds`)이 403이라, 품종별 사진 id를 `config.toml`에 직접 적었다. 고양이는 품종마다 사진이 1장으로 고정된다.
  - API에 없는 품종은 바꿨다: 진돗개 → 치와와, 코리안 숏헤어 → 아메리칸 숏헤어, 러시안 블루 → 아비시니안, 스코티시 폴드 → 노르웨이 숲.
- **의존성:** `streamlit`, `requests`(Streamlit에 포함돼 함께 설치됨). 루트 `requirements.txt`는 팀원 A가 관리하므로 `requests`도 적어 달라고 요청한다.
- **품종 수 (PRD와 다름):** PRD 13장 초안은 MVP 20종(개 10 + 고양이 10)이지만, 사진을 API로 불러와 일러스트 부담(R-4)이 줄어서 40종(개 20 + 고양이 20)으로 늘렸다. 희귀도별 품종 수 비율(일반 22 · 희귀 14 · 전설 4 = 55:35:10)과 출현 가중치(70/25/5)는 그대로다. 고양이 사진 id는 TheCatAPI `/v1/images/{id}` 응답의 `breeds`로 품종이 맞는지 확인했다. PRD v0.7에 제안으로 반영했다(D-1·D-2·R-4·13장). 13장 오픈 질문은 팀 확정 전이라 미완료로 두었다.
- **희귀도별 카드 연출:** 일반은 은빛 펄 테두리에 옅은 무지개, 희귀는 로즈골드 테두리에 무지개와 반짝이 가루, 별 2개를 더했다. 전설은 무지개 금박 테두리, 빛무리, 평소에도 빛나는 별 4개, 촘촘한 은하 무늬 홀로를 쓴다. 등장할 때 빛이 스치는 연출은 희귀와 전설에만 있다(1초 이내). "움직임 줄이기"가 켜져 있으면 깜빡임과 스침 연출을 끈다.
- **손님 등장 연출 (디자인 가이드와 다름):** 끼니를 기록하면 품종 색·귀 모양을 한 꼬마 캐릭터가 오른쪽 위에서 발자국을 남기며 가운데로 점점 커지며 다가오고(1.6초), "멍!"/"냥~" 인사 뒤에 카드가 별가루와 함께 뿅 나온다(1.85초부터 0.6초). 전체 약 2.5초로 디자인 가이드의 "1초 이내" 기준보다 길다. 서비스의 핵심 장면이라 길게 잡았으며, 줄이려면 `illustration.WALK_SECONDS`와 `diary.py`의 `guest-approach`·말풍선·카드 지연 시간을 함께 바꾼다. "움직임 줄이기" 설정이면 바로 도착한 모습과 카드를 보여 준다. 캐릭터는 직접 그린 SVG라 라이선스 문제가 없다. `st.html`은 `<svg>` 태그를 지우므로 캐릭터·발자국은 `<img>`(data URI)로 넣고, 걸음·꼬리 움직임은 SVG 안의 `<style>`에 둔다. 손님이 오면 방문 일기 위치로 한 번 부드럽게 스크롤해 연출을 놓치지 않게 한다.

- **dev.py 기록 메모지 스타일:** 개발용 기록 영역은 `st.container(key="guest_dev_logger")`가 만드는 `.st-key-guest_dev_logger` 안에만 CSS를 넣어 메모지처럼 꾸몄다. 전역 CSS는 아니지만 색을 직접 적었고, Streamlit 내부 속성(`data-variant`, `data-testid`)에 기대므로 버전이 바뀌면 깨질 수 있다. `dev.py` 전용이라 병합 앱에는 들어가지 않는다.
- **노트 한 권 스타일 (팀 규칙과 다름):** 일기장 첫 장·탭·오늘의 일기·카드 앨범·"카드 앨범에 붙이기" 버튼을 `st.container(key="guest_book")`가 만드는 `.st-key-guest_book` 안에 담고, 그 안에만 CSS를 넣어 노트처럼 꾸몄다(탭은 인덱스 스티커, 버튼은 마스킹 테이프). 다른 서비스 화면에는 영향이 없지만 색을 직접 적었고, Streamlit 내부 속성(`data-testid="stTab"`, `stRadioOption` 등)에 기대므로 Streamlit 버전이 바뀌면 깨질 수 있다. 병합 앱에 들어가는 부분이라 팀원 A와 확인하고, `shared/` 스타일 헬퍼가 나오면 그쪽으로 옮긴다.
