#!/usr/bin/env python3
"""Split the abstract book text into one segment per programme item.

Input : work/abstract_book_text/all_raw.txt   (pdftotext of the abstract book; never committed)
        work/kosmi.json                       (items with ids and titles)
Output: work/abstracts.json                   {item_id: {"page": n, "text": "..."}}

The abstract text stays in work/ (gitignored). Only short summaries written from it
(work/abstract_summaries.json) are used by build_site.py.

    python3 scripts/parse_abstracts.py
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "work" / "abstract_book_text" / "all_raw.txt"
K = json.loads((ROOT / "work" / "kosmi.json").read_text(encoding="utf-8"))

pages = RAW.read_text(encoding="utf-8", errors="replace").split("\f")
BODY_FROM = 22          # pages before this are the programme and the poster index
text, page_at = "", []  # page_at[i] = (offset, page_no)
for n, p in enumerate(pages, 1):
    if n < BODY_FROM: continue
    page_at.append((len(text), n))
    text += p + "\n"

def page_of(off):
    pg = page_at[0][1]
    for o, n in page_at:
        if o <= off: pg = n
        else: break
    return pg

# normalised view (letters/digits/hangul only) with a map back to raw offsets
keep = re.compile(r"[0-9A-Za-z가-힣]")
norm_chars, norm_map = [], []
for i, ch in enumerate(text):
    if keep.match(ch):
        norm_chars.append(ch.lower()); norm_map.append(i)
NORM = "".join(norm_chars)
def nz(s): return "".join(ch.lower() for ch in (s or "") if keep.match(ch))

S = {s["id"]: s for s in K["sessions"]}
starts = {}   # item id -> raw offset
missing = []
used = set()
fallback = []
# talks whose title in the book differs from the programme page
ALIAS = {
    "sym-2-3": "간호 기록에서 예측 모델까지",
    "sym-9-4": "AI 기반 보건의료데이터 표준 적용 자동화 기술 개발 및 실증",
    "sym-10-3": "접수에서 반출까지: 연구자를 위한DRB 실무 안내",
    "sym-15-3": "Bridging Governance and Practice",
    "sym-16-4": "수용을 넘어 적합성으로: 재가노인 로봇에 대한 주제범위고찰",
}
# one joint abstract covers the whole session
JOINT = {"sym-13": "First Steps with BioBigData.Korea: From Data to Research"}

def find_all(needle):
    out, i = [], NORM.find(needle)
    while i != -1:
        out.append(i); i = NORM.find(needle, i + 1)
    return out

for it in K["items"]:
    iid, title = it["id"], it["title"]
    hit = None
    if re.match(r"26F-E?P\d-\d+$", iid):
        m = re.search(re.escape(iid) + r"(?!\d)", text)
        if m: hit = m.start()
    if hit is None and it["sid"] in JOINT:
        c = find_all(nz(JOINT[it["sid"]]))
        if c: starts[iid] = norm_map[c[0]]; continue      # shared offset, not marked used
    if hit is None:
        t = nz(ALIAS.get(iid, title))
        for n in (len(t), 40, 24, 16):
            if len(t) < 8 or n > len(t): continue
            cands = [c for c in find_all(t[:n]) if norm_map[c] not in used]
            if cands:
                hit = norm_map[cands[0]]
                if n < len(t): fallback.append((iid, n))
                break
    if hit is None:
        missing.append(iid); continue
    used.add(hit); starts[iid] = hit

order = sorted(starts.items(), key=lambda kv: kv[1])
uniq = sorted(set(starts.values()))
next_of = {o: (uniq[i + 1] if i + 1 < len(uniq) else len(text)) for i, o in enumerate(uniq)}
HEAD = re.compile(r"^(2026 대한의료정보학회 추계학술대회|2026|대한의료정보학회|추계학술대회|심포지엄 ?\d+|자유연제 ?\d+|e-포스터 발표 I+|게시포스터 I+|\d{1,3})$")
session_titles = {nz(s["title"]) for s in K["sessions"]}
out = {}
for i, (iid, off) in enumerate(order):
    end = next_of[off]
    seg = text[off:min(end, off + 6000)]
    lines = [l.strip() for l in seg.splitlines()]
    lines = [l for l in lines if l and not HEAD.match(l) and nz(l) not in session_titles]
    out[iid] = {"page": page_of(off), "text": "\n".join(lines)}

(ROOT / "work" / "abstracts.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
by_kind = {}
for it in K["items"]:
    k = it["kind"]; a, b = by_kind.get(k, (0, 0))
    by_kind[k] = (a + (it["id"] in out), b + 1)
print("matched %d / %d items" % (len(out), len(K["items"])))
for k, (a, b) in sorted(by_kind.items()): print("  %-10s %d / %d" % (k, a, b))
if missing: print("missing:", ", ".join(missing))
if fallback: print("matched on a title prefix (check):", fallback)
ALL = {it["id"]: it for it in K["items"]}
nosp = [i for i, v in out.items() if ALL[i]["kind"] in ("talk", "plenary") and ALL[i].get("speaker")
        and nz(ALL[i]["speaker"].split("(")[0])[:3] not in nz(v["text"][:500])]
print("talk segments without the speaker name near the top:", nosp)
short = [i for i, v in out.items() if len(v["text"]) < 250]
print("short segments (<250 chars):", len(short), short[:20])
