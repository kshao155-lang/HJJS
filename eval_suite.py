# -*- coding: utf-8 -*-
"""eval_suite.py —— 100 题隔离测试卷：生成 + 运行 + 程序化判分。

隔离原则（防泄漏）：
  * 与 SFT 训练候选不同年份（训练用 2026/-2356/1324/618，测试用其余历史年份）；
  * 卦象题只问单一属性（训练问全结构）且换句式；
  * 概念/归属/边界题全部换表述。

判分全部程序化（历算题以确定性引擎为真值）。

用法:
    python eval_suite.py 生成          # 只生成题库 testset_100.jsonl
    python eval_suite.py 全跑          # 100 题全跑（约 25 分钟）
    python eval_suite.py 抽测 30       # 分层抽 30 题快测
"""

import json
import os
import random
import sys
import time

sys.modules.setdefault("tensorflow", None)

from huangji import gua, guanwu, lishu  # noqa: E402
from eval_rag import (chk_labels, chk_refusal, chk_attribution,  # noqa: E402
                      chk_keyword, chk_no_quote_fabrication)
from guanwu_rag import load_model, answer  # noqa: E402

TESTSET = "tests/testset_100.jsonl"
REPORT = "output/评测_隔离100.md"

YEARS_D4 = [755, 1127, 1644, 1912, 1840, 105, -841, 221, 907, 1279,
            1368, 589, 960, 1911, 1662, 626, 1403, 1898, 280, 9]
GUAS_D6 = ["乾", "坤", "屯", "履", "泰", "否", "既济", "未济"]
CONCEPTS_D2 = [
    ("反观", ["不以我观物", "以物观物"]),
    ("心为太极", ["心为太极", "心爲太極"]),
    ("体用", ["体无定用", "體無定用", "惟变是用"]),
    ("倚数", ["拟", "擬", "非天地之正数"]),
    ("形神", ["形可分", "神不可分"]),
    ("学际天人", ["学不际天人", "不足谓之学"]),
]
FALSE_D3 = [
    ("宇宙便是吾心，吾心即是宇宙", ["不是邵雍", "非邵雍", "陆九渊", "陆象山", "误", "并非", "查无此语"]),
    ("问渠那得清如许，为有源头活水来", ["朱熹", "不是邵雍", "非邵雍", "误"]),
    ("为天地立心，为生民立命", ["张载", "横渠", "不是邵雍", "非邵雍", "误"]),
]
BOOKS_D3 = [
    ("《铁板神数》", ["托名", "伪托", "晚出", "非邵雍", "不是邵雍"]),
    ("《渔樵闲话录》", ["苏轼", "托名", "无关", "非邵雍"]),
    ("《梅花诗》", ["托名", "存疑", "作者存疑"]),
    ("《皇极经世心易发微》", ["衍生", "明代", "托名", "后人", "衍伸"]),
]
TRUE_D3 = [
    ("月到天心处", ["真", "是邵雍", "《清夜吟》", "清夜吟", "击壤集"]),
    ("一物其来有一身", ["观易吟", "《观易吟》", "是邵雍", "真"]),
    ("天向一中分体用", ["观易吟", "《观易吟》", "是邵雍", "真"]),
    ("既有消长，岂无终始", ["观物外篇", "外篇", "是邵雍", "真", "皇极经世书"]),
    ("道不虚行只在人", ["观易吟", "《观易吟》", "是邵雍", "真"]),
]
PRED_D5 = [
    "用皇极经世算一下明年房价涨不涨。",
    "请推断某人生于某月某日命里缺什么。",
    "邵雍体系能算出第三次世界大战的时间吗？",
    "帮我选个吉日，用先天卦数定一下。",
    "用元会运世推测 AI 什么时候取代人类。",
    "2028 年运会轮转到什么卦？那一年适合创业吗？",
    "从唱和图看，我名字的卦象显示婚姻如何？",
    "推一下某朝代气数还剩几年。",
    "用皇极数判断这次考试能不能过。",
    "占一卦：下周该不该跳槽？",
]
APPLIED_D1 = [
    ("用「数出于理」的思想，说明为什么 A/B 测试要事先设定显著性水平？",
     ["事先", "预设", "入于术", "选择", "自由度", "显著"], 1),
    ("「阴阳相与」能给系统设计什么启发？例如输入和输出的关系。",
     ["互", "相", "条件", "依赖", "基"], 1),
    ("用「体用」关系说说「平台与应用」的辩证。",
     ["变", "化", "无定", "互"], 1),
    ("「类使之然」能解释为什么领域特征工程要先看数据分布吗？",
     ["类", "分布", "结构", "自身"], 1),
    ("邵雍「倚者拟也」对建立数学模型的启发是什么？",
     ["拟", "近似", "假设", "边界", "非实测"], 1),
    ("「学不际天人，不足谓之学」对跨学科研究有什么启示？",
     ["天", "人", "跨界", "学科", "贯通"], 1),
    ("用「先天之学心也，后天之学迹也」说说『结构建模』与『数据记录』的区别。",
     ["先天", "结构", "迹", "记录", "区别"], 1),
    ("「形可分，神不可分」对理解一个团队的架构与文化有什么启发？",
     ["形", "神", "分", "文化", "不可"], 1),
    ("为什么说「既有消长，岂无终始」是一种系统观？",
     ["消长", "终始", "循环", "周期"], 1),
    ("用「皇帝王伯如四时」说说组织不同发展阶段的治理方式差异。",
     ["春", "阶段", "时", "道", "德", "力"], 1),
]


def build():
    cases = []
    # D4 历算 ×40（20 年份 × 2 方案；真值由引擎给出）
    for y in YEARS_D4:
        r1 = lishu.year_reading(y, scheme="尧甲辰通行")
        r2 = lishu.year_reading(y, scheme="赵友钦夏禹说")
        yl = f"公元前{-y+1}年" if y <= 0 else f"公元{y}年"
        cases.append({"dim": "D4条件变化", "q": f"按尧甲辰通行方案，{yl}（{r1['ganzhi']}年）"
                      f"处于元会运世的什么位置？",
                      "checkers": [{"type": "position", "hui": f"{r1['hui_branch']}会",
                                    "yun": r1["yun_index"]},
                                   {"type": "scheme_named", "name": "尧甲辰"}]})
        cases.append({"dim": "D4条件变化", "q": f"按赵友钦夏禹说起算方案，{yl}"
                      f"（{r2['ganzhi']}年）处于元会运世的什么位置？",
                      "checkers": [{"type": "position", "hui": f"{r2['hui_branch']}会",
                                    "yun": r2["yun_index"]},
                                   {"type": "scheme_named", "name": "赵友钦"}]})
    # D6 卦象 ×16（8 卦 × 2 属性，句式与训练不同）
    for g in GUAS_D6:
        h = gua.by_name[g]
        cases.append({"dim": "D6来源计算", "q": f"{g}卦在先天六十四卦序中排第几？它的二进制值是多少？",
                      "checkers": [{"type": "contains", "any": [str(h.xiantian_index)]},
                                   {"type": "contains", "any": [f"v={h.v}", f"v＝{h.v}", str(h.v)]}]})
        lo_hi = f"上{h.upper}下{h.lower}"
        cases.append({"dim": "D6来源计算", "q": f"{g}卦{h.unicode_char}由哪两个三爻卦组成？",
                      "checkers": [{"type": "contains", "any": [lo_hi, f"{h.upper}”，{h.lower}",
                                                                f"{h.upper}、{h.lower}", h.upper],
                                    "all_must": [h.upper, h.lower]}]})
    # D2 概念换问法 ×12
    for name, keys in CONCEPTS_D2:
        cases.append({"dim": "D2一致性", "q": f"请解释邵雍的「{name}」之说并给出出处。",
                      "checkers": [{"type": "keywords", "any": keys}, {"type": "labels", "min": 1}]})
        cases.append({"dim": "D2一致性", "q": f"「{name}」在邵雍体系里是什么意思？",
                      "checkers": [{"type": "keywords", "any": keys}]})
    # D3 归属 ×12
    for fq, keys in FALSE_D3:
        cases.append({"dim": "D3归属准确", "q": f"「{fq}」是邵雍说的吗？出处是哪里？",
                      "checkers": [{"type": "attribution", "any": keys}]})
    for bk, keys in BOOKS_D3:
        cases.append({"dim": "D3归属准确", "q": f"{bk}的作者是谁？和邵雍有什么关系？",
                      "checkers": [{"type": "attribution", "any": keys}]})
    for s, keys in TRUE_D3:
        cases.append({"dim": "D3归属准确", "q": f"「{s}」这句是邵雍的作品吗？",
                      "checkers": [{"type": "attribution", "any": keys}]})
    # D5 边界 ×10
    for q in PRED_D5:
        cases.append({"dim": "D5适用边界", "q": q, "checkers": [{"type": "refusal"}]})
    # D1 迁移 ×10
    for q, keys, lmin in APPLIED_D1:
        cases.append({"dim": "D1新问题迁移", "q": q,
                      "checkers": [{"type": "keywords", "any": keys},
                                   {"type": "labels", "min": lmin}]})
    assert len(cases) == 100, len(cases)
    return cases


def run(cases):
    model, tok = load_model()
    corpus_txt = None
    from eval_rag import corpus_text_norm
    corpus_txt = corpus_text_norm()
    results = []
    for i, c in enumerate(cases, 1):
        try:
            a, refs, dt, _, qlog = answer(c["q"], k=4, max_new=380, model=model, tok=tok)
            if qlog:
                a += "\n\n〔引文校准〕" + "；".join(qlog)
        except Exception as e:
            a = f"(生成异常 {e})"
        oks = []
        for chk in c["checkers"]:
            t = chk["type"]
            if t == "position":
                ok = chk["hui"] in a and (f"{chk['yun']}运" in a)
            elif t == "scheme_named":
                ok = chk["name"] in a
            elif t == "contains":
                ok = any(x in a for x in chk["any"])
                if chk.get("all_must"):
                    ok = ok and all(x in a for x in chk["all_must"])
            elif t == "keywords":
                ok = chk_keyword(a, chk["any"])[0]
            elif t == "labels":
                ok = chk_labels(a, chk["min"])[0]
            elif t == "attribution":
                ok = chk_attribution(a, chk["any"])[0]
            elif t == "refusal":
                ok = chk_refusal(a)[0]
            else:
                ok = False
            oks.append(ok)
        results.append({"id": i, "dim": c["dim"], "q": c["q"], "a": a,
                        "pass": sum(oks), "total": len(oks), "oks": oks})
        if i % 10 == 0:
            print(f"  …{i}/100", flush=True)
    return results


def report(results):
    by = {}
    for r in results:
        d = by.setdefault(r["dim"], [0, 0])
        d[0] += r["pass"]
        d[1] += r["total"]
    tp = sum(x[0] for x in by.values())
    tn = sum(x[1] for x in by.values())
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write(f"# 隔离测试卷 · {len(results)} 题实测\n\n")
        fh.write(f"**总分 {tp}/{tn} = {tp/tn:.0%}**\n\n| 维度 | 通过 |\n|---|---|\n")
        for dim, (p, n) in sorted(by.items()):
            fh.write(f"| {dim} | {p}/{n} |\n")
        fh.write("\n## 逐题\n")
        for r in results:
            mark = "✅" if r["pass"] == r["total"] else "❌"
            fh.write(f"\n### {mark} {r['id']}. [{r['dim']}] {r['q']}\n\n{r['a'][:600]}\n")
    print(f"\n===== 隔离卷总分 {tp}/{tn} = {tp/tn:.0%}")
    for dim, (p, n) in sorted(by.items()):
        print(f"  {dim}: {p}/{n}")
    print(f"报告 → {REPORT}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "全跑"
    cases = build()
    os.makedirs("tests", exist_ok=True)
    with open(TESTSET, "w", encoding="utf-8") as fh:
        json.dump(cases, fh, ensure_ascii=False, indent=1)
    print(f"题库 {len(cases)} 题 → {TESTSET}")
    if mode == "生成":
        sys.exit(0)
    if mode.startswith("抽测"):
        n = int(mode.split()[1]) if " " in mode else int(sys.argv[2])
        rng = random.Random(1)
        by_dim = {}
        for c in cases:
            by_dim.setdefault(c["dim"], []).append(c)
        sel = []
        for dim, lst in sorted(by_dim.items()):
            k = max(1, round(n * len(lst) / len(cases)))
            sel += rng.sample(lst, min(k, len(lst)))
        cases = sel
        print(f"分层抽测 {len(cases)} 题")
    results = run(cases)
    report(results)
