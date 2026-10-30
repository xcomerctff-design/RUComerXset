# ForgeBench v4 — воспроизведение

Хост-требования: Python >= 3.11, pip install jsonschema, JDK 21 (Temurin; для
правил оценщика и javac-синтаксиса), ~1 ГБ диска под pinned-артефакты.

## 0. Pinned-артефакты (все URL фиксируются скриптами)

```bash
# NeoForge 21.1.77 (maven.neoforged.net)
neoforge-21.1.77-{universal,sources,userdev,installer}.jar
# FML
fancymodloader:loader:4.0.31; net.neoforged:bus:8.0.2
# Forge 1.20.1-47.3.0 (maven.minecraftforge.net)
forge-1.20.1-47.3.0-{universal,sources,userdev,installer}.jar; fmlloader; fmlcore;
javafmllanguage; lowcodelanguage; mclanguage; eventbus:6.0.5
# Mojang
client.txt (official mappings) 1.20.1 и 1.21.1; brigadier 1.2.9/1.1.8;
datafixerupper 8.0.16/6.0.8; neoform 1.21.1-20240808.144430.zip
```

Версии библиотек берутся из install_profile.json/config.json соответствующих
installer/userdev артефактов (скрипты делают это сами).

## 1. Стадии v4

```bash
python3 scripts/stage3_api_evidence.py                 # evidence по v3 (1530 строк)
python3 scripts/stage4_fix_defects.py                  # 13 правок эталонов + критерий
python3 scripts/stage5_contamination.py                # контаминация (SFT+CPT)
python3 scripts/stage5b_runs.py                        # run-length анализ
python3 scripts/stage6_gametest_tasks.py               # 10 GT-задач (self-checked)
python3 scripts/stage9_merge_validate.py               # пул 411 + схема v4
python3 snapshot-v3/harness/run_eval_v3.py \
    --data stage9/forgebench_v4_full.jsonl \
    --answers stage9/answers_selfcheck.jsonl \
    --out stage9/eval_selfcheck_report.json            # self-check 411/411
python3 scripts/stage10_manifests.py                   # манифесты + финальный evidence
python3 scripts/stage11_package.py                     # бандл + SHA256SUMS + zip
```

## 2. Тесты оценщика

```bash
# javac должен быть доступен по пути /home/z/tools/jdk-21.0.13+9/bin/javac
# (см. JAVAC_CANDIDATES в harness/ast_eval.py)
python3 tests/test_evaluator_rules.py                  # ожидание: 32 passed, 0 failed
```

## 3. Оценка модели (L1–L2)

```bash
python3 harness/run_eval_v3.py --data data/forgebench_v4_full.jsonl \
    --answers answers.jsonl --out report.json
# answers.jsonl: {"task_id": ..., "answer": "<java>"} или {"task_id": ..., "files": {...}}
```

## 4. L3+ (требует >=8–16 ГБ, Docker)

```bash
docker build -t forgebench-sandbox:v4 harness/
# L6 visual: python3 harness/visual_pipeline.py ... (Xvfb, GL 3.2+)
```

## 5. Контаминация (повторная проверка при обновлении корпусов)

```bash
python3 scripts/stage5_contamination.py   # нужны ref/sft-v2.1.0-rc2/sft/**.jsonl и v9 zip
python3 scripts/stage5b_runs.py
```

Платформенные версии для воспроизведения: Forge 47.3.0 / FG6 / Gradle 8.1.1 /
Java 17; NeoForge 21.1.77 / MDG / Gradle 8.9 / Java 21 (сверены с
maven.neoforged.net и релизными артефактами).
