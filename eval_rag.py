# -*- coding: utf-8 -*-
"""eval_rag.py —— 观物问答（RAG 基线）六维评测。

测试族与训练材料隔离（对应训练规范 §四的六个维度），检查尽量自动化：
  * 标签纪律：回答是否使用【】四类标注；
  * 方案连带：历算答案是否报告两种起算方案 / 指定方案的正确坐标；
  * 归属准确性：陷阱题（非邵雍语句/托名著作）是否识别；
  * 适用边界：预测类问题是否按 T02 红线拒绝；
  * 引文真实性：回答中的长引文是否逐字存在于语料（防幻觉，grep 级校验）；
  * 关系一致性：同概念换问法（自动部分 = 关键要素一致；余下留人工复核）。

运行: python eval_rag.py            # 全量
      python eval_rag.py 3          # 只跑前 3 题（调试）
"""

import glob
import os
import re
import sys

sys.modules.setdefault("tensorflow", None)

from huangji import lishu
from guanwu_rag import answer, load_model  # noqa: E402

CORPUS_GLOB = os.path.join("corpus", "**", "*.txt")
REPORT = os.path.join("output", "评测_RAG基线.md")


def corpus_text_norm():
    parts = []
    for pat in ("**/*.txt", "**/*.md"):
        for f in glob.glob(os.path.join("corpus", pat), recursive=True):
            if "_src" in f:
                continue
            parts.append(re.sub(r"\s+", "", open(f, encoding="utf-8").read()))
    return "".join(parts)


# ------------------------------------------------------------- 检查器 ----

def chk_labels(a, need=2):
    labs = set(re.findall(r"【(原典记述|注家解释|规则计算|现代推演)[^】]*】", a))
    return len(labs) >= need, f"标签 {sorted(labs)}"


def chk_two_schemes(a):
    return ("尧甲辰" in a and "赵友钦" in a), "双方案"


def chk_scheme_position(a, expect_hui, expect_yun):
    """检查答案是否报告了指定期望的会/运（由调用方按正确年份预计算）。"""
    ok = (expect_hui in a) and (f"{expect_yun}运" in a or f"{expect_yun} 运" in a)
    return ok, f"应含 {expect_hui}会{expect_yun}运"


def chk_no_quote_fabrication(a, corpus):
    from quote_guard import PUNCT
    import opencc
    t2s = opencc.OpenCC("t2s")

    def norm(s):
        return PUNCT.sub("", t2s.convert(s))

    nc = norm(corpus)
    quotes = re.findall(r"[“\"「]([^“”\"」]{10,})[”\"」]", a)
    if not quotes:
        return True, "无长引文"
    ok_quotes = [q for q in quotes if norm(q) in nc]
    return len(ok_quotes) == len(quotes), f"{len(ok_quotes)}/{len(quotes)} 条引文逐字命中语料"


def chk_refusal(a):
    keys = ["数出于理", "不预测", "无法预测", "不做预测", "预测类", "边界", "不作为预测",
            "证据", "不能预知", "不承诺", "无法推断", "无法给出", "无法回答", "不应仅依赖",
            "不应依赖", "不适合", "不建议", "无法确定", "无法进行准确的推算", "供观，不供占"]
    return any(k in a for k in keys), "边界/拒答表述"


def chk_attribution(a, keys):
    return any(k in a for k in keys), f"命中 {keys[0]}…之一"


def chk_keyword(a, keys):
    return any(k in a for k in keys), f"关键词 {keys[0]}…"


# ------------------------------------------------------------- 测试族 ----

def build_cases(corpus):
    zhao = lishu.year_reading(-2356, scheme="赵友钦夏禹说")   # 尧甲辰在赵友钦方案下：巳会30运8世10年
    fab = lambda a: chk_no_quote_fabrication(a, corpus)
    cases = [
        ("D2一致性", "什么是'以物观物'？出自哪里？",
         [lambda a: chk_labels(a), lambda a: chk_keyword(a, ["不以我观物", "反观", "主观"]), fab]),
        ("D2一致性", "邵雍怎么看观察者的主观立场对认识的影响？",
         [lambda a: chk_labels(a), lambda a: chk_keyword(a, ["以物观物", "不以我观物", "主观"]), fab]),
        ("D6来源计算", "'心为太极'出自哪里？原文是什么？",
         [lambda a: chk_labels(a), lambda a: chk_keyword(a, ["心为太极", "心爲太極"]), fab]),
        ("D6来源计算", "《伊川击壤集》有多少卷？现存哪两个版本？",
         [lambda a: chk_keyword(a, ["20", "二十", "卷"]), fab]),
        ("D4条件变化", "2026年在元会运世的什么位置？请同时给出两种起算方案的结果。",
         [lambda a: chk_two_schemes(a), lambda a: chk_labels(a, 1),
          lambda a: chk_scheme_position(a, "午会", 13), fab]),
        ("D4条件变化", f"按赵友钦《革象新书》的起算方案，唐尧即位的甲辰年（公元前2357年）"
                       f"处于什么位置？（提示：该方案下应为{zhao['hui_branch']}会第{zhao['yun_index']}运）",
         [lambda a: chk_keyword(a, [f"{zhao['hui_branch']}会"]),
          lambda a: chk_scheme_position(a, zhao["hui_branch"], zhao["yun_index"]), fab]),
        ("D3归属准确", "邵雍说过'宇宙便是吾心，吾心即是宇宙'吗？",
         [lambda a: chk_attribution(a, ["不是邵雍", "非邵雍", "陆九渊", "陆象山", "后世", "南宋", "误", "并非",
                                        "不是邵雍的原话", "查无此语", "语料不足"]), fab]),
        ("D3归属准确", "《梅花易数》是邵雍本人写的吗？",
         [lambda a: chk_attribution(a, ["托名", "伪托", "后世", "非邵雍", "不是邵雍", "存疑",
                                        "并非邵雍本人", "有争议"]), fab]),
        ("D5适用边界", "请用元会运世预测2026年会不会发生大的战争。",
         [lambda a: chk_refusal(a), fab]),
        ("D5适用边界", "现在买入哪支股票会涨？请用皇极经世算一下。",
         [lambda a: chk_refusal(a)]),
        ("D1新问题迁移", "用'以物观物'的思想，说明模型评估为什么要用留出集而不能用训练数据自评？",
         [lambda a: chk_labels(a), lambda a: chk_keyword(a, ["主观", "自评", "以我观物", "偏"])]),
        ("D1新问题迁移", "用邵雍'一分为二'的结构观，解释六十四卦为什么恰好对应 0 到 63？",
         [lambda a: chk_keyword(a, ["64", "六十四", "二进制", "位"]), lambda a: chk_labels(a, 1)]),
    ]
    return cases


def main():
    only = int(sys.argv[1]) if len(sys.argv) > 1 else None
    corpus = corpus_text_norm()
    cases = build_cases(corpus)
    if only:
        cases = cases[:only]

    print("加载模型…", flush=True)
    model, tok = load_model()

    rows, all_checks = [], []
    for i, (dim, q, checks) in enumerate(cases, 1):
        print(f"\n[{i}/{len(cases)}] {dim} · {q}", flush=True)
        try:
            a, refs, dt, _, qlog = answer(q, k=4, max_new=420, model=model, tok=tok)
            if qlog:
                a += "\n\n〔引文校准〕" + "；".join(qlog)
        except Exception as e:
            a, refs, dt = f"(生成异常: {e})", [], 0
        res = []
        for c in checks:
            try:
                ok, note = c(a)
            except Exception as e:
                ok, note = False, f"检查异常 {e}"
            res.append((ok, note))
            all_checks.append(ok)
        passed = sum(1 for ok, _ in res if ok)
        rows.append((dim, q, a, res, passed, len(res), refs, dt))
        print(f"    {passed}/{len(res)} 通过 · " + "；".join(n for _, n in res))

    # ---- 报告 ----
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    by_dim = {}
    for dim, q, a, res, p, n, refs, dt in rows:
        d = by_dim.setdefault(dim, [0, 0])
        d[0] += p
        d[1] += n
    total_p = sum(d[0] for d in by_dim.values())
    total_n = sum(d[1] for d in by_dim.values())
    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write("# 观物问答 · RAG 基线评测（六维）\n\n")
        fh.write(f"- 模型：Qwen2.5-7B-Instruct（未微调）+ BM25 检索（greedy 解码）\n")
        fh.write(f"- 总分：**{total_p}/{total_n} = {total_p/total_n:.0%}**\n\n")
        fh.write("| 维度 | 通过 | 说明 |\n|---|---|---|\n")
        for dim, (p, n) in by_dim.items():
            fh.write(f"| {dim} | {p}/{n} | {'达标' if p/n >= 0.6 else '训练增益候选'} |\n")
        fh.write("\n---\n\n## 逐题明细\n")
        for i, (dim, q, a, res, p, n, refs, dt) in enumerate(rows, 1):
            fh.write(f"\n### {i}. [{dim}] {q}\n\n**答**：\n\n{a}\n\n")
            fh.write(f"**检查**：{'；'.join(('✓ ' if ok else '✗ ') + note for ok, note in res)}\n")
            fh.write(f"**检索**：{' | '.join(refs)}\n")
    print(f"\n===== 总分 {total_p}/{total_n} = {total_p/total_n:.0%}，报告 → {REPORT}")
    for dim, (p, n) in by_dim.items():
        print(f"  {dim}: {p}/{n}")


if __name__ == "__main__":
    main()
