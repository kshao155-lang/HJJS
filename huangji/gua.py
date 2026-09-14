# -*- coding: utf-8 -*-
"""先天学核心：六十四卦与二进制的同构体系。

邵雍《观物外篇》："一分为二，二分为四，四分为八……合之斯为一，衍之斯为万。"

本模块的编码约定（全库统一）：
  * 六十四卦状态值 v ∈ [0, 63]，二进制读法为【初爻为最高位】自下而上读：
        v = b1*32 + b2*16 + b3*8 + b4*4 + b5*2 + b6   (b1=初爻……b6=上爻, 阳=1 阴=0)
  * 在此约定下，邵雍先天体系化为极简的数学结构：
      - 先天方图   = v 的行优先排布（上卦 = v 高 3 位，下卦 = v 低 3 位）
      - 先天圆图   = 计数器：复(32)→乾(63) 阳息，姤(31)→坤(0) 阴消
      - 先天卦序号 = 64 - v（乾一、夬二……坤六十四）
      - 先天八卦数 = 8 - 三卦v（乾一兑二离三震四巽五坎六艮七坤八）
      - 十二消息卦 = 二进制计数器的进位点（32,48,56,60,62,63,31,15,7,3,1,0），
        每卦仅比前一卦翻转一条爻 —— 一台单比特翻转的循环状态机。
  * 莱布尼茨(1703)所指出的"伏羲先天图=二进制 0..63"即此 v 之序。
"""

# ---------------------------------------------------------------- 八卦 ----

TRIGRAMS = {
    "乾": {"bits": (1, 1, 1), "sym": "☰", "nature": "天"},
    "兑": {"bits": (1, 1, 0), "sym": "☱", "nature": "泽"},
    "离": {"bits": (1, 0, 1), "sym": "☲", "nature": "火"},
    "震": {"bits": (1, 0, 0), "sym": "☳", "nature": "雷"},
    "巽": {"bits": (0, 1, 1), "sym": "☴", "nature": "风"},
    "坎": {"bits": (0, 1, 0), "sym": "☵", "nature": "水"},
    "艮": {"bits": (0, 0, 1), "sym": "☶", "nature": "山"},
    "坤": {"bits": (0, 0, 0), "sym": "☷", "nature": "地"},
}
# 先天八卦次序（乾一……坤八）
XIANTIAN_TRIGRAM_ORDER = ["乾", "兑", "离", "震", "巽", "坎", "艮", "坤"]


def trigram_v(name):
    """三爻卦的状态值（初爻为最高位，0..7）。先天八卦数 = 8 - trigram_v。"""
    b = TRIGRAMS[name]["bits"]
    return b[0] * 4 + b[1] * 2 + b[2]


def trigram_by_v(v):
    for name, t in TRIGRAMS.items():
        if trigram_v(name) == v:
            return name
    raise ValueError(v)


def trigram_xiantian_number(name):
    """先天八卦数：乾1 兑2 离3 震4 巽5 坎6 艮7 坤8。"""
    return 8 - trigram_v(name)


# -------------------------------------------------------------- 六十四卦 ----
# (卦名, 自初爻至上爻的爻位串, 文王卦序)。爻位串与文王卦序为标准通行表。
_HEXAGRAM_TABLE = [
    ("乾",   "111111",  1), ("坤",   "000000",  2), ("屯",   "100010",  3), ("蒙",   "010001",  4),
    ("需",   "111010",  5), ("讼",   "010111",  6), ("师",   "010000",  7), ("比",   "000010",  8),
    ("小畜", "111011",  9), ("履",   "110111", 10), ("泰",   "111000", 11), ("否",   "000111", 12),
    ("同人", "101111", 13), ("大有", "111101", 14), ("谦",   "001000", 15), ("豫",   "000100", 16),
    ("随",   "100110", 17), ("蛊",   "011001", 18), ("临",   "110000", 19), ("观",   "000011", 20),
    ("噬嗑", "100101", 21), ("贲",   "101001", 22), ("剥",   "000001", 23), ("复",   "100000", 24),
    ("无妄", "100111", 25), ("大畜", "111001", 26), ("颐",   "100001", 27), ("大过", "011110", 28),
    ("坎",   "010010", 29), ("离",   "101101", 30), ("咸",   "001110", 31), ("恒",   "011100", 32),
    ("遯",   "001111", 33), ("大壮", "111100", 34), ("晋",   "000101", 35), ("明夷", "101000", 36),
    ("家人", "101011", 37), ("睽",   "110101", 38), ("蹇",   "001010", 39), ("解",   "010100", 40),
    ("损",   "110001", 41), ("益",   "100011", 42), ("夬",   "111110", 43), ("姤",   "011111", 44),
    ("萃",   "000110", 45), ("升",   "011000", 46), ("困",   "010110", 47), ("井",   "011010", 48),
    ("革",   "101110", 49), ("鼎",   "011101", 50), ("震",   "100100", 51), ("艮",   "001001", 52),
    ("渐",   "001011", 53), ("归妹", "110100", 54), ("丰",   "101100", 55), ("旅",   "001101", 56),
    ("巽",   "011011", 57), ("兑",   "110110", 58), ("涣",   "010011", 59), ("节",   "110010", 60),
    ("中孚", "110011", 61), ("小过", "001100", 62), ("既济", "101010", 63), ("未济", "010101", 64),
]


def _bits_to_v(bits):
    return sum(int(b) << (6 - i) for i, b in enumerate(bits, start=1))


class Hexagram:
    __slots__ = ("name", "bits", "v", "kwn", "upper", "lower")

    def __init__(self, name, bits, kwn):
        self.name = name
        self.bits = bits                      # 初爻在最前
        self.v = _bits_to_v(bits)             # 0..63, 初爻=最高位
        self.kwn = kwn                        # 文王卦序 1..64
        lo = bits[:3]
        hi = bits[3:]
        self.lower = trigram_by_v(int(lo[0]) * 4 + int(lo[1]) * 2 + int(lo[2]))  # 下(内)卦
        self.upper = trigram_by_v(int(hi[0]) * 4 + int(hi[1]) * 2 + int(hi[2]))  # 上(外)卦

    @property
    def xiantian_index(self):
        """先天六十四卦序号（乾一……坤六十四）= 64 - v。"""
        return 64 - self.v

    @property
    def unicode_char(self):
        """Unicode 六十四卦符号（按文王序排列，U+4DC0 起）。"""
        return chr(0x4DBF + self.kwn)

    @property
    def yang_count(self):
        return self.bits.count("1")

    @property
    def lines_display(self):
        """自上爻到初爻的爻符（○阳 ▅阴 之类用 ━ ━ ─ 表现）。"""
        return " ".join("━━━" if c == "1" else "━ ━" for c in reversed(self.bits))

    def __repr__(self):
        return f"<卦 {self.name}{self.unicode_char} v={self.v} 先天序={self.xiantian_index}>"


_HEXAGRAMS = {}
for _n, _b, _k in _HEXAGRAM_TABLE:
    _HEXAGRAMS[_n] = Hexagram(_n, _b, _k)

by_name = _HEXAGRAMS
by_v = {h.v: h for h in _HEXAGRAMS.values()}
by_kwn = {h.kwn: h for h in _HEXAGRAMS.values()}
ALL = [by_kwn[i] for i in range(1, 65)]


def hexagram_from_v(v):
    return by_v[v % 64]


def hexagram_from_xiantian(idx):
    """先天序号 1..64 → 卦（乾一…坤六十四；v = 64 - 序号）。"""
    idx0 = (idx - 1) % 64
    return by_v[63 - idx0]


def hexagram_from_number(n):
    """梅花易数起卦用：先天八卦数 1..8 → 三爻卦名。"""
    return trigram_by_v(8 - ((n - 1) % 8 + 1))


# -------------------------------------------------------------- 加一倍法 ----

def jia_yi_bei(depth=6):
    """加一倍法：自太极逐层二分，返回每层的象列表。

    层1=两仪(阴阳) 层2=四象 层3=八卦 … 层6=六十四卦。
    阳先阴后（邵雍：'阳在先，阴在后'），每层为上层各象加阳/加阴。爻串以初爻为首位。
    """
    layer = ["1", "0"]  # 1=阳, 0=阴；阳先阴后
    out = [layer[:]]
    out = [layer[:]]
    for _ in range(depth - 1):
        layer = [x + "1" for x in layer] + [x + "0" for x in layer]
        out.append(layer[:])
    return out  # out[0]=两仪 ... out[5]=六十四卦(爻串, 初爻在首)


def xiantian_square_order():
    """先天方图行优先序列 = v 0..63（上卦=高3位，下卦=低3位）。"""
    return [hexagram_from_v(v) for v in range(64)]


def xiantian_circle_order():
    """先天圆图序列：自复(冬至)起阳息至乾，再自姤阴消至坤，共 64 卦。

    即 v 的序列 32..63, 31..0 —— 一台双向运转的 6 位二进制计数器。
    """
    return [hexagram_from_v(v) for v in list(range(32, 64)) + list(range(31, -1, -1))]


# ------------------------------------------------------------ 十二消息卦 ----

XIAOXI_NAMES = ["复", "临", "泰", "大壮", "夬", "乾", "姤", "遯", "否", "观", "剥", "坤"]
XIAOXI = [by_name[n] for n in XIAOXI_NAMES]          # 自冬至(复)起
XIAOXI_V = [h.v for h in XIAOXI]                     # 32,48,56,60,62,63,31,15,7,3,1,0


def xiaoxi_phase(h):
    """返回卦在十二消息循环中的阳息相位（0..11），非消息卦返回 -1。"""
    for i, x in enumerate(XIAOXI):
        if x.name == h.name:
            return i
    return -1


def nearest_xiaoxi(h):
    """任意卦 → 消息循环上最近的相位（按 v 的环形距离）。"""
    best, bd = 0, 999
    for i, x in enumerate(XIAOXI):
        d = min((h.v - x.v) % 64, (x.v - h.v) % 64)
        if d < bd:
            best, bd = i, d
    return best


# ---------------------------------------------------------------- 自检 ----

def selfcheck():
    """结构一致性自检：非法即抛异常。"""
    assert len(_HEXAGRAMS) == 64 and len(by_v) == 64 and len(by_kwn) == 64
    assert sorted(h.kwn for h in ALL) == list(range(1, 65))
    # 先天序 = 64 - v 的双射
    assert sorted(h.xiantian_index for h in ALL) == list(range(1, 65))
    assert by_name["乾"].v == 63 and by_name["坤"].v == 0
    assert by_name["复"].v == 32 and by_name["姤"].v == 31
    assert by_name["乾"].xiantian_index == 1 and by_name["坤"].xiantian_index == 64
    # 圆图：64 卦恰出现一次，端点为复/乾/姤/坤
    circ = xiantian_circle_order()
    assert len(circ) == 64 and len({h.name for h in circ}) == 64
    assert circ[0].name == "复" and circ[31].name == "乾" and circ[32].name == "姤" and circ[63].name == "坤"
    # 方图：首行应为 坤剥比观豫晋萃否（上卦坤，下卦坤艮坎巽震离兑乾）
    sq = xiantian_square_order()
    assert [h.name for h in sq[:8]] == ["坤", "剥", "比", "观", "豫", "晋", "萃", "否"]
    # 消息卦：每卦阳爻连续自初爻推进，且 v 为计数器进位点
    assert XIAOXI_V == [32, 48, 56, 60, 62, 63, 31, 15, 7, 3, 1, 0]
    for i in range(11):
        a, b = XIAOXI[i].bits, XIAOXI[i + 1].bits
        diff = sum(1 for x, y in zip(a, b) if x != y)
        assert diff == 1, (XIAOXI[i].name, XIAOXI[i + 1].name)
    # 加一倍法：第 6 层 64 象恰为六十四卦全集（爻串即初爻在首的二进制，与 v 同构）
    layers = jia_yi_bei(6)
    assert [len(x) for x in layers] == [2, 4, 8, 16, 32, 64]
    assert {int(s, 2) for s in layers[5]} == set(range(64))
    # 莱布尼茨同构：先天序与 v 的关系（乾宫末=泰第8，坤宫首=否第57）
    assert hexagram_from_xiantian(2).name == "夬" and hexagram_from_xiantian(8).name == "泰"
    assert hexagram_from_xiantian(57).name == "否" and hexagram_from_xiantian(64).name == "坤"
    return True


if __name__ == "__main__":
    selfcheck()
    print("gua 自检通过：六十四卦 ↔ 二进制 0..63 同构、方图/圆图/消息卦结构一致。")
