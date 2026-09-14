# -*- coding: utf-8 -*-
"""观物 —— 皇极模型命令行入口。

用法：
    python guanwu.py            观 2026 年（默认当年）
    python guanwu.py 1662       观指定公元年（负数表示公元前，如 -2356 = 公元前2357）
    python guanwu.py 卦 涣      展开一卦
    python guanwu.py 元谱       当前元的开合大事谱

"夫所以谓之观物者，非以目观之也；非观之以目，而观之以心也；非观之以心，而观之以理也。"
"""

import math
import sys

from huangji import gua, guanwu, lishu, moxing, shuju

YEAR = 2026


def gua_card(h, title=""):
    lines = [h.bits[i] for i in range(6)]  # 初→上
    rows = []
    for i in (5, 4, 3, 2, 1, 0):
        bar = "━━━━" if lines[i] == "1" else "━ ╱━"
        tag = ""
        if i == 0:
            tag = "  ←初爻"
        elif i == 5:
            tag = "  ←上爻"
        rows.append("   " + bar + tag)
    return "\n".join([
        f"【{h.name}卦 {h.unicode_char}】{title}",
        f"   上卦 {h.upper}{gua.TRIGRAMS[h.upper]['sym']}{gua.TRIGRAMS[h.upper]['nature']} · "
        f"下卦 {h.lower}{gua.TRIGRAMS[h.lower]['sym']}{gua.TRIGRAMS[h.lower]['nature']}",
        *rows,
        f"   二进制 v={h.v}（初爻为最高位）· 先天序 {h.xiantian_index} · 阳爻 {h.yang_count}/6",
    ])


def observe_year(yr):
    r = lishu.year_reading(yr)
    print("=" * 60)
    print("观  物")
    print("（非观之以目，而观之以理也 ——《观物内篇》）")
    print("=" * 60)
    print(lishu.format_reading(r))

    # 当前消息相位与运卦
    h = r["yun_gua"]
    xi = gua.nearest_xiaoxi(h)
    xs = gua.XIAOXI[xi]
    print()
    print(gua_card(h, f"当前运卦（{r['hui_branch']}会第{r['yun_index']}运）"))
    phase = guanwu.XIAOXI_COMMENT[xs.name]
    print(f"消息相位：近 {xs.name}（阳息 {xs.yang_count}/6）—— {phase}")

    # 训练模型的当期判定（即时训练一个物观模型，全窗拟合）
    print()
    print("-" * 60)
    print("模型判定（物观相位核 · 在 4018 年治乱史上即时训练）")
    X, y, years, meta = moxing.featurize("wuguan")
    f, _ = guanwu.phase_features(yr)
    Xs, mean, std = moxing.standardize(X)
    clf = moxing.SoftmaxRegression(len(X[0]), epochs=200)
    clf.fit(Xs, y)
    fs, _, _ = moxing.standardize([f], mean, std)
    p = clf._proba_one(fs[0])
    pred = max(range(3), key=lambda c: p[c])
    print(f"  {yr} 年相位 → 预测：{guanwu.LABEL_NAMES[pred]}  "
          f"(乱 {p[0]:.0%} · 平 {p[1]:.0%} · 盛 {p[2]:.0%})")
    base = moxing.majority_baseline(y)
    print(f"  诚实注记：运转留一下该模型与多数类基线无异（{moxing_results_note()}），")
    print(f"  此判定实为基线附近的历史先验 —— 供观，不供占。")
    print(f"  基线：平 {base:.0%}")

    # 宇宙钟上的位置
    print()
    print("-" * 60)
    print("宇宙钟（当前元 129,600 年）")
    pos = r["pos"]
    print(f"  元内位置：第 {pos} 年 / 129,600（{pos/1296:.1f}%）")
    nxt = [(n, p) for n, p, _ in lishu.cosmic_phase_notes() if p > pos]
    if nxt:
        nm, np_ = nxt[0]
        print(f"  下一节点：{nm}（元历第 {np_} 年，距今 {np_ - pos} 年）")
    print()
    print("-" * 60)
    print("康节曰：" + guanwu.quotes()["数理"])
    print("=" * 60)


def moxing_results_note():
    import json, os
    fp = os.path.join("output", "moxing.json")
    if os.path.exists(fp):
        with open(fp, encoding="utf-8") as fh:
            d = json.load(fh)
        w = d["results"].get("wuguan", {})
        return f"物观 {w.get('mean_loo', 0):.3f} vs 基线 {w.get('baseline', 0):.3f}"
    return "（尚未运行训练，见 xunlian.py）"


def show_gua(name):
    h = gua.by_name.get(name) or gua.by_v.get(int(name) % 64)
    if h is None:
        print(f"未识卦：{name}（可用卦名或 0-63 之数）")
        return
    print(gua_card(h))
    xi = gua.xiaoxi_phase(h)
    if xi >= 0:
        print(f"十二消息卦第 {xi + 1} 位：" + guanwu.XIAOXI_COMMENT[h.name])
    else:
        nx = gua.XIAOXI[gua.nearest_xiaoxi(h)]
        print(f"非消息卦；最近消息相位为 {nx.name} —— " + guanwu.XIAOXI_COMMENT[nx.name])


def yuan_spectrum():
    print("当前元开合谱（天开于子，地辟于丑，人生于寅；既有消长，必有终始）")
    for name, pos, astr in lishu.cosmic_phase_notes():
        print(f"  元历 {pos:>6d} 年  {lishu.bc_ad_label(astr):<12s}  {name}")


def compare_anchors(yr):
    """不同起算方案对照（Codex 反馈要求的'起算方案并列比较'）。"""
    print("=" * 60)
    print("起算方案对照")
    print(lishu.DISCLAIMER)
    print("=" * 60)
    for name, meta in lishu.ANCHOR_SCHEMES.items():
        r = lishu.year_reading(yr, scheme=name)
        print(f"\n〔{name}〕{meta['label']}")
        print(f"  依据：{meta['source']}")
        print("  " + lishu.format_reading(r).replace("\n", "\n  "))
    c = lishu.compare_schemes(yr)
    print(f"\n两方案元历坐标相差 {abs(c['pos_delta'])} 年 —— "
          f"这正是'同一坐标、不同注家'的真实分歧，读数必须连带方案报告。")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        observe_year(YEAR)
    elif args[0] == "卦":
        show_gua(args[1])
    elif args[0] == "元谱":
        yuan_spectrum()
    elif args[0] == "对比":
        compare_anchors(int(args[1]) if len(args) > 1 else YEAR)
    else:
        observe_year(int(args[0]))
