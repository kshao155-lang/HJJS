# -*- coding: utf-8 -*-
"""历数：元会运世宇宙历法（皇极历）。

《皇极经世》的时间骨架 —— 仿"年月日时"造"元会运世"：
    1 元 = 12 会 = 360 运 = 4320 世 = 129,600 年
    1 会 = 30 运；1 运 = 12 世；1 世 = 30 年
    天开于子，地辟于丑，人生于寅；开物于寅，闭物于戌，坤终而复始。

锚点说明（历史注家方案不一，故参数化）：
    通行解读取"唐尧即位甲辰年（传统编年 公元前2357年，天文年 -2356）
    当午会第一运第一世第一年"。由此当前元元年（元历第1年）= 天文年 -67156。
    本引擎的"天文年"采用无零年记法：公元1年=1，公元前1年=0，公元前2357年=-2356。

内部约定：元历位置 pos ∈ [1, 129600]，1-based。
"""

try:
    from . import gua
except ImportError:  # 允许以脚本方式直接运行
    import gua

# ------------------------------------------------------------- 常数 ----

YUAN_YEARS = 129600   # 一元
HUI_YEARS = 10800     # 一会（30 运）
YUN_YEARS = 360       # 一运（12 世）
SHI_YEARS = 30        # 一世

HUI_BRANCHES = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

# 十二会配十二消息卦（通行现代重建方案，会序自子起）：
#   子=复(天开,一阳) 丑=临 寅=泰(人生,三阳开泰) 卯=大壮 辰=夬 巳=乾(阳极)
#   午=姤(一阴始生) 未=遯 申=否 酉=观 戌=剥(闭物) 亥=坤(天地终)
HUI_XIAOXI = ["复", "临", "泰", "大壮", "夬", "乾", "姤", "遯", "否", "观", "剥", "坤"]

# 天文年锚点：尧甲辰 = 午会第1运第1世第1年
YAO_ACCESSION_ASTR = -2356
YUAN_START_ASTR = YAO_ACCESSION_ASTR - 64800   # = -67156，当前元元年（元历 pos=1）

# ------------------------------------------------------- 起算方案对照 ----
# Codex 反馈(2026-09-13)要求"不同起算方案的并列比较"；此处只收有文献依据的方案。
ANCHOR_SCHEMES = {
    "尧甲辰通行": {
        "label": "尧甲辰当午会初（通行注家解读，本项目默认）",
        "yao_astr": YAO_ACCESSION_ASTR,
        "source": "《皇极经世·以运经世》起唐尧即位甲辰年；通行解读取尧即位即午会第一运第一世第一年。尧年绝对值学界尚有 ±1 年出入。",
    },
    "赵友钦夏禹说": {
        "label": "夏禹八年甲子当午会初（元·赵友钦《革象新书》）",
        "yao_astr": -2216,
        "source": "《原本革象新书》（四库本）：'夏禹八年甲子用为午会之初，当今泰定甲子乃午会第十运之戌世初年'；并评邵雍体系'实不可准'。内校：由此推泰定甲子(1324)=午会10运11世1年，与原文相合。",
    },
}
DEFAULT_SCHEME = "尧甲辰通行"


def yuan_start(scheme=DEFAULT_SCHEME):
    """起算方案 → 当前元元年的天文年。"""
    return ANCHOR_SCHEMES[scheme]["yao_astr"] - 64800


def compare_schemes(astr_year):
    """同年在不同起算方案下的读数对照（含差值）。"""
    out = {"year": astr_year, "schemes": {}}
    for name in ANCHOR_SCHEMES:
        out["schemes"][name] = year_reading(astr_year, scheme=name)
    a, b = [out["schemes"][n]["pos"] for n in ANCHOR_SCHEMES]
    out["pos_delta"] = b - a
    return out


# 皇极历是纯年数结构（会/运/世皆以"年"为单位，月/日/时仅取象类比），
# 不含"一年当三百六十日"之换算；象数坐标与真实历法的对勘属另一模块。
DISCLAIMER = (
    "历法声明：元会运世是纯年数结构（1世=30年、1运=360年、1会=10800年、1元=129600年），"
    "'年月日时'仅取象类比，不存在把历法一年当三百六十日的换算；"
    "象数坐标与真实天文历法的对勘应交由历法模块处理"
    "（参见赵友钦《革象新书》对'数整齐与天行实际'差别的批评，已收入 corpus/05_批评与参照/）。"
    "同一坐标的答案取决于起算方案：本引擎以参数显式承载（见 ANCHOR_SCHEMES），"
    "任一读数必须连同所用方案一并报告。"
)

GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
SHENGXIAO = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]


# ------------------------------------------------------------- 干支 ----

def ganzhi(astr_year):
    """天文年 → 干支名（如 2026 → 丙午）。适用正负年。"""
    idx = (astr_year - 4) % 60
    return GAN[idx % 10] + ZHI[idx % 12]


def shengxiao(astr_year):
    return SHENGXIAO[(astr_year - 4) % 12]


def bc_ad_label(astr_year):
    """天文年 → 显示串（公元前/公元）。"""
    if astr_year > 0:
        return f"公元{astr_year}年"
    if astr_year == 0:
        return "公元前1年"
    return f"公元前{-astr_year + 1}年"


# --------------------------------------------------------- 皇极历换算 ----

def to_yuan_pos(astr_year, scheme=DEFAULT_SCHEME):
    """天文年 → 元历位置 pos（1-based，跨元取模处理）。"""
    return (astr_year - yuan_start(scheme)) % YUAN_YEARS + 1


def yuan_epoch(astr_year, scheme=DEFAULT_SCHEME):
    """该年属于第几个元（自该方案元元年为第 1 元，向前后推算）。"""
    return (astr_year - yuan_start(scheme)) // YUAN_YEARS + 1


def coordinate_to_year(hui_index, yun_index, shi_index, nian_index, scheme=DEFAULT_SCHEME):
    """逆运算：元会运世坐标 → 该坐标首年的天文年。

    会/运/世为区间坐标（分别跨 10800/360/30 年），nian 给定时返回该年；
    欲得区间终点，把更深层的索引取最大值即可（如会始=coordinate_to_year(h,1,1,1)，
    会末=coordinate_to_year(h,30,12,30)）。
    """
    pos = (hui_index - 1) * HUI_YEARS + (yun_index - 1) * YUN_YEARS \
        + (shi_index - 1) * SHI_YEARS + nian_index
    return yuan_start(scheme) + pos - 1


def pos_to_reading(pos):
    """元历位置 → 完整分层读数 dict。"""
    p0 = pos - 1
    hui_i = p0 // HUI_YEARS                      # 0..11
    yun_in_hui = p0 % HUI_YEARS
    yun_i = yun_in_hui // YUN_YEARS              # 0..29
    shi_in_yun = yun_in_hui % YUN_YEARS
    shi_i = shi_in_yun // SHI_YEARS              # 0..11
    nian = shi_in_yun % SHI_YEARS + 1            # 1..30
    return {
        "pos": pos,
        "hui_index": hui_i + 1,                  # 1..12
        "hui_branch": HUI_BRANCHES[hui_i],
        "hui_gua": HUI_XIAOXI[hui_i],
        "yun_index": yun_i + 1,                  # 会内第 1..30 运
        "shi_index": shi_i + 1,                  # 运内第 1..12 世
        "nian_index": nian,                      # 世内第 1..30 年
        "yun_abs": hui_i * 30 + yun_i + 1,       # 元内绝对运序 1..360
        "shi_abs": hui_i * 360 + yun_i * 12 + shi_i + 1,  # 元内绝对世序 1..4320
    }


def year_reading(astr_year, scheme=DEFAULT_SCHEME):
    """天文年 → 完整皇极历读数（含干支、元序、运卦；结果必须连同起算方案报告）。

    运卦重建方案：运卦自会卦起，沿先天圆图顺取（会卦所在半圆方向），每运一卦。
    （午会自姤起得 姤大过鼎恒……，与通行注家的午会运卦表一致；其余会为同法推广。）
    """
    r = pos_to_reading(to_yuan_pos(astr_year, scheme))
    r["astr_year"] = astr_year
    r["label"] = bc_ad_label(astr_year)
    r["ganzhi"] = ganzhi(astr_year)
    r["yuan_no"] = yuan_epoch(astr_year, scheme)
    r["yun_gua"] = yun_gua(r["hui_index"], r["yun_index"])
    r["scheme"] = scheme
    return r


def yun_gua(hui_index, yun_index):
    """第 hui 会第 yun 运之卦：自会卦（消息卦）沿圆图方向顺取第 yun 个。"""
    hui_gua = gua.by_name[HUI_XIAOXI[hui_index - 1]]
    circ = gua.xiantian_circle_order()
    names = [h.name for h in circ]
    start = names.index(hui_gua.name)
    # 圆图序列本身即卦气正序：复→…→乾（阳息）、姤→…→坤（阴消），故恒沿列表前进
    return circ[(start + yun_index - 1) % 64]


def cosmic_phase_notes(scheme=DEFAULT_SCHEME):
    """当前元大事节点的天文年换算（依起算方案推得）。"""
    ys = yuan_start(scheme)

    def _y(pos):
        return ys + pos - 1
    return [
        ("元始", 1, _y(1)),
        ("子会·天开（一阳，复）", 1, _y(1)),
        ("丑会·地辟（临）", 10801, _y(10801)),
        ("寅会·开物人生（三阳，泰）", 21601, _y(21601)),
        ("卯会（大壮）", 32401, _y(32401)),
        ("辰会（夬）", 43201, _y(43201)),
        ("巳会·阳极（乾）", 54001, _y(54001)),
        ("午会·一阴始生（姤）——尧即位", 64801, _y(64801)),
        ("未会（遯）", 75601, _y(75601)),
        ("申会（否）", 86401, _y(86401)),
        ("酉会（观）", 97201, _y(97201)),
        ("戌会·闭物（剥）", 108001, _y(108001)),
        ("亥会·天地终（坤）", 118801, _y(118801)),
        ("元终（复归一元）", 129600, _y(129600)),
    ]


def format_reading(r):
    """读数 dict → 多行文本。"""
    lines = []
    lines.append(f"公历 {r['label']}（{r['ganzhi']}年）")
    lines.append(f"元历 第 {r['yuan_no']} 元 · 第 {r['pos']} 年  〔起算方案：{r['scheme']}〕")
    lines.append(
        f"皇极历  {r['hui_branch']}会（{r['hui_gua']}卦）"
        f" 第 {r['yun_index']} 运（{r['yun_gua'].name}卦）"
        f" 第 {r['shi_index']} 世 第 {r['nian_index']} 年"
    )
    lines.append(f"元内序   运 {r['yun_abs']}/360 · 世 {r['shi_abs']}/4320")
    return "\n".join(lines)


if __name__ == "__main__":
    for y in (-2356, -1046, 618, 959, 2026):
        r = year_reading(y)
        print(format_reading(r)); print("-" * 40)
