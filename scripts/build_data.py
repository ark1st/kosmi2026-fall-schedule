#!/usr/bin/env python3
"""Merge official data + hand-typed timetable + work/research/*.json into work/kosmi.json (input of build_site.py)."""
import json, re, pathlib, datetime
ROOT = pathlib.Path(__file__).resolve().parent.parent
off = json.loads((ROOT / "work" / "official.json").read_text(encoding="utf-8"))

def load_research(name):
    p = ROOT / "work" / "research" / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print("!! invalid research file", name, e)
        return None

SITE = "https://www.kosmiconference.org/2026_fall"
DAYS = [
    {"id": "d1", "date": "2026-11-25", "dow": "수", "label": "11.25 수", "mode": "온라인", "place": "온라인 A–E (공식 홈페이지 접속)"},
    {"id": "d2", "date": "2026-11-26", "dow": "목", "label": "11.26 목", "mode": "오프라인", "place": "경주화백컨벤션센터(HICO)"},
    {"id": "d3", "date": "2026-11-27", "dow": "금", "label": "11.27 금", "mode": "오프라인", "place": "경주화백컨벤션센터(HICO)"},
]
SYM_SLOT = {}
for n in range(1, 6): SYM_SLOT[n] = ("d1", "13:00", "14:30")
for n in range(6, 9): SYM_SLOT[n] = ("d2", "14:30", "16:00")
for n in range(9, 13): SYM_SLOT[n] = ("d2", "16:20", "17:50")
for n in range(13, 18): SYM_SLOT[n] = ("d3", "09:00", "10:30")
for n in range(18, 23): SYM_SLOT[n] = ("d3", "13:00", "14:30")

TAG_RULES = [
    ("LLM·에이전트", r"LLM|언어\s?모델|Language Model|Agent|에이전트|RAG|검색증강|생성형|Claude|챗봇|chatbot|프롬프트|prompt|SLM|MCP|GPT"),
    ("표준·상호운용성", r"FHIR|CDM|OMOP|SNOMED|LOINC|표준|상호운용|매핑|Mapping|KR Core|KR CDI|K-IPS|mCODE|DCAT|CDASH|SDTM|KCD|NIC|NOC|Harmoniz|Standardiz|Interoperab|NMDS"),
    ("데이터 활용·거버넌스", r"2차\s?활용|DRB|거버넌스|가치평가|큐레이션|품질|빅데이터|플랫폼|데이터 개방|반출|중개|메타데이터|합성|Synthetic|데이터셋|Dataset|Data Element|CDW|데이터베이스|마이데이터"),
    ("법·윤리·정책", r"법|윤리|제도|규제|책임|신뢰|정책|Ethic|개인정보|가이드라인|Transparency|Responsible|ALTAI|컴플라이언스|공공"),
    ("유전체·정밀의료", r"유전|바이오빅데이터|BIKO|정밀의료|SNP|HLA|genom|바이오뱅크|UK Biobank|분자|ADMET|KoGES|Polygenic|조절인자"),
    ("예측모델·CDSS", r"예측|Predict|CDSS|의사결정|Decision|위험|Risk|Drift|Machine Learning|머신러닝|분류|Classification|Conformal|불확실성|Uncertainty"),
    ("영상·생체신호", r"영상|X-ray|X선|MRI|PET|CT\b|초음파|ECG|심전도|내시경|분할|Segmentation|Image|안저|생체신호|웨어러블|Wearable|혈당|CGM|Radiograph|호흡음|열화상|Ultrasound"),
    ("간호", r"간호|Nurs|돌봄|요양|Care Workers"),
    ("정신건강", r"정신|우울|자살|조현병|ADHD|수면|Mental|Suicid|Depress|Schizo|Sleep|환각|반항장애|알코올|물질사용"),
    ("임상연구", r"임상연구|임상시험|EDC|iCReaT|eSource|Trial|코호트|Cohort|Propensity|연구설계|연구 자동화|Research Agent"),
    ("디지털헬스 서비스", r"디지털\s?헬스|원격|비대면|telemedicine|애플리케이션|PHR|디지털\s?트윈|메타버스|전자약|로봇|혼합현실|홀로렌즈|키오스크|Kiosk|스마트 외래|EMA|라이프로그|Smart Patient"),
    ("감염·응급·중환자", r"감염|응급|Emergency|중환자|ICU|Sepsis|119|항생제|병상"),
]
def tags_for(*texts):
    blob = " ".join(t for t in texts if t)
    return [name for name, rx in TAG_RULES if re.search(rx, blob, re.I)]

sessions, items = [], []
def add_session(**kw):
    kw.setdefault("chairs", []); kw.setdefault("panel", []); kw.setdefault("note", "")
    sessions.append(kw); return kw
def add_item(**kw):
    kw.setdefault("aff", ""); kw.setdefault("sub", "")
    s = next(x for x in sessions if x["id"] == kw["sid"])
    kw["tags"] = tags_for(kw.get("title"), s.get("title") if kw["kind"] in ("talk", "oral") else "")
    items.append(kw); return kw

# ---- tutorials (online day)
ONLINE = ["온라인 A", "온라인 B", "온라인 C", "온라인 D", "온라인 E"]
for t in off["tutorials"]:
    s = add_session(id=f"tut-{t['no']}", kind="tutorial", label=f"튜토리얼 {t['no']}", title=t["title"], day="d1",
                    start="09:00", end="12:00", room=ONLINE[t["no"] - 1],
                    desc=t["goal"], audience=t["audience"], hands_on=t["hands_on"], limit=t["limit"])
    last = ""
    for i, p in enumerate(t["parts"], 1):
        inst = p["instructor"] or last; last = inst
        m = re.match(r"(.+?)\s*\((.+)\)$", inst)
        name, aff = (m.group(1), m.group(2)) if m else (inst, "")
        lines = p["content"].split("\n")
        add_item(id=f"tut-{t['no']}-{i}", sid=s["id"], kind="tutorial", title=lines[0].strip(),
                 detail="\n".join(l.strip() for l in lines[1:] if l.strip()), speaker=name, aff=aff,
                 minutes=p["minutes"])

# ---- symposia
for sy in off["symposia"]:
    day, st, en = SYM_SLOT[sy["no"]]
    chairs = [c for c in sy["chairs"]]
    s = add_session(id=f"sym-{sy['no']}", kind="symposium", label=f"심포지엄 {sy['no']}", title=sy["title"], day=day,
                    start=st, end=en, room=sy["room"], chairs=chairs)
    n = 0
    for tk in sy["talks"]:
        if tk["title"] == "패널토론":
            s["panel"].append({"name": tk["speaker"], "aff": tk["aff"]}); continue
        n += 1
        add_item(id=f"sym-{sy['no']}-{n}", sid=s["id"], kind="talk", title=tk["title"], speaker=tk["speaker"], aff=tk["aff"])

# ---- free papers / posters
ep_seen = {}
for g in off["paper_groups"]:
    m = re.search(r"11\. (\d+)\.\[(.)\] (\d\d:\d\d)-(\d\d:\d\d)", g["date_txt"])
    day = {"26": "d2", "27": "d3"}[m.group(1)]
    st, en = m.group(3), m.group(4)
    if g["tab"] == 1:
        no = int(re.search(r"\d+", g["label"]).group())
        s = add_session(id=f"oral-{no}", kind="oral", label=g["label"], title=g["title"], day=day, start=st, end=en,
                        room=g["room"], chairs=g["chairs"])
        for p in g["papers"]:
            add_item(id=p["id"], sid=s["id"], kind="oral", title=p["title"], speaker=p["speaker"], aff=p["aff"])
    elif g["tab"] == 2:
        rn = "I" if day == "d2" else "II"
        sid = f"ep-{1 if day == 'd2' else 2}"
        if sid not in ep_seen:
            ep_seen[sid] = add_session(id=sid, kind="eposter", label=f"e-포스터 발표 {rn}", title=f"e-포스터 발표 {rn} (키오스크 1–4호기)",
                                       day=day, start=st, end=en, room="300A",
                                       note="키오스크(호기)별로 동시에 진행됩니다. 발표 순서는 번호순.")
        for p in g["papers"]:
            add_item(id=p["id"], sid=sid, kind="eposter", title=p["title"], speaker=p["speaker"], aff=p["aff"], sub=g["title"])
    else:
        rn = "I" if day == "d2" else "II"
        s = add_session(id=f"post-{1 if day == 'd2' else 2}", kind="poster", label=f"게시포스터 {rn}", title=f"게시포스터 {rn} 질의응답",
                        day=day, start=st, end=en, room="300A",
                        note="질의응답 시간에는 발표자가 포스터 앞에 대기합니다. 포스터 전시는 300A에서 계속됩니다.")
        for p in g["papers"]:
            add_item(id=p["id"], sid=s["id"], kind="poster", title=p["title"], speaker=p["speaker"], aff=p["aff"])

# ---- plenary / ceremonies / side events (typed from the official timetable image, 2026-11-19 version)
ALL = "전체 (장소 미표기)"
def ev(id, kind, label, title, day, st, en, room, **kw):
    return add_session(id=id, kind=kind, label=label, title=title, day=day, start=st, end=en, room=room, **kw)

ev("d1-break", "break", "휴식", "휴식", "d1", "12:00", "13:00", "")
ev("d2-reg", "admin", "등록", "등록 (명찰 수령)", "d2", "09:00", "10:00", "HICO 등록데스크", note="현장등록도 이 시간에 가능합니다. 사전등록자는 명찰만 수령.")
ev("d2-lunch", "break", "점심", "점심식사", "d2", "11:30", "12:30", "", note="도시락 제공 — 사전등록 시 신청한 사람에 한함.")
ev("d2-open", "ceremony", "개회식", "개회식", "d2", "12:30", "13:00", ALL,
   desc="개회사 · 김종엽 추계학술대회 조직위원장 | 환영사 · 김일곤 대한의료정보학회장 | 축사 · 염민섭 한국보건의료정보원장")
ev("d2-award", "ceremony", "시상", "공로상 시상식", "d2", "13:00", "13:10", ALL)
ev("d2-award-lec", "plenary", "수상 강연", "정보의학학술상 강연", "d2", "13:10", "13:30", ALL, note="수상자·강연 제목은 공식 시간표에 표기되지 않았습니다.")
s = ev("d2-beomsan", "plenary", "범산특별강연", "표현형에서 생리지표로: 수리모델과 AI가 여는 디지털 헬스의 미래", "d2", "13:30", "14:10", ALL)
add_item(id="pl-beomsan", sid=s["id"], kind="plenary", title=s["title"], speaker="김재경", aff="KAIST")
ev("d2-break1", "break", "휴식", "휴식", "d2", "14:10", "14:30", "")
ev("d2-demo", "side", "Demo Day", "2026년 2차 Demo Day", "d2", "14:30", "16:30", "4층 라운지")
ev("d2-break2", "break", "휴식", "휴식", "d2", "16:00", "16:20", "")
ev("d2-partner", "side", "간담회", "산업파트너 간담회", "d2", "17:00", "18:00", "4층 라운지")
ev("d2-exhibit", "exhibit", "포스터 전시", "포스터 전시", "d2", "12:30", "17:50", "300A", note="게시포스터 상시 전시. 질의응답은 14:30–15:30.")
ev("d2-break3", "break", "이동", "휴식 · 황룡원으로 이동", "d2", "17:50", "18:30", "", note="HICO → 황룡원 셔틀 여부는 현장 안내 확인. 공식 셔틀: HICO 출발 18:00 / 18:20(황리단길 경유).")
ev("d2-reception", "social", "리셉션", "네트워킹 리셉션", "d2", "18:30", "21:00", "황룡원 연수동 1층 대연회장",
   note="사전신청자에 한함 (참가비 60,000원, 사전등록 시 신청). 주소: 경북 경주시 엑스포로 40. 종료 후 황룡원 출발 20:30 셔틀(경주역행).")
ev("d3-senior", "side", "포럼", "액티브 시니어 포럼 (Closed Meeting)", "d3", "07:30", "08:30", "4층 라운지", note="비공개 회의.")
ev("d3-reg", "admin", "등록", "등록", "d3", "08:30", "09:00", "HICO 등록데스크")
ev("d3-break1", "break", "휴식", "휴식", "d3", "10:30", "10:50", "")
s = ev("d3-keynote", "plenary", "Keynote Speech", "The Missing Variable in Clinical AI: Extracting Richer Evidence from Each Patient's Response", "d3", "10:50", "11:30", ALL)
add_item(id="pl-keynote", sid=s["id"], kind="plenary", title=s["title"], speaker="Yves Lussier", aff="University of Utah")
ev("d3-break2", "break", "휴식", "휴식", "d3", "11:30", "11:40", "")
ev("d3-iss1", "industry", "Industry Supported Symposia 1", "한국마이크로소프트", "d3", "11:40", "12:00", "300B")
ev("d3-iss2", "industry", "Industry Supported Symposia 2", "Wolters Kluwer", "d3", "11:40", "12:00", "300C")
ev("d3-student", "social", "학생 프로그램", "학생 네트워킹 프로그램", "d3", "11:40", "12:00", "203+204호")
ev("d3-exhibit", "exhibit", "포스터 전시", "포스터 전시", "d3", "10:00", "12:00", "300A", note="질의응답은 09:00–10:00.")
ev("d3-lunch", "break", "점심", "점심식사", "d3", "12:00", "13:00", "", note="도시락 제공 — 사전등록 시 신청한 사람에 한함.")
ev("d3-close", "ceremony", "폐회식", "폐회식", "d3", "14:30", "15:00", ALL,
   desc="2027년 춘계학술대회 안내 | 비트의료정보학술상 시상식 | 우수연제논문 시상식 | 폐회사 · 김종엽 추계학술대회 조직위원장 | 경품추첨")

# ---- research merge
def norm(s): return re.sub(r"[\s·\-–:,.()\[\]'\"‘’“”]", "", (s or "").lower())
def base(n): return re.sub(r"\s*[\(（].*?[\)）]\s*", " ", n or "").strip()
by_id = {s["id"]: s for s in sessions}
merged = {"sym": 0, "talk": 0, "event": 0, "unmatched": []}
for fname in ("symposia_06_12.json", "symposia_13_17.json", "symposia_18_22.json"):
    r = load_research(fname)
    if not r: continue
    for sy in r.get("symposia", []):
        s = by_id.get(f"sym-{sy.get('no')}")
        if not s: continue
        s["research"] = {k: sy.get(k) for k in ("background", "key_points", "questions", "links") if sy.get(k)}
        merged["sym"] += 1
        its = [i for i in items if i["sid"] == s["id"]]
        used = set()
        for tk in sy.get("talks", []):
            sp = norm(base(tk.get("speaker")))
            cand = [i for i in its if norm(i["speaker"]) == sp and i["id"] not in used]
            if len(cand) != 1:
                c2 = [i for i in its if norm(i["title"])[:14] == norm(tk.get("title"))[:14] and i["id"] not in used]
                cand = c2 or cand
            if cand:
                used.add(cand[0]["id"])
                rr = {k: tk.get(k) for k in ("profile", "prep", "links", "confidence") if tk.get(k)}
                if (rr.get("profile") or "").strip().startswith("확인 불가"):
                    rr.pop("profile", None); rr.pop("confidence", None); rr["unverified"] = True
                cand[0]["research"] = rr
                merged["talk"] += 1
            elif (tk.get("title") or "").strip() != "패널토론":
                merged["unmatched"].append((sy.get("no"), tk.get("speaker")))
so = load_research("sponsors_online.json") or {}
for o in so.get("online", []):
    sid = ("sym-" if o.get("kind") == "symposium" else "tut-") + str(o.get("no"))
    if sid in by_id:
        by_id[sid]["research"] = {k: o.get(k) for k in ("background", "key_points", "links") if o.get(k)}
        inst = [f"{x.get('name')}: {x.get('note')}" for x in (o.get("instructors") or []) if x.get("note") and "확인 불가" not in x.get("note")]
        if inst: by_id[sid]["research"]["instructors"] = inst
        merged["sym"] += 1
pe = load_research("plenary_events.json") or {}
for p in pe.get("people", []):
    p["name_full"] = p.get("name", ""); p["name"] = base(p.get("name"))
for it in items:
    if it["kind"] != "plenary": continue
    toks = [norm(x) for x in it["speaker"].split()]
    for p in pe.get("people", []):
        pn = norm(p["name"])
        if all(tk in pn for tk in toks):
            p["name"] = it["speaker"]
            it["research"] = {"profile": p.get("profile"), "prep": p.get("talk_preview"), "links": p.get("links"), "confidence": p.get("confidence")}
            merged["talk"] += 1
EVENT_MAP = [("Demo Day", "d2-demo"), ("산업파트너", "d2-partner"), ("액티브 시니어", "d3-senior"), ("학생 네트워킹", "d3-student"),
             ("마이크로소프트", "d3-iss1"), ("Wolters", "d3-iss2"), ("리셉션", "d2-reception")]
for e in pe.get("events", []):
    for kw, sid in EVENT_MAP:
        if kw in (e.get("name") or ""):
            by_id[sid]["research"] = {"background": e.get("what"), "key_points": [e["tips"]] if e.get("tips") else [], "links": e.get("links")}
            merged["event"] += 1
AWARD_MAP = [("공로상", "d2-award"), ("정보의학학술상", "d2-award-lec"), ("범산", "d2-beomsan"), ("비트의료정보학술상", "d3-close"), ("우수연제", "d3-close")]
for a in pe.get("awards", []):
    for kw, sid in AWARD_MAP:
        if kw in (a.get("name") or ""):
            r = by_id[sid].setdefault("research", {})
            txt = (a.get("name") or "") + ": " + (a.get("what") or "") + ((" " + a["winners"]) if a.get("winners") else "")
            r.setdefault("key_points", []).append(txt.strip())
            r["links"] = (r.get("links") or []) + (a.get("links") or [])
            merged["event"] += 1
            break
op = [f"{p['name']} ({p.get('affiliation','')}): {p.get('profile','')}" for p in pe.get("people", []) if "개회식" in (p.get("role_at_conf") or "")]
if op: by_id["d2-open"]["research"] = {"key_points": op}
print("research merged:", {k: v for k, v in merged.items() if k != "unmatched"}, "unmatched:", merged["unmatched"])

# ---- curated picks (editorial; assumes a genomics-diagnostics attendee building AI agents)
PICKS = [
    {"id": "oral-4", "level": "추천", "why": "AI 에이전트·CDSS 구현 사례 5편. 에이전트 평가 방식과 임상 연동 지점을 비교해 볼 수 있음."},
    {"id": "oral-1", "level": "대안", "why": "CDM·LOINC 매핑 등 표준화 실무. 병원 데이터와 연동할 때 부딪히는 용어 매핑 문제를 다룸."},
    {"id": "d2-open", "level": "추천", "why": "개회식 직후 범산특별강연까지 한자리에서 이어짐."},
    {"id": "d2-beomsan", "level": "추천", "why": "표현형 대신 생리지표를 쓰는 수리모델 접근. 표현형 기반 진단의 한계를 다른 각도에서 봄."},
    {"id": "sym-6", "level": "추천", "why": "보건의료데이터 2차 활용 경로(중개포털·빅데이터플랫폼). 기업이 공공 데이터를 신청하는 절차를 한 번에 파악."},
    {"id": "sym-8", "level": "대안", "why": "데이터 품질 평가·큐레이션. 다기관 데이터로 모델을 검증할 계획이 있다면 이쪽."},
    {"id": "post-1", "level": "추천", "why": "15:30까지. 멀티에이전트 연구 지원(P1-13, P1-17), 정밀의료 검사 협진 시스템(EP3-2) 발표자와 직접 대화 가능."},
    {"id": "sym-10", "level": "추천", "why": "DRB 접수부터 데이터 반출까지. 병원과 공동연구할 때 실제로 막히는 절차."},
    {"id": "oral-8", "level": "대안", "why": "책임 있는 AI 활용. 온프레미스 LLM, 멀티에이전트, CHAI 모델 카드 등 에이전트 연구와 직접 겹침."},
    {"id": "d2-reception", "level": "선택", "why": "사전신청자만 입장. 연자·좌장·후원사가 모이는 자리."},
    {"id": "post-2", "level": "필수", "why": "09:00–10:00 게시포스터 II 질의응답. 26F-P2-12 발표 시간."},
    {"id": "sym-13", "level": "추천", "why": "국가통합바이오빅데이터(BIKO) 개방·이용 안내. 포스터 질의응답과 겹치므로 10:00 이후 후반부(유전체 데이터·BBP 플랫폼 발표)에 합류."},
    {"id": "d3-keynote", "level": "추천", "why": "환자 한 명의 반응에서 근거를 뽑는 접근(N-of-1). 희귀질환·개인 단위 해석과 맞닿음."},
    {"id": "d3-iss1", "level": "선택", "why": "20분. 한국마이크로소프트의 헬스케어 AI 발표."},
    {"id": "sym-20", "level": "추천", "why": "배포 후 모델 성능 저하(Model Drift) 탐지와 생애주기 관리. AI 제품을 운영한다면 직접 해당."},
    {"id": "sym-19", "level": "대안", "why": "디지털헬스·데이터 2차활용 법안 쟁점. 유전체 데이터 활용 규제 방향을 가늠."},
    {"id": "d3-close", "level": "선택", "why": "우수연제논문 시상·경품추첨. 경주역행 셔틀은 15:10 / 15:20 / 15:30."},
]
MY_PAPERS = ["26F-P2-12"]
WATCH = [  # individual papers worth finding, same assumption as PICKS
    {"id": "26F-EP3-2", "why": "NGS 등 차세대 정밀의료 검사의 병리·진단검사의학과 협진 진행관리 시스템."},
    {"id": "26F-P2-29", "why": "HLA-B*58:01 위험 대립유전자의 tag SNP 대리표지 다인종 검증 + CDS 구현."},
    {"id": "26F-P1-13", "why": "연구기획 지원 멀티에이전트 시스템(HMARIS, 국립보건연구원)."},
    {"id": "26F-P1-17", "why": "사람이 감독하는 AI 연구 에이전트 방법론."},
    {"id": "26F-EP1-3", "why": "지식그래프 기반 멀티에이전트 추론으로 근거 기반 DDI 예측."},
    {"id": "26F-O6-2", "why": "선례 기반 에이전트 시스템 (약물 부작용)."},
    {"id": "26F-O8-2", "why": "Human-in-the-loop 다중 에이전트 시스템."},
    {"id": "26F-O8-4", "why": "폐쇄망 LLM으로 연구설계 구조화·분석 자동화."},
    {"id": "26F-EP8-4", "why": "SCHERA: 에이전트 탐색 기반 임상 이력 구조화."},
    {"id": "26F-EP3-1", "why": "KoGES 코드북 변수 검색 시스템."},
    {"id": "26F-P2-15", "why": "보건의료데이터 중개 포털용 메타데이터 기준(HealthDCAT-KR)."},
    {"id": "26F-P2-13", "why": "iCReaT 임상연구 과제 구축 절차."},
]
ids = {s["id"] for s in sessions} | {i["id"] for i in items}
for p in PICKS + WATCH:
    assert p["id"] in ids, p
assert all(m in ids for m in MY_PAPERS)

OFFICIAL = {
    "name": "2026 대한의료정보학회 추계학술대회",
    "theme": "Next AI: Advancing Trust, Sustainability, and Human-Centered Medical Innovation",
    "dates": "2026년 11월 25일(수) – 27일(금)",
    "venue": {"name": "경주화백컨벤션센터 (HICO)", "addr": "경상북도 경주시 보문로 507", "url": "https://www.hico.or.kr"},
    "site": SITE + "/",
    "links": [
        {"label": "공식 홈페이지", "url": SITE + "/"},
        {"label": "프로그램 시간표", "url": SITE + "/content/sche.html"},
        {"label": "심포지엄", "url": SITE + "/content/sympo.html"},
        {"label": "튜토리얼", "url": SITE + "/content/tutorial.html"},
        {"label": "연제논문 발표세션", "url": SITE + "/content/session.html"},
        {"label": "사전등록 확인 · 참가확인증", "url": SITE + "/entry/confirm.html"},
        {"label": "셔틀버스 · 주차", "url": SITE + "/content/layout.html"},
        {"label": "숙소 안내 (mice.link)", "url": "https://kosmi2026.mice.link/"},
        {"label": "공지사항", "url": "https://www.kosmiconference.org/content/community/post_list.php?bt=3"},
        {"label": "대한의료정보학회", "url": "https://www.kosmi.org/"},
        {"label": "Instagram @kosmi_official", "url": "https://www.instagram.com/kosmi_official/"},
        {"label": "YouTube @kosmi1987", "url": "https://www.youtube.com/@kosmi1987"},
    ],
    "key_dates": [
        {"what": "연제논문 접수 마감", "when": "2026-09-06 (일)"},
        {"what": "사전등록 마감", "when": "2026-11-13 (금) 13:00"},
        {"what": "이력·초록 접수 마감", "when": "2026-11-15 (일)"},
        {"what": "발표자료·e-포스터 자료 마감", "when": "2026-11-18 (수)"},
        {"what": "온라인 (튜토리얼 · 심포지엄 1–5)", "when": "2026-11-25 (수)"},
        {"what": "오프라인 1일차", "when": "2026-11-26 (목)"},
        {"what": "오프라인 2일차", "when": "2026-11-27 (금)"},
    ],
    "fees": {
        "cols": ["학부생", "대학원생", "전공의/간호사", "일반"],
        "rows": [
            {"when": "사전등록", "who": "정회원 · 학생회원 · 평생회원", "v": ["20,000", "80,000", "100,000", "200,000"]},
            {"when": "사전등록", "who": "준회원 · 비회원", "v": ["20,000", "110,000", "150,000", "250,000"]},
            {"when": "현장등록", "who": "정회원 · 학생회원 · 평생회원", "v": ["30,000", "90,000", "110,000", "220,000"]},
            {"when": "현장등록", "who": "준회원 · 비회원", "v": ["30,000", "120,000", "160,000", "270,000"]},
        ],
        "notes": [
            "학부생 등록비는 회원 구분과 무관하게 같은 금액으로 표기되어 있습니다 (공식 표의 병합 셀 기준).",
            "준회원/비회원으로 사전등록하면 이후 1년간 정회원(또는 학생회원) 자격 부여 (학부생 제외).",
            "튜토리얼: 세션당 70,000원, 온라인 진행, 단독 신청 불가.",
            "네트워킹 리셉션: 60,000원, 단독 신청 불가 (사전등록 시 신청).",
            "사전등록은 11/13 13시에 마감되었습니다. 지금은 현장등록만 가능합니다.",
            "참가확인증·영수증은 학술대회 종료 후 홈페이지 '사전등록 확인'에서 직접 출력.",
        ],
        "contact": {"email": "kosmi@kosmi.org", "tel": ["070-4281-0343", "02-734-7637", "02-733-7637"]},
    },
    "shuttle": {
        "stops": ["경주역: 1번 출구 광장 앞 '시티투어·셔틀버스 타는 곳'", "HICO: 1층 Gate 5 앞 주차장"],
        "days": [
            {"day": "d2", "label": "11/26 (목)", "to": ["08:00", "09:00", "09:40", "10:30", "11:30", "12:00"],
             "from": [{"t": "16:35"}, {"t": "18:00"}, {"t": "18:20", "n": "황리단길 경유"}, {"t": "20:30", "n": "황룡원 출발"}]},
            {"day": "d3", "label": "11/27 (금)", "to": ["07:30", "07:55", "08:56", "10:00"],
             "from": [{"t": "14:25"}, {"t": "15:10"}, {"t": "15:20"}, {"t": "15:30"}]},
        ],
    },
    "parking": {"fee": "무료", "total": 461, "ground": 338, "under": 123, "ev": 3, "url": "https://www.hico.or.kr/facility/parking/"},
    "caveats": [
        "공식 '행사장 안내' 페이지에는 2026 춘계(청주오스코, 6/24–26) 교통 정보가 그대로 남아 있습니다. 추계 장소는 경주 HICO입니다.",
        "튜토리얼 페이지 상단 날짜가 '11. 22.[토]'로 표기되어 있으나, 프로그램 시간표는 11/25(수) 09:00–12:00 온라인입니다. 이 사이트는 시간표를 따랐습니다.",
        "FAQ의 일반 준회원/비회원 등록비 '25,0000원'은 오타로 보입니다. 사전등록 안내 표는 250,000원입니다.",
        "개회식·범산특별강연·Keynote·폐회식은 시간표에 장소가 따로 적혀 있지 않습니다 (전체 세션룸 열에 걸쳐 표기). 현장 안내를 확인하세요.",
        "좌장 TBA: 자유연제 2·3, 심포지엄 5·6·20, 심포지엄 12·18·22의 공동좌장.",
        "심포지엄·자유연제의 개별 발표 시각은 공개되지 않았습니다. 이 사이트의 발표별 예상 시각은 세션 시간을 발표 수로 균등 분할한 추정치입니다.",
        "공식 시간표 이미지 버전: 2026-11-19. 이후 변경은 반영되지 않았을 수 있습니다.",
    ],
    "greeting": {
        "by": "김종엽 · 대한의료정보학회 이사장, 추계학술대회 조직위원장",
        "summary": [
            "주제 'Next AI'는 더 크고 빠른 AI가 아니라 신뢰할 수 있고(Trust), 의료체계에서 지속 가능하며(Sustainability), 사람을 중심에 둔(Human-Centered) AI를 뜻한다고 밝힘.",
            "신뢰: 성능·정확도를 넘어 안전성, 설명가능성, 공정성, 개인정보 보호, 책임 있는 활용까지 다층적 검증과 사회적 합의가 필요.",
            "지속가능성: 임상현장에서 계속 쓰여야 혁신. 의료진 업무 부담 경감, 자원 효율, 기관 규모·지역 간 디지털 격차 해소.",
            "인간 중심: AI의 목적은 의료진 대체가 아니라 의료진이 환자에게 더 집중하도록 돕는 것.",
        ],
        "url": SITE + "/content/intro.html",
    },
}

faq = []
for f in off["faq"]:
    a = f["a"]
    if f["q"].startswith("학술대회 등록비는"):
        a = "사전등록비는 '등록' 탭의 표와 같습니다. 현장등록비는 사전등록비보다 10,000–20,000원 높습니다. '정회원/준회원' 여부는 로그인 시 자동 설정되고, '구분'은 직접 선택합니다."
    faq.append({"section": f["section"], "q": f["q"], "a": a})
# section headings on the FAQ page: fix the fee block that the parser folded into the previous section
for f in faq:
    if re.search(r"등록비는|튜토리얼 등록비|리셉션 참가비|준회원으로 보입니다", f["q"]):
        f["section"] = "등록비"

data = {
    "built": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    "official": OFFICIAL, "days": DAYS, "sessions": sessions, "items": items,
    "picks": PICKS, "watch": WATCH, "my_papers": MY_PAPERS,
    "committee": off["committee"], "faq": faq,
    "glossary": (load_research("glossary.json") or {}).get("terms", []),
    "venue": load_research("venue_travel.json") or {},
    "sponsors": so.get("sponsors", []), "committee_notes": so.get("committee", []),
    "plenary": pe,
}
(ROOT / "work" / "kosmi.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("sessions", len(sessions), "items", len(items), "-> work/kosmi.json")
from collections import Counter
print(Counter(t for i in items for t in i["tags"]).most_common())
print("untagged:", sum(1 for i in items if not i["tags"]))

