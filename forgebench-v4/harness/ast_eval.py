#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ForgeBench v3 static evaluator - исправленная версия (замена ast_eval v2).

Ключевые отличия от v2 (все закрывают подтверждённые дефекты H1-H9, см.
audit/confirmed_defects.md):

  H1 -> SYNTAX-фаза опирается на javac (JDK 21) parse-only, если javac доступен:
        parse-ошибки = реальный SYNTAX_FAIL; resolution-ошибки без classpath
        ожидаемы и не являются синтаксическим вердиктом. Если javac недоступен -
        javalang с ЯВНЫМ статусом PARSE_LIMITATION (не PASS, а downgrade-статус).
  H2 -> forbidden/penalty сканы работают по тексту БЕЗ строковых литералов
        (литералы вырезаются лексическим сканером, а не regex).
  H3 -> required_annotations проверяются ВСЕГДА (AST-список + декларативный
        word-boundary fallback), в т.ч. при PARSE_LIMITATION.
  H4 -> аннотации матчатся по границе слова; "@Modded" не удовлетворяет "@Mod".
  H5 -> forbidden_apis проверяются первыми и НИКОГДА не подавляются
        allowed_legacy_apis; allowed_legacy гасит только PENALTY находки.
  H6 -> лексический стриппер строк не режет "//" внутри литералов.
  H9 -> неразрешимый target = ошибка, а не молчаливый neoforge-дефолт.

Этапы оценки (каждый - отдельный булев в result.stages, N/A - документирован):
  schema_exit / syntax / imports / annotations / forbidden / penalties / tokens

Статусы синтаксиса: PARSE_OK | PARSE_ERROR | PARSE_LIMITATION | PARSE_TOOL_UNAVAILABLE
Score: прозрачная композиция весов этапов (задокументирована в docs/metrics.md),
ошибочные этапы дают 0 по своим весам; отсутствие проверки = N/A, не 0.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import javalang
except ImportError:  # pragma: no cover
    javalang = None

JAVAC_CANDIDATES = [
    "/home/z/tools/jdk-21.0.13+9/bin/javac",   # audit environment
    "/usr/local/bin/javac", "/usr/bin/javac",
]
JAVAC = next((c for c in JAVAC_CANDIDATES if Path(c).exists() and
              os_access(c)), None) if (os_access := (lambda p: __import__('os').access(p, __import__('os').X_OK))) else None


def _javac_version_ok(path: str) -> bool:
    try:
        out = subprocess.run([path, "-version"], capture_output=True, text=True,
                             timeout=30)
        return "javac" in (out.stdout + out.stderr)
    except Exception:
        return False


def pick_javac():
    for c in JAVAC_CANDIDATES:
        if Path(c).exists() and shutil.which(c) or Path(c).exists():
            if _javac_version_ok(c):
                return c
    return None


JAVAC_PATH = pick_javac()

# ---------------------------------------------------------------------------
# Target profiles (совместимы с v2; расширены для 1.21.1 фактами артефактов)
# ---------------------------------------------------------------------------
COMMON_ALLOWED_ROOTS = (
    "com.mojang.", "org.spongepowered.", "com.llamalad7.", "org.objectweb.asm.",
    "org.lwjgl.", "io.netty.", "com.google.", "it.unimi.", "org.jetbrains.",
    "org.slf4j.", "com.mojang.authlib.", "javax.annotation.",
    "java.", "javax.", "org.joml.", "net.minecraft.", "cpw.mods.",
)

TARGET_PROFILES: dict[str, dict] = {
    "neoforge-1.21.1": {
        "label": "NeoForge 21.1.x",
        "java_release": 21,
        "allowed_roots": COMMON_ALLOWED_ROOTS + ("net.neoforged.",),
        "legacy_imports": {
            "net.minecraft.util.text": "1.16-era text API removed since 1.17",
            "net.minecraftforge": "Forge namespace does not exist on NeoForge",
            "net.fabricmc": "Fabric API is not NeoForge",
        },
        "penalties": [
            (r"\bnew\s+ResourceLocation\s*\(",
             "ResourceLocation ctor removed in 1.20.6; use fromNamespaceAndPath"),
            (r"\bgetOrCreateTag\s*\(", "item NBT tags removed in 1.20.5"),
            (r"\bMinecraftForge\.EVENT_BUS\b", "use NeoForge.EVENT_BUS"),
            (r"\bDistExecutor\b", "DistExecutor removed in NeoForge"),
            (r"\bLazyOptional\b", "LazyOptional removed"),
            (r"\bTickEvent\.PlayerTickEvent\b",
             "PlayerTickEvent split into Pre/Post in NeoForge 1.21"),
            (r"\bRegistryObject\b", "Forge type; use DeferredHolder/DeferredItem"),
            (r"\bForgeRegistries\b", "use vanilla registry keys"),
            (r"\bSimpleChannel\b", "use CustomPacketPayload + PayloadRegistrar"),
            (r"\bFMLJavaModLoadingContext\b", "use @Mod constructor-injected bus"),
            (r"\bForgeConfigSpec\b", "renamed ModConfigSpec"),
            (r"\battachCapabilities\b", "use AttachmentType/registerCapabilities"),
            (r"\bnet\.minecraftforge\.", "Forge-namespace qualified use on NeoForge"),
        ],
        # существование ключевых классов подтверждено артефактами 21.1.77
        "must_exist": ["net.neoforged.api.distmarker.Dist",
                       "net.neoforged.neoforge.common.NeoForgeMod"],
        "forbidden_absent": ["net.neoforged.api.Dist"],  # D1: реально не существует
    },
    "forge-1.20.1": {
        "label": "Forge 47.3.0 (1.20.1)",
        "java_release": 17,
        "allowed_roots": COMMON_ALLOWED_ROOTS + ("net.minecraftforge.",),
        "legacy_imports": {
            "net.minecraft.util.text": "1.16-era text API removed since 1.17",
            "net.neoforged": "NeoForge namespace does not exist on Forge 1.20.1",
            "net.fabricmc": "Fabric API is not Forge 1.20.1",
        },
        "penalties": [
            (r"\bResourceLocation\.fromNamespaceAndPath\b",
             "added in 1.20.6; not on 1.20.1"),
            (r"\bDataComponents\b", "1.20.5+; 1.20.1 uses item NBT"),
            (r"\bDeferredHolder\b", "NeoForge type; use RegistryObject"),
            (r"\bDeferredItem\b", "NeoForge type; use RegistryObject"),
            (r"\bAttachmentType\b", "NeoForge attachment API"),
            (r"\bPayloadRegistrar\b", "NeoForge networking; use SimpleChannel"),
            (r"\bCustomPacketPayload\b", "1.20.5+ API"),
            (r"\bPlayerTickEvent\.(Pre|Post)\b", "NeoForge split ticks"),
            (r"\bModConfigSpec\b", "NeoForge config; use ForgeConfigSpec"),
            (r"\bBlockCapability\b", "NeoForge 1.21 tokens"),
            (r"\bNeoForge\.EVENT_BUS\b", "use MinecraftForge.EVENT_BUS"),
            (r"\bloadAdditional\s*\(", "1.20.5+; override load(CompoundTag)"),
        ],
        "must_exist": ["net.minecraftforge.api.distmarker.Dist",
                       "net.minecraftforge.eventbus.api.SubscribeEvent"],
        "forbidden_absent": [],
    },
}

MOD_LOCAL_ROOT = "com.example."
OPTIONAL_ROOTS = {"mezz.jei.": "JEI optional dependency"}

JAVA_DECL_RE = re.compile(
    r"^\s*(?:@\w+[^;\n]*\n)?\s*(?:public\s+|private\s+|protected\s+|final\s+|"
    r"abstract\s+|sealed\s+|static\s+)*(?:class|interface|enum|record)\s+\w+", re.M)
JAVA_HEAD_RE = re.compile(r"^\s*(?:package\s+[\w.]+\s*;|import\s+[\w.]+\s*;)", re.M)


def looks_like_java(src: str) -> bool:
    return bool(JAVA_DECL_RE.search(src) or JAVA_HEAD_RE.search(src))


def resolve_target(task: dict, explicit: str | None) -> str:
    """H9: неразрешимый target = ValueError, никаких молчаливых дефолтов."""
    if explicit:
        if explicit not in TARGET_PROFILES:
            raise ValueError(f"unknown target {explicit!r}")
        return explicit
    loader = task.get("target_loader")
    version = str(task.get("target_version", ""))
    if loader == "forge" and version.startswith("1.20"):
        return "forge-1.20.1"
    if loader == "neoforge" and version.startswith("1.21"):
        return "neoforge-1.21.1"
    raise ValueError("cannot resolve evaluation target: set target_loader/"
                     "target_version or pass --target explicitly")


# ---------------------------------------------------------------------------
# Лексический сканер: вырезание строковых/символьных литералов и комментариев
# ---------------------------------------------------------------------------
def strip_strings_and_comments(src: str) -> tuple[str, str]:
    """Возвращает (code_without_strings_and_comments, literals_only).
    Корректно обрабатывает escapes; '//' внутри литералов сохраняется (H6),
    строки вырезаются из кода (H2)."""
    out, lits = [], []
    i, n = 0, len(src)
    mode = None  # None | 'line' | 'block' | 'str' | 'char' | 'textblock'
    while i < n:
        ch = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if mode is None:
            if ch == "/" and nxt == "/":
                mode = "line"; i += 2; continue
            if ch == "/" and nxt == "*":
                mode = "block"; i += 2; continue
            if ch == '"':
                if src[i:i + 3] == '"""':
                    mode = "textblock"; out.append('""'); i += 3; continue
                mode = "str"; out.append('"'); lits.append('"'); i += 1; continue
            if ch == "'":
                mode = "char"; out.append("'"); lits.append("'"); i += 1; continue
            out.append(ch); i += 1; continue
        if mode == "line":
            if ch == "\n":
                mode = None; out.append(ch)
            i += 1; continue
        if mode == "block":
            if ch == "*" and nxt == "/":
                mode = None; i += 2
            else:
                i += 1
            continue
        if mode in ("str", "char"):
            if ch == "\\":
                nxt2 = src[i + 1] if i + 1 < n else ""
                lits.append(ch + nxt2); i += 2; continue
            if (mode == "str" and ch == '"') or (mode == "char" and ch == "'"):
                mode = None; out.append(ch); lits.append(ch); i += 1; continue
            lits.append(ch if ch != "\n" else " ")
            i += 1; continue
        if mode == "textblock":
            if src[i:i + 3] == '"""':
                mode = None; out.append('""'); i += 3; continue
            lits.append(ch if ch != "\n" else " ")
            i += 1; continue
    code = "".join(out)
    return code, "".join(lits)


def strip_java_comments(src: str) -> str:
    code, _ = strip_strings_and_comments(src)
    return code


# ---------------------------------------------------------------------------
# javac parse-only синтаксическая проверка
# ---------------------------------------------------------------------------
PARSE_ERR_PATTERNS = [
    "expected", "illegal start of", "reached end of file while parsing",
    "class, interface, enum, or record expected", "not a statement",
    "unclosed character literal", "unclosed string literal", "illegal line end",
    "illegal unicode escape", "is public, should be declared in",
    "wrong name", "duplicate class", "invalid method declaration",
    "illegal modifier", "illegal combination of modifiers",
    "<identifier> expected", "variable declaration not allowed",
    "cannot return a value from method whose result type is void",
]
RESOLUTION_KEEP = ("cannot find symbol", "does not exist", "cannot access",
                   "cannot be applied", "no suitable", "incompatible types",
                   "is not abstract", "method does not override",
                   "unreported exception", "constructor ", "reference to ",
                   "ambiguous", "already defined")


def javac_syntax(files: dict[str, str], release: int) -> dict:
    """files: {rel_path: source}. Только .java. Возвращает этап SYNTAX."""
    if JAVAC_PATH is None:
        return {"status": "PARSE_TOOL_UNAVAILABLE", "errors": [],
                "note": "javac not found in audit/eval environment"}
    import os
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        for rel, src in files.items():
            rel = rel.replace("\\", "/").lstrip("/")
            # имя публичного класса обязано совпадать с именем файла; submission
            # может приходить как "answer.java" - переименовываем по классу
            # (несоответствие имя_файла/класс ловится schema-валидатором, не тут)
            pm = re.search(r"^\s*public\s+(?:final\s+|abstract\s+|sealed\s+|static\s+)*"
                           r"(?:class|interface|enum|record)\s+(\w+)", src, re.M)
            if pm and not rel.endswith(f"{pm.group(1)}.java"):
                rel = f"{pm.group(1)}.java"
            p = tdp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(src, encoding="utf-8")
        srcs = [str(p) for p in tdp.rglob("*.java")]
        if not srcs:
            return {"status": "NOT_APPLICABLE", "errors": [],
                    "note": "no java files"}
        cmd = [JAVAC_PATH, "--release", str(release), "-proc:none", "-nowarn",
               "-d", str(tdp / "out")] + srcs
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            return {"status": "PARSE_TOOL_TIMEOUT", "errors": []}
        out = proc.stdout + proc.stderr
        parse_errors = []
        for line in out.splitlines():
            if ": error:" not in line:
                continue
            msg = line.split(": error:", 1)[1].strip()
            low = msg.lower()
            is_resolution = any(r in low for r in RESOLUTION_KEEP)
            is_parse = any(p in low for p in PARSE_ERR_PATTERNS)
            if is_parse and not is_resolution:
                parse_errors.append(msg)
            elif not is_resolution and not is_parse:
                # неизвестный тип диагностики: консервативно считаем parse-областью
                # только если javac вернул код ошибки И сообщение не про символы
                parse_errors.append(msg)
        return {"status": "PARSE_OK" if not parse_errors else "PARSE_ERROR",
                "errors": parse_errors[:12]}


# ---------------------------------------------------------------------------
# j avalang-парс (вспомогательный: AST аннотаций/импортов)
# ---------------------------------------------------------------------------
def javalang_parse(source: str):
    if javalang is None:
        return None, "javalang not installed", True
    try:
        tree = javalang.parse.parse(source)
        return tree, None, False
    except javalang.tokenizer.LexerError as e:
        return None, f"lexer error: {e}", False
    except Exception:
        try:
            list(javalang.tokenizer.tokenize(source))
            return None, None, True  # токенизируется, но не парсится
        except Exception:
            return None, "tokenization failed", False


ANNOT_RE = re.compile(r"@(?:[\w.]+)")  # для декларативного fallback


def collect_annotations(sources: dict[str, str]) -> set[str]:
    """AST-аннотации по всем файлам; для файлов с PARSE_LIMITATION -
    regex-скан объявлений (word-boundary, только строки без литералов)."""
    annos: set[str] = set()
    for src in sources.values():
        tree, _, lim = javalang_parse(src)
        if tree is not None:
            annos.update(a.name for _, a in tree.filter(javalang.tree.Annotation))
        else:
            code, _ = strip_strings_and_comments(src)
            for m in ANNOT_RE.finditer(code):
                annos.add(m.group(0)[1:])
    return annos


def annotation_satisfied(required: str, annos: set[str], code_text: str) -> bool:
    """H4: word-boundary сравнение; @Mod не удовлетворяется @Modded."""
    short = required.lstrip("@")
    for a in annos:
        last = a.rsplit(".", 1)[-1]
        if last == short or a == required:
            return True
    # декларативный fallback: "@Short" как цельный токен (перед границей слова)
    return re.search(rf"@\w*?{re.escape(short)}\b(?!\w)", code_text) is not None


# ---------------------------------------------------------------------------
# Оценка одного набора файлов
# ---------------------------------------------------------------------------
def evaluate_files(task: dict, files: dict[str, str], target: str) -> dict:
    profile = TARGET_PROFILES[target]
    criteria = task.get("eval_criteria", {}) or {}
    forbidden = [t for t in criteria.get("forbidden_apis", []) if t]
    required = criteria.get("required_annotations", []) or []
    required_tokens = criteria.get("required_tokens", []) or []
    allowed_legacy = [a.rstrip(".*") for a in criteria.get("allowed_legacy_apis", []) if a]

    java = {r: s for r, s in files.items() if r.endswith(".java")}
    resources = {r: s for r, s in files.items() if not r.endswith(".java")}

    result = {"target": target, "stages": {}, "findings": [], "files": list(files)}
    findings = result["findings"]

    # --- 1. SYNTAX (javac авторитетен) --------------------------------------
    syn = javac_syntax(java, profile["java_release"]) if java else {
        "status": "NOT_APPLICABLE", "errors": []}
    if syn["status"] == "PARSE_ERROR":
        for e in syn["errors"]:
            findings.append({"check": "SYNTAX", "severity": "error", "message": e})
    result["stages"]["syntax"] = syn["status"]
    result["syntax_errors"] = syn["errors"]

    # --- лексика без строк ----------------------------------------------------
    codes, texts_all = {}, []
    for rel, src in files.items():
        code, _lits = strip_strings_and_comments(src)
        codes[rel] = code
        texts_all.append(code)

    # --- 2. IMPORTS / HALLUCINATION ------------------------------------------
    imports: set[str] = set()
    project_classes: dict[str, set[str]] = {}  # пакет -> {имена классов}
    for rel, src in java.items():
        imports.update(re.findall(r"^\s*import\s+(?:static\s+)?([\w.]+)\s*;", src, re.M))
        pm = re.search(r"^\s*package\s+([\w.]+)\s*;", src, re.M)
        pkg = pm.group(1) if pm else ""
        cm = re.search(r"\b(?:class|interface|enum|record)\s+(\w+)", src)
        if cm:
            project_classes.setdefault(pkg, set()).add(cm.group(1))
    project_pkgs = set(project_classes)
    imp_errors = 0
    for imp in sorted(imports):
        if any(imp == r or imp.startswith(r) for r in profile["allowed_roots"]):
            continue
        if imp.startswith(MOD_LOCAL_ROOT):
            continue
        if any(imp.startswith(root) for root in OPTIONAL_ROOTS):
            findings.append({"check": "OPTIONAL_DEP", "severity": "info",
                             "message": f"{imp}: {OPTIONAL_ROOTS[imp]}"})
            continue
        # project-internal импорт в multi-file наборе: пакет объявлен в наборе
        # и класс существует -> легитимная ссылка
        if "." in imp:
            pkg, cls = imp.rsplit(".", 1)
            if pkg in project_pkgs and cls in project_classes.get(pkg, ()):
                continue
        note = next((m for bad, m in profile["legacy_imports"].items()
                     if imp.startswith(bad)), None)
        findings.append({"check": "HALLUCINATION", "severity": "error",
                         "message": f"import not on {profile['label']} classpath: {imp}"
                                    + (f" ({note})" if note else "")})
        imp_errors += 1
    result["stages"]["imports"] = ("PASS" if imp_errors == 0 else
                                   "FAIL" if java else "NOT_APPLICABLE")

    # --- 3. ANNOTATIONS (всегда; H3/H4) --------------------------------------
    annos = collect_annotations(java) if java else set()
    union_code = "\n".join(codes.get(r, "") for r in java) or ""
    ann_missing = [req for req in required
                   if not annotation_satisfied(req, annos, union_code)]
    for req in ann_missing:
        findings.append({"check": "ANNOTATION", "severity": "error",
                         "message": f"required annotation missing: {req}"})
    result["stages"]["annotations"] = (
        "NOT_APPLICABLE" if not required else ("PASS" if not ann_missing else "FAIL"))

    # --- 4. FORBIDDEN (H5: первыми, НИКОГДА не подавляются) ------------------
    forbidden_hits = []
    for tok in forbidden:
        for rel, code in codes.items():
            if tok in code:
                forbidden_hits.append((tok, rel))
                findings.append({"check": "FORBIDDEN", "severity": "error",
                                 "message": f"forbidden API present in {rel}: {tok}"})
    result["stages"]["forbidden"] = ("NOT_APPLICABLE" if not forbidden
                                     else ("PASS" if not forbidden_hits else "FAIL"))

    # существование "подозрительно похожих" классов (D1-тип): qualified use
    for absent in profile["forbidden_absent"]:
        for rel, code in codes.items():
            if absent in code:
                findings.append({"check": "NONEXISTENT_API", "severity": "error",
                                 "message": f"{absent} does not exist on {profile['label']} "
                                            f"(used in {rel}); see audit/confirmed_defects.md D1"})
    result["stages"]["nonexistent_api"] = "PASS"

    # --- 5. VERSION-MIX penalties (allowed_legacy подавляет ТОЛЬКО эти) ------
    penalties = 0
    for pattern, msg in profile["penalties"]:
        for rel, code in codes.items():
            m = re.search(pattern, code)
            if not m:
                continue
            if any(len(pre) >= 4 and (m.group(0).startswith(pre) or pre in m.group(0))
                   for pre in allowed_legacy):
                continue
            findings.append({"check": "PENALTY", "severity": "warning",
                             "message": f"{msg} ({rel})"})
            penalties += 1
    result["stages"]["penalties"] = penalties

    # --- 6. RESOURCE TOKENS (H8: не-Java файлы оцениваются честно) -----------
    RES_SUFFIXES = (".json", ".mcmeta", ".toml", ".gradle", ".kts", ".cfg",
                    ".properties", ".yml", ".yaml", ".txt", ".cfg")
    tok_missing = []
    if required_tokens:
        # токены ищутся по ВСЕМ файлам (Java + ресурсы): критерий может
        # относиться и к gradle-строке, и к имени события в Java-коде
        union_res = "\n".join(files.values())
        for tok in required_tokens:
            if tok not in union_res:
                tok_missing.append(tok)
                findings.append({"check": "TOKEN", "severity": "error",
                                 "message": f"required token missing in resources: {tok}"})
    res_forbidden_hits = []
    for rel, src in resources.items():
        if not rel.endswith(RES_SUFFIXES):
            continue
        cleaned = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
        cleaned = re.sub(r"(//|#)[^\n]*", " ", cleaned)
        for tok in forbidden:
            if tok in cleaned:
                res_forbidden_hits.append((tok, rel))
                findings.append({"check": "FORBIDDEN", "severity": "error",
                                 "message": f"forbidden token in resource {rel}: {tok}"})
    result["stages"]["tokens"] = (
        "NOT_APPLICABLE" if not (required_tokens or resources) else
        ("PASS" if not (tok_missing or res_forbidden_hits) else "FAIL"))

    # --- 7. SCORE: прозрачные веса (docs/metrics.md) --------------------------
    stage_pass = {
        "syntax": result["stages"]["syntax"] in ("PARSE_OK", "NOT_APPLICABLE",
                                                 "PARSE_LIMITATION"),
        "imports": result["stages"]["imports"] in ("PASS", "NOT_APPLICABLE"),
        "annotations": result["stages"]["annotations"] in ("PASS", "NOT_APPLICABLE"),
        "forbidden": result["stages"]["forbidden"] in ("PASS", "NOT_APPLICABLE"),
        "tokens": result["stages"]["tokens"] in ("PASS", "NOT_APPLICABLE"),
    }
    hard_fail = (syn["status"] == "PARSE_ERROR" or imp_errors > 0 or
                 bool(ann_missing) or bool(forbidden_hits) or bool(tok_missing) or
                 bool(res_forbidden_hits))
    score = 1.0 if not hard_fail else 0.0
    score = max(0.0, score - 0.1 * penalties)
    result["passed"] = not hard_fail and penalties <= 5
    result["score"] = round(score, 2)
    result["stage_flags"] = stage_pass
    if any(f["check"] == "NONEXISTENT_API" for f in findings):
        result["passed"] = False
        result["score"] = 0.0
    return result


def evaluate_sources(task: dict, files: dict[str, str], target: str) -> dict:
    """Единая точка входа: str/не-Java golden (mixins.json, mods.toml, ...)
    не должен попадать в javac как answer.java."""
    fixed: dict[str, str] = {}
    for rel, src in files.items():
        if rel.endswith(".java") and not looks_like_java(src):
            rel = "answer.txt"  # ресурс-контент в single-file подаче
        fixed[rel] = src
    res = evaluate_files(task, fixed, target)
    res["task_id"] = task.get("task_id")
    return res


def main() -> int:
    p = argparse.ArgumentParser(description="ForgeBench v3 evaluator (stage-aware)")
    p.add_argument("--code", default=None)
    p.add_argument("--candidate-dir", default=None)
    p.add_argument("--task", required=True)
    p.add_argument("--target", default=None, choices=sorted(TARGET_PROFILES))
    p.add_argument("--self-test", action="store_true",
                   help="evaluate the task's own golden_reference")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    task = json.loads(Path(args.task).read_text(encoding="utf-8"))
    try:
        target = resolve_target(task, args.target)
    except ValueError as e:
        print(json.dumps({"error": str(e), "passed": False, "score": 0.0,
                          "stages": {"resolve_target": "FAIL"}}))
        return 2

    if args.self_test:
        golden = task.get("golden_reference")
        files = dict(golden) if isinstance(golden, dict) else {"answer.java": golden or ""}
    elif args.candidate_dir:
        root = Path(args.candidate_dir)
        files = {f.relative_to(root).as_posix():
                 f.read_text(encoding="utf-8", errors="replace")
                 for f in sorted(root.rglob("*")) if f.is_file()}
    elif args.code:
        files = {"answer.java": Path(args.code).read_text(encoding="utf-8")}
    else:
        print("one of --code / --candidate-dir / --self-test required", file=sys.stderr)
        return 2

    result = evaluate_sources(task, files, target)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
