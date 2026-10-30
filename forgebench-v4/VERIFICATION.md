# ForgeBench v4 — отчёт самоверификации

Дата: 2026-10-29 · Хост: 4 ГБ cgroup, JDK 21.0.13 (Temurin, portable), javalang 0.13,
Python jsonschema. Все числа ниже — результат исполненных команд этого сеанса;
неисполненное помечено NOT_RUN/BLOCKED.

## 1. Восстановление v3 и pinned-база (stage III prep) — ИСПОЛНЕНО
- Snapshot `ComerX/forgebench-v3` скачан полностью (45 файлов), SHA256SUMS v3: 8/8 OK.
- Pinned-артефакты скачаны и захешированы (evidence/…, pinned/ в рабочей директории):
  neoforge-21.1.77 {universal, sources, userdev, installer}, fml-loader-4.0.31, bus-8.0.2,
  forge-1.20.1-47.3.0 {universal, sources, fmlloader, installer, userdev},
  eventbus-6.0.5, fmlcore/javafmllanguage/lowcodelanguage/mclanguage 47.3.0,
  brigadier 1.2.9/1.1.8, datafixerupper 8.0.16/6.0.8, neoform 1.21.1 zip.
- Версии eventbus/fml-семейства взяты из install_profile.json/config.json самих
  артефактов, не угадывались.

## 2. API-evidence (stage III) — ИСПОЛНЕНО
- 401 задача v3 -> 1530 строк evidence, 344 уникальных символа.
- D1 машина-подтверждён и закрыт: baseline_v2 = 5 задач с net.neoforged.api.Dist
  (API_009/019/020, MIG_002/019); v3_full = 0.
- distmarker-вопрос аудита v3 закрыт: класса нет ни в одном артефакте; пакет реален
  (20 universal-ссылок + 26 fml-loader-ссылок + 12 patch-импортов); носитель —
  NeoForm-patched minecraft jar.
- 13 подтверждённых дефектов эталонов v3 (ручной аудит v3 их не ловил) —
  evidence/confirmed_defects_stage3.jsonl.
- Итог по v4-пулу: 0 class_missing / 0 vanilla_missing (stage10/api_evidence_final.csv).

## 3. Исправление эталонов (stage IV) — ИСПОЛНЕНО
- 13 задач исправлены точечными заменами с evidence; журнал: evidence/fix_log.jsonl.
- eval_criteria FORGE_API_008: @CapabilityInject -> @Mod.EventBusSubscriber.
- D5 (schema) машина-перепроверена: закрыт в v3-схеме (0 некорректных записей).

## 4. Контаминация (stage V) — ИЗМЕРЕНО
- Против SFT-v2.1.0-rc2/train (45 файлов, 7422 записи) и CPT-v9-full (32 шарда,
  12620 записей): 8-граммная контainment; 224/411 задач >= 0.10 (идиомы),
  max 0.51; анализ пробегов: max run против SFT-train = 39 шинглов (import-блок),
  против CPT = 44 (import-блок/литеральный массив) — 4 автоматических
  VERBATIM_LEAK_SUSPECT реклассифицированы вручную как boilerplate со сниппетами.
- Вывод: дословной утечки задач нет; ограничение #3 v3 закрыто измерением.

## 5. GameTest-семейство (stage VI) — ДОБАВЛЕНО
- 10 задач (GT_001..010: 8 NeoForge 1.21.1 + 2 Forge 1.20.1), synthetic=true,
  генератор с само-проверкой: все константы Blocks/Items и все методы
  GameTestHelper проверены по маппингам перед вставкой; @GameTestHolder/
  @PrefixGameTestTemplate сверены по исходникам платформ.
- API-проверка сгенерированных задач: 57/57 символов class_exists, 0 missing.

## 6. Оценщик и схема (stage IX) — ИСПОЛНЕНО
- tests/test_evaluator_rules.py: 32/32 (требовал javac: поставлен portable
  Temurin 21.0.13; путь /home/z/tools/jdk-21.0.13+9 воспроизведён symlink).
- Схема v4 = v3 + 'gametest' в module enum; 411/411 PASS.
- Evaluator self-check (эталоны как ответы): 411/411 syntax_pass,
  411/411 L2_static PASS, hallucinated_api = 0.
  (Первая итерация поймала 1 FAIL — FORGE_API_008 со stale-критерием; исправлено
  в stage IV и перепрогнано до 0.)

## 7. Компиляция и рантайм — BLOCKED/NOT_RUN, честно
- L3 Gradle: BLOCKED (4 ГБ cgroup; NeoForm >=8 ГБ; нет Docker).
- L4 GameTest: задачи добавлены; исполнение NOT_RUN (тот же лимит).
- L5/L6 client/server/visual: NOT_RUN (раннеры без изменений от v3).

## 8. Сплиты и приватность
- public_dev/public_eval: без изменений от v3 (неизменяемость eval).
- private_eval (82): исключён из публичного бандла; публикуется только в
  приватном репозитории ComerX/forgebench-v4-private. Ограничение #2 v3
  закрыто на уровне публикации v4.
