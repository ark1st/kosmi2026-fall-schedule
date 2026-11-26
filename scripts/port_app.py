#!/usr/bin/env python3
"""Port the NeurIPS 2026 schedule app (../neurips2026/assets) to KOSMI 2026 Fall.

Copies app.js / style.css from the NeurIPS project and applies a fixed list of patches:
single venue (Gyeongju HICO, KST only), KOSMI event types and labels, no sync server /
semantic search / poster insights, plus one extra "안내" view fed by data/info.js.
Every patch asserts that it matched, so an upstream change fails loudly instead of silently.

    python3 scripts/port_app.py [path-to-neurips2026]
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "neurips2026"
t = (SRC / "assets" / "app.js").read_text(encoding="utf-8")
css = (SRC / "assets" / "style.css").read_text(encoding="utf-8")


def rep(old, new, n=1):
    global t
    c = t.count(old)
    assert c == n, f"expected {n} match(es), found {c}: {old[:70]!r}"
    t = t.replace(old, new)


def cut(start, end, new):
    """Replace everything from `start` up to (not including) `end`."""
    global t
    a = t.index(start)
    b = t.index(end, a + len(start))
    t = t[:a] + new + t[b:]


def setk(lang, key, value):
    """Set one I18N string inside the given language block."""
    global t
    a = t.index("    %s: {" % lang)
    b = t.index("\n    },", a) if lang == "ko" else t.index("\n    }\n  };", a)
    block = t[a:b]
    pat = re.compile(r"(\b%s: )'(?:[^'\\]|\\.)*'" % re.escape(key))
    assert len(pat.findall(block)) == 1, (lang, key)
    block = pat.sub(lambda m: m.group(1) + "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'", block)
    t = t[:a] + block + t[b:]


# ---------------------------------------------------------------- labels
rep("/* NeurIPS 2026 bilingual schedule app (vanilla JS, works over file://) */",
    "/* KOSMI 2026 Fall schedule app — ported from the NeurIPS 2026 schedule app by scripts/port_app.py\n"
    "   (vanilla JS, works over file://). Edit the port script, not this file. */")

KO = {
    "search_ph": "일정·발표 검색 (제목, 발표자, 세션…)",
    "oral": "자유연제", "poster": "포스터", "invited": "초청·식순", "tutorial": "튜토리얼", "workshop": "심포지엄",
    "expo": "산업·데모", "social": "네트워킹", "ops": "운영·휴식",
    "papers_n": "건의 발표", "speakers": "연사", "talks": "발표 목록", "posters": "포스터 목록", "accepted": "발표 목록",
    "filter_papers": "이 세션에서 발표 검색…", "results_papers": "발표",
    "load_all": "전체 발표({n}건)에서도 검색하기",
    "offline_desc": "설치 후 저장하면 인터넷 없이도 전체 일정·발표를 볼 수 있습니다.",
    "wish_empty": "카드나 발표를 길게 누르면 위시리스트에 추가됩니다", "pinned_papers": "핀한 발표",
    "footer": "데이터 출처: 대한의료정보학회 2026 추계학술대회 홈페이지 + 웹 조사 · 모든 시간은 KST · 학회가 만든 사이트가 아닌 비공식 가이드입니다.",
    "search_hint_papers": "발표 제목도 함께 검색됩니다",
    "view_search": "🔍 발표 검색", "s_title": "발표 검색",
    "s_desc": "심포지엄·자유연제·포스터 발표 {n}건을 제목·발표자·소속·발표번호로 찾습니다.",
    "s_ph": "주제, 제목, 발표자, 소속, 발표번호를 입력하세요", "s_top_inst": "이 결과에 가장 많은 소속",
    "s_clear_inst": "소속 필터 해제",
    "wk_desc": "핀한 일정과 발표를 요일별로 한눈에 봅니다. 일정 탭에서 카드나 발표를 길게 눌러 추가하세요.",
    "wk_empty": "아직 핀한 일정이 없습니다", "wk_papers": "발표 {n}건",
}
EN = {
    "search_ph": "Search events & talks (title, presenter, session…)",
    "oral": "Free papers", "poster": "Posters", "invited": "Invited · Ceremonies", "tutorial": "Tutorials", "workshop": "Symposia",
    "expo": "Industry · Demo", "social": "Networking", "ops": "Logistics",
    "papers_n": " talks", "speakers": "Speakers", "talks": "Talks", "posters": "Posters", "accepted": "Talks",
    "filter_papers": "Filter talks in this session…", "results_papers": "Talks",
    "load_all": "Also search all {n} talks",
    "offline_desc": "Install and save to browse the full schedule and talks without internet.",
    "wish_empty": "Long-press any card or talk to add it to your wishlist", "pinned_papers": "Pinned talks",
    "footer": "Data: KOSMI 2026 Fall conference site + web research · All times KST · Unofficial guide, not made by the society.",
    "search_hint_papers": "Talk titles are searched too",
    "view_search": "🔍 Talk search", "s_title": "Talk search",
    "s_desc": "Find any of the {n} symposium talks, free papers and posters by title, presenter, affiliation or paper number.",
    "s_ph": "Type a topic, title, presenter, affiliation or paper number", "s_top_inst": "Most frequent affiliations in these results",
    "s_clear_inst": "Clear affiliation filter",
    "wk_desc": "Your pinned events and talks, laid out by day. Long-press any card or talk in Schedule to add it.",
    "wk_empty": "Nothing pinned yet", "wk_papers": "{n} talks",
}
KO["oral_pending"] = "세션별 발표 배정이 아직 공개되지 않았습니다."
EN["oral_pending"] = "Talk assignments for this session are not published yet."
for k, v in KO.items(): setk("ko", k, v)
for k, v in EN.items(): setk("en", k, v)
rep("      locs_btn: '⚙ 개최지',",
    "      view_info: 'ℹ 안내', info_title: '안내', k_sym: '심포지엄', k_oral: '자유연제', k_epo: 'e-포스터', k_post: '게시포스터', k_tut: '튜토리얼',\n"
    "      mine: '내 발표', watch: '추천', official: '공식 페이지', gloss_ph: '용어 검색 (예: FHIR, DRB, 2차활용)',\n"
    "      picks_add: '⭐ 추천 동선 담기', picks_note: '유전체 진단·AI 에이전트 관점에서 고른 편집 추천입니다. 공식 추천이 아닙니다.',\n"
    "      locs_btn: '⚙ 개최지',")
rep("      locs_btn: '⚙ Venues',",
    "      view_info: 'ℹ Info', info_title: 'Info', k_sym: 'Symposia', k_oral: 'Free papers', k_epo: 'e-Posters', k_post: 'Posters', k_tut: 'Tutorials',\n"
    "      mine: 'My talk', watch: 'Pick', official: 'Official page', gloss_ph: 'Search glossary (e.g. FHIR, DRB)',\n"
    "      picks_add: '⭐ Add suggested route', picks_note: 'Editorial picks for a genomics / AI-agent attendee. Not official.',\n"
    "      locs_btn: '⚙ Venues',")

# ---------------------------------------------------------------- event types
cut("  var TYPE_GROUP = {", "  var GROUP_COLOR = {", """  var TYPE_GROUP = {
    'symposium': 'workshop',
    'oral-session': 'oral',
    'poster-session': 'poster', 'eposter-session': 'poster',
    'invited-talk': 'invited', 'ceremony': 'invited', 'award': 'invited',
    'tutorial': 'tutorial',
    'industry': 'expo', 'demo': 'expo',
    'social': 'social', 'reception': 'social', 'forum': 'social',
    'break': 'ops', 'registration-desk': 'ops', 'exhibit': 'ops'
  };
""")
rep("var CHIP_ORDER = ['all', 'wish', 'oral', 'poster', 'invited', 'tutorial', 'workshop', 'expo', 'social', 'ops'];",
    "var CHIP_ORDER = ['all', 'wish', 'workshop', 'oral', 'poster', 'invited', 'tutorial', 'expo', 'social', 'ops'];")

# ---------------------------------------------------------------- single venue, KST, Korean by default, no sync server
rep("var MAIN_LOC = 'sydney';", "var MAIN_LOC = 'gyeongju';")
rep("var SYNC_API = localStorage.getItem('nips_sync_api') || 'https://neurips2026-mcp.neurips2026-mcp.workers.dev';",
    "var SYNC_API = '';   // this site has no sync / MCP server")
rep("var POSTER_BASE = 'https://min-kang-3b.github.io/neurips2026-posters/p/';", "var POSTER_BASE = '';   // no poster images for this site")
rep("lang: params.get('lang') || localStorage.getItem('nips_lang') || 'en',", "lang: params.get('lang') || localStorage.getItem('nips_lang') || 'ko',")
rep("loc: params.get('loc') || localStorage.getItem('nips_loc') || 'sydney',", "loc: params.get('loc') || localStorage.getItem('nips_loc') || 'gyeongju',")
rep("var UTC_OFF = { sydney: 11, atlanta: -5, paris: 1 };", "var UTC_OFF = { gyeongju: 9 };")
rep("/^(search|week)$/", "/^(search|week|info)$/", 2)
# HICO floors (HICO floor guide: 300A/B/C on 3F, rooms 201-206 on 2F)
cut("  function floorOf(room) {", "  function roomWithFloor(room) {", """  function floorOf(room) {
    var r = (room || '').toLowerCase();
    if (/^300[abc]/.test(r)) return '3F';
    if (/^20\\d/.test(r)) return '2F';
    return null;
  }
""")
rep("h('h1', null, ['NeurIPS 2026']),", "h('h1', null, ['KOSMI 2026 추계']),")
cut("          h('div', { class: 'seg seg-tz', title: 'Time zone' }, [", "          h('div', { class: 'seg' }, [", "")
rep("  function renderLocTabs(withWishCount) {\n",
    "  function renderLocTabs(withWishCount) {\n"
    "    if ((SCHED.locs || []).length < 2) return h('div', { class: 'loctabs-wrap', style: 'display:none' });\n")
rep("          h('span', null, ['🌏 ' + loc(LOCS[day.loc].name)]),\n", "")
rep("renderCard(hit.e, hit.d, loc(LOCS[hit.d.loc].name) + ' · ' + loc(hit.d.label))", "renderCard(hit.e, hit.d, loc(hit.d.label))")
rep("ctx: loc(LOCS[hit.d.loc].name) + ' · ' + loc(hit.d.label) + ' · ' + loc(hit.e.title)", "ctx: loc(hit.d.label) + ' · ' + loc(hit.e.title)")
rep("return loc(LOCS[d.loc].name) + ' · ' + loc(d.label) + ' · ' + loc(e.title) +", "return loc(d.label) + ' · ' + loc(e.title) +")
rep("state.lang === 'ko' ? '발표 ' + e.nPapers + '편' : e.nPapers + ' papers'", "state.lang === 'ko' ? '발표 ' + e.nPapers + '건' : e.nPapers + ' talks'")

# ---------------------------------------------------------------- extra view: 안내
rep("      h('button', { class: state.view === 'search' ? 'on' : '', onclick: function () { if (state.view !== 'search') setView('search'); } }, [t('view_search')])",
    "      h('button', { class: state.view === 'search' ? 'on' : '', onclick: function () { if (state.view !== 'search') setView('search'); } }, [t('view_search')]),\n"
    "      h('button', { class: state.view === 'info' ? 'on' : '', onclick: function () { if (state.view !== 'info') setView('info'); } }, [t('view_info')])")
rep("    if (state.view === 'week') {\n      app.appendChild(renderLocTabs(true));",
    "    if (state.view === 'info') {\n"
    "      var im = h('main', { class: 'timeline info-view', id: 'timeline' });\n"
    "      app.appendChild(im);\n"
    "      renderInfo(im);\n"
    "      app.appendChild(renderFooter());\n"
    "      return;\n"
    "    }\n"
    "    if (state.view === 'week') {\n      app.appendChild(renderLocTabs(true));")
rep("      SYNC_API ? renderSyncBox() : null\n    ]));", "      SYNC_API ? renderSyncBox() : null,\n      renderPicksBox()\n    ]));")
rep("  function renderFooter() {", """  // ---------------- suggested route + info view (data/info.js) ----------------
  function renderPicksBox() {
    var P = (window.KOSMI_INFO || {}).picks;
    if (!P) return null;
    return h('div', { class: 'picks-box' }, [
      h('button', { class: 'now-btn', onclick: function () {
        (P.events || []).forEach(function (id) { if (EV_INDEX[id]) wish.events[id] = 1; });
        (P.papers || []).forEach(function (p) { if (!wish.papers[p.id]) wish.papers[p.id] = { s: p.s, en: p.en, pos: p.pos, time: p.time }; });
        saveWish(); render();
      } }, [t('picks_add')]),
      h('span', null, [t('picks_note')])
    ]);
  }
  function renderInfo(main) {
    var INFO = window.KOSMI_INFO || { sections: [] };
    main.appendChild(h('div', { class: 'wk-head' }, [h('h2', null, [t('info_title')]), h('p', null, [INFO.note || ''])]));
    (INFO.sections || []).forEach(function (s) {
      var det = h('details', { class: 'info-sec' });
      if (s.open) det.setAttribute('open', '');
      det.appendChild(h('summary', null, [s.title, s.src ? h('span', { class: 'info-src' }, [s.src]) : null]));
      var body = h('div', { class: 'info-body' });
      if (s.glossary) {
        var list = h('div', { class: 'gloss' });
        var draw = function (q) {
          list.innerHTML = '';
          s.glossary.filter(function (g) { return !q || (g.t + ' ' + g.a + ' ' + g.s + ' ' + g.d).toLowerCase().indexOf(q) >= 0; }).forEach(function (g) {
            list.appendChild(h('div', { class: 'gloss-item' }, [
              h('div', { class: 'gloss-t' }, [g.t, g.a ? h('span', null, [' ' + g.a]) : null, h('em', null, [g.c])]),
              h('div', { class: 'gloss-s' }, [g.s]),
              g.d ? h('div', { class: 'gloss-d' }, [g.d]) : null,
              g.g ? h('div', { class: 'gloss-g' }, ['🧬 ' + g.g]) : null
            ]));
          });
        };
        body.appendChild(h('div', { class: 'searchbox' }, [h('span', { class: 'mag' }, ['⌕']),
          h('input', { type: 'search', placeholder: t('gloss_ph'), oninput: debounce(function (ev) { draw(ev.target.value.trim().toLowerCase()); }, 150) })]));
        body.appendChild(list);
        draw('');
      } else body.appendChild(h('div', { class: 'abs info-html', html: s.html }));
      det.appendChild(body);
      main.appendChild(det);
    });
  }

  function renderFooter() {""")

# ---------------------------------------------------------------- talks ("papers")
rep("  wish.papers = wish.papers || {};\n",
    "  wish.papers = wish.papers || {};\n"
    "  // first visit: start with the attendee's own talk pinned (data/info.js `seed`)\n"
    "  if (localStorage.getItem('nips_wish') == null && window.NIPS_INFO && window.NIPS_INFO.seed) {\n"
    "    window.NIPS_INFO.seed.forEach(function (p) { wish.papers[p.id] = { s: p.s, en: p.en, pos: p.pos, time: p.time }; });\n"
    "  }\n")
rep("    var tags = [];\n    if (p.tag) {",
    "    var tags = [];\n"
    "    if (p.mine) tags.push(h('span', { class: 'ptag ptag-oral' }, ['🎤 ' + t('mine')]));\n"
    "    if (p.watch) tags.push(h('span', { class: 'ptag ptag-spot' }, ['✨ ' + t('watch')]));\n"
    "    if (p.tag) {")
rep("[(/openreview/.test(p.link) ? 'OpenReview' : 'Link') + ' ↗']", "[(/openreview/.test(p.link) ? 'OpenReview' : t('official')) + ' ↗']")
rep("if (f) ['abs', 'absKo', 'link', 'psess', 'pos', 'ins', 'rv', 'pz'].forEach(", "if (f) ['abs', 'absKo', 'link', 'psess', 'pos', 'time', 'mine', 'watch', 'ins', 'rv', 'pz'].forEach(")
rep("var hay = ((p.en || '') + ' ' + (p.ko || '') + ' ' + (p.authors || '')).toLowerCase();",
    "var hay = ((p.en || '') + ' ' + (p.ko || '') + ' ' + (p.authors || '') + ' ' + (p.inst || '') + ' ' + (p.pos || '')).toLowerCase();")

# ---------------------------------------------------------------- search tab: keyword only, filter by talk kind
rep("mode: localStorage.getItem('nips_smode') || 'kw',", "mode: 'kw',")
rep("  if (params.get('mode') === 'sem') SX.mode = 'sem';\n", "")
rep("return { t: (r[2] + ' ' + r[3]).toLowerCase(),", "return { t: (r[2] + ' ' + r[3] + ' ' + (r[9] || '')).toLowerCase(),")
rep("    if (SX.kind === 'main' && r[7]) return false;\n    if (SX.kind === 'ws' && !r[7]) return false;\n    if (SX.tagOnly && !r[6]) return false;\n",
    "    if (SX.kind !== 'all' && r[7] !== SX.kind) return false;\n")
cut("    var kindChips = [", "    var examples = ", """    var kindChips = [['sym', 'k_sym'], ['oral', 'k_oral'], ['epo', 'k_epo'], ['post', 'k_post'], ['tut', 'k_tut']].map(function (k) {
      return filterChip(t(k[1]), SX.kind === k[0], function () { SX.kind = SX.kind === k[0] ? 'all' : k[0]; });
    });
""")
cut("    var examples = ", "    var hasHangul = ", "    var examples = ['에이전트', 'FHIR', 'LLM', '유전', 'DRB', '서울대학교'];\n")
rep("view.appendChild(h('div', { class: 's-row' }, [modeSeg,", "view.appendChild(h('div', { class: 's-row' }, [")
rep("var p = { id: r[0], en: r[2], ko: r[3], authors: r[4], inst: r[5], tag: r[6] };",
    "var p = { id: r[0], en: r[2], ko: r[3], authors: r[4], inst: r[5], tag: r[6], pos: r[9], time: r[11], mine: r[10] === 1, watch: r[10] === 2 };")

# ---------------------------------------------------------------- names + storage shim (artifact viewers may block localStorage)
t = t.replace("NIPS_", "KOSMI_").replace("nips_", "kosmi_")
assert "neurips" not in t.lower().replace("neurips 2026 schedule app", ""), "leftover NeurIPS reference"
t = t.replace("localStorage.", "LS.")
rep("  'use strict';\n",
    "  'use strict';\n\n"
    "  // storage that degrades to memory when the browser refuses localStorage (private windows, embedded viewers)\n"
    "  var LS = (function () {\n"
    "    try { var s = window.localStorage; s.getItem('kosmi_probe'); return s; } catch (e) {\n"
    "      var m = {};\n"
    "      return { getItem: function (k) { return k in m ? m[k] : null; }, setItem: function (k, v) { m[k] = String(v); }, removeItem: function (k) { delete m[k]; } };\n"
    "    }\n"
    "  })();\n")

# ---------------------------------------------------------------- css
css = css.replace("/* NeurIPS 2026 Schedule — bilingual schedule site */",
                  "/* KOSMI 2026 Fall schedule — styles from the NeurIPS 2026 schedule site, plus the 안내 view (scripts/port_app.py) */")
css += """
/* ---- KOSMI additions: info view, suggested route, lists inside abstracts ---- */
.abs ul, .abs ol { margin: 0 0 9px 20px; }
.abs li { margin-bottom: 4px; }
.abs a { color: var(--accent); }
.picks-box { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 10px; font-size: 12.5px; color: var(--text3); }
.info-view { padding-bottom: 30px; }
.info-sec { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); margin-bottom: 10px; overflow: hidden; }
.info-sec > summary { cursor: pointer; padding: 14px 16px; font-weight: 800; font-size: 15px; list-style: none; display: flex; align-items: center; gap: 8px; }
.info-sec > summary::-webkit-details-marker { display: none; }
.info-sec > summary::after { content: '+'; margin-left: auto; color: var(--text3); font-weight: 400; }
.info-sec[open] > summary::after { content: '−'; }
.info-src { font-size: 11px; font-weight: 600; color: var(--text3); border: 1px solid var(--border); border-radius: 99px; padding: 1px 8px; }
.info-body { padding: 0 12px 14px; }
.info-html { border: none; padding: 2px 4px; background: transparent; }
.info-html h5 { font-size: 14px; font-weight: 800; margin: 14px 0 6px; }
.info-html h5:first-child { margin-top: 0; }
.info-html .muted { color: var(--text2); font-size: 13px; }
.info-html .tw { overflow-x: auto; margin-bottom: 9px; }
.info-html table { border-collapse: collapse; width: 100%; font-size: 13.5px; }
.info-html th, .info-html td { border-bottom: 1px solid var(--border); padding: 7px 9px; text-align: left; vertical-align: top; }
.info-html th { color: var(--text2); font-size: 12px; white-space: nowrap; }
.info-html td.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.info-html .tm { display: inline-block; background: var(--surface2); border-radius: 7px; padding: 2px 8px; margin: 0 5px 5px 0; font-weight: 700; font-variant-numeric: tabular-nums; }
.info-html .tm small { font-weight: 500; color: var(--text2); margin-left: 3px; }
.info-html .lv { display: inline-block; font-size: 11px; font-weight: 800; border-radius: 6px; padding: 1px 7px; margin-right: 4px; background: var(--c-special); color: #fff; }
.info-html .lv.alt { background: var(--surface2); color: var(--text2); }
.gloss { margin-top: 10px; }
.gloss-item { padding: 11px 4px; border-top: 1px solid var(--border); }
.gloss-t { font-weight: 800; font-size: 14.5px; }
.gloss-t span { font-weight: 500; color: var(--text2); font-size: 13px; }
.gloss-t em { font-style: normal; font-size: 11px; font-weight: 600; color: var(--text3); border: 1px solid var(--border); border-radius: 99px; padding: 0 7px; margin-left: 6px; }
.gloss-s { font-size: 14px; margin-top: 2px; }
.gloss-d { font-size: 13px; color: var(--text2); margin-top: 4px; }
.gloss-g { font-size: 13px; color: var(--text2); margin-top: 4px; }
"""

(ROOT / "assets").mkdir(exist_ok=True)
(ROOT / "assets" / "app.js").write_text(t, encoding="utf-8")
(ROOT / "assets" / "style.css").write_text(css, encoding="utf-8")
print("ported app.js", len(t), "style.css", len(css))
