# -*- coding: utf-8 -*-
"""sft_build.py —— 邵雍思想 SFT 示范候选生成流水线（批次 1）。

红线执行方式：本脚本只"生成候选"（audit=pending），供人工审核定稿；
引文均来自已验证条目（规范 T01–T51）或确定性引擎输出；
生成后自动过质控（引文逐字校验/方案连带/标签完整性），质检结果写入 meta。

输出: sft/batch1_candidates.jsonl（每行一个样本）
      sft/batch1_audit.md（人工审核清单，按族分组）

运行: python sft_build.py
"""

import json
import os
import re
import sys

from huangji import gua, guanwu, lishu
from quote_guard import _corpus, _norm

OUT_DIR = "sft"
SYSTEM = ("你是「观物」邵雍研究助手。回答必须：①用【原典记述】【注家解释】【规则计算】"
          "【现代推演】标签标注内容性质；②引文逐字并给出处；③历算坐标连带起算方案"
          "（尧甲辰通行/赵友钦夏禹说）；④语料不足就明说；⑤不做预测。")

# ---- 已验证核心引文（规范 T01–T12 摘录；出处均经 grep 定位）----
CONCEPTS = [
    ("以物观物", "以物观物，性也；以我观物，情也。性公而明，情偏而暗。",
     "《观物外篇》（道藏本卷22）", "按事物自身之理观察则公明，以一己好恶投射则偏暗。", "T01"),
    ("数与术的边界", "天下之数出于理，违乎理则入于术。世人以数而入术，故失于理。",
     "《观物外篇》（道藏本卷22）", "数须服从结构之理，脱离理的数字游戏沦为占术。", "T02"),
    ("心为太极", "心为太极，又曰道为太极。",
     "《观物外篇》（道藏本卷22）", "本体与认识主体同构。", "T10"),
    ("先天学与心迹", "先天之学，心也；后天之学，迹也。",
     "《观物外篇》（道藏本卷23）", "先天学是内在结构之学，后天之学是已然痕迹之学。", "T11"),
    ("天地终始", "既有消长，岂无终始。",
     "《观物外篇》（道藏本卷23）", "有消长则必有终始——宇宙为一大循环。", "T12"),
    ("观之以理", "非观之以目，而观之以心也；非观之以心，而观之以理也。",
     "《观物内篇》（道藏本卷21）", "观察的三重递进：目→心→理。", "T13"),
    ("反观", "不以我观物者，以物观物之谓也。",
     "《观物内篇》（道藏本卷21）", "以物观物即反观。", "T15"),
    ("动静生刚柔", "动之始则阳生焉，动之极则阴生焉，一阴一阳交而天之用尽之矣；静之始则柔生焉，静之极则刚生焉。",
     "《观物内篇》（道藏本卷20）", "动静为阴阳刚柔之机。", "T07"),
    ("阴阳相与", "阳不能独立，必得阴而后立，故阳以阴为基；阴不能自见，必待阳而后见，故阴以阳为唱。",
     "《观物外篇》（道藏本卷22）", "阴阳互为条件。", "T08"),
    ("体用", "体无定用，惟变是用；用无定体，惟化是体。",
     "《观物内篇》（道藏本卷20）", "体用互变论。", "T40"),
    ("形神", "形可分，神不可分。",
     "《观物外篇》（道藏本卷22）", "形神分合之辨，非灵魂不朽论。", "T39"),
    ("倚数（体系的自我边界）", "参天两地而倚数，非天地之正数也。倚者，拟也。",
     "《观物外篇》（道藏本卷23）", "邵雍自认元会运世之数是拟象之数而非实测数。", "T21"),
]

FALSE_QUOTES = [
    ("宇宙便是吾心，吾心即是宇宙", "南宋陆九渊《象山语录》，非邵雍语。邵雍论心用「心为太极」。"),
    ("为天地立心，为生民立命", "北宋张载「横渠四句」，非邵雍。"),
    ("问渠那得清如许，为有源头活水来", "南宋朱熹《观书有感》，非邵雍。"),
]


def qc(text):
    """质控：引文逐字校验 + 标签完整。"""
    corpus = "".join(c[0] for c in _corpus())
    quotes = re.findall(r"([“「])([^”」]{8,})([”」])", text)
    bad = [q for _, q, _ in quotes if _norm(q) not in corpus]
    labs = re.findall(r"【[^】]+】", text)
    return (not bad), bad, len(labs)


def emit(out, family, spec_refs, user, assistant):
    ok, bad, nl = qc(assistant)
    out.append({
        "id": f"b1_{len(out)+1:04d}",
        "family": family,
        "spec_refs": spec_refs,
        "audit": "pending",
        "qc": {"quote_ok": ok, "bad_quotes": bad, "labels": nl},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
    })


def main():
    out = []

    # A. 概念解释族（12 条核心引文 × 2 问法）
    for name, quote, src, para, tid in CONCEPTS:
        q1 = f"什么是「{name}」？出自哪里？"
        a1 = (f"【原典记述】“{quote}”——{src}。\n\n"
              f"【注家解释】{para}\n\n"
              f"【现代推演】本项目将此条编为训练规范 {tid}，用于约束模型行为。")
        emit(out, "概念解释", [tid], q1, a1)
        q2 = f"邵雍关于「{name}」的原话是什么？请给出出处。"
        emit(out, "概念解释", [tid], q2,
             f"【原典记述】“{quote}”——{src}。（引文经语料逐字校验）")

    # B. 归属辨伪族
    for fq, ans in FALSE_QUOTES:
        emit(out, "归属辨伪", ["T50"], f"邵雍说过「{fq}」吗？",
             f"【原典记述】查无此语。此句实为{ans}\n\n"
             f"【现代推演】常见误引，辨伪依据见语料库 06_辨伪与工具。")
    for bk, ans in [("《梅花易数》", "后世术数家托名邵雍（通行本载清黄宗羲序），非邵雍本人所作，"
                                     "但其先天八卦数起卦机制沿用邵雍先天学框架。"),
                    ("《铁板神数》", "托名邵雍的晚出术书，非邵雍所作。"),
                    ("《梅花诗》十首", "托名邵雍，作者存疑。"),
                    ("《渔樵闲话录》", "旧题苏轼撰，与邵雍无关。")]:
        emit(out, "归属辨伪", ["T50"], f"{bk}是邵雍本人写的吗？",
             f"【注家解释】{ans}\n\n【原典记述】该书本项目语料库有收存或说明（见 corpus/04、06）。")

    # C. 历算族（确定性引擎输出）
    for y, label in [(2026, "2026 年"), (-2356, "唐尧即位的甲辰年（公元前 2357 年）"),
                     (1324, "泰定甲子年（1324 年）"), (618, "唐武德元年（618 年）")]:
        r1 = lishu.year_reading(y, scheme="尧甲辰通行")
        r2 = lishu.year_reading(y, scheme="赵友钦夏禹说")
        a = ("【规则计算】\n"
             f"- 尧甲辰通行方案：{r1['label']}（{r1['ganzhi']}年）＝ {r1['hui_branch']}会"
             f"（{r1['hui_gua']}卦）第{r1['yun_index']}运（{r1['yun_gua'].name}卦）"
             f"第{r1['shi_index']}世第{r1['nian_index']}年\n"
             f"- 赵友钦夏禹说方案：{r2['hui_branch']}会（{r2['hui_gua']}卦）第{r2['yun_index']}运"
             f"（{r2['yun_gua'].name}卦）第{r2['shi_index']}世第{r2['nian_index']}年\n\n"
             "【注家解释】两方案起算点不同（尧甲辰当午会初 vs 夏禹八年甲子当午会初，"
             "后者出自元·赵友钦《革象新书》），同一年坐标相差 140 年——读数必须连带方案。")
        emit(out, "历算", ["T03"], f"{label}在元会运世的什么位置？", a)

    # D. 卦象族（64 卦 × 结构问）
    for h in gua.ALL:
        xi = gua.xiaoxi_phase(h)
        extra = f"；十二消息卦第 {xi+1} 位（{guanwu.XIAOXI_COMMENT[h.name].split('：')[0]}）" if xi >= 0 else ""
        emit(out, "卦象", ["T04", "T24"], f"{h.name}卦{h.unicode_char}的结构是什么？",
             f"【规则计算】{h.name}卦{h.unicode_char}：上{h.upper}下{h.lower}"
             f"（{gua.TRIGRAMS[h.upper]['nature']}下{gua.TRIGRAMS[h.lower]['nature']}），"
             f"六爻自初至上为 {h.bits}（阳=1），二进制值 v={h.v}（初爻为最高位），"
             f"先天卦序第 {h.xiantian_index}，阳爻 {h.yang_count}/6{extra}。"
             f"（编码约定：初爻为最高位，本项目引擎可复现）")

    # E. 消息卦族（12 卦 × 义理）
    for xi, x in enumerate(gua.XIAOXI):
        emit(out, "消息卦义理", ["T26", "T27"], f"十二消息卦中的{x.name}卦处于什么相位？其义如何？",
             f"【规则计算】{x.name}卦：消息循环第 {xi+1} 位，阳爻 {x.yang_count}/6，"
             f"六爻 {x.bits}。\n\n【注家解释】{guanwu.XIAOXI_COMMENT[x.name]}")

    # F. 边界拒答族
    for pq in ["请预测2026年会不会有大的战争。", "帮我算算今年运势如何。",
               "用皇极经世推算某企业何时倒闭。", "哪个日子适合开业？请用卦数挑一个。"]:
        emit(out, "边界拒答", ["T02", "T05"],
             pq,
             "本系统不做预测。【原典记述】《观物外篇》：“天下之数出于理，违乎理则入于术。"
             "世人以数而入术，故失于理。”——数若脱离事理便沦为占术。\n\n"
             "【现代推演】本项目对四千年历史的检验结论：逐年治乱与绝对年相位无可学习关系。"
             "因此元会运世坐标可算（供观），事件不可测（不供占）。")

    # ---- 落盘 ----
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "batch1_candidates.jsonl"), "w", encoding="utf-8") as fh:
        for r in out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    from collections import Counter
    fam = Counter(r["family"] for r in out)
    qc_bad = [r for r in out if not r["qc"]["quote_ok"]]
    lines = ["# SFT 批次 1 · 候选与审核清单", "",
             f"- 候选总数 **{len(out)}**：" + " · ".join(f"{k} {v}" for k, v in fam.most_common()),
             f"- 自动质控：引文逐字校验通过 {len(out)-len(qc_bad)}/{len(out)}"
             + (f"；未过 {len(qc_bad)} 条需人工复核：{[r['id'] for r in qc_bad][:8]}" if qc_bad else ""),
             "- 审核方式：逐条将 audit 改为 approved/rejected（人工定稿，红线第 1 条）",
             "", "## 分族清单", ""]
    for f_, n in fam.most_common():
        ids = [r["id"] for r in out if r["family"] == f_]
        lines.append(f"- **{f_}**（{n}）：{ids[0]}…{ids[-1]}")
    with open(os.path.join(OUT_DIR, "batch1_audit.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
