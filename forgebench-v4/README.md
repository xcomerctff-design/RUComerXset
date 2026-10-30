---
license: cc0-1.0
task_categories:
- text-generation
language:
- en
tags:
- code
- minecraft
- forge
- neoforge
- benchmark
- loader-migration
- gui
- rendering
- gametest
- api-evidence
size_categories:
- 100K<n<1M
pretty_name: ForgeBench v4 (evidence-gated dual-target benchmark, 411 tasks)
configs:
- config_name: forgebench_v4_full
  data_files:
  - split: train
    path: data/forgebench_v4_full.jsonl
- config_name: public_dev
  data_files:
  - split: train
    path: data/public_dev.jsonl
- config_name: public_eval
  data_files:
  - split: train
    path: data/public_eval.jsonl
---
# ForgeBench v4 — evidence-gated dual-target Minecraft modding benchmark

**Dataset**: `ComerX/forgebench-v4` · **Predecessors**: `forgebench-v1`, `forgebench-v2`,
`forgebench-v3` (все сохранены неизменными). Held-out `private_eval` публикуется только
в приватном репозитории `ComerX/forgebench-v4-private`.

## Что это

411 задач для оценки реальной способности LLM разрабатывать, чинить, проверять и
переносить Minecraft-моды: 401 задача v3 (13 эталонов которой исправлены в v4 по
машинным доказательствам) + 10 новых GameTest-задач (NeoForge 1.21.1 / Forge 1.20.1).

Главное отличие v4 — **API-evidence гейт**: каждый API-символ каждого эталона проверен
машиной по pinned-артефактам целевых платформ (1530 строк evidence:
`evidence/api_evidence.csv`). Класс-уровень: 0 отсутствующих символов.

## Честный статус верификации

| Проверка | Статус |
|---|---|
| Схема v4 (v3 + модуль gametest) | PASS 411/411 |
| javac-21 parse-only синтаксис эталонов (Temurin 21.0.13) | PASS 411/411 |
| v3-evaluator self-check эталонов | PASS 411/411 (L2_static PASS, hallucinated_api=0) |
| Тесты правил оценщика | 32/32 |
| API-evidence (класс-уровень, 344 символа) | PASS: 0 class_missing / 0 vanilla_missing |
| Контаминация vs SFT-v2.1.0-rc2-train + CPT-v9 | ИЗМЕРЕНО: 0 дословных утечек (max run 39 шинглов = import-идиома) |
| Gradle-компиляция эталонов | **BLOCKED** (хост 4 ГБ; NeoForm >=8 ГБ) |
| GameTest / client / server smoke / visual исполнение | **NOT_RUN** (раннеры приложены; GT-задачи добавлены) |

Ни одна задача не помечена compile_verified. verification_status всех задач =
syntax_verified. Метрики L3-L6 = N/A, не ноль.

## Что изменилось против v3 (все правки с доказательствами)

- **13 эталонов исправлено** (stage IV; `evidence/fix_log.jsonl`): неверные пути классов
  (MIXIN_007, MIG_008, PORT_004, FORGE_API_009/012/013, GUI_010/015), удалённые API
  (FORGE_API_008 CapabilityInject -> CapabilityManager/CapabilityToken, FAPI_018 Material ->
  Properties.of(), FAPI_027 LivingSpawnEvent -> MobSpawnEvent.FinalizeSpawn), cross-loader
  галлюцинации (FORGE_API_011 RegisterMenuScreensEvent на Forge, PORT_006 IForgeMenuType на
  NeoForge). Ни одна правка не сделана «по памяти»: каждая подтверждена pinned-источниками.
- **eval_criteria FORGE_API_008**: устаревшее требование @CapabilityInject заменено.
- **+10 GameTest задач** (GT_001..010, synthetic=true, генератор с само-проверкой API
  по маппингам перед вставкой).
- **Схема v4**: module enum расширен значением `gametest`.
- **Контаминация измерена** (закрыто ограничение #3 v3).
- **private_eval выведен из публичного бандла** (закрыто ограничение #2 v3 — частично:
  перенесён в приватный репозиторий при публикации v4).

## Файлы

```
data/forgebench_v4_full.jsonl    411 задач (полный набор)
data/baseline_v2.jsonl           неизменённая копия v2 (130)
data/baseline_v2_fixed.jsonl     v2 + исправления D1-D6 в схеме v3
data/public_dev.jsonl            сплит для настройки оценщика (57, неизменён с v3)
data/public_eval.jsonl           публичный сравнительный сплит (262, неизменён с v3)
data/schema.json                 формальная схема v4 (v3 + gametest)
data/split_manifest.json         статистика/политика сплитов v4
data/parts/group_gt_gametest.jsonl  новые GT-задачи
evidence/                        машинные доказательства: api_evidence.csv (1530 строк),
                                 подтверждённые дефекты v3, журнал правок, контаминация
harness/                         ast_eval v3, run_eval_v3, visual_pipeline (без изменений)
tests/test_evaluator_rules.py    32 FP/FN-теста правил оценщика
docs/                            metrics.md, repro.md, dsl_limitations.md,
                                 modern_profile.md, PROJECT_DESCRIPTION.md
scripts/                         все скрипты стадий v4 (воспроизводимость)
reports/final_report_v4.md       итоговый отчёт
SHA256SUMS.txt                   контрольные суммы
```

## Сплиты

public_dev (57) и public_eval (262) наследуются от v3 БЕЗ ИЗМЕНЕНИЙ (неизменяемость
eval). GT-задачи добавлены в полный пул; их продвижение в сплиты — следующее
версионированное изменение. private_eval (82) — только в приватном репозитории.

## License

Данные: CC0-1.0. Harness: Apache-2.0. Эталоны написаны для этого бенчмарка;
API-факты сверены с официальными артефактами платформ (maven.neoforged.net 21.1.77
universal/sources/userdev + FML loader 4.0.31 + bus 8.0.2; forge 47.3.0
universal/sources/fmlloader + eventbus 6.0.5; официальные маппинги Mojang 1.20.1/1.21.1).
