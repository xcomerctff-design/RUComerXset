# ForgeBench — полное описание проекта

Версия документа: 2026-10-29 (актуальна для ForgeBench v4.0.0)

## 1. Назначение

ForgeBench — бенчмарк для проверки реальной способности LLM работать с
Minecraft-моддингом на трёх навыках:

1. **Forge-native coding** — писать, объяснять и чинить код под Minecraft 1.20.1 + Forge 47.x (Java 17);
2. **NeoForge-native coding** — то же под Minecraft 1.21.1 + NeoForge 21.1.x (Java 21);
3. **Перенос** — миграция проекта Forge 1.20.1 -> NeoForge 1.21.1 с сохранением поведения.

Бенчмарк создан как ответ на проверенную проблему пилота: модель выдумывала API,
классы и результаты сборки. Поэтому главный контракт — **сначала проверяемость,
потом объём**: каждое утверждение эталона должно быть проверяемым, а каждый статус —
подтверждённым исполненной проверкой (без «static_checked = работает»).

## 2. Состав датасета (v4.0.0)

- **411 задач**: 130 задач v2 (с исправлениями D1–D6) + 271 задача v3 (группы A–I:
  API/регистрация, mixins, GUI 41, рендер 53, ресурсы/datagen 37, геймплей/worldgen 44,
  сеть/безопасность 36, многофайловые проекты/миграции) + 10 GameTest-задач v4.
- Типы: generate (323+), migrate (37), diagnose (20), red-team подкатегории
  (malformed resource, regression, wrong loader, adversarial API).
- Два целевых профиля: Forge 1.20.1 (55 задач) и NeoForge 1.21.1 (356 задач);
  migration/porting-задачи проверяют обе стороны.
- Сплиты: public_dev 57 / public_eval 262 / private_eval 82 (held-out, приватный репо) +
  неизменяемые baseline-копии. Сплиты назначаются целыми семействами задач.

## 3. Архитектура стадий v4 (как строилась эта версия)

| Стадия | Артефакт | Статус |
|---|---|---|
| II. Восстановление v3 | snapshot-v3 (45 файлов, SHA 8/8) | ИСПОЛНЕНО |
| III. API-evidence | api_evidence.csv (1530 строк, 344 символа) | ИСПОЛНЕНО |
| IV. Правка дефектов | fix_log.jsonl (13 эталонов + 1 критерий) | ИСПОЛНЕНО |
| V. Контаминация | contamination_report + runs_report | ИЗМЕРЕНО |
| VI. GameTest-семейство | GT_001..GT_010 (synthetic, evidence-backed) | ИСПОЛНЕНО |
| VII. DSL-ограничение | docs/dsl_limitations.md | ЗАФИКСИРОВАНО |
| VIII. Приватность | private_eval -> приватный репо | ИСПОЛНЕНО (при публикации) |
| IX. Оценщик/схема | 32/32 правил; self-check 411/411; схема 411/411 | ИСПОЛНЕНО |
| X. Манифесты/метрики | split_manifest_v4, metrics_v4 | ИСПОЛНЕНО |
| XI. Упаковка | bundle + SHA256SUMS + zip | ИСПОЛНЕНО |
| XII. Итоговый отчёт | reports/final_report_v4.md | ИСПОЛНЕНО |

## 4. Pinned-доказательная база

Все API-факты v4 сверены не «по памяти», а по фиксированным артефактам:

- NeoForge 21.1.77: universal.jar (825 классов), sources.jar (931 класс), userdev (741 патч), installer;
- FML loader 4.0.31 (180 классов), eventbus 8.0.2 (20);
- Forge 1.20.1-47.3.0: universal (653), sources (665), fmlloader (96), eventbus 6.0.5 (29), fml-семейство (54);
- Моjang official mappings 1.21.1 (7927 классов) и 1.20.1 (7123) + brigadier/datafixerupper обоих поколений;
- NeoForm 1.21.1-20240808.144430 (носитель distmarker-классов — установлен косвенно).

Ключевые машинные факты: `net.neoforged.api.Dist` отсутствует во всех артефактах
(дефект D1, закрыт в v3); пакет `net.neoforged.api.distmarker` реален (20 universal +
26 fml-loader ссылок; носитель — патченный minecraft-jar).

## 5. Оценка (harness)

- Уровни: L1 структурный (схема) -> L2 статический (javac parse-only + imports +
  required/forbidden annotations + ресурсные токены) -> L3 Gradle-компиляция ->
  L4 GameTest -> L5 client/server smoke -> L6 visual.
- В среде 4 ГБ исполнимы L1–L2 (и самопроверка эталонов). L3–L6 честно N/A:
  требуется хост >=8–16 ГБ / Docker.
- Правила оценщика покрыты 32 FP/FN-тестами (строки, комментарии, generics,
  вложенные классы, перегрузки, мультифайл, allowed/forbidden, dist-классы).

## 6. Контаминация

v4 измерил пересечение задач с обучающими корпусами (SFT-v2.1.0-rc2/train,
CPT-v9-full): 8-граммная контainment до 0.51 — идиоматика Java/MC; анализ
непрерывных пробегов показал 0 дословных утечек (максимум — import-блоки и
литеральные массивы, сниппеты приложены). Проверка повторяема скриптом stage5.

## 7. Границы честности

- Ни одна задача не помечена compile_verified/test_verified: все статусы = syntax_verified.
- DSL-эталоны проверены token-level + класс-гейтом; парсера DSL нет (документировано).
- Современный профиль 1.21.9+/26.x — каркас без эталонов (не воспроизводим в среде).
- GameTest-задачи добавлены, их исполнение — следующий этап (нужен хост >=8 ГБ).

## 8. Воспроизведение

```bash
# JDK 21 (Temurin), Python >= 3.11, pip install jsonschema
python3 scripts/stage3_api_evidence.py                 # api_evidence.csv
python3 scripts/stage4_fix_defects.py                  # v4 goldens
python3 scripts/stage5_contamination.py && python3 scripts/stage5b_runs.py
python3 scripts/stage6_gametest_tasks.py               # GT-задачи
python3 scripts/stage9_merge_validate.py               # пул 411 + схема
python3 snapshot-v3/harness/run_eval_v3.py --data stage9/forgebench_v4_full.jsonl \
    --answers stage9/answers_selfcheck.jsonl --out stage9/eval_selfcheck_report.json
python3 scripts/stage10_manifests.py && python3 scripts/stage11_package.py
```

## 9. Лицензии

Данные CC0-1.0, harness Apache-2.0. Эталоны написаны для бенчмарка; факты API —
из официальных артефактов платформ под их лицензиями (LGPL-2.1 Forge/NeoForge,
Mojang mappings under their terms).
