# JOOYOU (`features/fuel`)

**담당:** 팀원 D · **PRD:** Epic E

주변 주유소 가격 조회와 나의 주유 기록. 내가 낸 가격을 그날 지역 평균과 비교한다.

## 만들 것
- E-1 반경 주유소 가격 조회 (P0): 오피넷 API, 반경 1/3/5km, 유종 선택, 가격순·거리순, KATEC 좌표 변환
- E-2 나의 주유 기록 (P0): 날짜·주유소·유종·리터당 가격·주유량, 총액 자동 계산, 월별 합계
- E-3 내가 낸 가격 vs 지역 평균 (P0): 금액·퍼센트 차이, 데이터 없으면 "비교 데이터 없음"

## 주의
- 오피넷이 과거 날짜의 지역 평균을 충분히 주지 않을 수 있다. 일별 평균가 스냅샷을 쌓는 방식을 먼저 검증한다. (PRD 11장 R-1)

## 실행 (Python 3.14 + Streamlit)

```
python -m venv .venv
.venv\Scripts\activate
pip install streamlit requests pyproj streamlit-geolocation
streamlit run features/fuel/dev.py
python -m unittest features.fuel.tests.test_fuel
```

- 저장소 루트의 `.env`에 `OPINET_KEY=...`를 넣는다(커밋 금지).
- 위치 권한은 `localhost` 또는 https에서만 동작한다.

## 구조
| 파일 | 역할 |
|---|---|
| `api/fuel/opinet.py` | 오피넷 호출(반경 조회·지역코드·시도/시군구 평균). 타임아웃 5초 |
| `api/fuel/coords.py` | 위경도 → KATEC 변환 |
| `features/fuel/view.py` | 화면. 주유소 30분, 지역코드 24시간 캐시 |
| `features/fuel/store.py` | SQLite(`.data/fuel.db`): `fuel_records`, `fuel_avg_snapshots` |
| `features/fuel/compare.py` | 일별 평균가 스냅샷, 시군구 평균 우선·없으면 시도 평균으로 비교 |
| `features/fuel/summary.py` | 홈 카드용 `get_today_summary()` → `{title, value, status}` |

## R-1 검증 결과 (2026-10-22)
- 무료 API의 평균가는 모두 "현재" 기준이라 과거 날짜의 지역 평균은 받을 수 없다.
- 그래서 기록 탭을 열 때(30분에 한 번) 선택한 시도의 오늘 시도·시군구 평균(전 유종)을 저장한다.
- 그날 스냅샷이 없는 날짜의 기록은 "비교 데이터 없음"으로 표시한다.

## 팀에 요청할 것 (이 폴더 밖)
- 루트 `requirements.txt`에 `streamlit`, `requests`, `pyproj`, `streamlit-geolocation` 추가
- 루트 `.gitignore`에 `.env`, `.venv/`, `__pycache__/` 추가
- 공통 규칙(`index.ts`의 `Page`·`routes`·`getTodaySummary`)의 파이썬 버전 확정. 지금은 `features/fuel/__init__.py`가 `page`, `routes`, `get_today_summary`를 내보낸다.
- 배포 시 기록 저장 방식: 로그인이 없으면 서버 SQLite를 모든 사용자가 같이 본다.
- 디자인 토큰이 나오면 Streamlit 테마(`.streamlit/config.toml`)로 맞춘다. 지금은 기본 테마다.

## 병합 규칙
- `index.ts`는 `Page`, `routes`, `getTodaySummary()`만 내보낸다. 홈 요약 카드에 최근 주유 요약을 보여줄 수 있게 한다.
- 경로 `/fuel`, 저장소·로컬 키 접두사 `fuel_`, 서버 코드는 `api/fuel/`, API 키 이름은 `OPINET_KEY`
- 다른 서비스와 직접 연결되는 부분은 없다. 단독으로 끝까지 동작해야 한다.
- 색·글꼴은 `shared/`의 디자인 토큰만 쓰고, 전역 CSS는 쓰지 않는다.
- 이 폴더 밖의 파일은 수정하지 않는다.
