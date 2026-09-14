# -*- coding: utf-8 -*-
"""quote_guard.py —— 引文忠实度后处理（"以物观物"约束的工程化）。

模型回答中的带引号长引文，逐条与语料规范化比对：
  * 逐字命中 → 保留；
  * 相似度 ≥ 0.72 → 用语料原文替换（保留模型所指，还原本字）；
  * 相似度过低 → 去引号改标〔模型转述〕（不得冒充原典）。

用法（通常由 guanwu_rag.answer 内部调用）:
    from quote_guard import verify_quotes
    fixed, log = verify_quotes(answer_text)
"""

import difflib
import re

import opencc

from rag import load_or_build

T2S = opencc.OpenCC("t2s")
CORPUS_CACHE = None


PUNCT = re.compile(r"[\s，。、；：？！“”\"'「」『』（）《》〈〉*·—…\-,.:;?!]")


def _norm(s):
    return PUNCT.sub("", T2S.convert(s))


def _corpus():
    global CORPUS_CACHE
    if CORPUS_CACHE is None:
        chunks, _ = load_or_build()
        CORPUS_CACHE = [(_norm(t), t, path, lab) for t, path, lab, _ in chunks]
    return CORPUS_CACHE


def _best_match(nq):
    """返回 (相似度, 语料连续原文段, 出处)。片段取首末匹配块之间的连续原文（含标点）。"""
    best = (0.0, "", "")
    for cnorm, ctext, path, lab in _corpus():
        if len(nq) < 14:
            prescreen = nq in cnorm
        else:
            prescreen = nq[:6] in cnorm or nq[-6:] in cnorm
        if not prescreen:
            continue
        sm = difflib.SequenceMatcher(None, cnorm, nq)
        blocks = [b for b in sm.get_matching_blocks() if b.size >= 2]
        matched = sum(b.size for b in blocks)
        score = matched / max(1, len(nq))
        if score > best[0] and blocks:
            span = ctext[blocks[0].a: blocks[-1].a + blocks[-1].size]
            best = (score, span, f"{path}（{lab}）")
    return best


def verify_quotes(text, min_len=8, replace_at=0.72):
    log = []

    def fix(m):
        open_q, body, close_q = m.group(1), m.group(2), m.group(3)
        if len(body) < min_len:
            return m.group(0)
        nq = _norm(body)
        corpus = "".join(c[0] for c in _corpus())
        if nq in corpus:
            return m.group(0)
        score, piece, src = _best_match(nq)
        if score >= replace_at and piece:
            log.append(f"已校准→语料原文（{src}，相似度{score:.2f}）：{piece[:40]}…")
            return f"{open_q}{piece}{close_q}"
        log.append(f"去引号改标〔模型转述〕（与语料最大相似度{score:.2f}）：{body[:30]}…")
        return f"〔模型转述〕{body}"

    fixed = re.sub(r"([“「])([^“”」]{8,})([”」])", fix, text)
    return fixed, log


if __name__ == "__main__":
    demo = ("【原典记述】“以物观物，性也；以我观物，情也。性公而明，情偏而暗。”"
            "【现代推演】“这句话说明了客观观察的重要性。”")
    fixed, log = verify_quotes(demo)
    print(fixed)
    print("\n".join(log) or "（无需修复）")
