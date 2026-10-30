#!/usr/bin/env python3
"""
ForgeBench v4 — Stage IX: pool merge + schema validation + evaluator self-check

- Merges stage4/forgebench_v4_full.jsonl (401 fixed) + stage6/gametest_tasks.jsonl (10 new)
  into stage9/forgebench_v4_full.jsonl (411 tasks).
- Validates EVERY task against snapshot-v3/data/schema.json (jsonschema draft used by v3).
- API-evidence re-verification over the merged pool (imports the stage3 classifier logic by
  re-running scripts/stage3_api_evidence.py with --data/--out pointing here; done separately).
- Evaluator self-check: feed goldens as answers to harness/run_eval_v3.py (v3 pattern,
  split_manifest.evaluator_self_check_pass) — executed by the caller via CLI.

Output: stage9/forgebench_v4_full.jsonl, stage9/schema_validation.json, stage9/answers_selfcheck.jsonl
"""
import json
import sys
from pathlib import Path

WB = Path("/home/z/my-project/forgebench-v4-work")
sys.path.insert(0, str(WB / "snapshot-v3" / "harness"))
OUT = WB / "stage9"
OUT.mkdir(parents=True, exist_ok=True)

fixed = [json.loads(l) for l in open(WB / "stage4" / "forgebench_v4_full.jsonl", encoding="utf-8")]
gt = [json.loads(l) for l in open(WB / "stage6" / "gametest_tasks.jsonl", encoding="utf-8")]

ids = [t["task_id"] for t in fixed + gt]
assert len(ids) == len(set(ids)), "duplicate task ids!"
pool = fixed + gt

with open(OUT / "forgebench_v4_full.jsonl", "w", encoding="utf-8") as f:
    for t in pool:
        f.write(json.dumps(t, ensure_ascii=False) + "\n")

# ---- schema validation (v4 schema = v3 schema + 'gametest' module enum entry)
import jsonschema  # noqa: E402
schema = json.load(open(WB / "snapshot-v3" / "data" / "schema.json", encoding="utf-8"))
mod_enum = schema.get("properties", {}).get("module", {}).get("enum")
if mod_enum and "gametest" not in mod_enum:
    mod_enum.append("gametest")
v4_schema_path = OUT / "schema-v4.json"
v4_schema_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
errors = []
validator = jsonschema.Draft7Validator(schema) if schema.get("$schema", "").endswith("draft-07") else jsonschema.validate
for t in pool:
    try:
        jsonschema.validate(instance=t, schema=schema)
    except jsonschema.ValidationError as e:
        errors.append({"task_id": t.get("task_id"), "path": list(e.absolute_path)[:4], "msg": e.message[:160]})
    except Exception as e:  # older jsonschema API
        errors.append({"task_id": t.get("task_id"), "msg": str(e)[:160]})

(OUT / "schema_validation.json").write_text(json.dumps({
    "tasks": len(pool),
    "schema": "stage9/schema-v4.json (v3 + gametest module)",
    "errors": errors,
    "ok": not errors,
}, indent=2, ensure_ascii=False), encoding="utf-8")

# ---- answers file for evaluator self-check (goldens as candidate answers)
# runner contract: string golden -> "answer"; dict golden -> "files": {path: content}
with open(OUT / "answers_selfcheck.jsonl", "w", encoding="utf-8") as f:
    for t in pool:
        g = t["golden_reference"]
        if isinstance(g, dict):
            f.write(json.dumps({"task_id": t["task_id"], "files": g}, ensure_ascii=False) + "\n")
        else:
            f.write(json.dumps({"task_id": t["task_id"], "answer": g}, ensure_ascii=False) + "\n")

import collections
print("pool:", len(pool))
print("families added:", dict(collections.Counter(t["task_family"] for t in gt)))
print("schema errors:", len(errors))
for e in errors[:5]:
    print("  ", e)
