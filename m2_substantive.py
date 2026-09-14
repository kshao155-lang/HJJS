# -*- coding: utf-8 -*-
"""m2_substantive.py —— 击壤集两版本"实质性异文率"统计（M2 立项裁决）。

方法：
  1) 逐卷 SequenceMatcher 对齐，收集所有 replace 片段对；
  2) 归一层：opencc t2s（繁简差异）+ 数据驱动异体表（从观测差异对自动汇总）；
  3) 归一后仍不相等的替换 = 实质性异文候选；按卷计率。

判读门槛（S2 试点延续）：实质异文率 ≥3% → M2 立项；<1% → 降级纠错任务。

运行: python m2_substantive.py
"""

import difflib
import os
import re
from collections import Counter

import opencc

T2S = opencc.OpenCC("t2s")
A_DIR = "corpus/01_伊川击壤集/版本甲_kanripo本"
B_DIR = "corpus/01_伊川击壤集/版本乙_bkkbooks本"
OUT = "corpus/07_唱和图结构化"  # 复用输出目录不合适；单独放 output/
REPORT = "output/M2实质异文.md"


def clean(t):
    return re.sub(r"\s+", "", t)


def norm(s, variant_map):
    s = T2S.convert(s)
    return "".join(variant_map.get(c, c) for c in s)


def main():
    variant_pairs = Counter()
    per_juan = []
    all_pairs = []

    # 第一遍：收集全部替换对
    for k in range(1, 21):
        fa = os.path.join(A_DIR, f"卷{k}.txt")
        fb = os.path.join(B_DIR, f"卷{k:02d}.txt")
        ta = clean(open(fa, encoding="utf-8").read())
        tb = clean(open(fb, encoding="utf-8").read())
        sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "replace" and (i2 - i1) == (j2 - j1) == 1:
                variant_pairs[(ta[i1], tb[j1])] += 1
                all_pairs.append((k, ta[i1], tb[j1]))
            elif tag in ("replace", "delete", "insert"):
                all_pairs.append((k, ta[i1:i2], tb[j1:j2]))

    # 高频 1:1 对 → 异体/讹字表（≥3 次视为系统性）
    variant_map = {}
    for (a, b), n in variant_pairs.items():
        if n >= 3 and T2S.convert(a) != T2S.convert(b):
            variant_map[a] = b
    # 若 a/b 繁简归一后相同（如 游/逰→游），归一层本就吸收
    sys_pairs = [(a, b, n) for (a, b), n in variant_pairs.most_common(20)]

    # 第二遍：实质性异文统计
    total_chars = 0
    subst_chars = 0
    juan_rows = []
    subst_samples = []
    for k in range(1, 21):
        fa = os.path.join(A_DIR, f"卷{k}.txt")
        fb = os.path.join(B_DIR, f"卷{k:02d}.txt")
        ta = clean(open(fa, encoding="utf-8").read())
        tb = clean(open(fb, encoding="utf-8").read())
        na, nb = norm(ta, variant_map), norm(tb, variant_map)
        sm = difflib.SequenceMatcher(None, na, nb, autojunk=False)
        diff = 0
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != "equal":
                diff += max(i2 - i1, j2 - j1)
                if tag == "replace" and len(subst_samples) < 25 and (i2 - i1) <= 6:
                    subst_samples.append((k, ta[max(0,i1-4):i2+4], tb[max(0,j1-4):j2+4]))
        r = diff / max(1, len(na))
        juan_rows.append((k, len(na), diff, r))
        total_chars += len(na)
        subst_chars += diff

    rate = subst_chars / total_chars
    lines = ["# M2 裁决：击壤集两版本实质性异文率", "",
             f"- 归一层：opencc 繁简 + 数据驱动异体表（{len(variant_map)} 字映射，≥3 次系统性对）",
             f"- **总实质异文率 = {subst_chars}/{total_chars} = {rate:.2%}**",
             "",
             "| 卷 | 归一字数 | 实质差异字 | 率 |", "|---|---|---|---|"]
    for k, n, d, r in juan_rows:
        lines.append(f"| {k} | {n} | {d} | {r:.2%} |")
    lines.append("\n## 高频 1:1 差异对 top20（第一遍，归一前）")
    for a, b, n in sys_pairs:
        same_after_norm = norm(a, {}) == norm(b, {})
        lines.append(f"- {a}↔{b} ×{n} {'（繁简/异体，归一层吸收）' if same_after_norm else '（进入实质差异）'}")
    lines.append("\n## 实质异文抽样")
    for k, a, b in subst_samples:
        lines.append(f"- 卷{k}：「{a}」↔「{b}」")
    verdict = ("≥3%：**M2 立项**（跨版本去噪+异文对齐研究有价值）" if rate >= 0.03
               else "<1%：M2 降级为纠错任务，不立项独立模型")
    lines.append(f"\n## 裁决\n\n{verdict}（实测 {rate:.2%}，门槛见 S2 试点）")
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    open(REPORT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"总实质异文率 = {rate:.2%}（{subst_chars}/{total_chars}）→ {verdict}")
    print(f"报告 → {REPORT}")


if __name__ == "__main__":
    main()
