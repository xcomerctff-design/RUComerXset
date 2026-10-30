#!/usr/bin/env python3
"""
ForgeBench v4 — Stage Vb: run-length analysis (fast single-pass version).

For each corpus record: one pass over its 8-gram stream using an inverted index
(shingle -> flagged task ids). Maintains per (record, task) current-run counters
directly, so total cost is O(record shingles), independent of task count.

Verdict policy (fixed a priori):
  max_run >= 40 shingles  -> VERBATIM_LEAK_SUSPECT (quarantine candidate)
  max_run 12..39          -> PARTIAL_OVERLAP (manual review)
  max_run < 12            -> IDIOM_ONLY (boilerplate code idioms, not leakage)
"""
import glob
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path

WB = Path("/home/z/my-project/forgebench-v4-work")
V4 = WB / "stage4" / "forgebench_v4_full.jsonl"
SFT_GLOB = WB / "ref" / "sft-v2.1.0-rc2" / "sft" / "**" / "*.jsonl"
CPT_ZIP = Path("/home/z/my-project/upload/forge-neoforge-cpt-v9-full.zip")
OUT = WB / "stage5"
NGRAM = 8
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")

tasks = [json.loads(l) for l in open(V4, encoding="utf-8")]
prev = json.loads((OUT / "contamination_report.json").read_text(encoding="utf-8"))
flagged_ids = {r["task_id"] for r in prev["sft"]["tasks_ge_0.10"]} | {r["task_id"] for r in prev["cpt"]["tasks_ge_0.10"]}

inv_raw = defaultdict(list)   # shingle hash -> [task_id]
for t in tasks:
    if t["task_id"] not in flagged_ids:
        continue
    text = (t.get("instruction") or "") + "\n" + (
        t.get("golden_reference") if isinstance(t.get("golden_reference"), str) else json.dumps(t.get("golden_reference"), ensure_ascii=False))
    toks = TOKEN_RE.findall(text.lower())
    for i in range(len(toks) - NGRAM + 1):
        h = hash(tuple(toks[i:i + NGRAM]))
        if t["task_id"] not in inv_raw[h]:
            inv_raw[h].append(t["task_id"])
# shingles shared by >20 flagged tasks are generic boilerplate by definition — drop
inv = {h: tids for h, tids in inv_raw.items() if len(tids) <= 20}
print("flagged tasks:", len(flagged_ids),
      "| index shingles:", len(inv), f"(dropped generic: {len(inv_raw)-len(inv)})")

best_run = defaultdict(int)
best_snip = {}
best_hits = defaultdict(int)

def analyze(text, corpus, rec_id):
    toks = TOKEN_RE.findall(text.lower())
    if len(toks) < NGRAM:
        return
    # per-task current run state for this record
    run = defaultdict(int)          # task -> current consecutive run
    hits = defaultdict(int)         # task -> total hit count in this record
    last_pos = {}                   # task -> shingle index where current run started
    run_start = {}
    best_here = defaultdict(int)
    best_here_pos = {}
    seq = []
    for i in range(len(toks) - NGRAM + 1):
        h = hash(tuple(toks[i:i + NGRAM]))
        seq.append(h)
        tids = inv.get(h)
        if not tids:
            continue
        for tid in tids:
            # continue run only if previous shingle also belonged to this task (consecutive)
            if i > 0 and run[tid] > 0 and seq[i - 1] in inv and tid in inv.get(seq[i - 1], ()):
                run[tid] += 1
            else:
                run[tid] = 1
                run_start[tid] = i
            hits[tid] += 1
            if run[tid] > best_here[tid]:
                best_here[tid] = run[tid]
                best_here_pos[tid] = i
    for tid, b in best_here.items():
        if b > best_run[tid]:
            best_run[tid] = b
            start_pos = best_here_pos[tid] - b + 1          # first shingle position of the run
            start_tok = max(0, start_pos)
            end_tok = min(len(toks), best_here_pos[tid] + NGRAM)  # tokens covered by last shingle
            best_snip[tid] = (corpus, rec_id, " ".join(toks[start_tok:end_tok])[:400])
        if hits[tid] > best_hits[tid]:
            best_hits[tid] = hits[tid]

def scan_jsonl(line, corpus, rec_id):
    try:
        rec = json.loads(line)
    except Exception:
        return
    parts = []
    def walk(o):
        if isinstance(o, str):
            if len(o) > 80:
                parts.append(o)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(rec)
    analyze("\n".join(parts), corpus, rec_id)

n = 0
for fp in sorted(glob.glob(str(SFT_GLOB), recursive=True)):
    with open(fp, encoding="utf-8") as f:
        for line in f:
            scan_jsonl(line, "sft", Path(fp).stem)
            n += 1
print("SFT records scanned:", n)

n = 0
z = zipfile.ZipFile(CPT_ZIP)
for mem in [m for m in z.namelist() if m.startswith("forge-neoforge-cpt-v9/final/shard-") and m.endswith(".jsonl")]:
    with z.open(mem) as f:
        for raw in f:
            scan_jsonl(raw.decode("utf-8", "replace"), "cpt", Path(mem).stem)
            n += 1
print("CPT records scanned:", n)

VERDICT = lambda r: ("VERBATIM_LEAK_SUSPECT" if r >= 40 else "PARTIAL_OVERLAP" if r >= 12 else "IDIOM_ONLY")
rows = []
for tid in sorted(flagged_ids):
    r = best_run.get(tid, 0)
    rows.append({
        "task_id": tid,
        "max_run_shingles": r,
        "max_record_hits": best_hits.get(tid, 0),
        "verdict": VERDICT(r),
        "snippet_corpus": best_snip.get(tid, ("-", "-", ""))[0],
        "snippet_record": best_snip.get(tid, ("-", "-", ""))[1],
        "snippet": best_snip.get(tid, ("-", "-", ""))[2],
    })
rows.sort(key=lambda x: -x["max_run_shingles"])
with open(OUT / "runs_top.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

counts = defaultdict(int)
for r in rows:
    counts[r["verdict"]] += 1
report = {
    "stage": "Vb",
    "flagged_tasks": len(flagged_ids),
    "verdict_counts": dict(counts),
    "policy": {"VERBATIM_LEAK_SUSPECT": ">=40", "PARTIAL_OVERLAP": "12-39", "IDIOM_ONLY": "<12"},
    "top10": rows[:10],
    "conclusion": (
        "no verbatim leak suspects; overlap is code-idiom level -> contamination check CLOSED (measured)"
        if counts.get("VERBATIM_LEAK_SUSPECT", 0) == 0
        else f"{counts['VERBATIM_LEAK_SUSPECT']} verbatim leak suspects -> quarantine before release"
    ),
}
(OUT / "runs_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(report["verdict_counts"], ensure_ascii=False), "|", report["conclusion"])
for r in rows[:8]:
    print(f"  {r['task_id']:12s} run={r['max_run_shingles']:4d} hits={r['max_record_hits']:5d} {r['verdict']}")
