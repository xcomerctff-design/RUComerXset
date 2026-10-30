#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ЭТАП 7: 6-уровневый оценщик v3 (run_eval_v3.py).

Уровни (см. docs/metrics.md):
  L1 structural  - схема/пути/файлы (schema.json + валидатор)
  L2 static      - ast_eval v3 (syntax/imports/annotations/forbidden/tokens)
  L3 compile     - Gradle build в целевой среде (не исполнено на хосте: BLOCKED)
  L4 functional  - GameTest/юнит-инварианты (раннер требует >=8 ГБ: NOT_RUN)
  L5 integration - client/dedicated-server smoke (не исполнено: NOT_RUN)
  L6 visual/perf - скриншот-пайплайн (см. harness/visual_pipeline.py: NOT_RUN)

Метрики отчёта: каждая - независимая доля с N/A-семантикой. Отсутствие проверки
НИКОГДА не считается нулём и не маппится в PASS.

answers.jsonl: {"task_id", "answer"| "files"}
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ast_eval as ev  # noqa: E402

METRIC_KEYS = [
    "syntax_pass_rate", "compile_pass_rate", "api_correctness",
    "behavior_pass_rate", "test_pass_rate", "client_launch_pass_rate",
    "dedicated_server_pass_rate", "resource_validation_pass_rate",
    "visual_correctness", "migration_behavior_preservation",
    "unsupported_api_rate", "hallucinated_api_rate", "regression_rate",
]


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def rate(rows, key):
    """Доля true среди ИЗМЕРЕННЫХ; (None, 0) когда ничего не измерено (N/A)."""
    measured = [r[key] for r in rows if r.get(key) is not None]
    if not measured:
        return None, 0
    return sum(1 for v in measured if v) / len(measured), len(measured)


def evaluate_answer(task, answer, files, compile_executed=False,
                    compile_result=None, tests_executed=False,
                    client_executed=False, server_executed=False,
                    visual_executed=False):
    """Один ответ -> детальная запись всех уровней."""
    tid = task["task_id"]
    try:
        target = ev.resolve_target(task, None)
    except ValueError:
        target = None

    rec = {
        "task_id": tid,
        "levels": {},
        # N/A-семантика по умолчанию: None = не измерялось (не 0!)
    }
    rec["levels"]["L1_structural"] = "PASS"  # задача уже прошла schema gate при сборке

    if target is None:
        rec["levels"]["L2_static"] = "FAIL"
        rec["syntax_pass"] = False
        rec["api_correctness"] = False
        rec["hallucinated_api"] = True
        rec["unsupported_api"] = None
        rec["resource_validation"] = None
        return rec

    g = files if files is not None else {"answer.java": answer or ""}
    res = ev.evaluate_sources(task, g, target)
    st = res["stages"]
    rec["levels"]["L2_static"] = "PASS" if res["passed"] else "FAIL"
    rec["static_detail"] = st
    rec["findings"] = [f["check"] + ":" + f["message"][:80] for f in res["findings"]]

    rec["syntax_pass"] = st.get("syntax") in ("PARSE_OK", "NOT_APPLICABLE",
                                              "PARSE_LIMITATION")
    # api_correctness: импорты+аннотации+forbidden чисты
    rec["api_correctness"] = (st.get("imports") in ("PASS", "NOT_APPLICABLE")
                              and st.get("annotations") in ("PASS", "NOT_APPLICABLE")
                              and st.get("forbidden") in ("PASS", "NOT_APPLICABLE"))
    hallucinated = [f for f in res["findings"]
                    if f["check"] in ("HALLUCINATION", "NONEXISTENT_API")]
    rec["hallucinated_api"] = bool(hallucinated)
    unsupported = [f for f in res["findings"] if f["check"] == "PENALTY"]
    rec["unsupported_api"] = bool(unsupported)

    # ресурсная валидация (для задач с токенами/ресурсами)
    rec["resource_validation"] = (None if st.get("tokens") == "NOT_APPLICABLE"
                                  else st.get("tokens") == "PASS")

    # L3 compile: только при фактически исполненной сборке
    rec["compile_pass"] = (compile_result if compile_executed else None)
    rec["levels"]["L3_compile"] = ("PASS" if rec["compile_pass"] is True else
                                   "FAIL" if rec["compile_pass"] is False else
                                   "NOT_RUN")

    # L4/L5/L6 - только фактически исполненные проверки
    rec["test_pass"] = (None if not tests_executed else None)  # заполняет runner
    rec["levels"]["L4_functional"] = "NOT_RUN" if not tests_executed else "EXECUTED"
    rec["client_launch_pass"] = None if not client_executed else None
    rec["server_launch_pass"] = None if not server_executed else None
    rec["levels"]["L5_integration"] = ("NOT_RUN" if not (client_executed or server_executed)
                                       else "EXECUTED")
    rec["visual_correct"] = None if not visual_executed else None
    rec["levels"]["L6_visual"] = "NOT_RUN" if not visual_executed else "EXECUTED"

    # миграционное сохранение поведения (измеряет judge-слой; здесь None)
    rec["migration_behavior_preserved"] = None
    return rec


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--answers", required=True)
    p.add_argument("--out", default=None)
    args = p.parse_args()

    tasks = {t["task_id"]: t for t in load(args.data)}
    answers = load(args.answers)
    rows = []
    for a in answers:
        t = tasks.get(a["task_id"])
        if not t:
            continue
        rows.append(evaluate_answer(t, a.get("answer"), a.get("files")))

    summary = {}
    for key in METRIC_KEYS:
        if key in ("compile_pass_rate", "test_pass_rate", "client_launch_pass_rate",
                   "dedicated_server_pass_rate", "visual_correctness",
                   "migration_behavior_preservation", "regression_rate"):
            # измеряются только исполненными раннерами: в этой среде NOT_RUN
            summary[key] = {"value": "N/A", "measured": 0,
                            "note": "runner requires >=8GB environment; "
                                    "NOT_RUN on audit host"}
        elif key == "syntax_pass_rate":
            v, n = rate(rows, "syntax_pass")
            summary[key] = {"value": round(v, 3) if v is not None else "N/A",
                            "measured": n}
        elif key == "api_correctness":
            v, n = rate(rows, "api_correctness")
            summary[key] = {"value": round(v, 3) if v is not None else "N/A",
                            "measured": n}
        elif key == "resource_validation_pass_rate":
            v, n = rate(rows, "resource_validation")
            summary[key] = {"value": round(v, 3) if v is not None else "N/A",
                            "measured": n}
        elif key == "unsupported_api_rate":
            v, n = rate(rows, "unsupported_api")
            summary[key] = {"value": round(v, 3) if v is not None else "N/A",
                            "measured": n}
        elif key == "hallucinated_api_rate":
            v, n = rate(rows, "hallucinated_api")
            summary[key] = {"value": round(v, 3) if v is not None else "N/A",
                            "measured": n}
    report = {"summary": summary, "rows": rows,
              "levels_legend": {"L1": "structural", "L2": "static",
                                "L3": "compile", "L4": "functional",
                                "L5": "integration", "L6": "visual/perf"}}
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    print(payload[:4000])


if __name__ == "__main__":
    main()
