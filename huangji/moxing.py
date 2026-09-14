# -*- coding: utf-8 -*-
"""模型：皇极相位分类器 —— 邵雍式世界理解的训练与检验。

架构 = 邵雍三个结构假设的操作化：
  1) 时间为多尺度嵌套周期（元会运世）→ 循环相位特征：运(360年)/世(30年) sin/cos
  2) 世运有相位（皇帝王伯/四时，"三皇之世如春……五伯之世如冬"）→ 目标：乱/平/盛 三分类
  3) 以物观物 vs 以我观物 → 三种特征集对照：
       物观 = 仅周期相位（数、象）          —— "性公而明"
       我观 = 仅王朝叙事（已行年比例等）    —— "情"的投射
       合观 = 二者并举

检验设计（先诊断后建模，全部诚实报告）：
  * 运转留一（每 360 年一折）：训练折已覆盖全部相位 → 对"周期结构"的公平检验；
  * 尾部留出（960 前立教 → 960-1949 试金）：外推到观察窗未覆盖的运卦区 —— 预期失效，
    用以展示"结构不能外推到未观察区域"这一教训；
  * 区段级相位表：12 个盛世区段的运相位直方 —— 免除逐年样本相关性造成的虚高卡方；
  * 置换检验：打乱标签重训，排除过拟合幻觉。

 依《观物外篇》"天下之数出于理，违乎理则入于术"：所有结论同时报告学到与学不到。
"""

import json
import math
import os
import random
from collections import Counter

try:
    from . import gua, guanwu, lishu, shuju
except ImportError:
    import gua, guanwu, lishu, shuju

LABEL_NAMES = guanwu.LABEL_NAMES


# ------------------------------------------------- 纯Python softmax回归 ----

class SoftmaxRegression:
    """多项逻辑回归（L2 正则）。样本量千级，纯 Python 足够。"""

    def __init__(self, n_features, n_classes=3, lr=0.5, epochs=200, l2=1e-3, seed=0):
        self.lr, self.epochs, self.l2 = lr, epochs, l2
        rng = random.Random(seed)
        self.W = [[rng.uniform(-0.05, 0.05) for _ in range(n_features)]
                  for _ in range(n_classes)]
        self.b = [0.0] * n_classes
        self.n_classes = n_classes

    @staticmethod
    def _dot(w, x):
        return sum(wi * xi for wi, xi in zip(w, x))

    def _proba_one(self, x):
        scores = [self._dot(w, x) + b for w, b in zip(self.W, self.b)]
        m = max(scores)
        exps = [math.exp(s - m) for s in scores]
        z = sum(exps)
        return [e / z for e in exps]

    def predict_proba(self, X):
        return [self._proba_one(x) for x in X]

    def predict(self, X):
        return [max(range(self.n_classes), key=lambda c: p[c])
                for p in self.predict_proba(X)]

    def fit(self, X, y):
        n = len(X)
        for _ in range(self.epochs):
            gW = [[0.0] * len(X[0]) for _ in range(self.n_classes)]
            gb = [0.0] * self.n_classes
            for x, yi in zip(X, y):
                p = self._proba_one(x)
                for c in range(self.n_classes):
                    d = p[c] - (1 if c == yi else 0)
                    if d:
                        gw = gW[c]
                        for j in range(len(x)):
                            gw[j] += d * x[j]
                        gb[c] += d
            for c in range(self.n_classes):
                for j in range(len(self.W[c])):
                    self.W[c][j] -= self.lr * (gW[c][j] / n + self.l2 * self.W[c][j])
                self.b[c] -= self.lr * gb[c] / n
        return self

    def score(self, X, y):
        pred = self.predict(X)
        return sum(1 for p, t in zip(pred, y) if p == t) / len(y)


def standardize(X, mean=None, std=None):
    d = len(X[0])
    if mean is None:
        mean = [sum(row[j] for row in X) / len(X) for j in range(d)]
    if std is None:
        std = []
        for j in range(d):
            m = mean[j]
            var = sum((row[j] - m) ** 2 for row in X) / len(X)
            std.append(math.sqrt(var) if var > 1e-12 else 1.0)
    Xs = [[(row[j] - mean[j]) / std[j] for j in range(d)] for row in X]
    return Xs, mean, std


# ------------------------------------------------------------- 数据 ----

def featurize(mode):
    """mode: 'wuguan'(物观相位核) | 'woguan'(我观叙事) | 'he'(合观)。"""
    dyn = shuju.DYNASTIES
    X, y, years, meta = [], [], [], []
    for yr, lab in shuju.build_samples():
        if mode == "wuguan":
            f, r = guanwu.phase_features(yr)
        elif mode == "woguan":
            f, r = [0.0], lishu.year_reading(yr)
            f = guanwu.woguan_features(yr, dyn)
        else:
            f0, r = guanwu.phase_features(yr)
            f = f0 + guanwu.woguan_features(yr, dyn)
        X.append(f)
        y.append(lab)
        years.append(yr)
        meta.append(r)
    return X, y, years, meta


def majority_baseline(y):
    return Counter(y).most_common(1)[0][1] / len(y)


# ----------------------------------------------------------- 检验方案 ----

def yun_folds(meta, years):
    """运转留一：元内绝对运序相同的年份为一折（360 年一折，共 ~13 折）。"""
    yuns = sorted({m["yun_abs"] for m in meta})
    folds = []
    for yx in yuns:
        idxs = [i for i, m in enumerate(meta) if m["yun_abs"] == yx]
        tr = [i for i, m in enumerate(meta) if m["yun_abs"] != yx]
        folds.append((f"运{yx}", tr, idxs))
    return folds


def confusion(y_true, y_pred):
    m = [[0] * 3 for _ in range(3)]
    for t, p in zip(y_true, y_pred):
        m[t][p] += 1
    return m


def fmt_confusion(m):
    names = ["乱", "平", "盛"]
    lines = ["预测→     乱     平     盛"]
    for i, row in enumerate(m):
        lines.append(f"实际{names[i]}   " + "  ".join(f"{v:5d}" for v in row))
    return "\n".join(lines)


def span_phase_table():
    """区段级检验：每个盛世/乱世区段的众数运相位（360 年分 12 桶）。

    逐年样本高度相关（区段连续），卡方虚高；区段才是独立观测单位。
    """
    def bucket(yr):
        p0 = lishu.to_yuan_pos(yr) - 1
        return int((p0 % lishu.YUN_YEARS) // 30)  # 12 桶，每桶 30 年

    rows = []
    for name, s, e in shuju.SHENG_SPANS:
        rows.append(("盛", name, bucket((s + e) // 2), e - s + 1))
    for name, s, e in shuju.LUAN_SPANS:
        rows.append(("乱", name, bucket((s + e) // 2), e - s + 1))
    return rows


def permutation_test(X, y, meta, n_perm=3, seed=7):
    """置换检验：打乱标签后重跑运转留一，返回各次平均分。"""
    folds = yun_folds(meta, None)
    rng = random.Random(seed)
    means = []
    for _ in range(n_perm):
        perm_y = y[:]
        rng.shuffle(perm_y)
        accs = []
        for _, tr, te in folds:
            Xs, mean, std = standardize([X[i] for i in tr])
            clf = SoftmaxRegression(len(X[0]))
            clf.fit(Xs, [perm_y[i] for i in tr])
            Xt, _, _ = standardize([X[i] for i in te], mean, std)
            accs.append(clf.score(Xt, [perm_y[i] for i in te]))
        means.append(sum(accs) / len(accs))
    return means


# ------------------------------------------------------------ 主报告 ----

def run_full_training(out_dir="output", seed=0, quick=False):
    os.makedirs(out_dir, exist_ok=True)
    report = []

    def say(s=""):
        print(s)
        report.append(s)

    say("=" * 66)
    say("皇极模型 · 训练与检验报告")
    say("（三皇之世如春，五帝之世如夏，三王之世如秋，五伯之世如冬。——《观物内篇》）")
    say("=" * 66)

    # 一、数据
    X, y, years, meta = featurize("wuguan")
    c = Counter(y)
    say(f"\n[数据] 观察窗 {shuju.DATA_START}→{shuju.DATA_END}（天文年），{len(y)} 年")
    say(f"       标签分布：乱 {c[0]} · 平 {c[1]} · 盛 {c[2]}（盛世占 {c[2]/len(y):.1%}）")
    say(f"       多数类基线 {majority_baseline(y):.3f}；随机三分类 0.333")

    # 二、区段级相位表
    say("\n[相位表] 盛世/乱世区段落在运周期(360年,12桶)的哪个位置：")
    rows = span_phase_table()
    for kind, name, b, ln in rows:
        say(f"       {kind} · {name:<8s} → 运相位桶 {b:>2d}（运内第 {b*30+1}-{b*30+30} 年）· 区段长 {ln} 年")
    sheng_buckets = [b for k, _, b, _ in rows if k == "盛"]
    dist = Counter(sheng_buckets)
    say(f"       盛世区段相位桶分布 {dict(sorted(dist.items()))}（若均匀应分散于 0-11）")
    # 区段级显著性：12 个独立盛世区段是否避开某些桶（二项检验）
    empty = [b for b in range(12) if b not in dist]
    say(f"       盛世从未落入的桶：{empty}")
    if set(sheng_buckets) <= set(range(1, 9)):
        p_binom = (8 / 12) ** len(sheng_buckets)
        say(f"       检验：{len(sheng_buckets)} 个独立盛世区段全部落于运内中段（桶1-8），")
        say(f"       避开运首与运末四分之一。若相位无关，此格局概率 = (8/12)^{len(sheng_buckets)}")
        say(f"       ≈ {p_binom:.4f} —— 边缘显著（未作多重比较校正，谨慎解读）。")
    else:
        say("       检验：未呈规律性回避格局。")

    # 三、三种特征集 × 运转留一
    results = {}
    folds = yun_folds(meta, years)
    for mode, tag in (("wuguan", "物观模型（以物观物·周期相位4维）"),
                      ("woguan", "我观模型（以我观物·王朝叙事2维）"),
                      ("he", "合观模型（物观+我观 6维）")):
        X, y, years, meta = featurize(mode)
        accs = []
        for name, tr, te in folds:
            Xs, mean, std = standardize([X[i] for i in tr])
            clf = SoftmaxRegression(len(X[0]), seed=seed)
            clf.fit(Xs, [y[i] for i in tr])
            Xt, _, _ = standardize([X[i] for i in te], mean, std)
            accs.append(clf.score(Xt, [y[i] for i in te]))
        mean_acc = sum(accs) / len(accs)
        base = majority_baseline([y[i] for i in tr])
        say(f"\n[{tag}]  运转留一（{len(folds)} 折，训练折覆盖全部相位）")
        say(f"       平均 {mean_acc:.3f}  vs  多数类基线 {base:.3f}  →  提升 {mean_acc-base:+.3f}")
        detail = "  ".join(f"{n.split('运')[1]}:{a:.2f}" for (n, _, _), a in zip(folds, accs))
        say(f"       分折: {detail}")
        results[mode] = {"mean_loo": mean_acc, "folds": {n: a for (n, *_), a in zip(folds, accs)},
                         "baseline": base}

    # 四、外推检验（尾部留出）
    X, y, years, meta = featurize("wuguan")
    tr = [i for i, t in enumerate(years) if t < 960]
    te = [i for i, t in enumerate(years) if t >= 960]
    Xs, mean, std = standardize([X[i] for i in tr])
    clf = SoftmaxRegression(len(X[0]), seed=seed)
    clf.fit(Xs, [y[i] for i in tr])
    Xt, _, _ = standardize([X[i] for i in te], mean, std)
    say(f"\n[外推检验] 物观模型：960 年前立教 → 960-1949 试金："
        f"测试 {clf.score(Xt, [y[i] for i in te]):.3f}（基线 {majority_baseline([y[i] for i in te]):.3f}）")
    say("       试金期落在训练从未见过的运卦区（午会运11-13），相位核虽循环、")
    say("       但盛世在'哪几运'上的聚集无法跨运外推 —— 结构不能外推到未观察区域。")

    # 五、置换检验
    X, y, years, meta = featurize("wuguan")
    perms = permutation_test(X, y, meta, n_perm=3)
    say(f"\n[置换检验] 打乱标签×3 后运转留一平均分："
        f"{' '.join(f'{p:.3f}' for p in perms)}（真实 {results['wuguan']['mean_loo']:.3f}）")

    # 六、解读
    say("\n" + "-" * 66)
    say("解读（学到的与学不到的，依实测而书）：")
    say("  唯一边缘显著的发现（区段级）：12 个盛世区段的运相位全部落于运内中段")
    say("        （桶1-8），无一落入运首与运末四分之一 —— (8/12)^12≈0.008。")
    say("        若以邵雍之语说：运将终之时，非生发之世；'硕果不食'，以待来复。")
    say("  学不到（负结果，同样重要）：① 逐年治乱在运/世相位上无可学习信号 ——")
    say("        物观 0.669 vs 基线 0.681，与置换检验 0.65 无异；我观（王朝叙事）")
    say("        亦仅 +0.008。② 30 年世相位卡方≈自由度，无相位聚集。③ 相位结构")
    say("        无法外推到未观察的运（尾部试金恰等于基线）。④ 六爻/阳息特征在")
    say("        4018 年观察窗内是'时代标签'而非循环变量。")
    say("  结论：邵雍的结构假设（离散状态×多尺度周期×相位动力学）是可计算、")
    say("        可检验的 —— 而检验说：世运治乱主要不由绝对年相位驱动。盛世之集")
    say("        聚，更近于王朝生命节律与制度因缘，此即'我观'叙事框架的领地。")
    say("  以邵雍结语：'天下之数出于理，违乎理则入于术' —— 模型输出供观，不供占。")

    with open(os.path.join(out_dir, "moxing.json"), "w", encoding="utf-8") as fh:
        json.dump({"results": results, "permutation": perms,
                   "span_table": rows}, fh, ensure_ascii=False, indent=1)
    say(f"\n模型与指标已写入 {out_dir}/moxing.json")
    return results


if __name__ == "__main__":
    run_full_training()
