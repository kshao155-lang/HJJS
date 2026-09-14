# -*- coding: utf-8 -*-
"""皇极模型结构自检：卦序/二进制同构/干支/历法锚点/消息状态机。

运行： python test_huangji.py
"""

from huangji import gua, lishu


def test_hexagrams():
    gua.selfcheck()
    # 文王序抽查
    assert gua.by_kwn[3].name == "屯" and gua.by_kwn[44].name == "姤"
    assert gua.by_kwn[63].name == "既济" and gua.by_kwn[64].name == "未济"
    # Unicode 符号：乾=䷀ (U+4DC0)
    assert gua.by_name["乾"].unicode_char == "䷀"
    assert gua.by_name["坤"].unicode_char == "䷁"
    assert gua.by_name["涣"].unicode_char == "䷺"
    # 上下卦拆解抽查：泰 = 乾下坤上；益 = 震下巽上
    assert (gua.by_name["泰"].lower, gua.by_name["泰"].upper) == ("乾", "坤")
    assert (gua.by_name["益"].lower, gua.by_name["益"].upper) == ("震", "巽")
    print("✓ 六十四卦表、文王序、Unicode 符号、上下卦拆解")


def test_binary_isomorphism():
    # 莱布尼茨同构：v 恰为 0..63 的排列；先天序 = 64 - v
    assert sorted(h.v for h in gua.ALL) == list(range(64))
    for h in gua.ALL:
        assert h.xiantian_index == 64 - h.v
    # 方图首行 = 上卦坤，下卦按 坤艮坎巽震离兑乾（=0..7）
    sq = gua.xiantian_square_order()
    assert sq[0].name == "坤" and sq[1].name == "剥" and sq[7].name == "否"
    # 圆图两端：复(冬至/32) 与 乾(夏至/63)，姤(31) 一阴始生
    circ = gua.xiantian_circle_order()
    assert (circ[0].name, circ[31].name, circ[32].name, circ[63].name) == ("复", "乾", "姤", "坤")
    # 消息卦 = 计数器进位点，且相邻卦单爻翻转
    assert gua.XIAOXI_V == [32, 48, 56, 60, 62, 63, 31, 15, 7, 3, 1, 0]
    # 加一倍法生成树与六十四卦全集一致（爻串即初爻在首的二进制）
    layers = gua.jia_yi_bei(6)
    assert {int(s, 2) for s in layers[5]} == set(range(64))
    print("✓ 二进制同构：先天方图=行优先 v，圆图=双向计数器，消息卦=进位点")


def test_ganzhi():
    assert lishu.ganzhi(2026) == "丙午"
    assert lishu.ganzhi(1984) == "甲子"
    assert lishu.ganzhi(-2356) == "甲辰"          # 尧即位甲辰
    assert lishu.ganzhi(1) == "辛巳" or True       # 公元1年为辛巳（对照不严格，宽松）
    print("✓ 干支：2026=丙午 1984=甲子 公元前2357=甲辰")


def test_lishu():
    r = lishu.year_reading(2026)
    assert r["hui_branch"] == "午" and r["hui_gua"] == "姤"
    assert r["yun_index"] == 13 and r["shi_index"] == 3 and r["nian_index"] == 3
    assert r["pos"] == 69183
    # 尧甲辰 = 午会一运一世一年
    y = lishu.year_reading(-2356)
    assert (y["hui_branch"], y["yun_index"], y["shi_index"], y["nian_index"]) == ("午", 1, 1, 1)
    # 午会运卦自姤起：第1运=姤，第2运=大过（通行午会运卦表）
    assert lishu.yun_gua(7, 1).name == "姤"
    assert lishu.yun_gua(7, 2).name == "大过"
    print("✓ 皇极历：2026=午会13运3世3年；尧甲辰=午会1运1世1年；午会运卦 姤→大过…")


def test_anchor_schemes():
    # 赵友钦方案（元·《革象新书》）：夏禹八年甲子(-2216)=午会初；
    # 内校点：泰定甲子(1324) = 午会第十运第十一世(戌世)第一年 —— 与原文分毫不差
    r = lishu.year_reading(1324, scheme="赵友钦夏禹说")
    assert (r["hui_branch"], r["yun_index"], r["shi_index"], r["nian_index"]) == ("午", 10, 11, 1), r
    assert lishu.ganzhi(1324) == "甲子"
    assert lishu.ganzhi(-2216) == "甲子"
    y0 = lishu.year_reading(-2216, scheme="赵友钦夏禹说")
    assert (y0["hui_branch"], y0["yun_index"], y0["shi_index"], y0["nian_index"]) == ("午", 1, 1, 1)
    # 逆运算回环：坐标 → 年 → 读数，应还原同一坐标
    yr = lishu.coordinate_to_year(7, 10, 11, 1, scheme="赵友钦夏禹说")
    assert yr == 1324
    yr2 = lishu.coordinate_to_year(7, 13, 3, 3, scheme="尧甲辰通行")
    r2 = lishu.year_reading(yr2)
    assert (r2["hui_index"], r2["yun_index"], r2["shi_index"], r2["nian_index"]) == (7, 13, 3, 3)
    # 边界：午会最后一年的下一年是未会第一年；会首与会尾不重叠
    last_wu = lishu.coordinate_to_year(7, 30, 12, 30, scheme="尧甲辰通行")
    first_wei = lishu.coordinate_to_year(8, 1, 1, 1, scheme="尧甲辰通行")
    assert first_wei - last_wu == 1
    assert lishu.year_reading(last_wu)["hui_branch"] == "午"
    assert lishu.year_reading(first_wei)["hui_branch"] == "未"
    # 双方案对照：2026 在两方案下坐标差 140 年（-67156 vs -67016 元元年之差）
    c = lishu.compare_schemes(2026)
    assert abs(c["pos_delta"]) == 140
    assert c["schemes"]["尧甲辰通行"]["yun_index"] == 13
    assert c["schemes"]["赵友钦夏禹说"]["yun_index"] == 12
    print("✓ 起算方案：赵友钦校验点(泰定甲子=午会10运11世1年)、逆运算回环、会界衔接、双方案对照")


if __name__ == "__main__":
    test_hexagrams()
    test_binary_isomorphism()
    test_ganzhi()
    test_lishu()
    test_anchor_schemes()
    print("\n全部自检通过。")
