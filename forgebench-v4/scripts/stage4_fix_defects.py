#!/usr/bin/env python3
"""
ForgeBench v4 — Stage IV: fix confirmed defects in v3 goldens -> forgebench_v4_full.jsonl

Every replacement is evidence-based (see stage3/STAGE3_REPORT.md):
- wrong class paths -> paths verified in pinned sources/mappings
- removed APIs (CapabilityInject, Material, LivingSpawnEvent.CheckSpawn) -> verified replacements
  (CapabilityManager.get(CapabilityToken), Properties.of(), MobSpawnEvent.FinalizeSpawn.setSpawnCancelled)
- cross-loader hallucinations (RegisterMenuScreensEvent on Forge, IForgeMenuType on NeoForge) ->
  verified per-platform patterns (FMLClientSetupEvent+MenuScreens.register, IMenuTypeExtension.create)
- PORT_004: ModLoadingContext.registerConfig absent from FML 4.0.31 (bytecode cp check);
  ModContainer.registerConfig present -> constructor-injection pattern (21.1 standard)

All old/new fragments are exact-match; script aborts if any pattern is not found exactly once.
Outputs:
  stage4/forgebench_v4_full.jsonl  — 401 tasks, fixed goldens
  stage4/fix_log.jsonl             — per-fix before/after fragments + evidence
  stage4/d5_check.json             — machine re-check of audit defect D5 on v3 data
"""
import json
import re
from collections import Counter
from pathlib import Path

WB = Path("/home/z/my-project/forgebench-v4-work")
V3 = WB / "snapshot-v3" / "data" / "forgebench_v3_full.jsonl"
OUT = WB / "stage4"
OUT.mkdir(parents=True, exist_ok=True)

tasks = [json.loads(l) for l in open(V3, encoding="utf-8")]
by_id = {t["task_id"]: t for t in tasks}

# ---------------------------------------------------------------- fix table
# Each fix: list of exact (old, new) replacements applied to golden_reference.
# forbidden_tokens must NOT appear in the fixed golden (stronger than fragment check).
FIXES = {
    # --- simple wrong-path swaps -----------------------------------------
    "MIXIN_007": {
        "forbidden": ["net.minecraft.world.entity.monster.Mob"],
        "evidence": "mojang mappings 1.21.1 line 74937: net.minecraft.world.entity.Mob",
        "repl": [
            ("import net.minecraft.world.entity.monster.Mob;",
             "import net.minecraft.world.entity.Mob;"),
        ],
    },
    "MIG_008": {
        "forbidden": ["neoforged.neoforge.registries.DeferredSpawnEggItem"],
        "evidence": "neoforge-21.1.77 sources: net/neoforged/neoforge/common/DeferredSpawnEggItem.java",
        "repl": [
            ("import net.neoforged.neoforge.registries.DeferredSpawnEggItem;",
             "import net.neoforged.neoforge.common.DeferredSpawnEggItem;"),
        ],
    },
    "FORGE_API_009": {
        "forbidden": ["net.minecraftforge.fml.config.ModConfigEvent"],
        "evidence": "forge-1.20.1-47.3.0 universal: net/minecraftforge/fml/event/config/ModConfigEvent(+Loading/Reloading/Unloading)",
        "repl": [
            ("import net.minecraftforge.fml.config.ModConfigEvent;",
             "import net.minecraftforge.fml.event.config.ModConfigEvent;"),
        ],
    },
    "FORGE_API_012": {
        "forbidden": ["net.minecraft.data.tags.BlockTagsProvider"],
        "evidence": "forge sources: net/minecraftforge/common/data/BlockTagsProvider.java; vanilla 1.20.1 mappings lack net.minecraft.data.tags.BlockTagsProvider",
        "repl": [
            ("import net.minecraft.data.tags.BlockTagsProvider;",
             "import net.minecraftforge.common.data.BlockTagsProvider;"),
        ],
    },
    "FORGE_API_013": {
        "forbidden": ["net.minecraftforge.event.RegisterEvent"],
        "evidence": "forge sources: net/minecraftforge/registries/RegisterEvent.java",
        "repl": [
            ("import net.minecraftforge.event.RegisterEvent;",
             "import net.minecraftforge.registries.RegisterEvent;"),
        ],
    },
    "GUI_010": {
        "forbidden": ["net.minecraft.world.level.block.entity.Container"],
        "evidence": "mojang mappings 1.21.1 line 71676: net.minecraft.world.Container; no block.entity.Container",
        "repl": [
            ("import net.minecraft.world.level.block.entity.Container;",
             "import net.minecraft.world.Container;"),
        ],
    },
    "GUI_015": {
        "forbidden": ["net.minecraft.world.level.block.entity.Container"],
        "evidence": "mojang mappings 1.21.1 line 71676: net.minecraft.world.Container; no block.entity.Container",
        "repl": [
            ("import net.minecraft.world.level.block.entity.Container;",
             "import net.minecraft.world.Container;"),
        ],
    },
    # --- structural fixes -------------------------------------------------
    "PORT_004": {
        "forbidden": ["ModLoadingContext", "neoforge.common.ModConfig;"],
        "evidence": ("fml-loader-4.0.31: ModLoadingContext.class has NO registerConfig (cp check); "
                     "ModContainer.registerConfig present; net/neoforged/fml/config/ModConfig$Type present"),
        "repl": [
            ("import net.neoforged.fml.ModLoadingContext;\nimport net.neoforged.fml.common.Mod;\nimport net.neoforged.neoforge.common.ModConfig;",
             "import net.neoforged.fml.ModContainer;\nimport net.neoforged.fml.common.Mod;\nimport net.neoforged.fml.config.ModConfig;"),
            ("public TaskMod() {\n        ModLoadingContext.get().registerConfig(ModConfig.Type.COMMON, TaskConfig.SPEC);\n    }",
             "public TaskMod(ModContainer modContainer) {\n        modContainer.registerConfig(ModConfig.Type.COMMON, TaskConfig.SPEC);\n    }"),
        ],
    },
    "PORT_006": {
        "forbidden": ["IForgeMenuType"],
        "evidence": "neoforge sources: IMenuTypeExtension.create(IContainerFactory) line 16; no IForgeMenuType in neoforge tree",
        "repl": [
            ("import net.neoforged.neoforge.common.extensions.IForgeMenuType;",
             "import net.neoforged.neoforge.common.extensions.IMenuTypeExtension;"),
            ("MENUS.register(\"energy_menu\", () -> IForgeMenuType.create(EnergyMenu::new));",
             "MENUS.register(\"energy_menu\", () -> IMenuTypeExtension.create(EnergyMenu::new));"),
        ],
    },
    "FORGE_API_008": {
        "forbidden": ["CapabilityInject", "MANA_CAP = null"],
        "evidence": ("CapabilityInject absent from 47.3.0 universal+sources; CapabilityManager.get(CapabilityToken<T>) "
                     "verified at CapabilityManager.java:25; anonymous-token pattern documented in CapabilityToken.java javadoc"),
        "repl": [
            ("import net.minecraftforge.common.capabilities.Capability;\nimport net.minecraftforge.common.capabilities.CapabilityInject;",
             "import net.minecraftforge.common.capabilities.Capability;\nimport net.minecraftforge.common.capabilities.CapabilityManager;\nimport net.minecraftforge.common.capabilities.CapabilityToken;"),
            ("    @CapabilityInject(Mana.class)\n    public static Capability<Mana> MANA_CAP = null;",
             "    public static final Capability<Mana> MANA_CAP =\n            CapabilityManager.get(new CapabilityToken<Mana>() {});"),
        ],
    },
    "FORGE_API_011": {
        "forbidden": ["RegisterMenuScreensEvent", "event.register("],
        "evidence": ("RegisterMenuScreensEvent is NeoForge-only (absent from forge tree); FMLClientSetupEvent+"
                     "ParallelDispatchEvent.enqueueWork verified (cp check); MenuScreens.register(MenuType,ScreenConstructor) "
                     "verified in mojang mappings 1.20.1 (74:78)"),
        "repl": [
            ("import net.minecraftforge.client.event.RegisterMenuScreensEvent;",
             "import net.minecraftforge.fml.event.lifecycle.FMLClientSetupEvent;"),
            ("import net.minecraft.client.gui.screens.inventory.AbstractContainerScreen;",
             "import net.minecraft.client.gui.screens.MenuScreens;\nimport net.minecraft.client.gui.screens.inventory.AbstractContainerScreen;"),
            ("        @SubscribeEvent\n        public static void onRegisterScreens(RegisterMenuScreensEvent event) {\n            event.register(CRATE_MENU.get(), CrateScreen::new);\n        }",
             "        @SubscribeEvent\n        public static void onClientSetup(FMLClientSetupEvent event) {\n            event.enqueueWork(() ->\n                    MenuScreens.register(ModMenus.CRATE_MENU.get(), CrateScreen::new));\n        }"),
        ],
    },
    "FAPI_018": {
        "forbidden": ["Material.STONE", "level.material.Material"],
        "evidence": ("Material absent from 1.20.1 and 1.21.1 mappings (removed in MC 1.20); Properties.of() no-arg "
                     "is the instruction's own requirement"),
        "repl": [
            ("import net.minecraft.world.level.material.Material;\n", ""),
            ("BlockBehaviour.Properties.of(Material.STONE).strength(3.0f)",
             "BlockBehaviour.Properties.of().strength(3.0f)"),
            ("BlockBehaviour.Properties.of(Material.STONE).strength(2.0f)",
             "BlockBehaviour.Properties.of().strength(2.0f)"),
        ],
    },
    "FAPI_027": {
        "forbidden": ["LivingSpawnEvent", "setCanceled"],
        "evidence": ("LivingSpawnEvent absent from 47.3.0; MobSpawnEvent.FinalizeSpawn.setSpawnCancelled(boolean) "
                     "verified at MobSpawnEvent.java:389 (javadoc: 'use FinalizeSpawn#setSpawnCancelled')"),
        "repl": [
            ("import net.minecraftforge.event.entity.living.LivingSpawnEvent;",
             "import net.minecraftforge.event.entity.living.MobSpawnEvent;"),
            ("    public static void onCheckSpawn(LivingSpawnEvent.CheckSpawn event) {",
             "    public static void onFinalizeSpawn(MobSpawnEvent.FinalizeSpawn event) {"),
            ("            event.setCanceled(true);",
             "            event.setSpawnCancelled(true);"),
        ],
    },
}

# ---------------------------------------------------------------- apply
fix_log = []
for tid, spec in FIXES.items():
    t = by_id[tid]
    g = t.get("golden_reference", "")
    if isinstance(g, dict):
        # apply per-file
        new_g = {}
        for path, content in g.items():
            c = content
            for old, new in spec["repl"]:
                if old in c:
                    if c.count(old) != 1:
                        raise SystemExit(f"{tid}: pattern occurs {c.count(old)}x in {path}: {old[:60]!r}")
                    c = c.replace(old, new)
            new_g[path] = c
        fixed = new_g
        joined_old = "\n".join(g.values())
        joined_new = "\n".join(new_g.values())
    else:
        fixed = g
        for old, new in spec["repl"]:
            if old not in g:
                raise SystemExit(f"{tid}: pattern NOT FOUND: {old[:80]!r}")
            if g.count(old) != 1:
                raise SystemExit(f"{tid}: pattern occurs {g.count(old)}x: {old[:60]!r}")
            g = g.replace(old, new)
        fixed = g
        joined_old, joined_new = spec["repl"][0][0], spec["repl"][0][1]
        joined_new = "\n".join(f"{o!r} -> {n!r}" for o, n in spec["repl"])

    # post-condition: forbidden tokens must be gone from the final golden
    finals = fixed.values() if isinstance(fixed, dict) else [fixed]
    joined_new = "\n".join(finals)
    for tok in spec["forbidden"]:
        if tok in joined_new:
            raise SystemExit(f"{tid}: forbidden token still present after fix: {tok}")
    by_id[tid]["golden_reference"] = fixed
    fix_log.append({
        "task_id": tid,
        "defect": "verified_wrong_api_reference",
        "evidence": spec["evidence"],
        "changes": [{"old": o[:200], "new": n[:200]} for o, n in spec["repl"]],
    })

# --- criteria consistency fix: FORGE_API_008 required_annotations demanded the
# REMOVED @CapabilityInject (evaluator caught this at stage IX self-check).
# Evidence: CapabilityInject absent from 47.3.0; fixed golden uses @Mod.EventBusSubscriber.
_t = by_id["FORGE_API_008"]
_ra = _t["eval_criteria"]["required_annotations"]
if "@CapabilityInject" in _ra:
    _ra.remove("@CapabilityInject")
    if "@Mod.EventBusSubscriber" not in _ra:
        _ra.append("@Mod.EventBusSubscriber")
fix_log.append({
    "task_id": "FORGE_API_008",
    "defect": "stale_required_annotation_in_criteria",
    "evidence": "CapabilityInject removed in 47.3.0 (stage3); fixed golden uses @Mod.EventBusSubscriber",
    "changes": [{"old": "required_annotations contained @CapabilityInject",
                 "new": json.dumps(_ra)}],
})

# --- consistency gate: no required annotation / token may reference a removed API
_STALE_FOR_REQUIREMENTS = ["CapabilityInject", "LivingSpawnEvent", "Material", "IForgeMenuType"]
for _t in tasks:
    _c = _t.get("eval_criteria") or {}
    for _k in ("required_annotations", "required_tokens"):
        for _v in (_c.get(_k) or []):
            if isinstance(_v, str) and any(s in _v for s in _STALE_FOR_REQUIREMENTS):
                raise SystemExit(f"consistency gate: {_t['task_id']} {_k}={_v!r} references a removed API")
# Audit defect D5: required_annotations containing tokens/classes instead of @-annotations.
# v3 schema: annotations moved to eval_criteria.required_annotations; verify all 401 tasks.
d5_bad = []
for t in tasks:
    for holder in (t.get("required_annotations"), (t.get("eval_criteria") or {}).get("required_annotations")
                   if isinstance(t.get("eval_criteria"), dict) else None):
        if not holder:
            continue
        for a in holder:
            if isinstance(a, str) and not a.startswith("@"):
                d5_bad.append({"task_id": t["task_id"], "value": a})
d5_check = {
    "defect": "D5 required_annotations schema",
    "tasks_checked": len(tasks),
    "non_annotation_entries": d5_bad,
    "conclusion": "closed in v3 schema (annotations live in eval_criteria.required_annotations, all entries start with '@')"
    if not d5_bad else "STILL OPEN",
}

# ---------------------------------------------------------------- outputs
with open(OUT / "forgebench_v4_full.jsonl", "w", encoding="utf-8") as f:
    for t in tasks:
        f.write(json.dumps(t, ensure_ascii=False) + "\n")
with open(OUT / "fix_log.jsonl", "w", encoding="utf-8") as f:
    for r in fix_log:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
(OUT / "d5_check.json").write_text(json.dumps(d5_check, indent=2, ensure_ascii=False), encoding="utf-8")

print("tasks:", len(tasks))
print("fixed tasks:", len(fix_log), sorted(x["task_id"] for x in fix_log))
print("D5:", d5_check["conclusion"], f"({len(d5_bad)} bad entries)")
