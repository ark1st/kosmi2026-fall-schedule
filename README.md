# KOSMI 2026 추계학술대회 일정 사이트 (경주 HICO)

대한의료정보학회 2026 추계학술대회(11/25 온라인, 11/26–27 경주화백컨벤션센터) 공식 홈페이지를 수집하고
웹 조사로 보충해 만든 **비공식** 정적 일정 웹사이트 + PWA입니다.
앱(`assets/app.js`, `assets/style.css`)은 `../neurips2026` 일정 사이트를 `scripts/port_app.py`로 옮긴 것입니다.

**배포:** https://ark1st.github.io/kosmi2026-fall-schedule/

## 실행

```bash
python3 -m http.server 8791
# → http://localhost:8791
```

`index.html`을 브라우저로 직접 열어도 동작합니다(모든 데이터가 `<script>` 태그로 로드됨).

## 기능

- **요일 탭** — 수(온라인) · 목 · 금 타임라인, 모든 시간 KST, 당일 "지금 시각으로"
- **유형 필터** — 심포지엄 / 자유연제 / 포스터 / 초청·식순 / 튜토리얼 / 산업·데모 / 네트워킹 / 운영
- **상세 모달** — 세션 배경·알아둘 것·질문(웹 조사), 발표 목록, 발표별 예습·발표자 정보, 공식 링크
- **위시리스트** — 카드/발표를 길게 눌러 핀, ⭐ 필터로 하루 동선 보기
- **🗓 타임테이블** — 위시리스트를 수~금 격자로, 「추천 동선 담기」 버튼
- **🔍 발표 검색** — 발표 259건을 제목·발표자·소속·발표번호로 검색, 결과 상위 소속 막대
- **ℹ 안내** — 셔틀·주차, 세션룸·층, KTX·숙박·식사·날씨, 등록비·FAQ, 부대행사, 후원사, 용어집 80개
- **PWA**, 다크 모드, 한국어/English UI 전환, 딥링크 `?day=&open=<eventId>&q=&view=week|search|info&pin=`

발표 시각(`~10:18`)은 공식 공개가 없어 세션 시간을 발표 수로 나눈 추정치입니다.
공식 홈페이지는 초록을 공개하지 않았습니다.

## 데이터 파이프라인 (`scripts/`)

작업 디렉토리는 `work/`(gitignore). 수집 원본(`work/source/`)과 웹 조사 결과(`work/research/*.json`)가 여기에 있습니다.

```bash
python3 scripts/parse_official.py   # work/source/html → work/official.json
python3 scripts/build_data.py       # + 시간표(수기 입력) + work/research → work/kosmi.json
python3 scripts/build_site.py       # → data/ (schedule.js, details.js, info.js, papers/, search/) + artifact.html
python3 scripts/port_app.py         # ../neurips2026/assets → assets/ (앱을 다시 옮길 때만)
```

- 시간표는 공식 이미지(`work/source/img/program_timetable.jpg`, 2026-11-19판)를 보고 `build_data.py`에 직접 입력했습니다.
- 추천 동선·"내 발표" 표시는 `build_data.py`의 `PICKS` / `WATCH` / `MY_PAPERS`에서 바꿉니다.

출처: https://www.kosmiconference.org/2026_fall/ · 비공식 사이트입니다.
