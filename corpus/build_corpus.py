# -*- coding: utf-8 -*-
"""把 corpus/_src 下的原始下载整理为 corpus/ 阅读版文本。

来源（均为公有领域古籍数字化文本）:
  * kanripo/KR5d0063  《皇極經世》正统道藏本 (DZ1040)，org-mode txt
  * kanripo/KR5d0065  《伊川擊壤集》kanripo 本，org-mode txt
  * bkkbooks/KR3g0005 《皇極經世書》文渊阁四库全书本 (WYG)，yaml
  * bkkbooks/KR4d0062 《擊壤集》bkkbooks 本，yaml
  * daizhige/         《梅花易数》《渔樵问对》等殆知阁整理本，纯文本

用法: python corpus/build_corpus.py
"""

import os
import re
import sys

SRC = os.path.join(os.path.dirname(__file__), "_src")
OUT = os.path.dirname(__file__)


def clean_kanripo(txt):
    """org-mode 头与页码标记清洗。"""
    lines = []
    for ln in txt.splitlines():
        if ln.startswith("#"):            # org 头（含 #+TITLE 等，单独提取）
            continue
        ln = re.sub(r"<pb:[^>]*>", "", ln)  # 版面页码
        ln = ln.replace("¶", "")            # 段落符号
        ln = re.sub(r"[\ue000-\uf8ff]", "", ln)  # 私用区字符
        if ln.strip():
            lines.append(ln.rstrip())
    return "\n".join(lines) + "\n"


def kanripo_meta(txt):
    title = juan = None
    for ln in txt.splitlines():
        if ln.startswith("#+TITLE:"):
            title = ln.split(":", 1)[1].strip()
        elif ln.startswith("#+PROPERTY: JUAN"):
            juan = ln.split()[-1]
        if title and juan:
            break
    return title, juan


def parse_bkk_yaml(txt):
    """提取 yaml 中 front:/body: 的 text 字段（朴素解析，够用）。"""
    section = None
    front, body = [], []
    for ln in txt.splitlines():
        if re.match(r"^(front|body):", ln):
            section = ln.split(":")[0]
            continue
        m = re.match(r"^  text: ?(.*)$", ln)
        if m and section == "front":
            front.append(m.group(1))
        elif m and section == "body":
            body.append(m.group(1))
    pua = re.compile(r"[\ue000-\uf8ff]")
    return pua.sub("", "\n".join(front)).strip(), pua.sub("", "\n".join(body)).strip()


def save(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return len(content)


def zh(n):
    return f"{n/10000:.1f}万字" if n >= 10000 else f"{n}字"


def main():
    stats = []

    # ---- 皇极经世 · 道藏本 (KR5d0063) ----
    src = os.path.join(SRC, "KR5d0063")
    d = os.path.join(OUT, "00_皇极经世", "版本甲_正统道藏本DZ1040")
    for f in sorted(os.listdir(src)):
        if not f.endswith(".txt") or f.endswith("_000.txt"):
            continue
        raw = open(os.path.join(src, f), encoding="utf-8").read()
        title, juan = kanripo_meta(raw)
        n = save(os.path.join(d, f"卷{juan or f[9:12]}.txt"), clean_kanripo(raw))
        stats.append(("皇极经世·道藏本", f"卷{juan}", n))

    # ---- 皇极经世书 · 四库本 (KR3g0005, yaml) ----
    src = os.path.join(SRC, "KR3g0005")
    d = os.path.join(OUT, "00_皇极经世", "版本乙_文渊阁四库全书本")
    for f in sorted(os.listdir(src)):
        if not re.search(r"_\d+\.yaml$", f) or f.endswith("_000.yaml"):
            continue
        raw = open(os.path.join(src, f), encoding="utf-8").read()
        front, body = parse_bkk_yaml(raw)
        seq = re.search(r"_(\d+)\.yaml$", f).group(1)
        head = (front + "\n" if front else "")
        n = save(os.path.join(d, f"卷{int(seq):02d}.txt"), head + body + "\n")
        stats.append(("皇极经世书·四库本", f"卷{int(seq):02d}", n))

    # ---- 伊川击壤集 · kanripo 本 (KR5d0065) ----
    src = os.path.join(SRC, "KR5d0065")
    d = os.path.join(OUT, "01_伊川击壤集", "版本甲_kanripo本")
    for f in sorted(os.listdir(src)):
        if not f.endswith(".txt") or f.endswith("_000.txt"):
            continue
        raw = open(os.path.join(src, f), encoding="utf-8").read()
        title, juan = kanripo_meta(raw)
        n = save(os.path.join(d, f"卷{juan or f[9:12]}.txt"), clean_kanripo(raw))
        stats.append(("伊川击壤集·kanripo本", f"卷{juan}", n))

    # ---- 击壤集 · bkkbooks 本 (KR4d0062, yaml) ----
    src = os.path.join(SRC, "KR4d0062")
    d = os.path.join(OUT, "01_伊川击壤集", "版本乙_bkkbooks本")
    for f in sorted(os.listdir(src)):
        if not re.search(r"_\d+\.yaml$", f) or f.endswith("_000.yaml"):
            continue
        raw = open(os.path.join(src, f), encoding="utf-8").read()
        front, body = parse_bkk_yaml(raw)
        seq = re.search(r"_(\d+)\.yaml$", f).group(1)
        head = (front + "\n" if front else "")
        n = save(os.path.join(d, f"卷{int(seq):02d}.txt"), head + body + "\n")
        stats.append(("击壤集·bkkbooks本", f"卷{int(seq):02d}", n))

    # ---- 殆知阁单文件 ----
    singles = [
        ("_src/daizhige/梅花易数.txt", "02_梅花易数/梅花易数_黄宗羲序本.txt", "梅花易数"),
        ("_src/daizhige/渔樵问对.txt", "03_渔樵问对/渔樵问对.txt", "渔樵问对"),
        ("_src/daizhige/皇极经世.txt", "00_皇极经世/版本丙_邵子全书辑校本/皇极经世_邵子全书本.txt", "皇极经世·邵子全书本"),
        ("_src/daizhige/皇极经世书.txt", "00_皇极经世/版本丁_四库点校整理本/皇极经世书_四库整理本.txt", "皇极经世书·整理本"),
        ("_src/daizhige/皇极经世观物外篇衍义.txt", "00_皇极经世/注家_张行成/观物外篇衍义_张行成.txt", "观物外篇衍义(张行成)"),
        ("_src/daizhige/皇极经世心易发微.txt", "04_附_托名与衍生/皇极经世心易发微.txt", "皇极经世心易发微(衍生)"),
        ("_src/daizhige/渔樵闲话录.txt", "04_附_托名与衍生/渔樵闲话录_旧题苏轼.txt", "渔樵闲话录(旧题苏轼)"),
        ("_src/daizhige/原本革象新书.txt", "05_批评与参照/原本革象新书_赵友钦_四库本.txt", "革象新书(赵友钦原本)"),
        ("_src/daizhige/重修革象新书.txt", "05_批评与参照/重修革象新书_王祎删定_四库本.txt", "革象新书(王祎重修)"),
    ]
    for src_rel, dst_rel, name in singles:
        p = os.path.join(OUT, src_rel)
        raw = open(p, encoding="utf-8").read().strip()
        n = save(os.path.join(OUT, dst_rel), raw + "\n")
        stats.append((name, "全文", n))

    # ---- 汇总 ----
    print(f"{'著作':<24s}{'篇卷':<8s}{'字数':>10s}")
    cur = None
    agg, cnt = 0, 0
    rows = []
    for name, juan, n in stats:
        if name != cur and cur is not None:
            rows.append((cur, cnt, agg))
            agg, cnt = 0, 0
        cur = name
        agg += n
        cnt += 1
    rows.append((cur, cnt, agg))
    for name, cnt, agg in rows:
        print(f"{name:<26s}{cnt:>3d} 个文件  合计 {zh(agg)}")
    print(f"\n输出目录: {OUT}")


if __name__ == "__main__":
    main()
