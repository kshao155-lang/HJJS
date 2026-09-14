# -*- coding: utf-8 -*-
"""rag.py —— 邵雍语料检索件（RAG 基线的检索端）。

纯 Python BM25 + opencc 繁简归一 + 字符二元组分词。
索引对象 = corpus 全部分卷文本，按 ~500 字切块；检索结果带出处定位，
并按路径给出内容性质标签（原典/注家/托名衍生/批评参照）——呼应训练规范的四类标注。

用法:
    python rag.py 检索 以物观物            # 默认 top-5
    python rag.py 检索 "元会运世 129600" -k 8
    python rag.py 统计
    python rag.py 重建                     # 语料变更后重建缓存
"""

import glob
import os
import pickle
import re
import sys
from collections import Counter
from math import log

import opencc

ROOT = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(ROOT, "corpus")
CACHE = os.path.join(ROOT, "models", "rag_index.pkl")
CHUNK = 500          # 切块目标字符数
K1, B = 1.5, 0.75

T2S = opencc.OpenCC("t2s")

# 内容性质标签（按路径）
LABEL_RULES = [
    ("06_辨伪与工具", "辨伪工具"),
    ("05_批评与参照", "批评参照"),
    ("04_附_托名与衍生", "托名衍生"),
    ("00_皇极经世/注家", "注家解释"),
    ("01_伊川击壤集", "原典·诗集"),
    ("02_梅花易数", "托名·术数"),
    ("03_渔樵问对", "原典·问答"),
]


def label_of(path):
    rel = os.path.relpath(path, CORPUS)
    for pat, lab in LABEL_RULES:
        if pat in rel:
            return lab
    return "原典"


def load_chunks():
    """(文本, 出处, 性质标签, 块序号) 列表。"""
    chunks = []
    files = [f for f in glob.glob(os.path.join(CORPUS, "**", "*.txt"), recursive=True)
             + glob.glob(os.path.join(CORPUS, "**", "*.md"), recursive=True)
             if "_src" not in f and "build_corpus" not in f]
    for f in sorted(files):
        raw = open(f, encoding="utf-8").read()
        raw = re.sub(r"\s+", "", raw)
        for i in range(0, len(raw), CHUNK):
            piece = raw[i:i + CHUNK]
            if len(piece) < 30:
                continue
            chunks.append((piece, os.path.relpath(f, CORPUS), label_of(f), i // CHUNK))
    return chunks


def tokens(text_simplified):
    return [text_simplified[i:i + 2] for i in range(len(text_simplified) - 1)] or \
        ([text_simplified] if text_simplified else [])


class BM25:
    def __init__(self, chunks):
        self.chunks = chunks
        self.docs = [tokens(T2S.convert(c[0])) for c in chunks]
        self.tf = [Counter(d) for d in self.docs]
        self.len_avg = sum(len(d) for d in self.docs) / len(self.docs)
        self.N = len(self.docs)
        df = Counter()
        for d in self.docs:
            df.update(set(d))
        self.idf = {t: log((self.N - n + 0.5) / (n + 0.5) + 1) for t, n in df.items()}

    def search(self, query, k=5):
        q = tokens(T2S.convert(query))
        scores = []
        for i in range(self.N):
            s = 0.0
            dl = len(self.docs[i])
            for t in set(q):
                if t not in self.tf[i]:
                    continue
                f = self.tf[i][t]
                s += self.idf.get(t, 0) * f * (K1 + 1) / (f + K1 * (1 - B + B * dl / self.len_avg))
            if s > 0:
                scores.append((s, i))
        scores.sort(reverse=True)
        return scores[:k]


def build(save=True):
    chunks = load_chunks()
    idx = BM25(chunks)
    if save:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE, "wb") as fh:
            pickle.dump(chunks, fh)
    return chunks, idx


def load_or_build():
    if os.path.exists(CACHE):
        with open(CACHE, "rb") as fh:
            chunks = pickle.load(fh)
        return chunks, BM25(chunks)
    return build()


def show(chunks, hits):
    for s, i in hits:
        text, path, lab, ci = chunks[i]
        print(f"\n[{s:6.2f}] {path}（{lab}·块{ci}）")
        print("  " + text[:160] + ("…" if len(text) > 160 else ""))


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "检索"
    if cmd == "重建":
        chunks, _ = build()
        print(f"索引已重建：{len(chunks)} 块 → {CACHE}")
    elif cmd == "统计":
        chunks, _ = load_or_build()
        by = Counter(c[2] for c in chunks)
        print(f"语料块数 {len(chunks)}：" + " · ".join(f"{k}{v}" for k, v in by.most_common()))
    else:
        query = args[1] if len(args) > 1 and args[0] == "检索" else (args[0] if args else "以物观物")
        k = int(args[args.index("-k") + 1]) if "-k" in args else 5
        chunks, idx = load_or_build()
        hits = idx.search(query, k)
        print(f"检索「{query}」（繁简归一后匹配，共 {len(chunks)} 块）")
        show(chunks, hits)


if __name__ == "__main__":
    main()
