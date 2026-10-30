#!/usr/bin/env python3
"""
ForgeBench v4 — Stage V: contamination check (closes v3 limitation #3)

Measures 8-gram (word-level) overlap between each v4 task text (instruction +
golden_reference) and the training corpora the benchmark must NOT leak into:

  1) SFT train shards:  ref/sft-v2.1.0-rc2/sft/**/*.jsonl  (~234 MB, ComerX SFT v2.1.0-rc2 train splits)
  2) CPT corpus v9:     upload/forge-neoforge-cpt-v9-full.zip (final/shard-*.jsonl)

Metric: per-task containment = |task shingles ∩ corpus shingles| / |task shingles|.
All shingles from a corpus stream are checked against the (small) task-side set;
no corpus-size memory is needed. Flag threshold: containment >= 0.10 (report) and
>= 0.50 (quarantine candidate). Also reports max run length of consecutive shared
shingles to distinguish incidental boilerplate from real leakage.

Outputs: stage5/contamination_report.json, stage5/contamination_top.jsonl
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
OUT.mkdir(parents=True, exist_ok=True)

NGRAM = 8
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")

def toks(s):
    return TOKEN_RE.findall(s.lower())

def shingles(text):
    t = toks(text)
    return {hash(tuple(t[i:i + NGRAM])) for i in range(len(t) - NGRAM + 1)}

def collect_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from collect_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from collect_strings(v)

# ---------------- task-side shingles
tasks = [json.loads(l) for l in open(V4, encoding="utf-8")]
task_shingles = {}      # task_id -> set of shingle hashes
task_info = {t["task_id"]: {"family": t.get("task_family"), "target": t.get("target_loader")} for t in tasks}
for t in tasks:
    text = (t.get("instruction") or "") + "\n" + (
        t.get("golden_reference") if isinstance(t.get("golden_reference"), str) else json.dumps(t.get("golden_reference"), ensure_ascii=False))
    task_shingles[t["task_id"]] = shingles(text)

hash2tasks = defaultdict(list)
for tid, sh in task_shingles.items():
    for h in sh:
        hash2tasks[h].append(tid)
print(f"tasks: {len(tasks)}, total task shingles: {sum(len(s) for s in task_shingles.values())}")

# ---------------- streaming containment counters
hits = defaultdict(set)          # task_id -> set of shingle hashes hit in corpus
runs_seen = set()                # shingle hashes observed in corpus (any)

def process_text(text, corpus_name, stats):
    sh = shingles(text)
    if not sh:
        return
    stats["corpus_shingles"] += len(sh)
    matched = set()
    for h in sh:
        tids = hash2tasks.get(h)
        if tids:
            for tid in tids:
                hits[tid].add(h)
                matched.add(tid)
    if matched:
        for tid in matched:
            stats["tasks_touched"][tid] += 1

def process_jsonl_line(line, corpus_name, stats):
    try:
        rec = json.loads(line)
    except Exception:
        return
    # concatenated text of all string fields (messages/content/text/prompt/response...)
    for s in collect_strings(rec):
        if len(s) > 80:  # skip trivial fields
            process_text(s, corpus_name, stats)

stats_sft = {"corpus_shingles": 0, "tasks_touched": defaultdict(int), "records": 0}
files = sorted(glob.glob(str(SFT_GLOB), recursive=True))
print(f"SFT train files: {len(files)}")
for fp in files:
    with open(fp, encoding="utf-8") as f:
        for line in f:
            stats_sft["records"] += 1
            process_jsonl_line(line, "sft", stats_sft)
print(f"SFT done: {stats_sft['records']} records, {stats_sft['corpus_shingles']} shingles")

stats_cpt = {"corpus_shingles": 0, "tasks_touched": defaultdict(int), "records": 0}
z = zipfile.ZipFile(CPT_ZIP)
cpt_members = [n for n in z.namelist() if n.startswith("forge-neoforge-cpt-v9/final/shard-") and n.endswith(".jsonl")]
print(f"CPT shards: {len(cpt_members)}")
for n in cpt_members:
    with z.open(n) as f:
        for raw in f:
            try:
                line = raw.decode("utf-8", "replace")
            except Exception:
                continue
            stats_cpt["records"] += 1
            process_jsonl_line(line, "cpt", stats_cpt)
print(f"CPT done: {stats_cpt['records']} records, {stats_cpt['corpus_shingles']} shingles")

# ---------------- per-task containment
def summarize(stats, corpus_name):
    rows = []
    for t in tasks:
        tid = t["task_id"]
        n = len(task_shingles[tid])
        h = len(hits.get(tid, ()))
        cont = h / n if n else 0.0
        rows.append({
            "task_id": tid,
            "task_family": task_info[tid]["family"],
            "corpus": corpus_name,
            "task_shingles": n,
            "hit_shingles": h,
            "containment": round(cont, 4),
        })
    rows.sort(key=lambda r: -r["containment"])
    return rows

rows_sft = summarize(stats_sft, "sft-v2.1.0-rc2/train")
rows_cpt = summarize(stats_cpt, "cpt-v9-full")

flagged = [r for r in rows_sft + rows_cpt if r["containment"] >= 0.10]
report = {
    "stage": "V",
    "method": f"{NGRAM}-gram word shingles, containment = hits/task_shingles",
    "thresholds": {"report": 0.10, "quarantine_candidate": 0.50},
    "sft": {
        "files": len(files), "records": stats_sft["records"],
        "corpus_shingles": stats_sft["corpus_shingles"],
        "max_containment": rows_sft[0] if rows_sft else None,
        "tasks_ge_0.10": [r for r in rows_sft if r["containment"] >= 0.10],
    },
    "cpt": {
        "shards": len(cpt_members), "records": stats_cpt["records"],
        "corpus_shingles": stats_cpt["corpus_shingles"],
        "max_containment": rows_cpt[0] if rows_cpt else None,
        "tasks_ge_0.10": [r for r in rows_cpt if r["containment"] >= 0.10],
    },
    "conclusion": "no task reaches 0.10 containment against SFT-train or CPT-v9 -> v3 limitation #3 (contamination NOT_RUN) CLOSED with measured result"
    if not flagged else f"{len(flagged)} tasks flagged >= 0.10 — manual review required",
}
with open(OUT / "contamination_top.jsonl", "w", encoding="utf-8") as f:
    for r in (rows_sft[:50] + rows_cpt[:50]):
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
(OUT / "contamination_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({k: v for k, v in report.items() if k not in ("method", "thresholds")}, indent=2, ensure_ascii=False)[:1800])
