# -*- coding: utf-8 -*-
"""m1_matrix.py —— 声音唱和图 v1：律块级重建与逐块恒等式核验。

结构（据道藏本卷19–20 版面）：
  每律块 = 觀物篇之N + [声组名][平上去入][闢翕] + [音组名][開發收閉][清濁]
           + 字表 + (声组名N下唱地之用音一百五十二) (音组名M上和天之用聲一百一十二)
           + (分律注数×2)
预期（卷21 原文锚定）：
  * 声组 16 个（日月星辰×日月星辰），每块 N=7 → 16×7=112 = 声之用数；
  * 音组 16 个（水火土石×水火土石），M∈{9..12}，ΣM=152 = 音之用数；
  * 每块声注 = N×152，音注 = M×112（OCR 常脱"零"，如 一千零八→一千八，容缺核验）。

运行: python m1_matrix.py
"""

import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "corpus", "00_皇极经世", "版本甲_正统道藏本DZ1040")
OUT = os.path.join(ROOT, "corpus", "07_唱和图结构化")

CN = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
      "八": 8, "九": 9, "十": 10, "百": 100, "千": 1000, "萬": 10000}


def cn2int(s):
    """中文数字 → int（一万以内，容错）。"""
    total, cur = 0, 0
    for ch in s:
        v = CN.get(ch)
        if v is None:
            return None
        if ch in "十百千萬":
            total += (cur or 1) * v
            cur = 0
        else:
            cur = cur * 10 + v
    return total + cur


def int2cn_variants(n):
    """int → 中文数字写法变体（含 OCR 脱'零'形态）。"""
    def full(n):
        if n < 10:
            return {k: v for k, v in CN.items() if v == n} and next(k for k, v in CN.items() if v == n)
        s = ""
        for unit in (1000, 100, 10):
            d, n = divmod(n, unit) if n >= unit else (None, n)
            if d is None:
                continue
            if d == 1 and unit == 10:
                s += "十"
            else:
                s += next(k for k, v in CN.items() if v == d) + next(k for k, v in CN.items() if v == unit)
            if 0 < n < unit and unit > 10:
                s += "零"
        if n:
            s += next(k for k, v in CN.items() if v == n)
        return s

    f = full(n)
    variants = {f, f.replace("零", "")}          # 脱零形态
    return {v for v in variants if v}


def int2cn_variants(n):
    """int → 中文数字写法变体集合（含 OCR 脱'零'形态）。覆盖 500–9999。"""
    D = {v: k for k, v in CN.items()}

    def full(n):
        s = ""
        rest = n
        for unit in (1000, 100, 10):
            if rest >= unit:
                d = rest // unit
                s += ("十" if (unit == 10 and d == 1) else D[d] + D[unit])
                rest %= unit
                if 0 < rest < unit and unit > 10:
                    s += D[0]
        if rest:
            s += D[rest]
        return s or D[0]

    f = full(n)
    return {f, f.replace(D[0], "")}


def main():
    text = ""
    for vol in ("卷19", "卷20"):
        text += re.sub(r"\s+", "", open(os.path.join(SRC, f"{vol}.txt"), encoding="utf-8").read())
    text = text.replace("/", "")   # 版面分栏斜杠归一化

    parts = re.split(r"(觀物篇之[一二三四五六七八九十]+)", text)
    blocks = []
    for i in range(1, len(parts) - 1, 2):
        name, body = parts[i], parts[i + 1]
        head = body[:90]
        m = re.match(
            r"([日月星辰]{2})聲(平|上|去|入)(闢|翕)([水火土石]{2})音(開|發|收|閉)(清|濁)",
            head)
        if not m:
            # 容忍空格/变体，稍后再报
            blocks.append({"pian": name, "raw_head": head, "parsed": False})
            continue
        sheng_name, tiao, pi, yin_name, kai, zhuo = m.groups()
        mn = re.search(r"([一二三四五六七八九十]+)下唱地之用音一百五十二", body[:200])
        mm = re.search(r"([一二三四五六七八九十]+)上和天[之]?用聲一百一十二", body[:200])
        N = cn2int(mn.group(1)) if mn else None
        M = cn2int(mm.group(1)) if mm else None
        notes = []
        for v in re.findall(r"[一二三四五六七八九十百千]+", body[:400]):
            x = cn2int(v)
            if x and x >= 400 and len(set(v)) > 1:   # 排除字表内的 九九九九 类
                notes.append(x)
        blocks.append({
            "pian": name, "sheng": sheng_name + "聲", "tiao": tiao, "pi": pi,
            "yin": yin_name + "音", "kai": kai, "zhuo": zhuo,
            "N": N, "M": M, "notes": notes, "parsed": True, "raw_head": head,
            "raw": body[:400],
        })

    parsed = [b for b in blocks if b["parsed"]]
    sheng_groups = {b["sheng"] for b in parsed}
    yin_groups = {b["yin"] for b in parsed}
    sum_N = sum(b["N"] or 0 for b in parsed)
    sum_M = sum(b["M"] or 0 for b in parsed)

    lines = ["# 声音唱和图 · v1 律块级重建", ""]
    lines.append(f"- 块总数 {len(blocks)}（解析成功 {len(parsed)}）")
    lines.append(f"- 声组 {len(sheng_groups)} 种：{sorted(sheng_groups)}")
    lines.append(f"- 音组 {len(yin_groups)} 种：{sorted(yin_groups)}")
    lines.append(f"- ΣN（声行数）= {sum_N}（预期 112）· ΣM（音行数）= {sum_M}（预期 152）")

    ok_all = True
    lines.append("\n## 逐块恒等式（声注 = N×152 · 音注 = M×112，容 OCR 脱零）")
    for b in parsed:
        N, M = b["N"], b["M"]
        exp_s, exp_y = (N or 0) * 152, (M or 0) * 112
        raw = b["raw"]
        s_ok = bool(exp_s) and any(v in raw for v in int2cn_variants(exp_s))
        y_ok = bool(exp_y) and any(v in raw for v in int2cn_variants(exp_y))
        ok_all &= s_ok and y_ok
        lines.append(f"- {b['pian']} {b['sheng']}({b['tiao']}{b['pi']})×{b['yin']}({b['kai']}{b['zhuo']})"
                     f" N={N} M={M} → 声注{exp_s}:{'✅' if s_ok else '❌'} 音注{exp_y}:{'✅' if y_ok else '❌'}"
                     + ("" if (s_ok and y_ok) else f" 实际注{b['notes']}"))

    lines.append(f"\n核验：{'✅ 全部通过' if ok_all else '❌ 有未通过项（明细如上）'}")
    lines.append("\n## 预期核对")
    lines.append(f"- 声组 16 种：{'✅' if len(sheng_groups) == 16 else '❌ ' + str(len(sheng_groups))}")
    lines.append(f"- 音组 16 种：{'✅' if len(yin_groups) == 16 else '❌ ' + str(len(yin_groups))}")
    lines.append(f"- ΣN=112：{'✅' if sum_N == 112 else '❌'} · ΣM=152：{'✅' if sum_M == 152 else '❌'}")

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "blocks_v1.json"), "w", encoding="utf-8") as fh:
        json.dump(blocks, fh, ensure_ascii=False, indent=1)
    report = "\n".join(lines)
    with open(os.path.join(OUT, "summary_v1.md"), "w", encoding="utf-8") as fh:
        fh.write(report + "\n")
    print(report)


if __name__ == "__main__":
    main()
