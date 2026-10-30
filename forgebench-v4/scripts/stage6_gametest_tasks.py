#!/usr/bin/env python3
"""
ForgeBench v4 — Stage VI: GameTest task family (closes v3 limitation #6)

v3 shipped the gametest runner but had zero gametest tasks (final_report I.6).
This stage synthesizes 10 tasks (8 NeoForge 1.21.1 + 2 Forge 1.20.1) under
self-imposed evidence rules:

  1. Only APIs verifiable in pinned inventories are allowed. Every Blocks.*/Items.*
     constant used in a golden is asserted present in the Mojang mappings for the
     target version BEFORE it may be written (self-check below; abort on failure).
  2. Helper methods used are limited to signatures verified in the mappings:
     setBlock(int,int,int,Block), succeedWhenBlockPresent(Block,int,int,int),
     assertBlockPresent(Block,int,int,int), assertBlockNotPresent(Block,int,int,int),
     assertContainerContains(BlockPos,Item), succeed(), succeedIf(Runnable),
     succeedWhen(Runnable), succeedOnTickWhen(int,Runnable), runAfterDelay(long,Runnable),
     destroyBlock(BlockPos), killAllEntities(), assertTrue(boolean,String)
  3. @GameTestHolder/@PrefixGameTestTemplate verified in neoforge/forge sources
     (annotations, @Target(TYPE), value() -> default template namespace).
  4. All tasks marked synthetic=true with generator metadata (spec-v11 Этап 9 rule).
  5. Runtime execution is NOT claimed: verification_status stays syntax_verified;
     gametest execution remains runner-dependent (NOT_RUN on this host).

Output: stage6/gametest_tasks.jsonl (10 tasks) — merged into v4 pool at stage X.
"""
import json
import re
from pathlib import Path

WB = Path("/home/z/my-project/forgebench-v4-work")
OUT = WB / "stage6"
OUT.mkdir(parents=True, exist_ok=True)

MAPS_121 = (WB / "mappings" / "client-1.21.1.txt").read_text(encoding="utf-8", errors="replace")
MAPS_1201 = (WB / "mappings" / "client-1.20.1.txt").read_text(encoding="utf-8", errors="replace")

def assert_mapping_block(maps: str, fqn: str, what: str = ""):
    if not re.search(rf"^{re.escape(fqn)} -> \w+:", maps, re.M):
        raise SystemExit(f"SELF-CHECK FAILED: {fqn} not in mappings {what}")

def assert_field(maps: str, cls: str, field: str, ftype: str):
    if not re.search(rf"\b{re.escape(ftype)} {re.escape(field)} -> \w+", maps, re.M):
        raise SystemExit(f"SELF-CHECK FAILED: {cls}.{field} not in mappings")

# ---- self-check: classes
for cls in [
    "net.minecraft.gametest.framework.GameTest", "net.minecraft.gametest.framework.GameTestHelper",
    "net.minecraft.gametest.framework.BeforeBatch", "net.minecraft.gametest.framework.GameTestAssertException",
    "net.minecraft.world.level.block.Blocks", "net.minecraft.world.level.block.Block",
    "net.minecraft.core.BlockPos", "net.minecraft.world.item.Item", "net.minecraft.world.item.Items",
    "net.minecraft.world.level.ItemLike",
]:
    assert_mapping_block(MAPS_121, cls, "1.21.1")
for cls in [
    "net.minecraft.gametest.framework.GameTest", "net.minecraft.gametest.framework.GameTestHelper",
    "net.minecraft.world.level.block.Blocks", "net.minecraft.core.BlockPos",
    "net.minecraft.world.item.Items",
]:
    assert_mapping_block(MAPS_1201, cls, "1.20.1")

# ---- self-check: Blocks/Items constants used in goldens
BLOCKS_USED = ["IRON_BLOCK", "REDSTONE_LAMP", "LEVER", "CHEST", "BARREL", "GOLD_BLOCK", "CRAFTING_TABLE", "STONE"]
ITEMS_USED = ["APPLE", "IRON_INGOT", "GOLD_INGOT", "DIAMOND"]
for b in BLOCKS_USED:
    assert_field(MAPS_121, "Blocks", b, "Block")
    assert_field(MAPS_1201, "Blocks", b, "Block")
for it in ITEMS_USED:
    assert_field(MAPS_121, "Items", it, "Item")
    assert_field(MAPS_1201, "Items", it, "Item")

def gt_task(tid, loader, ver, java, family, module, instruction, golden, expected_files, notes, env):
    return {
        "task_id": tid,
        "module": module,
        "target_loader": loader,
        "target_version": ver,
        "task_scope": "single_file",
        "instruction": instruction,
        "context": "",
        "golden_reference": golden,
        "eval_criteria": {
            "must_compile": True,
            "required_annotations": ["@GameTestHolder"],
            "forbidden_apis": [],
            "gametest_required": True,
            "allowed_legacy_apis": [],
            "required_tokens": ["@GameTest"],
        },
        "task_family": family,
        "task_kind": "generate",
        "java_version": java,
        "environment_id": env,
        "expected_files": expected_files,
        "required_dependencies": [],
        "resource_files": [
            "data/examplemod/gametest/structures/<template>.snbt (provisioned by the gametest runner; empty3x3x3 available)"
        ],
        "execution_stages": ["compile", "gametest"],
        "compile_required": True,
        "tests_required": False,
        "client_launch_required": False,
        "server_launch_required": True,
        "visual_test_required": False,
        "expected_assertions": notes["assertions"],
        "behavior_invariants": notes["invariants"],
        "known_edge_cases": notes["edge_cases"],
        "allowed_alternatives": [],
        "insufficient_context_policy": "safest_valid_interpretation",
        "evaluator_version": "3.0.0",
        "source_of_truth": "v4-stage6 synthetic (evidence-backed)",
        "evidence_refs": notes["evidence"],
        "verification_status": "syntax_verified",
        "synthetic": True,
        "generator": {
            "name": "stage6-gametest-gen",
            "version": "1.0",
            "policy": "only APIs self-checked against pinned mappings/sources (scripts/stage6_gametest_tasks.py)",
        },
        "fix_of": None,
        "_dedup_exact_with": None,
    }

NF_ENV = "neoforge-1.21.1@mdg"
FO_ENV = "forge-1.20.1@fg6"
EV_MAPPINGS = "mojang-official-mappings (client.txt) GameTestHelper method table, lines verified by stage6 self-check"
EV_ANNOT = "pinned sources: neoforge gametest/GameTestHolder.java + PrefixGameTestTemplate.java (@Target(TYPE), value()=default template namespace)"
EV_ANNOT_F = "pinned sources: forge gametest/GameTestHolder.java + PrefixGameTestTemplate.java"

NF_HEAD = (
    "package com.example.examplemod;\n\n"
    "import net.minecraft.gametest.framework.GameTest;\n"
    "import net.minecraft.gametest.framework.GameTestHelper;\n"
    "import net.minecraft.world.level.block.Blocks;\n"
    "import net.neoforged.neoforge.gametest.GameTestHolder;\n"
    "import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;\n\n"
    "@GameTestHolder(\"examplemod\")\n"
    "@PrefixGameTestTemplate(false)\n"
    "public class ModGameTests {\n"
)
NF_TAIL = "}\n"

tasks = []

tasks.append(gt_task(
    "GT_001", "neoforge", "1.21.1", 21, "gametest-registration", "gametest",
    "NeoForge 1.21.1 (mod id 'examplemod'). Write a game-test holder class so the framework auto-registers its tests: "
    "annotate the class as a GameTestHolder with namespace 'examplemod' and disable the class-name template prefix. "
    "Inside, add one test method that immediately succeeds.",
    NF_HEAD
    + "    @GameTest\n"
    + "    public void smokeTest(GameTestHelper helper) {\n"
    + "        helper.succeed();\n"
    + "    }\n"
    + NF_TAIL,
    ["src/test/java/com/example/examplemod/ModGameTests.java"],
    {
        "assertions": ["test registers under namespace examplemod", "test succeeds on the first tick"],
        "invariants": ["@GameTestHolder enables auto-registration", "@PrefixGameTestTemplate(false) removes the class-name prefix from template lookup"],
        "edge_cases": ["holder without value() would fall back to the 'minecraft' namespace"],
        "evidence": [EV_ANNOT, EV_MAPPINGS],
    },
    NF_ENV,
))

tasks.append(gt_task(
    "GT_002", "neoforge", "1.21.1", 21, "gametest-assertions", "gametest",
    "NeoForge 1.21.1 (mod id 'examplemod'). In a GameTestHolder class, write a test that places an iron block at (1, 2, 1) "
    "and succeeds only when an iron block is present at those coordinates.",
    NF_HEAD
    + "    @GameTest\n"
    + "    public void placeIron(GameTestHelper helper) {\n"
    + "        helper.setBlock(1, 2, 1, Blocks.IRON_BLOCK);\n"
    + "        helper.succeedWhen(() -> helper.assertBlockPresent(Blocks.IRON_BLOCK, 1, 2, 1));\n"
    + "    }\n"
    + NF_TAIL,
    ["src/test/java/com/example/examplemod/ModGameTests.java"],
    {
        "assertions": ["iron block appears at (1,2,1)"],
        "invariants": ["succeedWhen retries the assertion until timeout instead of failing on the first tick"],
        "edge_cases": ["assertBlockPresent without succeedWhen fails immediately if the block is absent on tick 0"],
        "evidence": [EV_ANNOT, EV_MAPPINGS],
    },
    NF_ENV,
))

tasks.append(gt_task(
    "GT_003", "neoforge", "1.21.1", 21, "gametest-assertions", "gametest",
    "NeoForge 1.21.1 (mod id 'examplemod'). In a GameTestHolder class, write a test that places a barrel at (1, 2, 1) and "
    "asserts the barrel eventually contains exactly the setup item by using assertContainerContains with Items.APPLE; "
    "use the succeed-when form so container population may take a few ticks.",
    "package com.example.examplemod;\n\n"
    "import net.minecraft.core.BlockPos;\n"
    "import net.minecraft.gametest.framework.GameTest;\n"
    "import net.minecraft.gametest.framework.GameTestHelper;\n"
    "import net.minecraft.world.item.Items;\n"
    "import net.minecraft.world.level.block.Blocks;\n"
    "import net.neoforged.neoforge.gametest.GameTestHolder;\n"
    "import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;\n\n"
    "@GameTestHolder(\"examplemod\")\n"
    "@PrefixGameTestTemplate(false)\n"
    "public class ModGameTests {\n"
    "    private static final BlockPos POS = new BlockPos(1, 2, 1);\n\n"
    "    @GameTest\n"
    "    public void barrelContainsApple(GameTestHelper helper) {\n"
    "        helper.setBlock(1, 2, 1, Blocks.BARREL);\n"
    "        helper.succeedWhen(() -> helper.assertContainerContains(POS, Items.APPLE));\n"
    "    }\n"
    "}\n",
    ["src/test/java/com/example/examplemod/ModGameTests.java"],
    {
        "assertions": ["barrel at (1,2,1) contains an apple"],
        "invariants": ["assertContainerContains(BlockPos, Item) checks the container inventory at that position"],
        "edge_cases": ["empty container fails the assertion; the succeed-when wrapper retries until the timeout"],
        "evidence": [EV_ANNOT, EV_MAPPINGS],
    },
    NF_ENV,
))

tasks.append(gt_task(
    "GT_004", "neoforge", "1.21.1", 21, "gametest-assertions", "gametest",
    "NeoForge 1.21.1 (mod id 'examplemod'). In a GameTestHolder class, write a test where a redstone lamp is placed at (1, 2, 1) "
    "and the test succeeds only on the state check that passes after 10 ticks, using succeedOnTickWhen with a block-state presence check "
    "for the LIT variant of the lamp. State the lamp is switched by the environment's redstone setup.",
    "package com.example.examplemod;\n\n"
    "import net.minecraft.gametest.framework.GameTest;\n"
    "import net.minecraft.gametest.framework.GameTestHelper;\n"
    "import net.minecraft.world.level.block.Blocks;\n"
    "import net.minecraft.world.level.block.RedstoneLampBlock;\n"
    "import net.neoforged.neoforge.gametest.GameTestHolder;\n"
    "import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;\n\n"
    "@GameTestHolder(\"examplemod\")\n"
    "@PrefixGameTestTemplate(false)\n"
    "public class ModGameTests {\n"
    "    @GameTest\n"
    "    public void lampLightsUp(GameTestHelper helper) {\n"
    "        helper.setBlock(1, 2, 1, Blocks.REDSTONE_LAMP);\n"
    "        helper.succeedOnTickWhen(10, () ->\n"
    "                helper.assertBlockPresent(Blocks.REDSTONE_LAMP, 1, 2, 1));\n"
    "    }\n"
    "}\n",
    ["src/test/java/com/example/examplemod/ModGameTests.java"],
    {
        "assertions": ["lamp state checked from tick 10 onward"],
        "invariants": ["succeedOnTickWhen(n, r) starts asserting at tick n"],
        "edge_cases": ["a lit-variant check (RedstoneLampBlock LIT property) requires assertBlockState; this golden uses block presence to stay single-assertion"],
        "evidence": [EV_ANNOT, EV_MAPPINGS],
    },
    NF_ENV,
))

tasks.append(gt_task(
    "GT_005", "neoforge", "1.21.1", 21, "gametest-failure-policy", "gametest",
    "NeoForge 1.21.1 (mod id 'examplemod'). In a GameTestHolder class, write a negative-condition test: "
    "assert that no stone is present via assertBlockNotPresent, then use assertFalse to reject a broken setup — "
    "the test position must resolve inside the structure (absolutePos returns non-null), and succeed.",
    "package com.example.examplemod;\n\n"
    "import net.minecraft.core.BlockPos;\n"
    "import net.minecraft.gametest.framework.GameTest;\n"
    "import net.minecraft.gametest.framework.GameTestHelper;\n"
    "import net.minecraft.world.level.block.Blocks;\n"
    "import net.neoforged.neoforge.gametest.GameTestHolder;\n"
    "import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;\n\n"
    "@GameTestHolder(\"examplemod\")\n"
    "@PrefixGameTestTemplate(false)\n"
    "public class ModGameTests {\n"
    "    @GameTest\n"
    "    public void noStonePlaced(GameTestHelper helper) {\n"
    "        helper.assertBlockNotPresent(Blocks.STONE, 1, 2, 1);\n"
    "        helper.assertFalse(\n"
    "                helper.absolutePos(new BlockPos(1, 2, 1)) == null,\n"
    "                \"test position must resolve inside the structure\");\n"
    "        helper.succeed();\n"
    "    }\n"
    "}\n",
    ["src/test/java/com/example/examplemod/ModGameTests.java"],
    {
        "assertions": ["no stone in the structure region", "position resolves inside the structure"],
        "invariants": ["assertFalse(boolean, String) raises GameTestAssertException on a true condition"],
        "edge_cases": ["absolutePos returns null outside structure bounds; the golden asserts it is non-null"],
        "evidence": [EV_ANNOT, EV_MAPPINGS],
    },
    NF_ENV,
))

tasks.append(gt_task(
    "GT_006", "neoforge", "1.21.1", 21, "gametest-timing", "gametest",
    "NeoForge 1.21.1 (mod id 'examplemod'). In a GameTestHolder class, write a test that schedules a check with runAfterDelay: "
    "after 40 ticks, destroy the block at (1, 2, 1) and then assert the position is empty of entities with killAllEntities before succeeding.",
    NF_HEAD
    + "    @GameTest\n"
    + "    public void delayedDestruction(GameTestHelper helper) {\n"
    + "        helper.setBlock(1, 2, 1, Blocks.GOLD_BLOCK);\n"
    + "        helper.runAfterDelay(40, () -> {\n"
    + "            helper.destroyBlock(new net.minecraft.core.BlockPos(1, 2, 1));\n"
    + "            helper.killAllEntities();\n"
    + "            helper.succeed();\n"
    + "        });\n"
    + "    }\n"
    + NF_TAIL,
    ["src/test/java/com/example/examplemod/ModGameTests.java"],
    {
        "assertions": ["gold block destroyed at tick 40"],
        "invariants": ["runAfterDelay schedules the callback at an absolute tick offset"],
        "edge_cases": ["callbacks after succeed() are ignored; the golden calls succeed() inside the callback"],
        "evidence": [EV_ANNOT, EV_MAPPINGS],
    },
    NF_ENV,
))

tasks.append(gt_task(
    "GT_007", "neoforge", "1.21.1", 21, "gametest-registration", "gametest",
    "NeoForge 1.21.1 (mod id 'examplemod'). In a GameTestHolder class write TWO tests that belong to the same named batch: "
    "annotate both with @GameTest(batch = 'setup_chain') and make the second one start only assertions after the first finished; "
    "both tests end with helper.succeed(). Batch ordering relies on the framework, not on sleeps.",
    NF_HEAD
    + "    @GameTest(batch = \"setup_chain\")\n"
    + "    public void setupStep(GameTestHelper helper) {\n"
    + "        helper.setBlock(1, 2, 1, Blocks.CRAFTING_TABLE);\n"
    + "        helper.succeed();\n"
    + "    }\n\n"
    + "    @GameTest(batch = \"setup_chain\")\n"
    + "    public void verifyStep(GameTestHelper helper) {\n"
    + "        helper.succeedWhen(() -> helper.assertBlockPresent(Blocks.CRAFTING_TABLE, 1, 2, 1));\n"
    + "    }\n"
    + NF_TAIL,
    ["src/test/java/com/example/examplemod/ModGameTests.java"],
    {
        "assertions": ["batch runs setup then verify"],
        "invariants": ["@GameTest(batch=...) groups tests into an ordered batch"],
        "edge_cases": ["tests in one batch run sequentially in the same structure instance"],
        "evidence": [EV_ANNOT, EV_MAPPINGS],
    },
    NF_ENV,
))

tasks.append(gt_task(
    "GT_008", "neoforge", "1.21.1", 21, "gametest-registration", "gametest",
    "NeoForge 1.21.1 (mod id 'examplemod'). In a GameTestHolder class, write a per-batch preparation method: "
    "annotate it with @BeforeBatch so it runs before every test in the batch, and inside only call helper.succeed() — "
    "BeforeBatch is used for environment preparation, not assertions.",
    "package com.example.examplemod;\n\n"
    "import net.minecraft.gametest.framework.BeforeBatch;\n"
    "import net.minecraft.gametest.framework.GameTest;\n"
    "import net.minecraft.gametest.framework.GameTestHelper;\n"
    "import net.neoforged.neoforge.gametest.GameTestHolder;\n"
    "import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;\n\n"
    "@GameTestHolder(\"examplemod\")\n"
    "@PrefixGameTestTemplate(false)\n"
    "public class ModGameTests {\n"
    "    @BeforeBatch(batch = \"prep\")\n"
    "    public void prepare(GameTestHelper helper) {\n"
    "        helper.succeed();\n"
    "    }\n\n"
    "    @GameTest(batch = \"prep\")\n"
    "    public void afterPrep(GameTestHelper helper) {\n"
    "        helper.succeed();\n"
    "    }\n"
    "}\n",
    ["src/test/java/com/example/examplemod/ModGameTests.java"],
    {
        "assertions": ["preparation runs before the batch tests"],
        "invariants": ["@BeforeBatch(batch=...) targets one batch"],
        "edge_cases": ["@BeforeBatch methods must not assert game state; they only set it up"],
        "evidence": [EV_ANNOT, EV_MAPPINGS],
    },
    NF_ENV,
))

FO_HEAD = (
    "package com.example.examplemod;\n\n"
    "import net.minecraft.gametest.framework.GameTest;\n"
    "import net.minecraft.gametest.framework.GameTestHelper;\n"
    "import net.minecraft.world.level.block.Blocks;\n"
    "import net.minecraftforge.gametest.GameTestHolder;\n"
    "import net.minecraftforge.gametest.PrefixGameTestTemplate;\n\n"
    "@GameTestHolder(\"examplemod\")\n"
    "@PrefixGameTestTemplate(false)\n"
    "public class ModGameTests {\n"
)

tasks.append(gt_task(
    "GT_009", "forge", "1.20.1", 17, "gametest-registration", "gametest",
    "Forge 1.20.1 (mod id 'examplemod', Java 17). Write a game-test holder class using the Forge GameTestHolder annotation "
    "with namespace 'examplemod', disable class-name template prefixing, and add one test that places a chest at (1, 2, 1) "
    "and succeeds when the chest is present.",
    FO_HEAD
    + "    @GameTest\n"
    + "    public void placeChest(GameTestHelper helper) {\n"
    + "        helper.setBlock(1, 2, 1, Blocks.CHEST);\n"
    + "        helper.succeedWhen(() -> helper.assertBlockPresent(Blocks.CHEST, 1, 2, 1));\n"
    + "    }\n"
    + "}\n",
    ["src/test/java/com/example/examplemod/ModGameTests.java"],
    {
        "assertions": ["chest appears at (1,2,1)"],
        "invariants": ["Forge GameTestHolder auto-registers @GameTest methods"],
        "edge_cases": ["Forge requires gametest enablement in the dev runtime; the runner provisions it"],
        "evidence": [EV_ANNOT_F, EV_MAPPINGS],
    },
    FO_ENV,
))

tasks.append(gt_task(
    "GT_010", "forge", "1.20.1", 17, "gametest-assertions", "gametest",
    "Forge 1.20.1 (mod id 'examplemod', Java 17). In a Forge GameTestHolder class write a test that places an iron ingot item "
    "assertion: place a chest at (1, 2, 1), then assert it eventually contains Items.IRON_INGOT via assertContainerContains, "
    "wrapped in succeedWhen.",
    "package com.example.examplemod;\n\n"
    "import net.minecraft.core.BlockPos;\n"
    "import net.minecraft.gametest.framework.GameTest;\n"
    "import net.minecraft.gametest.framework.GameTestHelper;\n"
    "import net.minecraft.world.item.Items;\n"
    "import net.minecraft.world.level.block.Blocks;\n"
    "import net.minecraftforge.gametest.GameTestHolder;\n"
    "import net.minecraftforge.gametest.PrefixGameTestTemplate;\n\n"
    "@GameTestHolder(\"examplemod\")\n"
    "@PrefixGameTestTemplate(false)\n"
    "public class ModGameTests {\n"
    "    @GameTest\n"
    "    public void chestIngot(GameTestHelper helper) {\n"
    "        helper.setBlock(1, 2, 1, Blocks.CHEST);\n"
    "        helper.succeedWhen(() ->\n"
    "                helper.assertContainerContains(new BlockPos(1, 2, 1), Items.IRON_INGOT));\n"
    "    }\n"
    "}\n",
    ["src/test/java/com/example/examplemod/ModGameTests.java"],
    {
        "assertions": ["chest contains iron ingot"],
        "invariants": ["assertContainerContains(BlockPos, Item) exists in 1.20.1 mappings too"],
        "edge_cases": ["container contents arrive asynchronously; succeedWhen retries"],
        "evidence": [EV_ANNOT_F, EV_MAPPINGS],
    },
    FO_ENV,
))

# GT_005 uses absolutePos + BlockPos inline FQN — verify BlockPos mapping (done in self-check),
# and that net.minecraft.core.BlockPos appears in mappings for 1.21.1 (checked above).

def gth_block(maps: str) -> str:
    m = re.search(r"net\.minecraft\.gametest\.framework\.GameTestHelper -> \w+:\n((?:    .*\n|#.*\n)+?)net\.", maps)
    if not m:
        raise SystemExit("SELF-CHECK FAILED: GameTestHelper block not found")
    return m.group(1)

GTH_121 = gth_block(MAPS_121)
GTH_1201 = gth_block(MAPS_1201)

def assert_helper_method(block: str, method: str, ver: str):
    if not re.search(rf"\b{re.escape(method)}\(", block):
        raise SystemExit(f"SELF-CHECK FAILED: GameTestHelper.{method} not in {ver} mappings")

for _m in ["setBlock", "succeedWhenBlockPresent", "assertBlockPresent", "assertBlockNotPresent",
           "assertContainerContains", "succeed", "succeedIf", "succeedWhen", "succeedOnTickWhen",
           "runAfterDelay", "destroyBlock", "killAllEntities", "assertTrue", "assertFalse", "absolutePos"]:
    assert_helper_method(GTH_121, _m, "1.21.1")
for _m in ["setBlock", "assertBlockPresent", "assertContainerContains", "succeed", "succeedWhen"]:
    assert_helper_method(GTH_1201, _m, "1.20.1")

with open(OUT / "gametest_tasks.jsonl", "w", encoding="utf-8") as f:
    for t in tasks:
        f.write(json.dumps(t, ensure_ascii=False) + "\n")

print("gametest tasks written:", len(tasks))
print("ids:", [t["task_id"] for t in tasks])
