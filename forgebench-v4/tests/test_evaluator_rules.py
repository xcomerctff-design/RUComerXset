#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ForgeBench v3 - тесты правил оценщика (ЭТАП 3, требование ТЗ).

Каждое правило оценщика имеет позитивные и негативные тесты, включая:
строки/комментарии, qualified-имена, generic-типы, вложенные классы,
перегрузки (на уровне статики - сигнатурные токены), мультифайл,
аннотации, forbidden/allowed взаимодействие, javac-синтаксис.

Запуск: python3 tests/test_evaluator_rules.py   (exit 0 = все тесты пройдены)
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "harness"))
import ast_eval as ev  # noqa: E402

PASS, FAIL = 0, []


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        FAIL.append(name)
        print(f" FAIL {name} {detail}")


def nf_task(**ec):
    base = {"task_id": "T", "module": "api", "target_loader": "neoforge",
            "target_version": "1.21.1", "task_scope": "single_file",
            "instruction": "t", "context": "", "golden_reference": ""}
    base["eval_criteria"] = {"must_compile": True, "required_annotations": [],
                             "forbidden_apis": [], "allowed_legacy_apis": [],
                             "gametest_required": False}
    base["eval_criteria"].update(ec)
    return base


def forge_task(**ec):
    t = nf_task(**ec)
    t["target_loader"], t["target_version"] = "forge", "1.20.1"
    return t


def run(task, code, files=None):
    return ev.evaluate_sources(task, files or {"answer.java": code},
                               ev.resolve_target(task, None))


# --- 1. SYNTAX ----------------------------------------------------------------
r = run(nf_task(), "package a;\nclass X { void f() { int x = ; } }\n")
check("syntax: javac ловит broken code",
      r["stages"]["syntax"] == "PARSE_ERROR" and not r["passed"], r["stages"])
r = run(nf_task(), "package a;\npublic record P(int a, int b) {\n public int sum(){return a+b;}\n}\n")
check("syntax: record (Java 21) = PARSE_OK, а не PARSE_LIMITATION",
      r["stages"]["syntax"] == "PARSE_OK", r["stages"])
r = run(nf_task(), "package a;\nclass X { int f(int a) { return switch(a) { case 1 -> 2; default -> 0; }; } }\n")
check("syntax: switch expression = PARSE_OK", r["stages"]["syntax"] == "PARSE_OK", r["stages"])
r = run(nf_task(), "package a;\nclass X { void f() { String s = \"\"\"\nhello\"\"\"; } }\n")
check("syntax: text block = PARSE_OK", r["stages"]["syntax"] == "PARSE_OK", r["stages"])

# --- 2. FORBIDDEN в строках/комментариях (H2/H6) --------------------------------
r = run(nf_task(forbidden_apis=["net.minecraftforge"]),
        'package a;\nclass X { String s = "migrated from net.minecraftforge"; }\n')
check("forbidden: строковый литерал НЕ триггерит", r["passed"] is True, r["findings"])
r = run(nf_task(forbidden_apis=["net.minecraftforge"]),
        "package a;\n// см. net.minecraftforge docs\nclass X {}\n")
check("forbidden: комментарий НЕ триггерит", r["passed"] is True, r["findings"])
r = run(nf_task(forbidden_apis=["net.minecraftforge"]),
        "package a;\nimport net.minecraftforge.common.ForgeHooks;\nclass X {}\n")
check("forbidden: импорт триггерит", r["passed"] is False, r["findings"])
r = run(nf_task(forbidden_apis=["net.minecraftforge"]),
        'package a;\nclass X { String s = "a//b net.minecraftforge/x"; }\n')
check("forbidden: '//' внутри строки не ломает лексер (строка вырезана)",
      r["passed"] is True, r["findings"])
r = run(nf_task(forbidden_apis=["net.minecraftforge"]),
        "package a;\nclass X { int f(net.minecraftforge.common.ForgeHooks h) { return 0; } }\n")
check("forbidden: квалифицированное использование в коде триггерит",
      r["passed"] is False, r["findings"])

# --- 3. FORBIDDEN vs allowed_legacy (H5) ----------------------------------------
r = run(nf_task(forbidden_apis=["net.minecraftforge.eventbus.api.SubscribeEvent"],
                allowed_legacy_apis=["net.minecraftforge"]),
        "package a;\nclass X { void f() { var c = net.minecraftforge.eventbus.api.SubscribeEvent.class; } }\n")
check("forbidden НЕ подавляется allowed_legacy (квалифицированное имя)",
      r["passed"] is False, r["findings"])
r = run(forge_task(allowed_legacy_apis=["net.minecraftforge.*"],
                   forbidden_apis=["net.neoforged"]),
        "package a;\nimport net.minecraftforge.common.ForgeHooks;\nclass X {}\n")
check("forge: allowed_legacy гасит PENALTY, forbidden продолжает работать",
      r["passed"] is True and r["stages"]["forbidden"] == "PASS", r["findings"])

# --- 4. ANNOTATIONS (H3/H4) ------------------------------------------------------
r = run(nf_task(required_annotations=["@Mod"]),
        "package a;\npublic record R(int a) {}\n")
check("annotations: record без @Mod = FAIL (не пропускается)",
      r["stages"]["annotations"] == "FAIL", r["stages"])
r = run(nf_task(required_annotations=["@Mod"]),
        'package a;\n@Mod("x")\npublic record R(int a) {}\n')
check("annotations: @Mod на record = PASS", r["stages"]["annotations"] == "PASS", r["stages"])
r = run(nf_task(required_annotations=["@Mod"]),
        "package a;\n@Modded\npublic class X {}\n")
check("annotations: @Modded не удовлетворяет @Mod",
      r["stages"]["annotations"] == "FAIL", r["stages"])
r = run(nf_task(required_annotations=["@Mod.EventBusSubscriber"]),
        "package a;\n@Mod.EventBusSubscriber\npublic class X {}\n")
check("annotations: composite token = PASS", r["stages"]["annotations"] == "PASS", r["stages"])
r = run(nf_task(required_annotations=["@SubscribeEvent"]),
        "package a;\nimport net.neoforged.bus.api.SubscribeEvent;\nclass X {\n  @SubscribeEvent void f(ExampleEvent e) {}\n}\n")
check("annotations: @SubscribeEvent с импортом = PASS",
      r["stages"]["annotations"] == "PASS", r["stages"])

# --- 5. IMPORTS allowlist / классификация целей ---------------------------------
r = run(nf_task(), "package a;\nimport net.neoforged.api.distmarker.Dist;\nclass X {}\n")
check("imports: distmarker.Dist на NeoForge = PASS (реальное местоположение)",
      r["stages"]["imports"] == "PASS", r["findings"])
r = run(nf_task(), "package a;\nimport net.neoforged.api.Dist;\nclass X {}\n")
check("imports: net.neoforged.api.Dist (D1) = FAIL nonexistent_api",
      any(f["check"] == "NONEXISTENT_API" for f in r["findings"]), r["findings"])
r = run(nf_task(), "package a;\nimport com.example.examplemod.Config;\nclass X {}\n")
check("imports: mod-local пакет разрешён", r["stages"]["imports"] == "PASS", r["findings"])
r = run(forge_task(), "package a;\nimport net.minecraftforge.common.ForgeHooks;\nclass X {}\n")
check("imports: forge-native на forge-таргете = PASS",
      r["stages"]["imports"] == "PASS", r["findings"])
r = run(forge_task(), "package a;\nimport net.neoforged.fml.common.Mod;\nclass X {}\n")
check("imports: neoforge-импорт на forge = FAIL",
      r["stages"]["imports"] == "FAIL", r["findings"])
try:
    ev.resolve_target({"target_loader": "x", "target_version": "9"}, None)
    check("resolve_target: неразрешимый = ValueError", False)
except ValueError:
    check("resolve_target: неразрешимый = ValueError", True)

# --- 6. PENALTIES и word-boundary ------------------------------------------------
r = run(nf_task(), "package a;\nclass X { int myRegistryObjectFactory; }\n")
check("penalty: слово внутри идентификатора не штрафуется",
      r["score"] == 1.0, r["findings"])
r = run(nf_task(), "package a;\nclass X { void f(RegistryObject<?> ro) {} }\n")
check("penalty: реальное использование RegistryObject штрафуется",
      any(f["check"] == "PENALTY" for f in r["findings"]), r["findings"])
r = run(nf_task(), 'package a;\nclass X { String doc = "RegistryObject was removed"; }\n')
check("penalty: строковый литерал не штрафуется", r["score"] == 1.0, r["findings"])

# --- 7. GENERICS / NESTED / OVERLOADS-токены -------------------------------------
r = run(nf_task(), "package a;\nclass X<T extends Comparable<T>> {\n  class Inner {}\n  <E> E pick(E a, E b) { return a; }\n  void f() { Inner i = new Inner(); var l = java.util.List.of(pick(1,2)); }\n}\n")
check("syntax: generics/nested/var = PARSE_OK", r["stages"]["syntax"] == "PARSE_OK", r["stages"])
r = run(nf_task(), "package a;\nclass X {\n  int f(String s){return 1;}\n  int f(Integer i){return 2;}\n}\n")
check("syntax: перегрузки = PARSE_OK", r["stages"]["syntax"] == "PARSE_OK", r["stages"])

# --- 8. MULTI-FILE ----------------------------------------------------------------
files = {
    "src/main/java/a/X.java": "package a;\nimport a.Y;\nclass X { int f(){ return new Y().g(); } }\n",
    "src/main/java/a/Y.java": "package a;\npublic class Y { public int g(){ return 1; } }\n",
    "src/main/resources/META-INF/neoforge.mods.toml": 'modLoader="javafml"\nloaderVersion="[4,)"\n[[mods]]\nmodId="x"\n',
}
r = run(nf_task(required_tokens=["modId"]), None, files=files)
check("multi-file: связный набор = PASS", r["passed"] is True, r["findings"])
r = run(nf_task(required_tokens=["modId=\"expected-id\""]), None, files=files)
check("multi-file: required-token отсутствие = FAIL",
      r["stages"]["tokens"] == "FAIL", r["stages"])
files_bad = {
    "src/main/java/a/X.java": "package a;\nclass X { int f(){ return new Y().g(; } }\n",
    "src/main/java/a/Y.java": "package a;\npublic class Y { public int g(){ return 1; } }\n",
}
r = run(nf_task(), None, files=files_bad)
check("multi-file: ошибка в ОДНОМ файле = PARSE_ERROR (все файлы вместе)",
      r["stages"]["syntax"] == "PARSE_ERROR", r["stages"])

# --- 9. resource forbidden ---------------------------------------------------------
files2 = {
    "src/main/java/a/X.java": "package a;\nclass X {}\n",
    "src/main/resources/build.gradle.kts": 'plugins { id("net.neoforged.moddev") }\ndependencies { implementation("net.minecraftforge.gradle:ForgeGradle:6.0") }\n',
}
r = run(nf_task(forbidden_apis=["net.minecraftforge"]), None, files=files2)
check("resource forbidden: активная forge-зависимость ловится",
      r["passed"] is False, r["findings"])
files2c = {
    "src/main/java/a/X.java": "package a;\nclass X {}\n",
    "src/main/resources/build.gradle.kts": 'plugins { id("net.neoforged.moddev") }\n/* миграция: был net.minecraftforge.gradle */\n',
}
r = run(nf_task(forbidden_apis=["net.minecraftforge"]), None, files=files2c)
check("resource forbidden: закомментированное упоминание НЕ ловится (FP-фикс)",
      r["passed"] is True, r["findings"])

# --- 10. javalang-only среда (javac недоступен) ------------------------------------
if ev.JAVAC_PATH is None:
    r = run(nf_task(), "package a;\nclass X { void f() { int x = ; } }\n")
    check("no-javac: статус PARSE_LIMITATION/не-PASS", r["stages"]["syntax"] != "PARSE_OK")

print(f"\n{PASS} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
