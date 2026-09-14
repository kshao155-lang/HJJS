# -*- coding: utf-8 -*-
"""观物：把邵雍的认识论变成特征工程。

《观物外篇》："以物观物，性也；以我观物，情也。性公而明，情偏而暗。"

物观特征（WUGUAN）——只允许使用世界自身的结构：时（元会运世相位）、位（卦、消息）。
    这是"非观之以目而观之以理"的可计算化：模型看到的只有数与象。
我观特征（WOGUAN）——人类叙事特征：王朝已行年比例（"这个故事讲到第几章了"）。
    这是"以我观物"：把人的历史叙事框架投射进模型。对照两者的泛化能力，
    即是对照"性公而明"与"情偏而暗"。

标签体系：邵雍"皇帝王伯/四时"的简化三分类 —— 乱（冬）、平（秋）、盛（春夏）。
"""

import math

try:
    from . import gua, lishu
except ImportError:
    import gua, lishu

# ------------------------------------------------------------- 标签 ----

LABEL_NAMES = {0: "乱", 1: "平", 2: "盛"}
LABEL_SEASON = {0: "冬", 1: "秋", 2: "春夏"}


# ---------------------------------------------------------- 物观特征 ----

def _cyc(pos, period):
    """周期相位 → (sin, cos)。位置从 0 起。"""
    theta = 2.0 * math.pi * (pos % period) / period
    return math.sin(theta), math.cos(theta)


def wuguan_features(astr_year):
    """以物观物：仅由时间位置与卦象导出的结构特征。

    15 维：
      1-2   会内相位  sin/cos（周期 10800 年）
      3-4   运内相位  sin/cos（周期 360 年）
      5-6   世内相位  sin/cos（周期 30 年）
      7-8   运卦在先天圆图上的相位 sin/cos（周期 64）
      9-14  运卦六爻（阳=1 阴=0，初爻在前）
      15    消息阳息分数（最近消息卦的阳爻数 / 6）
    """
    r = lishu.year_reading(astr_year)
    p0 = r["pos"] - 1
    hui_in = p0 % lishu.HUI_YEARS
    yun_in = p0 % lishu.YUN_YEARS
    shi_in = p0 % lishu.SHI_YEARS

    h = r["yun_gua"]
    f = []
    f += list(_cyc(hui_in, lishu.HUI_YEARS))
    f += list(_cyc(yun_in, lishu.YUN_YEARS))
    f += list(_cyc(shi_in, lishu.SHI_YEARS))
    f += list(_cyc(h.v, 64))
    f += [int(c) for c in h.bits]
    nx = gua.XIAOXI[gua.nearest_xiaoxi(h)]
    f += [nx.yang_count / 6.0]
    return f, r


WUGUAN_DIM = 15
WUGUAN_NAMES = (
    ["会相位sin", "会相位cos", "运相位sin", "运相位cos", "世相位sin", "世相位cos",
     "圆图相位sin", "圆图相位cos",
     "初爻", "二爻", "三爻", "四爻", "五爻", "上爻", "阳息分数"]
)


# ----------------------------------------------------- 物观·相位核 ----

def phase_features(astr_year):
    """物观·相位核（4 维）：只保留在观察窗内真正循环的周期。

    特征集取舍（诚实建模）：
      * 运(360年)在 4018 年观察窗中循环 11 次、世(30年)循环 134 次 —— 可检验、入模；
      * 会(10800年)仅行 0.37 个周期、运卦六爻/阳息在窗内近似常量 —— 它们是"时代
        标签"而非循环变量，入模只会让模型记时代，故不入相位核（见调研报告 §九）。
    """
    r = lishu.year_reading(astr_year)
    p0 = r["pos"] - 1
    f = []
    f += list(_cyc(p0 % lishu.YUN_YEARS, lishu.YUN_YEARS))
    f += list(_cyc(p0 % lishu.SHI_YEARS, lishu.SHI_YEARS))
    return f, r


PHASE_NAMES = ["运相位sin", "运相位cos", "世相位sin", "世相位cos"]


# ---------------------------------------------------------- 我观特征 ----

def woguan_features(astr_year, dynasties):
    """以我观物：人类叙事特征（王朝已行年比例、王朝长度对数）。

    需要人类书写的王朝表 —— 这正是"我"的框架；若该年无王朝覆盖则取 0。
    """
    age_frac = 0.0
    log_len = 0.0
    for name, s, e in dynasties:
        if s <= astr_year <= e:
            age_frac = (astr_year - s) / max(1, (e - s))
            log_len = math.log10(max(1, e - s + 1))
            break
    return [age_frac, log_len]


WOGUAN_NAMES = ["王朝已行年比例", "王朝长度对数"]


def combined_features(astr_year, dynasties, use_woguan=False):
    f, r = wuguan_features(astr_year)
    if use_woguan:
        f = f + woguan_features(astr_year, dynasties)
    return f, r


# --------------------------------------------------------- 世运解读 ----

XIAOXI_COMMENT = {
    "复": "一阳来复：旧局已终，新机萌于至暗。既不可因循，亦不可躁进。",
    "临": "二阳浸长：事在渐进，宜蓄势观衅。",
    "泰": "三阳开泰：上下交而其志同。此治世之象，然泰极将否。",
    "大壮": "四阳方壮：气盛而宜以正自持，壮于进者凶。",
    "夬": "五阳决一阴：去之已近，然扬于王庭，危事也。",
    "乾": "六阳纯全：飞龙在天。物极之位，盈不可久——邵雍曰'阳极则阴生'。",
    "姤": "一阴始生：午会之象。盛极而微衰已萌，君子于此作百年之计。",
    "遯": "二阴浸长：退避非怯，与时行也。",
    "否": "三阴成否：天地不交。大往小来，宜俭德避难。",
    "观": "四阴方盛：观国之光。势不在进而在观。",
    "剥": "五阴剥一阳：闭物之候。硕果不食，藏用以待来复。",
    "坤": "六阴纯全：万化归藏。穷则变，变则通——坤之后复生一阳。",
}


def phase_comment(label):
    return {
        0: "衰乱之世（冬）：如五伯之世，以力相持，非生发之时。",
        1: "平守之世（秋）：如三王之世，以功以制，持盈保泰而已。",
        2: "隆盛之世（春夏）：如皇帝之世，道德新民，生发长养。",
    }[label]


def quotes():
    return {
        "观物": "非观之以目，而观之以心也；非观之以心，而观之以理也。",
        "物我": "以物观物，性也；以我观物，情也。性公而明，情偏而暗。",
        "数理": "天下之数出于理，违乎理则入于术。世人以数而入术，故失于理。",
        "消长": "既有消长，必有终始。",
        "一多": "合之斯为一，衍之斯为万。",
    }
