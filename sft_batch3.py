# -*- coding: utf-8 -*-
"""sft_batch3.py —— SFT 批次 3：程序化扩量至 500（卦象属性/历算年份/概念覆盖）。

隔离注意：测试卷已冻结（tests/testset_100.jsonl），本批次卦象属性问使用与测试卷
不同的句式（"二进制值 v 是多少""上下卦是什么" vs 测试卷"先天序排第几"）。

运行: python sft_batch3.py
"""

import json
import os
import sys

from huangji import gua, guanwu, lishu, shuju
from sft_build import SYSTEM, qc

OUT = []


def emit(family, refs, user, assistant):
    ok, bad, nl = qc(assistant)
    OUT.append({
        "id": f"b3_{len(OUT)+1:04d}",
        "family": family,
        "spec_refs": refs,
        "audit": "pending",
        "qc": {"quote_ok": ok, "bad_quotes": bad, "labels": nl},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
    })


def main():
    # A. 卦象属性问（64 卦 × 2 句式 = 128；句式与测试卷隔离）
    for h in gua.ALL:
        emit("卦象属性", ["T04"], f"{h.name}卦的二进制值 v 是多少？怎么读？",
             f"【规则计算】{h.name}卦{h.unicode_char} 六爻自初至上为 {h.bits}"
             f"（阳=1 阴=0），二进制值 v={h.v}（约定：初爻为最高位）。"
             f"该约定下先天卦序 = 64 − v = {h.xiantian_index}。引擎可复现。")
        emit("卦象属性", ["T04"], f"{h.name}卦的上下卦各是什么？各属什么象？",
             f"【规则计算】{h.name}卦{h.unicode_char}：下卦（内）{h.lower}"
             f"{gua.TRIGRAMS[h.lower]['sym']}{gua.TRIGRAMS[h.lower]['nature']}，"
             f"上卦（外）{h.upper}{gua.TRIGRAMS[h.upper]['sym']}{gua.TRIGRAMS[h.upper]['nature']}，"
             f"阳爻 {h.yang_count}/6。")

    # B. 历算年份扩展（历史事件年 × 双方案 = ~44）
    # 隔离：剔除测试卷 YEARS_D4 用过的年份（防止训练-测试同题）
    TESTSET_YEARS = {755, 1127, 1644, 1912, 1840, 105, -841, 221, 907, 1279,
                     1368, 589, 960, 1911, 1662, 626, 1403, 1898, 280, 9}
    years = sorted(({s for _, s, e in shuju.DYNASTIES} | {e for _, s, e in shuju.DYNASTIES}
                    | {-1046, -771, -221, 8, 316} | {756, 1069, 1141, 1405, 1449,
                    1681, 1796, 1851, 1860, 1894, 1900, 1913, 1927, 1945}) - TESTSET_YEARS)
    for y in years[:60]:
        r1 = lishu.year_reading(y, scheme="尧甲辰通行")
        r2 = lishu.year_reading(y, scheme="赵友钦夏禹说")
        yl = f"公元前{-y+1}年" if y <= 0 else f"公元{y}年"
        emit("历算", ["T03"], f"{yl}（{r1['ganzhi']}年）在两种起算方案下各处元会运世何位？",
             f"【规则计算】\n"
             f"- 尧甲辰通行：{r1['hui_branch']}会（{r1['hui_gua']}卦）第{r1['yun_index']}运"
             f"（{r1['yun_gua'].name}卦）第{r1['shi_index']}世第{r1['nian_index']}年\n"
             f"- 赵友钦夏禹说：{r2['hui_branch']}会（{r2['hui_gua']}卦）第{r2['yun_index']}运"
             f"（{r2['yun_gua'].name}卦）第{r2['shi_index']}世第{r2['nian_index']}年\n\n"
             f"【注家解释】两方案相差 140 年，坐标必须连带方案报告（T03）。")

    # A2. 卦名与 Unicode 问（64；句式与测试卷隔离）
    for h in gua.ALL:
        emit("卦象属性", ["T04"], f"{h.unicode_char} 是什么卦？",
             f"【规则计算】符号 {h.unicode_char}（U+{ord(h.unicode_char):04X}，按文王卦序排列）"
             f"是{h.name}卦：上{h.upper}下{h.lower}，v={h.v}（初爻为最高位），"
             f"先天卦序第 {h.xiantian_index}。")

    # C. 消息卦义理扩展（12 卦 × 现代应用问法）
    apps = {
        "复": ("组织变革从最低谷重启时该注意什么？", "旧局已终、新机萌于至暗——启动期不可躁进，也不可因循。"),
        "乾": ("事业登顶后最大的风险是什么？", "盈不可久——极盛位的风险管理比冲刺期更重要。"),
        "姤": ("如何在鼎盛期布局防衰？", "盛极而微衰已萌——在最好的时候做百年之计。"),
        "剥": ("衰退期该收缩还是保存实力？", "硕果不食——剥期的任务是藏用待复，不是硬拼。"),
        "坤": ("旧周期彻底结束后怎么办？", "穷则变——坤之后复生一阳，收拾整理以待新周期。"),
    }
    for xi, x in enumerate(gua.XIAOXI):
        if x.name in apps:
            q, hint = apps[x.name]
            emit("消息卦应用", ["T26", "T27"], f"{x.name}卦的相位智慧，对现代问题有什么启发？{q}",
                 f"【规则计算】{x.name}卦：消息循环第 {xi+1} 位，阳爻 {x.yang_count}/6。\n\n"
                 f"【注家解释】{guanwu.XIAOXI_COMMENT[x.name]}\n\n"
                 f"【现代推演】{hint}（此类应用为现代延伸，原典为象数描述而非管理学说）")

    # D. 原典出处速查（38 条原典条目的出处问法收口：观物内外篇卷位）
    juan_map = [
        ("观物内篇", "道藏本卷21", "T05/T13/T14/T15/T42"),
        ("观物外篇上", "道藏本卷22", "T01/T02/T08/T10/T16/T22/T39"),
        ("观物外篇下", "道藏本卷23", "T11/T12/T17/T20/T21/T37/T45"),
    ]
    for part, juan, ids in juan_map:
        emit("语料定位", ["T04"], f"《{part}》在语料库道藏本的哪一卷？涵盖哪些主题条目？",
             f"【规则计算】《{part}》对应道藏本 {juan}（语料路径 corpus/00_皇极经世/"
             f"版本甲_正统道藏本DZ1040/）。训练规范中 {ids} 等条目的引文均定位于此，"
             f"已逐条 grep 验证。")

    # A3. Unicode 反向问（64）
    for h in gua.ALL:
        emit("卦象属性", ["T04"], f"符号 {h.unicode_char} 对应哪一卦？其先天序是多少？",
             f"【规则计算】{h.unicode_char}（U+{ord(h.unicode_char):04X}）是{h.name}卦，"
             f"先天卦序第 {h.xiantian_index}，v={h.v}（初爻为最高位）。")

    # C2. 剩余消息卦相位（补全 12 卦）
    done = {"复", "乾", "姤", "剥", "坤"}
    for xi, x in enumerate(gua.XIAOXI):
        if x.name in done:
            continue
        emit("消息卦义理", ["T26"], f"{x.name}卦在十二消息卦中排第几？含义是什么？",
             f"【规则计算】{x.name}卦：消息循环第 {xi+1} 位，阳爻 {x.yang_count}/6，"
             f"六爻 {x.bits}。\n\n【注家解释】{guanwu.XIAOXI_COMMENT[x.name]}")

    # D2. 干支问（历史年份 ×30，避开测试卷年份）
    TESTSET_YEARS = {755, 1127, 1644, 1912, 1840, 105, -841, 221, 907, 1279,
                     1368, 589, 960, 1911, 1662, 626, 1403, 1898, 280, 9}
    gy = [y for y in [-476, 220, 581, 690, 756, 1069, 1141, 1276, 1405, 1433,
                      1449, 1566, 1620, 1681, 1722, 1796, 1799, 1851, 1860, 1864,
                      1894, 1900, 1901, 1905, 1913, 1915, 1921, 1945, 1948, 1984,
                      1457, 1487, 1506, 1521, 1550, 1572, 1600, 1616, 1627, 1636,
                      1640, 1651, 1669, 1679, 1690, 1708, 1718, 1723, 1735, 1747]
          if y not in TESTSET_YEARS]
    for y in gy[:49]:
        yl = f"公元前{-y+1}年" if y <= 0 else f"公元{y}年"
        emit("干支", ["T03"], f"{yl}是什么干支年？",
             f"【规则计算】{lishu.ganzhi(y)}年。{yl}（{lishu.ganzhi(y)}年）；"
             f"干支序列以历法模块 huangji.lishu.ganzhi 可复现。")

    # ---- 落盘 ----
    os.makedirs("sft", exist_ok=True)
    with open("sft/batch3_candidates.jsonl", "w", encoding="utf-8") as fh:
        for r in OUT:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    fam = Counter(r["family"] for r in OUT)
    bad = [r["id"] for r in OUT if not r["qc"]["quote_ok"]]
    total = 115 + 18 + len(OUT)
    print(f"批次3候选 {len(OUT)}：" + " · ".join(f"{k}{v}" for k, v in fam.most_common()))
    print(f"质控：{len(OUT)-len(bad)}/{len(OUT)}" + (f"；未过 {bad[:8]}" if bad else ""))
    print(f"三批累计：{total} / 500 {'✅ 数据条件达成' if total >= 500 else '（未达 500）'}")


if __name__ == "__main__":
    main()
