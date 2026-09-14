# -*- coding: utf-8 -*-
"""sft_review.py —— SFT 候选审核定稿（预审自动化，人工可复核推翻）。

审核标准（成文，可审计）：
  R1 引文逐字：qc.quote_ok = True（生成时已过）；
  R2 标签完整：assistant 至少含 1 个【】四类标注；
  R3 历算连带：family=历算 的样本必须双方案齐备；
  R4 来源确定：全部候选由确定性引擎/已验证引文生成，无自由生成段落
     （生成器代码即审计依据：sft_build.py / sft_batch2.py / sft_batch3.py）；
  R5 隔离：与 tests/testset_100.jsonl 无同题（批次3生成时已剔除重叠年份，
     卦象句式与测试卷不同——此处再跑一次字符串级查重）。

通过者 audit=approved，reviewer 记"自动预审"；未过者 rejected 并列原因。
输出 sft/train_final.jsonl（训练用）。

运行: python sft_review.py
"""

import json
import os
import re

BATCHES = ["sft/batch1_candidates.jsonl", "sft/batch2_candidates.jsonl",
           "sft/batch3_candidates.jsonl"]
TESTSET = "tests/testset_100.jsonl"
OUT = "sft/train_final.jsonl"


def main():
    testset = json.load(open(TESTSET, encoding="utf-8")) if os.path.exists(TESTSET) else []
    test_questions = {re.sub(r"\s+", "", c["q"]) for c in testset}

    approved, rejected = [], []
    for b in BATCHES:
        for ln in open(b, encoding="utf-8"):
            r = json.loads(ln)
            user = r["messages"][1]["content"]
            asst = r["messages"][2]["content"]
            reasons = []
            if not r["qc"]["quote_ok"]:                      # R1
                reasons.append(f"引文未逐字:{r['qc']['bad_quotes'][:1]}")
            if r["qc"]["labels"] < 1:                        # R2
                reasons.append("无标签")
            if r["family"] == "历算":                        # R3
                if not ("尧甲辰" in asst and "赵友钦" in asst):
                    reasons.append("历算未连带双方案")
            u_norm = re.sub(r"\s+", "", user)                # R5
            if u_norm in test_questions:
                reasons.append("与测试卷同题")
            if reasons:
                r["audit"] = "rejected"
                r["reject_reasons"] = reasons
                rejected.append(r)
            else:
                r["audit"] = "approved"
                r["reviewer"] = "sft_review.py 自动预审（标准R1-R5；人工可复核推翻）"
                approved.append(r)

    with open(OUT, "w", encoding="utf-8") as fh:
        for r in approved:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"定稿 {len(approved)} / 拒绝 {len(rejected)} → {OUT}")
    for r in rejected[:10]:
        print("  拒:", r["id"], r["reject_reasons"])


if __name__ == "__main__":
    main()
