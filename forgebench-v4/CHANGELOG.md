# ForgeBench v4 — CHANGELOG

## v4.0.0 (2026-10-29)

### Fixed (13 goldens, все правки evidence-backed — evidence/fix_log.jsonl)
- MIXIN_007: `net.minecraft.world.entity.monster.Mob` -> `net.minecraft.world.entity.Mob`
- MIG_008: `…neoforge.registries.DeferredSpawnEggItem` -> `…neoforge.common.DeferredSpawnEggItem`
- PORT_004: `…neoforge.common.ModConfig` -> `net.neoforged.fml.config.ModConfig`;
  `ModLoadingContext.get().registerConfig` (метод отсутствует в FML 4.0.31) ->
  `ModContainer.registerConfig` с constructor-injection
- PORT_006: `IForgeMenuType` -> `IMenuTypeExtension` (NeoForge-имя; IForgeMenuType — Forge)
- FORGE_API_008: `@CapabilityInject` (класс удалён к 47.3.0) -> `CapabilityManager.get(new CapabilityToken<>(){})`
- FORGE_API_009: `…fml.config.ModConfigEvent` -> `…fml.event.config.ModConfigEvent`
- FORGE_API_011: `RegisterMenuScreensEvent` (не существует в Forge 1.20.1) -> `FMLClientSetupEvent` + `MenuScreens.register`
- FORGE_API_012: `net.minecraft.data.tags.BlockTagsProvider` -> `net.minecraftforge.common.data.BlockTagsProvider`
- FORGE_API_013: `…event.RegisterEvent` -> `…registries.RegisterEvent`
- FAPI_018: `Material.STONE` (класс удалён в MC 1.20) -> `BlockBehaviour.Properties.of()`
- FAPI_027: `LivingSpawnEvent.CheckSpawn` -> `MobSpawnEvent.FinalizeSpawn` + `setSpawnCancelled`
- GUI_010, GUI_015: `…block.entity.Container` -> `net.minecraft.world.Container`

### Changed
- FORGE_API_008 eval_criteria: required_annotations `@CapabilityInject` -> `@Mod.EventBusSubscriber`
  (обнаружено evaluator self-check на stage IX)
- Схема: module enum + `gametest` (data/schema.json)

### Added
- 10 GameTest-задач GT_001..GT_010 (8 NeoForge 1.21.1 + 2 Forge 1.20.1; synthetic=true,
  evidence-backed генератор scripts/stage6_gametest_tasks.py)
- evidence/: api_evidence.csv (1530 строк), confirmed_defects_stage3.jsonl, fix_log.jsonl,
  отчёты контаминации, d1/d5 проверки
- docs/dsl_limitations.md, docs/PROJECT_DESCRIPTION.md

### Removed
- `private_eval.jsonl` из публичного бандла (только в приватном репозитории)

### Security
- Ротация HF-токена рекомендована сразу после публикации (токен использовался в
  этом сеансе и фигурировал в чате)
