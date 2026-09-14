# -*- coding: utf-8 -*-
"""changhe.py —— 《皇极经世·声音唱和图》结构化抽取与整数恒等式核验（M1）。

数据源：corpus/00_皇极经世/版本甲_正统道藏本DZ1040/卷19.txt、卷20.txt（观物篇三十五—四十六，
声音律吕之图）。

核验链（全部可在语料中定位原文）：
  卷21 观物内篇：太阳少阳太刚少刚用数 112，太阴少阴太柔少柔用数 152（体数 160/192）；
        声唱音 → 112×152 = 17,024 = 动数 = 植数；再唱和通数 = 17,024² = 28,981,657,6?→ 2,898,165,76?（见下）
  图内律注：每声组唱 152（音之用数），每音组和平 112（声之用数）；分律另有 152×7=1064、112×12=1344 等。

输出：corpus/07_唱和图结构化/sound_cells.jsonl（逐格）、summary.md（计数与核验报告）。

用法: python changhe.py
"""

import glob
import json
import os
import re
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "corpus", "00_皇极经世", "版本甲_正统道藏本DZ1040")
OUT = os.path.join(ROOT, "corpus", "07_唱和图结构化")

CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8,
          "九": 9, "十": 10}


def cn2int(s):
    """极简中文数（支持 一~九十九）。"""
    s = s.strip()
    if not s:
        return None
    if "十" not in s:
        return CN_NUM.get(s)
    parts = s.split("十")
    a = CN_NUM.get(parts[0], 1) if parts[0] else 1
    b = CN_NUM.get(parts[1], 0) if parts[1] else 0
    return a * 10 + b


CELL_RE = re.compile(r"([一二三四五六七八九十]{1,2})(聲|音)\(?([^()/]*)/?([^()]*)\)?")
GUAN = set("乾坤震巽坎離艮兌")


def parse_line(ln):
    """一行 → 若干格 {label, kind, left, right}。左段=本行样本字/空，右段=字集或卦集。"""
    cells = []
    for m in CELL_RE.finditer(ln):
        idx, kind, left, right = m.groups()
        left, right = left.strip(), right.strip()
        if not (left or right):
            continue
        is_gua = bool(right) and all(c in GUAN or c == "○" for c in right) and len(right) >= 2
        cells.append({
            "kind": "sheng" if kind == "聲" else "yin",
            "seq": cn2int(idx),
            "left": left,
            "right": right,
            "right_is_gua": is_gua,
        })
    return cells


def main():
    rows = []
    for vol in ("卷19", "卷20"):
        t = open(os.path.join(SRC, f"{vol}.txt"), encoding="utf-8").read()
        cur_lu = None
        for ln in t.splitlines():
            s = ln.strip()
            mlu = re.search(r"(發音清和律[之第].{1,6}|觀物篇之[一二三四五六七八九十]+)", s)
            if mlu:
                cur_lu = mlu.group(1)
            if "聲" not in s and "音" not in s:
                continue
            for c in parse_line(s):
                c["juan"] = vol
                c["lu"] = cur_lu
                rows.append(c)

    sheng_rows = [r for r in rows if r["kind"] == "sheng"]
    yin_rows = [r for r in rows if r["kind"] == "yin"]
    sheng_chars = Counter()
    yin_chars = Counter()
    gua_cells = 0
    for r in sheng_rows:
        for ch in r["right"]:
            if ch not in "○/":
                sheng_chars[ch] += 1
    for r in yin_rows:
        for ch in r["right"]:
            if ch not in "○/":
                yin_chars[ch] += 1
    gua_cells = sum(1 for r in rows if r["right_is_gua"])

    # ---- 整数恒等式核验（原文出处 + 算术） ----
    checks = []
    n21 = re.sub(r"\s+", "", open(os.path.join(SRC, "卷21.txt"), encoding="utf-8").read())
    checks.append(("用数112原文", "一百一十二" in n21 and "用數一百一十二" in n21))
    checks.append(("用数152原文", "用數一百五十二" in n21))
    checks.append(("体数160/192原文", "體數一百六十" in n21 and "體數一百九十二" in n21))
    checks.append(("112×152=17024", 112 * 152 == 17024))
    checks.append(("动数原文（一萬七千二十四）", "一萬七千二十四" in n21))
    checks.append(("17024²=289,816,576", 17024 ** 2 == 289816576))
    checks.append(("通数原文（二萬八千九百八十一萬六千五百七十六）",
                   "二萬八千九百八十一萬六千五百七十六" in n21))
    t19 = re.sub(r"\s+", "", open(os.path.join(SRC, "卷19.txt"), encoding="utf-8").read())
    checks.append(("图注152（用音一百五十二）", "用音一百五十二" in t19))
    checks.append(("图注112（用聲一百一十二）", "用聲一百一十二" in t19))
    checks.append(("分律恒等式152×7=1064（图注一千六十四）", 152 * 7 == 1064 and "一千六十四" in t19))
    t20 = re.sub(r"\s+", "", open(os.path.join(SRC, "卷20.txt"), encoding="utf-8").read())
    checks.append(("分律恒等式112×12=1344（图注一千三百四十四）",
                   112 * 12 == 1344 and "一千三百四十四" in t20))

    # ---- 落盘 ----
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "sound_cells.jsonl"), "w", encoding="utf-8") as fh:
        for i, r in enumerate(rows):
            fh.write(json.dumps({"id": f"c{i:05d}", **r}, ensure_ascii=False) + "\n")

    lines = ["# 声音唱和图 · 结构化抽取与核验（M1 v0）", ""]
    lines.append(f"- 数据源：道藏本卷19–20（观物篇三十五起，声音律吕之图）")
    lines.append(f"- 抽取格数：{len(rows)}（聲 {len(sheng_rows)} 行 · 音 {len(yin_rows)} 行）；"
                 f"卦配格 {gua_cells}")
    lines.append(f"- 聲字种数 {len(sheng_chars)}：{''.join(sorted(sheng_chars))[:64]}…")
    lines.append(f"- 音字种数 {len(yin_chars)}：{''.join(sorted(yin_chars))[:64]}…")
    lines.append("")
    lines.append("## 整数恒等式核验")
    for name, ok in checks:
        lines.append(f"- {'✅' if ok else '❌'} {name}")
    n_ok = sum(1 for _, ok in checks if ok)
    lines.append("")
    lines.append(f"核验通过 {n_ok}/{len(checks)}。")
    lines.append("")
    lines.append("## 口径说明（诚实边界）")
    lines.append("- 本 v0 抽取的是图的行级格（标注+左右段），尚未重建 16声组×7行=112、"
                 "16音组×(9~12)行=152 的完整矩阵——行有重复标注与空位（○），需按律分组"
                 "二次对齐后再下断言；")
    lines.append("- 卦配格（如 坎坎坎坎）与字集格（如 多可个舌）已分流（right_is_gua）；")
    lines.append("- AIHub J3 口径警示仍有效：图为'声组×音组'嵌套结构，'十声×十二音'"
                 "与 152/112 的关系以卷21原文（体数160/192→用数112/152）为准。")
    with open(os.path.join(OUT, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
