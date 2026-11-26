#!/usr/bin/env python3
"""Short Korean summaries of the abstract-book segments via codex exec (parallel, resume-safe).

Same approach as ../neurips2026/scripts/summarize_codex.py.

Input : work/abstracts.json            {id: {"page", "text"}}   (scripts/parse_abstracts.py)
Output: work/abstract_summaries.json   {id: {"sum", "rel", "why"}}

The site only ever shows these summaries, never the abstract text itself.

    python3 scripts/summarize_abstracts.py [limit]
Env: SUM_WORKERS (6), SUM_MODEL (gpt-6-luna), SUM_BATCH (8).
"""
import json, os, pathlib, re, subprocess, sys, tempfile, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = json.loads((ROOT / "work" / "abstracts.json").read_text(encoding="utf-8"))
K = json.loads((ROOT / "work" / "kosmi.json").read_text(encoding="utf-8"))
TITLE = {it["id"]: it["title"] for it in K["items"]}
OUT = ROOT / "work" / "abstract_summaries.json"
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else None
WORKERS = int(os.environ.get("SUM_WORKERS", "6"))
MODEL = os.environ.get("SUM_MODEL", "gpt-6-luna")
BATCH = int(os.environ.get("SUM_BATCH", "8"))

PROMPT = (
    "You get abstracts from a Korean medical-informatics conference (KOSMI 2026 Fall), keyed by id. "
    "For each id return an object:\n"
    '{"sum": Korean summary in your own words, at most 2 sentences and 170 characters: what was done and the main finding '
    "(keep 1-2 key numbers if the abstract reports them). Do NOT copy sentences or long phrases from the abstract; paraphrase. "
    "Do not add anything that is not in the abstract. If the text is only a talk outline, say what the talk will cover.\n"
    '"rel": integer 0-3, relevance to the REFERENCE STUDY below. '
    "3 = method directly overlaps (AI agent or multi-agent system that searches/verifies literature or evidence, generates or "
    "tests research hypotheses, literature-based discovery, citation/evidence grounding and verification, human-supervised research agents). "
    "2 = adjacent (LLM information extraction, retrieval/RAG, knowledge graphs, agent evaluation or benchmarks, LLM hallucination/grounding; "
    "OR genomics, genetic variants, rare disease, pharmacogenomics, genomic data resources or genomic test workflows). "
    "1 = weak (general clinical AI or health-data infrastructure). 0 = unrelated.\n"
    '"why": if rel >= 2, one short Korean sentence naming the concrete point of contact with the reference study; otherwise "".}\n'
    "REFERENCE STUDY: MODIFINDER, an AI agent that builds genetic-modifier hypotheses. It searches PubMed abstracts and full texts "
    "iteratively according to the current evidence state, links independent literature evidence along query gene A - intermediate concept B - "
    "candidate gene C, stores each relation with direction, biological context, PMID and a quote verified against the source text, separates "
    "direct A-C relations from literature-based hypotheses, and hands hypothesis cards to expert review. Built at a rare-disease genomic diagnostics company.\n"
    "Keep method/model/dataset names and acronyms in English. "
    "Return ONLY a valid JSON object mapping each id to its object. No markdown fences, no commentary."
)

done = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
todo = sorted(k for k in SRC if k not in done)
if LIMIT: todo = todo[:LIMIT]
batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
print("%d total, %d done, %d todo in %d batches (model %s)" % (len(SRC), len(done), len(todo), len(batches), MODEL), flush=True)
lock = threading.Lock()

def valid(o):
    return (isinstance(o, dict) and isinstance(o.get("sum"), str) and re.search(r"[가-힣]", o["sum"])
            and len(o["sum"]) <= 260 and o.get("rel") in (0, 1, 2, 3) and isinstance(o.get("why", ""), str))

def run(ids, tries=3):
    payload = {k: {"title": TITLE.get(k, ""), "abstract": SRC[k]["text"][:4500]} for k in ids}
    prompt = PROMPT + "\n\n" + json.dumps(payload, ensure_ascii=False)
    for attempt in range(tries):
        fd, outpath = tempfile.mkstemp(suffix=".txt"); os.close(fd)
        try:
            cmd = ["codex", "exec", "-m", MODEL, "-s", "read-only", "--skip-git-repo-check",
                   "-c", 'model_reasoning_effort="low"', "-o", outpath, "-"]
            subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=1200, cwd=tempfile.gettempdir())
            raw = re.sub(r"^```(json)?|```$", "", open(outpath, encoding="utf-8").read().strip(), flags=re.M).strip()
            m = re.search(r"\{.*\}", raw, re.S)
            res = json.loads(m.group(0)) if m else {}
            ok = {k: {"sum": res[k]["sum"].strip(), "rel": res[k]["rel"], "why": (res[k].get("why") or "").strip()}
                  for k in ids if valid(res.get(k))}
            if len(ok) < len(ids) * 0.7 and attempt < tries - 1:
                raise ValueError("%d/%d valid" % (len(ok), len(ids)))
            return ok
        except Exception as e:
            if attempt == tries - 1: print("BATCH FAIL", ids[:2], e, flush=True)
        finally:
            try: os.unlink(outpath)
            except OSError: pass
    return {}

n = 0
with ThreadPoolExecutor(WORKERS) as ex:
    for f in as_completed([ex.submit(run, b) for b in batches]):
        with lock:
            done.update(f.result()); n += 1
            OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
            print("batch %d/%d total %d/%d" % (n, len(batches), len(done), len(SRC)), flush=True)
print("FINISHED", len(done), "/", len(SRC), flush=True)
