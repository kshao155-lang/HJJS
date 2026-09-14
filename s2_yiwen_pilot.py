# -*- coding: utf-8 -*-
"""S2 试点：击壤集两版本异文率 —— 决定"双版本去噪模型(M2)"是否立项。

版本甲 = corpus/01_伊川击壤集/版本甲_kanripo本/卷1..20（影印数字化，繁体无标点）
版本乙 = corpus/01_伊川击壤集/版本乙_bkkbooks本/卷01..20（文渊阁四库本，繁体无标点）

方法：去空白后逐卷做 SequenceMatcher 相似度；差异率 = 1 - ratio。
判读：若差异率以低个位数百分比为主且差异多为形近字 → 主要是 OCR 讹字，
M2 退化为拼写纠错（不立项为"理解模型"）；若存在成句异文 → 有真实版本价值。

运行: python s2_yiwen_pilot.py
"""

import difflib
import glob
import os
import re

A_DIR = "corpus/01_伊川击壤集/版本甲_kanripo本"
B_DIR = "corpus/01_伊川击壤集/版本乙_bkkbooks本"


def clean(t):
    return re.sub(r"\s+", "", t)


def main():
    rows = []
    for k in range(1, 21):
        fa = os.path.join(A_DIR, f"卷{k}.txt")
        fb = os.path.join(B_DIR, f"卷{k:02d}.txt")
        if not (os.path.exists(fa) and os.path.exists(fb)):
            print(f"  卷{k}: 缺文件（甲={os.path.exists(fa)} 乙={os.path.exists(fb)}）")
            continue
        ta = clean(open(fa, encoding="utf-8").read())
        tb = clean(open(fb, encoding="utf-8").read())
        n = min(len(ta), len(tb))
        sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
        ratio = sm.ratio()
        rows.append((k, len(ta), len(tb), ratio))
        print(f"  卷{k:>2d}: 甲{len(ta):>6d}字 乙{len(tb):>6d}字  长度差{abs(len(ta)-len(tb)):>5d}"
              f"  相似度 {ratio:.4f}  差异率 {1-ratio:.4f}")

    tot_a = sum(r[1] for r in rows)
    tot_b = sum(r[2] for r in rows)
    wavg = sum(r[3] * r[1] for r in rows) / tot_a
    print(f"\n合计：甲 {tot_a} 字 · 乙 {tot_b} 字 · 加权相似度 {wavg:.4f} · 总差异率 {1-wavg:.4f}")

    # 抽样展示卷1前几处差异片段（供人工判读：讹字 or 真异文）
    ta = clean(open(os.path.join(A_DIR, "卷1.txt"), encoding="utf-8").read())
    tb = clean(open(os.path.join(B_DIR, "卷01.txt"), encoding="utf-8").read())
    sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
    print("\n[卷1 差异片段抽样]（左=kanripo本 右=四库本）")
    shown = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal" and max(i2 - i1, j2 - j1) <= 12 and shown < 8:
            print(f"  「{ta[max(0,i1-6):i2+6]}」 ↔ 「{tb[max(0,j1-6):j2+6]}」")
            shown += 1

    print("\n[判读门槛] 总差异率 <3% 且差异以 1-2 字形近讹误为主 → M2 降级为纠错任务，"
          "不立项独立'理解模型'；")
    print("           3-10% 且含成句异文 → M2 立项（平行语料去噪+异文对齐研究）。")


if __name__ == "__main__":
    main()
