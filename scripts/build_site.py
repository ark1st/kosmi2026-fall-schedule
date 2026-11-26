#!/usr/bin/env python3
"""Build data/ for the KOSMI 2026 Fall schedule site from work/kosmi.json.

Emits the same data layout as the NeurIPS / ICML schedule sites:
  data/schedule.js       window.KOSMI_SCHEDULE  {locs, days[{events}], built}
  data/details.js        window.KOSMI_DETAILS   {eventId: {abs, speakers, links, program}}
  data/papers/s<id>.js   window.KOSMI_PAPERS[id] = [...]   (lazy-loaded per session)
  data/search/index.js   window.KOSMI_INDEX     {rows}     (keyword search tab)
  data/info.js           window.KOSMI_INFO      {sections, picks, seed}   (안내 view)
plus artifact.html (page fragment for publishing as a claude.ai artifact) and assets/icon-*.png.

    python3 scripts/build_data.py && python3 scripts/build_site.py
"""
import datetime, html, json, pathlib, re, struct, urllib.parse, zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
K = json.loads((ROOT / "work" / "kosmi.json").read_text(encoding="utf-8"))
OFF = K["official"]
SITE = OFF["site"].rstrip("/")
E = html.escape

S = {s["id"]: s for s in K["sessions"]}
ITEMS = {}
for it in K["items"]:
    ITEMS.setdefault(it["sid"], []).append(it)
PICK = {p["id"]: p for p in K["picks"]}
WATCH = {p["id"]: p for p in K["watch"]}
MINE = set(K["my_papers"])
# short summaries written from the abstract book (scripts/summarize_abstracts.py); the abstract text itself is never published
_sp = ROOT / "work" / "abstract_summaries.json"
SUMS = json.loads(_sp.read_text(encoding="utf-8")) if _sp.exists() else {}
_ap = ROOT / "work" / "abstracts.json"
ABS_PAGE = {k: v["page"] for k, v in json.loads(_ap.read_text(encoding="utf-8")).items()} if _ap.exists() else {}
DAYS = {d["id"]: d for d in K["days"]}
DAYKEY = {d["id"]: "gyeongju-" + d["date"] for d in K["days"]}


def mins(t): return int(t[:2]) * 60 + int(t[3:5])
def hm(m): return "%02d:%02d" % (m // 60, m % 60)
def P(text): return "<p>" + E(text) + "</p>"
def UL(items): return "<ul>" + "".join("<li>" + E(x) + "</li>" for x in items) + "</ul>"
def A(label, url): return '<a href="%s" target="_blank" rel="noopener">%s ↗</a>' % (E(url, quote=True), E(label))
def LINKS(links): return "<p>" + " · ".join(A(l.get("label") or l["url"], l["url"]) for l in links if l and l.get("url")) + "</p>" if links else ""


def est_times(s):
    its, out = ITEMS.get(s["id"], []), {}
    dur = mins(s["end"]) - mins(s["start"])
    if s["kind"] in ("symposium", "oral"):
        n = len(its) + (1 if s.get("panel") else 0)
        for i, it in enumerate(its): out[it["id"]] = hm(mins(s["start"]) + round(dur / n * i))
    elif s["kind"] == "eposter":
        groups = {}
        for it in its: groups.setdefault(it["sub"], []).append(it)
        for g in groups.values():
            for i, it in enumerate(g): out[it["id"]] = hm(mins(s["start"]) + round(dur / len(g) * i))
    elif s["kind"] == "tutorial":
        t = mins(s["start"])
        for it in its:
            out[it["id"]] = hm(t); t += int(it.get("minutes") or 0)
    return out


# ---------------------------------------------------------------- glossary -> session / talk
LABEL2SID = {re.sub(r"\s", "", s["label"]): s["id"] for s in K["sessions"] if s.get("label")}
ALL_ITEMS = {it["id"]: it for it in K["items"]}
def rel_target(r):
    if r in ALL_ITEMS: return r
    k = re.sub(r"\s", "", str(r))
    if k in LABEL2SID: return LABEL2SID[k]
    m = re.match(r"^(심포지엄|튜토리얼|자유연제)(\d+)", k)
    if m:
        sid = {"심포지엄": "sym-", "튜토리얼": "tut-", "자유연제": "oral-"}[m.group(1)] + m.group(2)
        if sid in S: return sid
    return None
GLOSS_BY = {}
for g in K.get("glossary") or []:
    for r in g.get("related") or []:
        tgt = rel_target(r)
        if not tgt: continue
        for key in {tgt, ALL_ITEMS[tgt]["sid"] if tgt in ALL_ITEMS else tgt}:
            lst = GLOSS_BY.setdefault(key, [])
            if g not in lst: lst.append(g)
def gloss_html(key, limit=8):
    lst = GLOSS_BY.get(key) or []
    if not lst: return ""
    return "<p><b>관련 용어</b></p><ul>" + "".join("<li><b>%s</b> %s</li>" % (E(g["term"]), E(g.get("short") or "")) for g in lst[:limit]) + "</ul>"


# ---------------------------------------------------------------- events
EN_TITLE = {
    "휴식": "Break", "점심식사": "Lunch", "등록 (명찰 수령)": "Registration (badge pickup)", "등록": "Registration",
    "포스터 전시": "Poster exhibition", "휴식 · 황룡원으로 이동": "Break · move to Hwangnyongwon", "개회식": "Opening ceremony",
    "폐회식": "Closing ceremony", "공로상 시상식": "Service award ceremony", "네트워킹 리셉션": "Networking reception",
    "학생 네트워킹 프로그램": "Student networking program", "액티브 시니어 포럼 (Closed Meeting)": "Active Senior Forum (closed meeting)",
    "산업파트너 간담회": "Industry partner meeting", "정보의학학술상 강연": "Medical Informatics Academic Award lecture",
    "한국마이크로소프트": "Microsoft Korea",
}
def ev_type(s):
    k, sid, label = s["kind"], s["id"], s.get("label") or ""
    no = (re.search(r"\d+", label) or [""])[0] if k in ("tutorial", "symposium", "oral") else ""
    if k == "tutorial": return "tutorial", {"en": "Tutorial " + no, "ko": label}
    if k == "symposium": return "symposium", {"en": "Symposium " + no, "ko": label}
    if k == "oral": return "oral-session", {"en": "Free Papers " + no, "ko": label}
    if k == "eposter": return "eposter-session", {"en": "e-Poster", "ko": "e-포스터"}
    if k == "poster": return "poster-session", {"en": "Poster Q&A", "ko": "게시포스터"}
    if k == "plenary": return "invited-talk", {"en": {"범산특별강연": "Beomsan Special Lecture", "수상 강연": "Award Lecture"}.get(label, label), "ko": label}
    if k == "ceremony": return ("award", {"en": "Award", "ko": "시상"}) if sid == "d2-award" else ("ceremony", {"en": "Ceremony", "ko": "식순"})
    if k == "industry": return "industry", {"en": "Industry Symposium", "ko": "산업 세션"}
    if k == "side":
        if sid == "d2-demo": return "demo", {"en": "Demo Day", "ko": "데모데이"}
        if sid == "d2-partner": return "industry", {"en": "Industry Meeting", "ko": "간담회"}
        return "forum", {"en": "Forum", "ko": "포럼"}
    if k == "social": return ("reception", {"en": "Reception", "ko": "리셉션"}) if sid == "d2-reception" else ("social", {"en": "Networking", "ko": "네트워킹"})
    if k == "exhibit": return "exhibit", {"en": "Poster Exhibition", "ko": "포스터 전시"}
    if k == "admin": return "registration-desk", {"en": "Registration", "ko": "등록"}
    return "break", ({"en": "Lunch", "ko": "점심"} if "점심" in s["title"] else {"en": "Break", "ko": "휴식"})

def official_url(s):
    return SITE + {"symposium": "/content/sympo.html", "oral": "/content/session.html", "eposter": "/content/session.html",
                   "poster": "/content/session.html", "tutorial": "/content/tutorial.html"}.get(s["kind"], "/content/sche.html")

PAPER_KINDS = ("tutorial", "symposium", "oral", "eposter", "poster")
KIND_CODE = {"talk": "sym", "oral": "oral", "eposter": "epo", "poster": "post", "tutorial": "tut"}
days_out, details, index_rows, papers_by_sid = [], {}, [], {}
EN_DOW = {"수": ("Wed", "Wednesday"), "목": ("Thu", "Thursday"), "금": ("Fri", "Friday")}
NOTES = {"d1": {"en": "Online day", "ko": "온라인"}, "d2": {"en": "Main conference day 1", "ko": "오프라인 1일차"}, "d3": {"en": "Main conference day 2", "ko": "오프라인 2일차"}}

for d in K["days"]:
    y, mo, dd = d["date"].split("-")
    short, full = EN_DOW[d["dow"]]
    day = {"day": DAYKEY[d["id"]], "loc": "gyeongju", "date": d["date"],
           "label": {"en": "%s · Nov %d" % (short, int(dd)), "ko": "%s · %d/%d" % (d["dow"], int(mo), int(dd))},
           "dateFull": {"en": "%s, November %d, %s" % (full, int(dd), y), "ko": "%s년 %d월 %d일 %s요일" % (y, int(mo), int(dd), d["dow"])},
           "note": NOTES[d["id"]], "events": []}
    for s in sorted((x for x in K["sessions"] if x["day"] == d["id"]), key=lambda x: (x["start"], x["end"])):
        typ, type_name = ev_type(s)
        its = ITEMS.get(s["id"], [])
        est = est_times(s)
        R = s.get("research") or {}
        title = {"en": s["title"]}
        if s["title"] in EN_TITLE: title = {"en": EN_TITLE[s["title"]], "ko": s["title"]}
        room = s.get("room") or None
        no_room = bool(room and "장소 미표기" in room)
        if no_room: room = None
        ev = {"id": s["id"], "type": typ, "kind": "session" if s["kind"] in PAPER_KINDS else "simple", "typeName": type_name,
              "title": title, "start": s["start"], "end": s["end"], "room": room, "hasDetail": True}
        chairs = [c["name"] for c in s.get("chairs") or [] if c.get("name")]
        if chairs: ev["organizers"] = "좌장 " + ", ".join(chairs)
        if s["kind"] == "plenary" and its: ev["speaker"] = "%s (%s)" % (its[0]["speaker"], its[0]["aff"])
        if s["kind"] in PAPER_KINDS and its: ev["nPapers"] = len(its)
        day["events"].append(ev)

        # ---- detail modal
        parts = []
        pk = PICK.get(s["id"])
        if pk: parts.append("<p><b>⭐ 추천 동선 · %s</b> %s</p>" % (E(pk["level"]), E(pk["why"])))
        if no_room: parts.append(P("📍 공식 시간표에 장소가 따로 적혀 있지 않습니다. 현장 안내를 확인하세요."))
        if s.get("note"): parts.append(P("📌 " + s["note"]))
        if s.get("desc") and s["kind"] == "tutorial": parts.append("<p><b>교육 목표</b></p>" + "".join(P(x) for x in s["desc"].split("\n") if x.strip()))
        for key, lab in (("audience", "대상"), ("hands_on", "실습"), ("limit", "정원")):
            if s.get(key): parts.append("<p><b>%s</b> %s</p>" % (lab, E(s[key]).replace("\n", "<br>")))
        for c in s.get("chairs") or []:
            if c.get("aff"): parts.append("<p><b>좌장</b> %s <span>%s</span></p>" % (E(c["name"]), E(c["aff"])))
        if s.get("panel"): parts.append("<p><b>패널</b> " + E(", ".join("%s (%s)" % (c["name"], c["aff"]) for c in s["panel"])) + "</p>")
        if R.get("background"): parts.append("<p><b>배경</b> %s</p>" % E(R["background"]))
        if R.get("key_points"): parts.append("<p><b>들어가기 전에 알아둘 것</b></p>" + UL(R["key_points"]))
        if R.get("instructors"): parts.append("<p><b>강사</b></p>" + UL(R["instructors"]))
        if R.get("questions"): parts.append("<p><b>물어볼 만한 질문</b></p>" + UL(R["questions"]))
        parts.append(gloss_html(s["id"]))
        if est and s["kind"] != "tutorial": parts.append('<p style="color:var(--text3);font-size:12.5px">발표 시각(~)은 세션 시간을 발표 수로 나눈 추정치입니다.</p>')
        det = {}
        speakers = []
        if s["kind"] == "plenary" and its:
            r = its[0].get("research") or {}
            if r.get("prep"): parts.insert(0, "<p><b>강연 미리보기</b> %s</p>" % E(r["prep"]))
            sm0 = SUMS.get(its[0]["id"])
            if sm0: parts.insert(0, "<p><b>초록 요약</b> %s</p>" % E(sm0["sum"]))
            w0 = WATCH.get(its[0]["id"])
            if w0 and w0.get("rel"): parts.insert(0, "<p><b>🔗 내 연구와의 연관 · %s</b> %s</p>" % (E(w0["rel"]), E(w0["why"])))
            if r.get("profile"): speakers.append({"name": "%s (%s)" % (its[0]["speaker"], its[0]["aff"]), "bio": {"en": r["profile"]}})
            R = dict(R); R["links"] = (R.get("links") or []) + (r.get("links") or [])
        body = "".join(x for x in parts if x)
        if not body and s["kind"] not in ("break", "admin", "exhibit"): body = P("공식 시간표에 제목과 시간만 공개된 항목입니다.")
        if body: det["abs"] = {"en": body}
        if speakers: det["speakers"] = speakers
        if s.get("desc") and s["kind"] == "ceremony":
            det["program"] = {"schedule": [{"time": "", "en": x.strip(), "kind": "other"} for x in s["desc"].split(" | ")]}
        links, seen = [], set()
        for l in [{"label": "공식 페이지", "url": official_url(s)}] + (R.get("links") or []):
            if l and l.get("url") and l["url"] not in seen:
                seen.add(l["url"]); links.append({"label": l.get("label") or l["url"], "url": l["url"]})
        det["links"] = links[:9]
        details[s["id"]] = det

        # ---- talks
        if s["kind"] in PAPER_KINDS and its:
            rows = []
            for it in its:
                r = it.get("research") or {}
                ab = []
                w = WATCH.get(it["id"])
                if w and w.get("rel"): ab.append("<p><b>🔗 내 연구와의 연관 · %s</b> %s</p>" % (E(w["rel"]), E(w["why"])))
                elif w: ab.append("<p><b>✨ 추천 이유</b> %s</p>" % E(w["why"]))
                sm = SUMS.get(it["id"])
                if sm:
                    ab.append("<p><b>초록 요약</b> %s</p>" % E(sm["sum"]))
                    ab.append('<p style="color:var(--text3);font-size:12.5px">초록집%s 내용을 짧게 줄인 요약이며 원문이 아닙니다.</p>'
                              % (" (PDF %d쪽)" % ABS_PAGE[it["id"]] if it["id"] in ABS_PAGE else ""))
                if it.get("detail"): ab.append("".join(P(x) for x in it["detail"].split("\n") if x.strip()))
                if r.get("prep"): ab.append("<p><b>예습</b> %s</p>" % E(r["prep"]))
                if r.get("profile"):
                    conf = {"high": "확인됨", "medium": "부분 확인", "low": "불확실"}.get(r.get("confidence"), "")
                    ab.append("<p><b>발표자</b> %s%s</p>" % (E(r["profile"]), " <i>(%s)</i>" % conf if conf else ""))
                if not (it.get("detail") or r.get("prep") or sm): ab.insert(0, '<p style="color:var(--text2)">공식 홈페이지는 제목·발표자·소속만 공개하고 초록은 공개하지 않았습니다.</p>')
                if it.get("tags"): ab.append('<p style="color:var(--text2)">주제(자동 분류): %s</p>' % E(", ".join(it["tags"])))
                ab.append(gloss_html(it["id"], 5))
                extra = list(r.get("links") or [])
                if it["speaker"] and s["kind"] != "tutorial":
                    extra.append({"label": "발표자 논문 검색", "url": "https://scholar.google.com/scholar?q=" + urllib.parse.quote(it["speaker"] + " " + it.get("aff", ""))})
                    extra.append({"label": "제목 웹 검색", "url": "https://www.google.com/search?q=" + urllib.parse.quote('"' + it["title"] + '"')})
                ab.append(LINKS(extra))
                is_code = it["id"].startswith("26F")
                p = {"id": it["id"], "en": it["title"], "authors": it["speaker"], "inst": it.get("aff") or "",
                     "abs": "".join(x for x in ab if x), "link": official_url(s)}
                if is_code: p["pos"] = it["id"]
                if it.get("sub"): p["psess"] = "키오스크 " + it["sub"]
                if est.get(it["id"]): p["time"] = "~" + est[it["id"]]
                elif it.get("minutes"): p["time"] = it["minutes"] + "분"
                if it["id"] in MINE: p["mine"] = 1
                elif it["id"] in WATCH: p["watch"] = 1
                rows.append(p)
                index_rows.append([it["id"], s["id"], it["title"], "", it["speaker"], it.get("aff") or "", "", KIND_CODE.get(it["kind"], ""), -1,
                                   p.get("pos", ""), 1 if it["id"] in MINE else 2 if it["id"] in WATCH else 0, p.get("time", "")])
            papers_by_sid[s["id"]] = rows
    days_out.append(day)

built = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
schedule = {"locs": [{"id": "gyeongju", "name": {"en": "Gyeongju HICO", "ko": "경주 HICO"}, "tz": "Asia/Seoul", "abbr": "KST",
                      "role": {"en": "Venue", "ko": "행사장"}, "range": {"en": "Nov 25 – 27", "ko": "11.25 – 11.27"}}],
            "days": days_out, "built": built}


# ---------------------------------------------------------------- 안내 view
def table(head, rows, num_from=None):
    out = '<div class="tw"><table><thead><tr>' + "".join("<th>%s</th>" % E(h) for h in head) + "</tr></thead><tbody>"
    for r in rows:
        out += "<tr>" + "".join('<td%s>%s</td>' % (' class="n"' if num_from is not None and i >= num_from else "", c) for i, c in enumerate(r)) + "</tr>"
    return out + "</tbody></table></div>"

def research_html(sec):
    out = P(sec["summary"]) if sec.get("summary") else ""
    for it in sec.get("items") or []:
        meta = " · ".join("%s %s" % (k, v) for k, v in (it.get("meta") or {}).items() if v)
        out += "<h5>%s</h5>" % E(it["title"]) + ('<p class="muted">%s</p>' % E(meta) if meta else "")
        out += "<p>%s</p>" % E(it.get("body") or "").replace("\n", "<br>") + LINKS(it.get("links"))
    return out

V = K.get("venue") or {}
VSEC = {s["id"]: s for s in V.get("sections") or []}
PL = K.get("plenary") or {}
sections = []
def add(title, body, src="", open_=False):
    if body: sections.append({"title": title, "src": src, "open": open_, "html": body})

add("알아둘 점", UL(OFF["caveats"]), "", True)

# suggested route
route = '<p class="muted">유전체 진단 기업에서 AI 에이전트를 만드는 참가자를 가정하고 고른 편집 추천입니다. 타임테이블 탭의 「추천 동선 담기」로 한 번에 위시리스트에 넣을 수 있습니다.</p>'
for d in K["days"]:
    ps = sorted((p for p in K["picks"] if S[p["id"]]["day"] == d["id"]), key=lambda p: S[p["id"]]["start"])
    if not ps: continue
    route += "<h5>%s</h5>" % E(d["label"]) + table(["시간", "세션", "이유"], [
        ['<span style="white-space:nowrap">%s</span>' % S[p["id"]]["start"],
         '<span class="lv%s">%s</span><b>%s</b><br>%s%s' % (" alt" if p["level"] in ("대안", "선택") else "", E(p["level"]), E(S[p["id"]]["label"]),
                                                         E(S[p["id"]]["title"]) if S[p["id"]]["title"] != S[p["id"]]["label"] else "",
                                                         ' <span class="muted">· %s</span>' % E(S[p["id"]]["room"]) if S[p["id"]].get("room") else ""),
         E(p["why"])] for p in ps])
route += "<h5>눈여겨볼 개별 발표</h5>" + table(["번호", "발표", "이유"], [
    ['<span style="white-space:nowrap">%s</span>' % E(w["id"] if w["id"].startswith("26F") else S[ALL_ITEMS[w["id"]]["sid"]]["label"]),
     "<b>%s</b><br><span class=\"muted\">%s · %s</span>" % (E(ALL_ITEMS[w["id"]]["title"]), E(ALL_ITEMS[w["id"]]["speaker"]), E(ALL_ITEMS[w["id"]].get("aff") or "")),
     E(w["why"])] for w in K["watch"]])
add("추천 동선", route, "추정")

rel = [w for w in K["watch"] if w.get("rel")]
if rel:
    def when(w):
        it = ALL_ITEMS[w["id"]]; ss = S[it["sid"]]
        row = next((p for p in papers_by_sid.get(it["sid"], []) if p["id"] == w["id"]), {})
        its_ = ITEMS.get(it["sid"], [])
        extra = row.get("psess", "").replace("키오스크 ", "")
        if not extra and ss["kind"] in ("symposium", "oral"): extra = "%d번째 발표" % (its_.index(it) + 1)
        return ss["day"], ss["start"], row.get("time", ""), ss, extra
    body = ('<p class="muted">초록집을 읽고 고른, 게시포스터 26F-P2-12(MODIFINDER)와 방법이나 대상이 맞닿는 발표입니다. '
            '「직접」은 에이전트로 문헌·근거를 탐색·검증하거나 가설을 만드는 연구, 「인접」은 근거 검색·지식그래프·평가 방법이나 유전체 데이터·검사를 다루는 연구입니다. '
            '~로 시작하는 시각은 공식 시각이 아니라 추정치입니다(자유연제·심포지엄은 세션을 발표 수로, e-포스터는 키오스크별 발표 수로 나눔). 게시포스터는 질의응답 시간대만 있습니다.</p>')
    for lv in ("직접", "인접"):
        rows = sorted((w for w in rel if w["rel"] == lv), key=lambda w: when(w)[:3])
        if not rows: continue
        body += "<h5>%s 연관 (%d)</h5>" % (lv, len(rows)) + table(["언제·어디", "발표", "연관되는 점"], [
            ['<span style="white-space:nowrap">%s %s</span><br><span class="muted">%s%s</span>' % (
                E(DAYS[when(w)[0]]["label"]), E(when(w)[2] or when(w)[1]), E(when(w)[3]["label"]),
                (" · " + E(when(w)[3]["room"]) if when(w)[3].get("room") else "") + (" · " + E(when(w)[4]) if when(w)[4] else "")),
             "<b>%s</b><br><span class=\"muted\">%s%s · %s</span>" % (
                E(ALL_ITEMS[w["id"]]["title"]), E(w["id"] + " · " if w["id"].startswith("26F") else ""),
                E(ALL_ITEMS[w["id"]]["speaker"]), E(ALL_ITEMS[w["id"]].get("aff") or "")),
             E(w["why"])] for w in rows])
    sections.insert(1, {"title": "내 연구와 연관된 발표 (%d)" % len(rel), "src": "초록집 요약", "open": True, "html": body})

sh = OFF["shuttle"]
body = P(" ↔ ".join(sh["stops"]))
for dd in sh["days"]:
    body += "<h5>%s</h5><p><b>경주역 → HICO</b><br>%s</p><p><b>HICO → 경주역</b><br>%s</p>" % (
        E(dd["label"]), "".join('<span class="tm">%s</span>' % t for t in dd["to"]),
        "".join('<span class="tm">%s%s</span>' % (x["t"], "<small>%s</small>" % E(x["n"]) if x.get("n") else "") for x in dd["from"]))
pk = OFF["parking"]
body += "<h5>주차</h5><p>HICO 주차장 %s · 총 %d대 (지상 %d · 지하 %d) · 전기차 충전 %d대</p>" % (E(pk["fee"]), pk["total"], pk["ground"], pk["under"], pk["ev"]) + LINKS([{"label": "HICO 주차 안내", "url": pk["url"]}])
add("셔틀버스 · 주차", body, "공식")

rooms = {r["room"]: r for r in V.get("rooms") or []}
used = {}
for s in K["sessions"]:
    if s.get("room") and s["day"] != "d1" and s["kind"] in PAPER_KINDS + ("industry", "side", "social"):
        used.setdefault(s["room"], []).append(s)
order = ["300B", "300C", "203+204호", "205+206호", "201+202호", "300A", "4층 라운지"]
def col(r, d): return "<br>".join("%s %s" % (x["start"], E(x["label"])) for x in sorted(used.get(r, []), key=lambda x: x["start"]) if x["day"] == d) or "–"
body = "<p><b>%s</b><br>%s</p><p class=\"muted\">등록: 11/26 09:00–10:00 · 11/27 08:30–09:00</p>" % (E(OFF["venue"]["name"]), E(OFF["venue"]["addr"]))
body += table(["방", "층", "11.26 목", "11.27 금"], [["<b>%s</b>" % E(r), E((rooms.get(r) or {}).get("floor", "")), col(r, "d2"), col(r, "d3")] for r in order if r in used])
body += LINKS([{"label": "HICO 홈페이지", "url": OFF["venue"]["url"]}, {"label": "네이버 지도", "url": "https://map.naver.com/p/search/" + urllib.parse.quote("경주화백컨벤션센터")}])
if "floor" in VSEC: body += research_html(VSEC["floor"])
add("행사장 · 세션룸", body, "공식 + 웹 조사")

for sid, title in (("train", "경주역(KTX) 가는 법"), ("local_transit", "경주역·터미널 → HICO (셔틀 외)"), ("car", "자가용"), ("reception", "네트워킹 리셉션 · 황룡원"),
                   ("hotels", "숙박"), ("food", "식사 · 카페"), ("weather", "날씨"), ("sightseeing", "짧은 관광"), ("notices", "HICO 행사일 공지")):
    if sid in VSEC: add(title, research_html(VSEC[sid]), "웹 조사")

f = OFF["fees"]
body = table(["구분", "회원"] + f["cols"], [[E(r["when"]), E(r["who"])] + r["v"] for r in f["rows"]], 2) + UL(f["notes"])
body += '<p class="muted">문의: %s · %s</p>' % (E(f["contact"]["email"]), E(" · ".join(f["contact"]["tel"])))
add("등록비", body, "공식")

body, last = "", None
for q in K["faq"]:
    if q["section"] != last: body += "<h5>%s</h5>" % E(q["section"]); last = q["section"]
    body += "<p><b>Q. %s</b><br>%s</p>" % (E(q["q"]), E(q["a"]).replace("\n", "<br>"))
add("자주하는 질문", body, "공식")

if PL.get("events"):
    add("부대행사", "".join("<h5>%s</h5><p class=\"muted\">%s</p><p>%s</p>%s%s" % (
        E(e["name"]), E(" · ".join(x for x in (e.get("when"), e.get("where")) if x)), E(e.get("what") or ""),
        "<p><b>팁</b> %s</p>" % E(e["tips"]) if e.get("tips") else "", LINKS(e.get("links"))) for e in PL["events"]), "웹 조사")
if PL.get("awards"):
    add("시상", "".join("<h5>%s</h5><p>%s</p>%s%s" % (E(a["name"]), E(a.get("what") or ""), '<p class="muted">%s</p>' % E(a["winners"]) if a.get("winners") else "", LINKS(a.get("links"))) for a in PL["awards"]), "웹 조사")
if PL.get("people"):
    add("기조·개회 인사", "".join("<h5>%s <span class=\"muted\">%s</span></h5><p>%s</p>%s" % (E(p["name"]), E(p.get("affiliation") or ""), E(p.get("profile") or ""), LINKS(p.get("links"))) for p in PL["people"]), "웹 조사")
news = (PL.get("news") or []) + [{"title": n.get("title"), "date": n.get("date"), "source": "공지", "url": n.get("url"), "summary": n.get("summary")} for n in PL.get("notices") or []]
if news:
    add("소식 · 공지", "".join("<p><b>%s</b> <span class=\"muted\">%s · %s</span><br>%s</p>" % (
        A(n["title"], n["url"]) if n.get("url") else E(n.get("title") or ""), E(n.get("date") or ""), E(n.get("source") or ""), E(n.get("summary") or "")) for n in news), "웹 조사")
if K.get("sponsors"):
    add("후원사 · 전시", "".join("<h5>%s <span class=\"muted\">%s</span></h5><p>%s</p>%s%s%s%s" % (
        E(s["name"]), E(s.get("type") or ""), E(s.get("what") or ""),
        "<p class=\"muted\"><b>주요 제품</b> %s</p>" % E(s["products"]) if s.get("products") else "",
        "<p class=\"muted\"><b>최근</b> %s</p>" % E(s["recent"]) if s.get("recent") else "",
        "<p><b>부스에서</b> %s</p>" % E(s["why_visit"]) if s.get("why_visit") else "",
        LINKS(([{"label": "홈페이지", "url": s["url"]}] if s.get("url") else []) + (s.get("links") or []))) for s in K["sponsors"]), "웹 조사")
if K.get("glossary"):
    sections.append({"title": "용어집 (%d)" % len(K["glossary"]), "src": "웹 조사", "glossary": [
        {"t": g["term"], "a": g.get("aka") or "", "c": g.get("category") or "", "s": g.get("short") or "", "d": g.get("detail") or "", "g": g.get("genomics_angle") or ""}
        for g in K["glossary"]]})
body = ""
if (PL.get("kosmi") or {}).get("about"): body += "<h5>대한의료정보학회</h5>" + P(PL["kosmi"]["about"]) + LINKS(PL["kosmi"].get("links"))
body += "<h5>인사말 요지</h5><p class=\"muted\">%s</p>" % E(OFF["greeting"]["by"]) + UL(OFF["greeting"]["summary"]) + LINKS([{"label": "인사말 전문", "url": OFF["greeting"]["url"]}])
lead = [c for c in K["committee"] if c["role"] != "조직위원"]; rest = [c for c in K["committee"] if c["role"] == "조직위원"]
body += "<h5>조직위원회</h5>" + "".join("<p><b>%s</b> %s <span class=\"muted\">%s</span></p>" % (E(c["role"]), E(c["name"]), E(c["aff"])) for c in lead)
body += '<p class="muted">조직위원 %d명: %s</p>' % (len(rest), E(" · ".join("%s(%s)" % (c["name"], c["aff"]) for c in rest)))
add("학회 · 조직위원회", body, "공식 + 웹 조사")
add("공식 링크", LINKS(OFF["links"]).replace(" · ", "<br>"), "공식")
nf = [x for x in (V.get("not_found") or []) if x]
if nf: add("확인하지 못한 항목 (교통·숙소)", UL(nf), "웹 조사")

def wish_paper(pid):
    it = ALL_ITEMS[pid]; row = next(p for p in papers_by_sid[it["sid"]] if p["id"] == pid)
    return {"id": pid, "s": it["sid"], "en": it["title"], "pos": row.get("pos", ""), "time": row.get("time", "")}
info = {"note": "공식 홈페이지 내용과 웹 조사 결과를 모았습니다. 일정·장소는 공식 안내가 우선합니다. 데이터 생성 " + built + ".",
        "sections": sections,
        "picks": {"events": [p["id"] for p in K["picks"] if p["level"] in ("필수", "추천")],
                  "papers": [wish_paper(i) for i in list(MINE) + [w["id"] for w in K["watch"]]
                             if ALL_ITEMS[i]["sid"] in papers_by_sid]},
        "seed": [wish_paper(i) for i in MINE]}


# ---------------------------------------------------------------- write
def dump(o): return json.dumps(o, ensure_ascii=False, separators=(",", ":"))
data = ROOT / "data"
(data / "papers").mkdir(parents=True, exist_ok=True)
(data / "search").mkdir(parents=True, exist_ok=True)
for old in (data / "papers").glob("s*.js"): old.unlink()
(data / "schedule.js").write_text("window.KOSMI_SCHEDULE = " + dump(schedule) + ";\n", encoding="utf-8")
(data / "details.js").write_text("window.KOSMI_DETAILS = " + dump(details) + ";\n", encoding="utf-8")
(data / "info.js").write_text("window.KOSMI_INFO = " + dump(info) + ";\n", encoding="utf-8")
(data / "search" / "index.js").write_text('window.KOSMI_INDEX = {"rows":[\n' + ",\n".join(dump(r) for r in index_rows) + "\n]};\n", encoding="utf-8")
for sid, rows in papers_by_sid.items():
    (data / "papers" / ("s%s.js" % sid)).write_text('window.KOSMI_PAPERS = window.KOSMI_PAPERS || {};\nwindow.KOSMI_PAPERS[%s] = [\n' % json.dumps(sid) + ",\n".join(dump(r) for r in rows) + "\n];\n", encoding="utf-8")


# ---------------------------------------------------------------- icons (plain PNG writer, no dependencies)
def png(size, path):
    bg, card, bar = (37, 99, 235), (255, 255, 255), (37, 99, 235)
    def px(x, y):
        u, v = x / size, y / size
        if 0.2 <= u <= 0.8 and 0.24 <= v <= 0.8:
            if v <= 0.38: return (219, 234, 254)
            for row in (0.48, 0.60, 0.72):
                if abs(v - row) < 0.028 and 0.28 <= u <= (0.72 if row < 0.7 else 0.56): return bar
            return card
        return bg
    raw = b"".join(b"\x00" + bytes(c for x in range(size) for c in px(x, y)) for y in range(size))
    def chunk(tag, body): return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xffffffff)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
for n in (192, 512):
    if not (ROOT / "assets" / ("icon-%d.png" % n)).exists(): png(n, ROOT / "assets" / ("icon-%d.png" % n))

# ---------------------------------------------------------------- artifact fragment (the artifact host supplies <html>/<head>/<body>)
(ROOT / "artifact.html").write_text("""<title>KOSMI 2026 추계 가이드</title>
<link rel="stylesheet" href="assets/style.css">
<div id="app"></div>
<script src="data/schedule.js"></script>
<script src="data/details.js"></script>
<script src="data/info.js"></script>
<script src="assets/app.js"></script>
""", encoding="utf-8")

n_ev = sum(len(d["events"]) for d in days_out)
print("events", n_ev, "| details", len(details), "| talk files", len(papers_by_sid), "| talks", len(index_rows), "| info sections", len(sections))
for f in ("schedule.js", "details.js", "info.js", "search/index.js"): print("  %-16s %7d bytes" % (f, (data / f).stat().st_size))
print("  papers/*         %7d bytes" % sum(p.stat().st_size for p in (data / "papers").glob("*.js")))
