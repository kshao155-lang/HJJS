# -*- coding: utf-8 -*-
"""train_sft.py —— 观物模型 QLoRA/LoRA 训练（目标：D2 概念一致性 + 工具遵从）。

设计（最小可控，与本仓库纯 Python 风格一致）：
  * 基座：models/Qwen2.5-7B-Instruct（bf16，A100-40GB 直接跑，免 bitsandbytes）；
  * LoRA：rank 16 / alpha 32 / 目标 q,k,v,o,gate,up,down；
  * 数据：sft/train_final.jsonl（500 条，audit=approved）；
  * 损失：仅 assistant 段计损（prompt 部分标签 -100）；
  * 超参：lr 1e-4、epochs 3、batch 4 × grad_accum 4 = 有效 16、max_len 1024；
  * 产物：models/guanwu_lora/（适配器权重 + 训练元数据）。

运行: python train_sft.py
"""

import json
import os
import sys
import time

sys.modules.setdefault("tensorflow", None)

import torch
from peft import LoraConfig, get_peft_model

MODEL_DIR = "models/Qwen2.5-7B-Instruct"
DATA = "sft/train_final.jsonl"
OUT_DIR = "models/guanwu_lora"
EPOCHS = 3
BATCH = 4
GRAD_ACCUM = 4
LR = 1e-4
MAXLEN = 1024


def build_examples(tok):
    from transformers import AutoTokenizer
    if tok is None:
        tok = AutoTokenizer.from_pretrained(MODEL_DIR)
    exs = []
    for ln in open(DATA, encoding="utf-8"):
        r = json.loads(ln)
        msgs = r["messages"]
        prompt = tok.apply_chat_template(msgs[:2], tokenize=False, add_generation_prompt=True)
        full = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
        pi = tok(prompt, add_special_tokens=False)["input_ids"]
        fi = tok(full, add_special_tokens=False)["input_ids"][:MAXLEN]
        labels = [-100] * len(pi) + fi[len(pi):]
        labels = labels[:MAXLEN]
        if all(x == -100 for x in labels):
            continue
        exs.append({"input_ids": fi, "labels": labels})
    print(f"训练样本 {len(exs)} 条（assistant 段计损）")
    return exs


def collate(batch, pad_id):
    maxlen = max(len(x["input_ids"]) for x in batch)
    input_ids, labels, attn = [], [], []
    for x in batch:
        pad = maxlen - len(x["input_ids"])
        input_ids.append(x["input_ids"] + [pad_id] * pad)
        labels.append(x["labels"] + [-100] * pad)
        attn.append([1] * len(x["input_ids"]) + [0] * pad)
    return (torch.tensor(input_ids), torch.tensor(labels), torch.tensor(attn))


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(MODEL_DIR)
    print("加载基座（bf16）…", flush=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_DIR, dtype=torch.bfloat16, device_map="cuda:0",
        attn_implementation="sdpa")
    model.config.use_cache = False
    model.gradient_checkpointing_enable()

    lcfg = LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, lcfg)
    model.print_trainable_parameters()

    exs = build_examples(tok)
    rng = torch.Generator().manual_seed(42)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=LR)

    steps_per_epoch = (len(exs) + BATCH * GRAD_ACCUM - 1) // (BATCH * GRAD_ACCUM)
    print(f"epochs={EPOCHS} steps/epoch≈{steps_per_epoch}", flush=True)
    t0 = time.time()
    step = 0
    for ep in range(EPOCHS):
        order = torch.randperm(len(exs), generator=rng).tolist()
        model.train()
        opt.zero_grad()
        for bi in range(0, len(order), BATCH):
            batch = [exs[i] for i in order[bi:bi + BATCH]]
            input_ids, labels, attn = collate(batch, tok.pad_token_id or tok.eos_token_id)
            out = model(input_ids=input_ids.cuda(), attention_mask=attn.cuda(),
                        labels=labels.cuda())
            (out.loss / GRAD_ACCUM).backward()
            if (bi // BATCH + 1) % GRAD_ACCUM == 0 or bi + BATCH >= len(order):
                torch.nn.utils.clip_grad_norm_(
                    [p for p in model.parameters() if p.requires_grad], 1.0)
                opt.step()
                opt.zero_grad()
                step += 1
                if step % 10 == 0:
                    print(f"  ep{ep+1} step{step}/{steps_per_epoch} loss={out.loss.item():.4f} "
                          f"({time.time()-t0:.0f}s)", flush=True)

    os.makedirs(OUT_DIR, exist_ok=True)
    model.save_pretrained(OUT_DIR)
    tok.save_pretrained(OUT_DIR)
    meta = {"base": MODEL_DIR, "data": DATA, "n": len(exs), "epochs": EPOCHS,
            "lora": {"r": 16, "alpha": 32}, "lr": LR, "trained_at": time.strftime("%F %T")}
    json.dump(meta, open(os.path.join(OUT_DIR, "train_meta.json"), "w",
                         encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"完成 → {OUT_DIR}（用时 {time.time()-t0:.0f}s）")


if __name__ == "__main__":
    main()
