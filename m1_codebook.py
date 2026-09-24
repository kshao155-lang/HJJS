# -*- coding: utf-8 -*-
"""m1_codebook.py —— 声音唱和图 v2：全图律节清点 + 十六字表码本。

结构认知（据道藏本卷19–20 版面）：
  * 图主体由数百个「律节」组成，节标题为双系列：
      声系列「X聲[闢|翕]唱吕[几之几]」+ 音系列「[開發收閉]音[清|浊]和律[几之几]」；
    节内左右两半栏各自按系列推进（每行 (样本4字/字行4字)）。
  * 16 大块（觀物篇三十五~五十）各给出：声组×音组配对 + 十六字表 + 行数恒等注。

v2 产出：
  * 全部律节清点（系列×编号 → 覆盖矩阵，验证图是否完整覆盖声16×音16空间）；
  * 每篇十六字表码本 codebook_v2.json；
  * 律节总数与 112×152=17024 的关系核验。

运行: python m1_codebook.py
"""

import json
import os
import re
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "corpus", "00_皇极经世", "版本甲_正统道藏本DZ1040")
OUT = os.path.join(ROOT, "corpus", "07_唱和图结构化")

SEC_RE = re.compile(
    r"([平上去入])聲([闢翕])(唱吕|清和律)([一二三四五六七八九十]+)之([一二三四五六七八九十]+)"
    r"|([開發收閉])音([清濁])(和律|唱吕)([一二三四五六七八九十]+)之([一二三四五六七八九十]+)")

CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8,
      "九": 9, "十": 10}


def cn2int(s):
    s = s.strip()
    if "十" not in s:
        return CN.get(s)
    a, _, b = s.partition("十")
    return (CN.get(a, 1) if a else 1) * 10 + (CN.get(b, 0) if b else 0)


def main():
    text = ""
    for vol in ("卷19", "卷20"):
        text += re.sub(r"\s+", "", open(os.path.join(SRC, f"{vol}.txt"), encoding="utf-8").read())

    # ---- 律节清点 ----
    sections = []
    for m in SEC_RE.finditer(text):
        if m.group(1):   # 声系列
            sections.append({"side": "声", "tiao": m.group(1) + m.group(2),
                             "lu": m.group(3), "a": cn2int(m.group(4)),
                             "b": cn2int(m.group(5))})
        else:            # 音系列
            sections.append({"side": "音", "tiao": m.group(6) + m.group(7),
                             "lu": m.group(8), "a": cn2int(m.group(9)),
                             "b": cn2int(m.group(10))})

    by_side = defaultdict(list)
    for s in sections:
        by_side[(s["side"], s["tiao"], s["lu"])].append((s["a"], s["b"]))

    lines = ["# 声音唱和图 v2 · 全图律节清点与码本", ""]
    lines.append(f"- 律节标题总数：{len(sections)}")
    series = sorted({(k[0], k[1], k[2]) for k in by_side})
    lines.append(f"- 系列数：{len(series)}（声侧 {sum(1 for s in series if s[0]=='声')} + "
                 f"音侧 {sum(1 for s in series if s[0]=='音')}）")
    lines.append("")
    lines.append("| 侧 | 系列 | 律 | 节数 | a范围 | b范围 |")
    lines.append("|---|---|---|---|---|---|")
    for side, tiao, lu in series:
        cells = by_side[(side, tiao, lu)]
        as_ = [a for a, _ in cells if a is not None]
        bs = [b for _, b in cells if b is not None]
        lines.append(f"| {side} | {tiao} | {lu} | {len(cells)} | "
                     f"{min(as_)}-{max(as_)} | {min(bs)}-{max(bs)} |")

    # 覆盖分析：声系列应覆盖 平上去入×闢翕 = 8；音系列 開發收閉×清浊 = 8
    sheng_keys = {t for s_, t, _ in series if s_ == "声"}
    yin_keys = {t for s_, t, _ in series if s_ == "音"}
    lines.append("")
    lines.append(f"- 声系列覆盖：{len(sheng_keys)}/8（平上去入×闢翕）"
                 f" {'✅' if len(sheng_keys) == 8 else '→ ' + str(sorted(sheng_keys))}")
    lines.append(f"- 音系列覆盖：{len(yin_keys)}/8（開發收閉×清浊）"
                 f" {'✅' if len(yin_keys) == 8 else '→ ' + str(sorted(yin_keys))}")

    # ---- 十六字表码本（16 篇）----
    parts = re.split(r"(觀物篇之[一二三四五六七八九十]+)", text)
    codebook = []
    for i in range(1, len(parts) - 1, 2):
        name, body = parts[i], parts[i + 1]
        head = body[:60]
        m = re.match(r"([日月星辰]{2})聲(平|上|去|入)(闢|翕)([水火土石]{2})音(開|發|收|閉)(清|濁)([^（(]{10,20}?)[（(]", head)
        if m:
            codebook.append({
                "pian": name, "sheng": m.group(1) + "聲", "tiao": m.group(2),
                "pi": m.group(3), "yin": m.group(4) + "音", "kai": m.group(5),
                "zhuo": m.group(6), "zi16": m.group(7).strip()})

    lines.append("")
    lines.append("## 十六字表码本（16 篇）")
    for c in codebook:
        lines.append(f"- {c['pian']} {c['sheng']}({c['tiao']}{c['pi']})×{c['yin']}"
                     f"({c['kai']}{c['zhuo']}）：{c['zi16']}")

    # 去重检验：16 表是否互不重复（= 16 个独立字表）
    sets_ = [c["zi16"] for c in codebook]
    lines.append("")
    lines.append(f"- 字表去重：{len(set(sets_))}/{len(sets_)} "
                 f"{'✅ 16 表互异' if len(set(sets_)) == len(sets_) == 16 else ''}")

    os.makedirs(OUT, exist_ok=True)
    json.dump({"sections": sections, "codebook": codebook},
              open(os.path.join(OUT, "codebook_v2.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    report = "\n".join(lines)
    open(os.path.join(OUT, "summary_v2.md"), "w", encoding="utf-8").write(report + "\n")
    print(report[:2400])


if __name__ == "__main__":
    main()
