#!/usr/bin/env python3
"""Parse the scraped KOSMI 2026 Fall pages into data/official.json."""
import re, html, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "work" / "source" / "html"

def clean(s):
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t\r]+", " ", s)
    s = re.sub(r" ?\n ?", "\n", s).strip()
    return s

def one(s):
    return re.sub(r"\s+", " ", clean(s)).strip()

def body(name):
    t = (SRC / name).read_text(encoding="utf-8")
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", t)
    t = re.sub(r"(?is)<!--.*?-->", "", t)
    return t

def rows(fragment):
    out = []
    for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", fragment):
        cells = re.findall(r"(?is)<(th|td)([^>]*)>(.*?)</\1>", tr)
        out.append([(k.lower(), a, c) for k, a, c in cells])
    return out

def split_person(cell_html):
    """'<strong>양현종</strong> 순천향대학교 서울병원, <strong>..' -> list of {name, aff}"""
    people = []
    parts = re.split(r"(?is)<strong[^>]*>(.*?)</strong>", cell_html)
    for i in range(1, len(parts), 2):
        name = one(parts[i])
        aff = one(parts[i + 1]) if i + 1 < len(parts) else ""
        aff = aff.strip(" ,")
        if name:
            people.append({"name": name, "aff": aff})
    return people

# ---------------------------------------------------------------- symposia
def parse_sympo():
    t = body("content_sympo.html")
    res = []
    cur = None
    for r in rows(t):
        if not r:
            continue
        k0, _, c0 = r[0]
        head = one(c0)
        m = re.match(r"심포지엄\s*(\d+)", head)
        if k0 == "th" and m:
            cur = {"no": int(m.group(1)), "title": one(r[1][2]) if len(r) > 1 else "",
                   "room": one(r[2][2]) if len(r) > 2 else "", "chairs": [], "talks": []}
            res.append(cur)
        elif cur is not None and head == "좌장":
            cur["chairs"] = [p for p in split_person(r[1][2]) if p["name"]] if len(r) > 1 else []
        elif cur is not None and len(r) >= 3:
            cur["talks"].append({"title": one(r[0][2]), "speaker": one(r[1][2]), "aff": one(r[2][2])})
        elif cur is not None and len(r) == 2:
            cur["talks"].append({"title": one(r[0][2]), "speaker": one(r[1][2]), "aff": ""})
    return res

# ---------------------------------------------------------------- free papers
def parse_session():
    t = body("content_session.html")
    tabs = re.split(r'(?i)<div id="tab-(\d)"', t)
    groups = []
    for i in range(1, len(tabs), 2):
        tab = int(tabs[i]); frag = tabs[i + 1]
        # walk date headers and tables in order
        pieces = re.split(r'(?is)<p class="date_txt">(.*?)</p>', frag)
        for j in range(1, len(pieces), 2):
            date_txt = one(pieces[j]); table = pieces[j + 1]
            cur = None
            for r in rows(table):
                if not r:
                    continue
                k0, _, c0 = r[0]
                head = one(c0)
                if k0 == "th" and head != "좌장":
                    cur = {"tab": tab, "date_txt": date_txt, "label": head,
                           "title": one(r[1][2]) if len(r) > 1 else "",
                           "room": one(r[2][2]) if len(r) > 2 else "",
                           "chairs": [], "papers": []}
                    if tab == 3 and len(r) == 2:   # 게시포스터: th + room
                        cur["room"] = one(r[1][2]); cur["title"] = ""
                    groups.append(cur)
                elif cur is not None and head == "좌장":
                    cur["chairs"] = split_person(r[1][2]) if len(r) > 1 else []
                elif cur is not None and re.match(r"26F-", head):
                    cur["papers"].append({"id": head, "title": one(r[1][2]) if len(r) > 1 else "",
                                          "speaker": one(r[2][2]) if len(r) > 2 else "",
                                          "aff": one(r[3][2]) if len(r) > 3 else ""})
    return groups

# ---------------------------------------------------------------- tutorials
def parse_tutorial():
    t = body("content_tutorial.html")
    res = []
    blocks = re.split(r"(?is)<th[^>]*>\s*튜토리얼\s*(\d)\s*</th>", t)
    for i in range(1, len(blocks), 2):
        no = int(blocks[i]); frag = blocks[i + 1]
        tut = {"no": no, "title": "", "goal": "", "parts": [], "audience": "", "hands_on": "", "limit": ""}
        rs = rows("<tr><th>x</th>" + frag)  # re-open the first row
        mode = None
        for r in rs:
            cells = [clean(c) for _, _, c in r]
            flat = [re.sub(r"\s+", " ", c) for c in cells]
            if not flat:
                continue
            if flat[0] == "x":
                flat = flat[1:]; cells = cells[1:]
            if not flat:
                continue
            key = flat[0]
            if key == "제목" and len(flat) > 1: tut["title"] = flat[1]
            elif key == "교육 목표" and len(cells) > 1: tut["goal"] = cells[1]
            elif key == "교육내용": mode = "parts"
            elif key == "참여 대상" and len(cells) > 1: tut["audience"] = cells[1]; mode = None
            elif key == "컴퓨터 실습" and len(cells) > 1: tut["hands_on"] = cells[1]; mode = None
            elif key == "인원 제한" and len(cells) > 1: tut["limit"] = flat[1]; mode = None
            elif mode == "parts":
                if key == "내용":
                    continue
                part = {"content": cells[0], "instructor": "", "minutes": ""}
                if len(cells) == 3:
                    part["instructor"] = flat[1]; part["minutes"] = flat[2]
                elif len(cells) == 2:
                    if re.fullmatch(r"\d+", flat[1]): part["minutes"] = flat[1]
                    else: part["instructor"] = flat[1]
                tut["parts"].append(part)
        res.append(tut)
    return res

# ---------------------------------------------------------------- committee
def parse_committee():
    t = body("content_group.html")
    out = []
    for r in rows(t):
        c = [one(x[2]) for x in r]
        if len(c) == 3 and c[0] not in ("담당",):
            out.append({"role": c[0], "name": c[1], "aff": c[2]})
    return out

# ---------------------------------------------------------------- FAQ
def parse_faq():
    t = body("content_group.html")
    t = body("entry_faq.html")
    txt = clean(re.sub(r"(?i)</(p|div|li|tr|h\d|dd|dt|td|th)>", "\n", t))
    lines = [l.strip() for l in txt.split("\n") if l.strip()]
    try:
        start = max(i for i, l in enumerate(lines) if l == "자주하는 질문")
    except ValueError:
        start = 0
    lines = lines[start + 1:]
    faq = []; section = ""; cur = None
    for l in lines:
        if l.startswith("Q."):
            cur = {"section": section, "q": l[2:].strip(), "a": ""}
            faq.append(cur)
        elif l.startswith("A.") and cur is not None:
            cur["a"] = l[2:].strip()
        elif cur is not None and cur["a"] and not re.match(r"^(Privacy Policy|대한의료정보학회$|TOP$|Address)", l) and len(faq) and l not in ("등록비",):
            # section headings are short lines without punctuation following a completed answer
            if len(l) <= 14 and not re.search(r"[.:\d]", l) and not l.startswith(("-", "*", "(")) and l not in ("구분", "정회원", "준회원/비회원", "대학원생", "전공의/간호사", "일반", "학부생"):
                section = l; cur = None
            else:
                cur["a"] += "\n" + l
        elif cur is None and len(l) <= 14:
            section = l
        if l.startswith("(Tel :"):
            break
    return faq

data = {
    "symposia": parse_sympo(),
    "paper_groups": parse_session(),
    "tutorials": parse_tutorial(),
    "committee": parse_committee(),
    "faq": parse_faq(),
}
(ROOT / "work").mkdir(exist_ok=True)
(ROOT / "work" / "official.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("symposia", len(data["symposia"]), "talks", sum(len(s["talks"]) for s in data["symposia"]))
print("paper groups", len(data["paper_groups"]), "papers", sum(len(g["papers"]) for g in data["paper_groups"]))
for g in data["paper_groups"]:
    print("  ", g["tab"], g["date_txt"], "|", g["label"], "|", g["title"], "|", g["room"], "|", [c["name"] for c in g["chairs"]], len(g["papers"]))
print("tutorials", [(t["no"], t["title"], len(t["parts"]), t["limit"]) for t in data["tutorials"]])
print("committee", len(data["committee"]), data["committee"][:3])
print("faq", len(data["faq"]))
for f in data["faq"]: print("  [%s] %s => %s" % (f["section"], f["q"][:40], f["a"][:50].replace("\n", " / ")))
for s in data["symposia"]:
    print(s["no"], s["room"], [c["name"] + "/" + c["aff"] for c in s["chairs"]], len(s["talks"]), s["title"])
bad = [p for g in data["paper_groups"] for p in g["papers"] if not p["speaker"] or not p["aff"] or not p["title"]]
print("papers with missing fields:", bad)
