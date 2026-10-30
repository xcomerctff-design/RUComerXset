#!/usr/bin/env python3
"""
ForgeBench v4 — Stage XI: assemble the public bundle + private bundle, SHA256SUMS, zip.

Public bundle  -> stage11/bundle/forgebench-v4/           (assembled here)
Private bundle -> stage11/private-bundle/forgebench-v4-private/
Zip            -> /home/z/my-project/download/forgebench-v4.0.0.zip
                  /home/z/my-project/download/forgebench-v4-private.0.0.zip
"""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

WB = Path("/home/z/my-project/forgebench-v4-work")
SNAP = WB / "snapshot-v3"
B = WB / "stage11" / "bundle" / "forgebench-v4"
PB = WB / "stage11" / "private-bundle" / "forgebench-v4-private"
DL = Path("/home/z/my-project/download")

# ---- data
(B / "data").mkdir(parents=True, exist_ok=True)
shutil.copy(WB / "stage9" / "forgebench_v4_full.jsonl", B / "data" / "forgebench_v4_full.jsonl")
for f in ["baseline_v2.jsonl", "baseline_v2_fixed.jsonl", "public_dev.jsonl", "public_eval.jsonl"]:
    shutil.copy(SNAP / "data" / f, B / "data" / f)
shutil.copy(WB / "stage9" / "schema-v4.json", B / "data" / "schema.json")
shutil.copy(WB / "stage10" / "split_manifest_v4.json", B / "data" / "split_manifest.json")
for f in (SNAP / "data" / "parts").glob("*.jsonl"):
    shutil.copy(f, B / "data" / "parts" / f.name)
shutil.copy(WB / "stage6" / "gametest_tasks.jsonl", B / "data" / "parts" / "group_gt_gametest.jsonl")

# ---- harness + tests (unchanged from v3)
if (B / "harness").exists():
    shutil.rmtree(B / "harness")
shutil.copytree(SNAP / "harness", B / "harness")
shutil.copy(SNAP / "tests" / "test_evaluator_rules.py", B / "tests" / "test_evaluator_rules.py")

# ---- evidence
EV = B / "evidence"
EV.mkdir(exist_ok=True)
for f in ["api_evidence.csv", "api_evidence_summary.json", "d1_confirmed_tasks.json",
          "confirmed_defects_stage3.jsonl", "STAGE3_REPORT.md"]:
    shutil.copy(WB / "stage3" / f, EV / f)
shutil.copy(WB / "stage3" / "api_evidence.csv", EV / "api_evidence_v3_scan.csv")
shutil.copy(WB / "stage4" / "fix_log.jsonl", EV / "fix_log.jsonl")
shutil.copy(WB / "stage4" / "d5_check.json", EV / "d5_check.json")
for f in ["contamination_report.json", "runs_report.json", "runs_top.jsonl"]:
    shutil.copy(WB / "stage5" / f, EV / f)
shutil.copy(WB / "stage9" / "schema_validation.json", EV / "schema_validation.json")
shutil.copy(WB / "stage9" / "eval_selfcheck_report.json", EV / "eval_selfcheck_report.json")
shutil.copy(WB / "stage10" / "api_evidence.csv", EV / "api_evidence_final.csv")
shutil.copy(WB / "stage10" / "api_evidence_summary.json", EV / "api_evidence_final_summary.json")

# ---- docs: copy modern_profile from v3
shutil.copy(SNAP / "docs" / "modern_profile.md", B / "docs" / "modern_profile.md")

# ---- scripts
for f in sorted((WB / "scripts").glob("stage*.py")):
    shutil.copy(f, B / "scripts" / f.name)

# ---- SHA256SUMS (data + top-level docs + evidence)
lines = []
def add(p: Path, base: Path):
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    lines.append(f"{h}  {p.relative_to(base)}")

for p in sorted(B.rglob("*")):
    if p.is_file() and p.suffix in {".jsonl", ".json", ".csv", ".md"} and "evidence" not in p.parts:
        add(p, B)
for p in sorted((B / "evidence").glob("*")):
    if p.is_file():
        add(p, B)
(B / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

# ---- private bundle
PB.mkdir(parents=True, exist_ok=True)
shutil.copy(SNAP / "data" / "private_eval.jsonl", PB / "private_eval.jsonl")
(PB / "README.md").write_text(
    "# ForgeBench v4 — private held-out eval\n\n"
    "Приватный held-out сплит (82 задачи) бенчмарка ForgeBench v4.\n"
    "Публичная часть: https://huggingface.co/datasets/ComerX/forgebench-v4\n\n"
    "- НЕ публиковать. Используется только для лидерборда владельцем.\n"
    "- Задачи идентичны по схеме публичному пулу (schema.json в публичном репо).\n"
    "- Суммы: SHA256SUMS.txt рядом.\n", encoding="utf-8")
pl = []
h = hashlib.sha256((PB / "private_eval.jsonl").read_bytes()).hexdigest()
pl.append(f"{h}  private_eval.jsonl")
(PB / "SHA256SUMS.txt").write_text("\n".join(pl) + "\n", encoding="utf-8")

# ---- zips
DL.mkdir(exist_ok=True)
pub_zip = DL / "forgebench-v4.0.0.zip"
with zipfile.ZipFile(pub_zip, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(B.rglob("*")):
        if p.is_file():
            z.write(p, p.relative_to(B.parent))
priv_zip = DL / "forgebench-v4-private.0.0.zip"
with zipfile.ZipFile(priv_zip, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(PB.rglob("*")):
        if p.is_file():
            z.write(p, p.relative_to(PB.parent))

print("public bundle files:", sum(1 for p in B.rglob('*') if p.is_file()))
print("private bundle files:", sum(1 for p in PB.rglob('*') if p.is_file()))
print("zips:", pub_zip, f"({pub_zip.stat().st_size/1e6:.1f} MB)", "|", priv_zip, f"({priv_zip.stat().st_size/1e6:.1f} MB)")
