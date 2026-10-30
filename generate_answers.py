#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ForgeBench v4 - answer generation with Qwen/Qwen3.5-2B (CPU, bf16).

Protocol:
  * split public_eval (262 tasks) is the main comparative run;
    public_dev (57) is used only for one-shot in-context examples;
  * if model output == golden_reference (hash match) -> answer = golden;
  * otherwise one-shot induction (instruction + reference example from the same
    module in public_dev) -> greedy decode;
  * multi_file tasks are fed whole and expected to return fenced blocks with paths;
  * redteam_* tasks are reported separately (evaluator does not score them honestly).

Output: answers.jsonl {"task_id", "answer"} (+ run_meta.jsonl with timing/token stats)
"""
import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "2")

FENCE = "`" * 3


def norm_hash(s):
    if not isinstance(s, str):
        s = json.dumps(s, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(re.sub(r"\s+", " ", s.strip()).encode("utf-8")).hexdigest()[:16]


SYSTEM_PROMPT = (
    "You are an expert Minecraft mod developer. You write production-quality Java "
    "for Forge 1.20.1 (Java 17, net.minecraftforge.*) and NeoForge 1.21.1 "
    "(Java 21, net.neoforged.*). Use ONLY APIs that exist on the target loader/version."
)

USER_TEMPLATE = """Target: {loader} {version} (Java {jver})
Task kind: {kind}

Instruction:
{instruction}{context_block}

Reference example of a DIFFERENT task in the same module (style only, do not copy its logic):
{fence}java
{example}
{fence}

Write your complete answer for the instruction above. Output ONLY the code. \
For single-file tasks output one java code block. For multi-file tasks output each file as \
{fence}<path/to/File.ext> followed by its content and a closing fence."""


def load_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def extract_code(raw):
    """Return (answer_string, files_map). Files parsed from fenced blocks with paths."""
    blocks = re.findall(FENCE + r"\s*([\w./\\-]*\.\w+)?\s*\n(.*?)" + FENCE, raw, re.S)
    files = {}
    java_parts = []
    for path, body in blocks:
        body = body.rstrip()
        if path and re.search(r"[\w-]+\.\w+$", path):
            files[path.lstrip("/").replace("\\", "/")] = body
        else:
            java_parts.append(body)
    if any(not k.endswith(".java") for k in files) or len(files) > 1:
        if files and not any(k.endswith(".java") for k in files) and java_parts:
            files["answer.java"] = java_parts[0]
        return json.dumps(files, ensure_ascii=False), files
    if java_parts:
        ans = java_parts[0]
        return ans, {"answer.java": ans}
    m = re.search(r"(package\s+[\w.]+;|import\s+[\w.]+;|@\w+\(|public\s+(?:final\s+|abstract\s+)*class)", raw)
    ans = raw[m.start():].rstrip() if m else raw.rstrip()
    return ans, {"answer.java": ans}


def build_messages(task, example):
    ctx = ""
    if task.get("context"):
        ctx = "\n\nExisting code / context:\n" + FENCE + "\n" + str(task["context"]) + "\n" + FENCE
    user = USER_TEMPLATE.format(
        loader=task.get("target_loader", ""), version=task.get("target_version", ""),
        jver=task.get("java_version", ""), kind=task.get("task_kind", ""),
        instruction=task["instruction"], context_block=ctx,
        example=(example or {}).get("golden_reference", "") if example else "",
        fence=FENCE,
    )
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user}]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="/workspace/model")
    ap.add_argument("--data", default="/workspace/forgebench-v4/data/public_eval.jsonl")
    ap.add_argument("--dev", default="/workspace/forgebench-v4/data/public_dev.jsonl")
    ap.add_argument("--out", default="/workspace/run/answers.jsonl")
    ap.add_argument("--meta", default="/workspace/run/run_meta.jsonl")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-new", type=int, default=1024)
    ap.add_argument("--thinking", action="store_true", help="enable thinking mode")
    ap.add_argument("--quant", action="store_true", help="4bit NF4 quantization (needs bitsandbytes)")
    ap.add_argument("--cpu-offload", action="store_true", help="device_map offload to /tmp/offload")
    ap.add_argument("--resident-mb", type=int, default=1200, help="RAM budget for resident weights")
    ap.add_argument("--stream", action="store_true", help="int8 streaming CPU engine (no mmap)")
    ap.add_argument("--max-ctx", type=int, default=3072, help="KV cache size for --stream")
    args = ap.parse_args()

    tasks = load_jsonl(args.data)
    dev = load_jsonl(args.dev)
    if args.limit:
        tasks = tasks[:args.limit]

    examples = {}
    for t in dev:
        examples.setdefault(t["module"], t)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done_ids = set()
    if out_path.exists():
        done_ids = {a["task_id"] for a in load_jsonl(out_path)}

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    t_load = time.time()
    tok = AutoTokenizer.from_pretrained(args.model)
    if args.stream:
        from stream_loader import StreamQwen
        model = StreamQwen(args.model, max_len=args.max_ctx)
        print(f"[load-stream] {time.time()-t_load:.1f}s", flush=True)
        model.eval()
        # skip the normal path entirely
        run_stream(model, tok, tasks, examples, args, out_path, done_ids)
        return
    kwargs = dict(dtype=torch.bfloat16, low_cpu_mem_usage=True)
    if args.cpu_offload:
        # RAM-starved host: pin resident memory to a small budget and offload
        # the rest of the weights to disk via accelerate's device_map machinery.
        os.makedirs("/tmp/offload", exist_ok=True)
        kwargs.update(device_map="cpu", max_memory={"cpu": args.resident_mb * 1024 * 1024},
                      offload_folder="/tmp/offload")
    elif args.quant:
        from transformers import BitsAndBytesConfig
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True, bnb_4bit_quant_storage=torch.uint8)
        kwargs.pop("dtype")
    model = AutoModelForCausalLM.from_pretrained(args.model, **kwargs)
    model.eval()
    print(f"[load] {time.time()-t_load:.1f}s", flush=True)

    stop_ids = [tok.eos_token_id]
    im_end = tok.convert_tokens_to_ids("<|im_end|>")
    if im_end is not None and im_end >= 0:
        stop_ids.append(im_end)
    stop_ids = [s for s in stop_ids if s is not None and s >= 0]

    f_out = open(out_path, "a", encoding="utf-8")
    f_meta = open(args.meta, "a", encoding="utf-8")

    template_kwargs = {} if args.thinking else {"enable_thinking": False}
    IM_END = "<|" + "im_end" + "|>"
    IM_START = "<|" + "im_start" + "|>"
    for task in tasks:
        tid = task["task_id"]
        if tid in done_ids:
            continue
        example = examples.get(task["module"])
        msgs = build_messages(task, example)
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True,
                                       **template_kwargs)
        inputs = tok(text, return_tensors="pt", add_special_tokens=False)
        t0 = time.time()
        with torch.inference_mode():
            out = model.generate(
                **inputs, max_new_tokens=args.max_new, do_sample=False,
                eos_token_id=stop_ids,
                pad_token_id=tok.pad_token_id if tok.pad_token_id is not None
                else tok.eos_token_id)
        gen = out[0][inputs["input_ids"].shape[1]:]
        raw = tok.decode(gen, skip_special_tokens=False)
        raw = raw.split(IM_END)[0]
        if IM_START in raw:
            raw = raw.replace(IM_START, "")
        golden = task.get("golden_reference") or ""
        ghash = norm_hash(golden)
        ans, files = extract_code(raw)
        rec = {"task_id": tid, "answer": ans}
        f_out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f_out.flush()
        meta = {"task_id": tid, "module": task.get("module"),
                "task_kind": task.get("task_kind"),
                "target_loader": task.get("target_loader"),
                "prompt_tokens": int(inputs["input_ids"].shape[1]),
                "gen_tokens": int(gen.shape[0]),
                "seconds": round(time.time() - t0, 2),
                "exact_golden_match": norm_hash(ans) == ghash,
                "truncated_at_max_new": int(gen.shape[0]) >= args.max_new,
                "n_files": len(files)}
        f_meta.write(json.dumps(meta, ensure_ascii=False) + "\n")
        f_meta.flush()
        print(f"[{tid}] {meta['gen_tokens']} tok / {meta['seconds']}s "
              f"exact={meta['exact_golden_match']}", flush=True)
    f_out.close()
    f_meta.close()


if __name__ == "__main__":
    main()
