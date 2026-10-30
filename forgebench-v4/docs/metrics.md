# ForgeBench v4 — метрики (честная семантика)

Полные машинные данные: `evidence/api_evidence_final_summary.json`,
`evidence/eval_selfcheck_report.json`, `split_manifest.json` (в корне data/).

## Измерено (исполнено на этом хосте, 4 ГБ cgroup, JDK 21.0.13)

| Метрика | Значение | Метод |
|---|---|---|
| schema_pass_rate | 1.0 (411/411) | jsonschema, схема v4 |
| syntax_pass_rate | 1.0 (411/411) | javac-21 parse-only + ast_eval |
| api_correctness (static) | 0.998 | L2: imports+annotations+forbidden |
| hallucinated_api_rate | 0.0 | L2 findings (HALLUCINATION/NONEXISTENT_API) |
| evaluator_self_check | 411/411 | эталоны как ответы, run_eval_v3 |
| rule_tests | 32/32 | tests/test_evaluator_rules.py |
| api_evidence (класс-уровень) | 0 missing / 344 символа | pinned-инвентари (см. STAGE3_REPORT) |
| contamination (verbatim) | 0 утечек | 8-граммы + run-length (stage5/5b) |
| exact_golden_duplicates | 0 | sha256 нормализованных эталонов |

## НЕ измерено (N/A — не ноль!)

| Метрика | Причина |
|---|---|
| compile_pass_rate | BLOCKED: NeoForm >=8 ГБ (хост 4 ГБ), нет Docker |
| test_pass_rate | NOT_RUN (L4) |
| gametest_pass_rate | NOT_RUN: задачи добавлены в v4, исполнение требует хоста >=8 ГБ |
| client_launch_pass_rate | NOT_RUN (L5) |
| dedicated_server_pass_rate | NOT_RUN (L5) |
| visual_correctness | NOT_RUN (L6, >=16 ГБ, GL 3.2+) |
| migration_behavior_preservation | NOT_RUN |

Правило v3 сохраняется: N/A не заменяется нулём и не переименовывается в PASS.
