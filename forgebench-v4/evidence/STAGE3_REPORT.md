# ForgeBench v4 — Stage III: API Evidence (api_evidence.csv)

Дата: 2026-10-29. Статус: **ЗАВЕРШЁН** (исполнено на этом хосте, все проверки воспроизводимы).

## 1. Назначение

Этап закрывает класс дефектов «выдуманный API» (D1 из аудита v3) машинной проверкой:
для каждой из 401 задачи v3 (`snapshot-v3/data/forgebench_v3_full.jsonl`) из эталона
(`golden_reference`) извлечены API-символы (import + полные имена) и проверены по
**pinned-инвентарям целевых платформ**. Артефакт — `stage3/api_evidence.csv` (1530 строк,
344 уникальных символа).

## 2. Pinned-инвентари (все скачаны и захешированы в `pinned/`)

| Платформа | Артефакт | Классов |
|---|---|---|
| NeoForge 21.1.77 | universal.jar | 825 |
| NeoForge 21.1.77 | sources.jar | 931 (.java) |
| FML loader | fancymodloader:loader:4.0.31 | 180 |
| eventbus | net.neoforged:bus:8.0.2 | 20 |
| Forge 1.20.1-47.3.0 | universal.jar | 653 |
| Forge 1.20.1-47.3.0 | sources.jar | 665 (.java) |
| Forge FML | fmlloader + fmlcore + javafmllanguage + lowcodelanguage + mclanguage | 150 |
| eventbus | net.minecraftforge:eventbus:6.0.5 | 29 |
| Vanilla 1.21.1 | Mojang official mappings (client.txt) | 7 927 |
| Vanilla 1.20.1 | Mojang official mappings (client.txt) | 7 123 |
| Mojang libs 1.21.1 | brigadier 1.2.9 + datafixerupper 8.0.16 | 211 |
| Mojang libs 1.20.1 | brigadier 1.1.8 + datafixerupper 6.0.8 | 207 |

Версии eventbus/fml-семейства взяты из `install_profile.json` / `config.json`
userdev-артефактов соответствующей платформы (не угадывались).

## 3. Ключевые доказательства (машино-проверяемые)

### 3.1. D1 закрыт в v3_full — подтверждено

- `baseline_v2.jsonl` (неисправленный): ровно 5 задач импортируют несуществующий
  `net.neoforged.api.Dist` — **API_009, API_019, API_020, MIG_002, MIG_019**
  (совпадает с ручным аудитом v3).
- `forgebench_v3_full.jsonl`: **0** таких задач; все используют
  `net.neoforged.api.distmarker.Dist` — реальный пакет.

### 3.2. Где физически живёт distmarker (вопрос из аудита v3, закрыт)

- Класса НЕТ в: neoforge universal/sources, FML loader 4.0.31, forge universal/sources/fmlloader,
  neoform zip (бинарный grep по всем записям).
- Пакет `net/neoforged/api/distmarker` РЕАЛЬНО существует: на него ссылаются
  **20 классов** neoforge-universal (совпадает с аудитом v3 дословно), **26 классов**
  FML loader (RuntimeDistCleaner), его импортируют **12 патчей** userdev.
  Носитель — NeoForm-patched minecraft jar (NeoForm 1.21.1-20240808.144430).
  В CSV такие символы помечены `exists_indirect`.

### 3.3. Подтверждённые дефекты v3_full (13 задач) — НОВЫЕ находки stage III

Все — в эталонах; ручной аудит v3 их не ловил. Детали в
`stage3/confirmed_defects_stage3.jsonl` (поле `evidence_source` содержит верификацию):

| Задача | Выдуманный путь | Реальность (проверено по pinned) |
|---|---|---|
| MIXIN_007 | `net.minecraft.world.entity.monster.Mob` | `net.minecraft.world.entity.Mob` (маппинги 1.21.1) |
| MIG_008 | `...neoforge.registries.DeferredSpawnEggItem` | `...neoforge.common.DeferredSpawnEggItem` (sources) |
| PORT_004 | `...neoforge.common.ModConfig` | `net.neoforged.fml.config.ModConfig` (fml-loader) |
| PORT_006 | `...common.extensions.IForgeMenuType` | `IMenuTypeExtension`; IForgeMenuType — имя из Forge (cross-loader) |
| FORGE_API_008 | `...common.capabilities.CapabilityInject` | класс удалён к 47.3.0; замена `RegisterCapabilitiesEvent` |
| FORGE_API_009 | `...fml.config.ModConfigEvent` | `...fml.event.config.ModConfigEvent` (sources) |
| FORGE_API_011 | `...client.event.RegisterMenuScreensEvent` | в Forge 1.20.1 НЕТ (это NeoForge API; cross-loader) |
| FORGE_API_012 | `net.minecraft.data.tags.BlockTagsProvider` | в vanilla 1.20.1 отсутствует; `net.minecraftforge.common.data.BlockTagsProvider` |
| FORGE_API_013 | `...event.RegisterEvent` | `...registries.RegisterEvent` (sources) |
| FAPI_018 | `...material.Material` | класс удалён в MC 1.20.x (нет ни в 1.20.1, ни в 1.21.1) |
| FAPI_027 | `...living.LivingSpawnEvent` | `...living.MobSpawnEvent` (sources) |
| GUI_010, GUI_015 | `...block.entity.Container` | `net.minecraft.world.Container` (маппинги 1.21.1) |

## 4. Метод и ограничения

- Проверка **на уровне классов** (класс-префиксный проход по инвентарям, самый длинный
  кандидат первым; пакетные упоминания не создают строк). Member-level (методы/поля) —
  вне скоупа stage III: их проверка требует javac classpath (статусы stage VI).
- `external_unverified` (240 строк): пространства имён вне гейта
  (org.spongepowered, org.lwjgl и т.п.) — проверяются на следующих этапах по
  списку зависимостей платформ.
- Воспроизведение: `python3 scripts/stage3_api_evidence.py` (все jar в `pinned/`).

## 5. Влияние на этапы IV+

- Stage IV (исправление дефектов): 13 задач выше — кандидаты на правку эталона/карантин.
- Stage V (контаминация): evidence-подход расширяется на SFT-корпуса.
- Оценщик v4 получает evidence-гейт: любые `class_missing`/`vanilla_missing`
  в ответах моделей могут детектироваться автоматически тем же раннером.
