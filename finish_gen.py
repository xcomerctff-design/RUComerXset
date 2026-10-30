#!/usr/bin/env python3
"""Append the remaining part of generate_answers.py (heredoc-safe helper)."""
from pathlib import Path

p = Path('/workspace/generate_answers.py')
src = p.read_text()
marker = '    im_end = tok.convert_tokens_to_ids("'
assert src.rstrip().endswith(marker), repr(src[-200:])

rest = """im_end")
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
"""
p.write_text(src.rstrip() + rest, encoding="utf-8")
print("OK, final size:", len(src) + len(rest))
