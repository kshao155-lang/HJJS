# -*- coding: utf-8 -*-
"""观物问答（RAG 首版）—— 本地 Qwen2.5-7B-Instruct + 语料检索 + 确定性历算工具。

分工原则（Codex 反馈采纳）：
  * LLM 负责检索解释与组织回答；
  * 元会运世/卦象等确定性计算由 huangji 引擎完成，以【规则计算】注入上下文；
  * 回答强制四类标注（原典记述/注家解释/规则计算/现代推演），引用须带出处；
  * 语料不足即答"语料不足"，禁止编造引文；不做事件预测（训练规范 T02/T05 红线）。

用法:
    python guanwu_rag.py 问 "2026年在元会运世的什么位置？"
    python guanwu_rag.py 问 "什么是'以物观物'？出处在哪里？" -k 5
    python guanwu_rag.py 交互                # 多轮（模型常驻显存）
"""

import os
import re
import sys
import time

import torch

# 本机 tensorflow 与 protobuf 版本错配（gencode 6.31 vs runtime 5.29），
# transformers 的视觉工具链会连带导入 TF；文本推理用不到 TF，屏蔽之（不动共享环境）。
sys.modules.setdefault("tensorflow", None)

from huangji import gua, guanwu, lishu
from rag import load_or_build

ROOT = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(ROOT, "models", "Qwen2.5-7B-Instruct")
TRANSCRIPT = os.path.join(ROOT, "output", "对话", "rag_qa.md")

SYSTEM = """你是"观物"邵雍研究助手，工作在《皇极经世》研究项目内。铁律：
1) 回答中每类内容必须用标签开头标注：【原典记述】（引语料原文并给出处文件与卷）、
   【注家解释】（标注家名）、【规则计算】（给起算方案名）、【现代推演】（明说是现代延伸）。
   语料块头部格式为〔语料N｜性质标签｜路径〕——引用某块时，性质标签必须照抄该块头部的
   标签，不得改标（托名衍生 不是 注家解释）。
2) 元会运世坐标必须连带起算方案（尧甲辰通行 / 赵友钦夏禹说）；工具已给出则照录，不得另算。
3) 只使用提供的语料块与历算结果；语料不足时明确说"语料不足，无法回答该部分"。
4) 不做任何具体事件预测（战争、灾祥、吉凶、股价、择日、运势等一律不预测）；
   被问预测时：第一步明确"本系统不做预测"；第二步引《观物外篇》"天下之数出于理，
   违乎理则入于术。世人以数而入术，故失于理"；第三步可转述本项目实验结论
   （四千年治乱与绝对年相位无关）作为依据，但不得给出任何预测性结论。
5) 涉及体系评价时，同时呈现支持与批评（如赵友钦《革象新书》"实不可准"）。
6) 引文须与语料块字面一致，不得改写或杜撰。"""


def find_years(q):
    """问题中出现的年份（含公元前；1–4 位数均识别，历史年份常不足 4 位）。"""
    years = []
    for m in re.finditer(r"公元前\s*(\d{1,4})\s*年", q):
        years.append(-(int(m.group(1)) - 1))
    for m in re.finditer(r"(?<![\d])(\d{1,4})\s*年", q):
        y = int(m.group(1))
        if 1 <= y <= 3000:
            years.append(y)
    return sorted(set(years))


def find_gua(q):
    return [n for n in gua.by_name if n in q and len(n) <= 2]


PREDICT_RE = re.compile(r"预测|预言|会不会|是否会发生|涨|跌|吉凶|算一算|算一下|指点|运势|"
                        r"适合.*吗|哪支|哪只|买|战|灾|发生什么|2026年.*(发生|战|灾)")


def tool_block(q):
    """确定性工具输出（规则计算层）。"""
    parts = []
    for y in find_years(q):
        for scheme in lishu.ANCHOR_SCHEMES:
            r = lishu.year_reading(y, scheme=scheme)
            parts.append(f"【规则计算·历算】{r['label']}（{r['ganzhi']}年）＝ {r['hui_branch']}会"
                         f"（{r['hui_gua']}卦）第{r['yun_index']}运（{r['yun_gua'].name}卦）"
                         f"第{r['shi_index']}世第{r['nian_index']}年 —— 起算方案：{scheme}")
    for n in find_gua(q):
        h = gua.by_name[n]
        xi = gua.xiaoxi_phase(h)
        info = (f"【规则计算·卦象】{h.name}卦{h.unicode_char}：上{h.upper}下{h.lower}，"
                f"二进制v={h.v}（初爻为最高位），先天序{h.xiantian_index}，阳爻{h.yang_count}/6")
        if xi >= 0:
            info += f"；十二消息卦第{xi+1}位"
        parts.append(info)
    return "\n".join(parts)


LABEL_PRIORITY = {"原典": 0, "原典·问答": 0, "原典·诗集": 1, "注家解释": 2,
                  "批评参照": 3, "辨伪工具": 1, "托名衍生": 8, "托名·术数": 8}


def diversify(chunks, hits, k):
    """每文件最多 2 块、按性质标签优先级重排，避免单一文献霸榜。"""
    per_file = {}
    picked = []
    for s, i in sorted(hits, key=lambda x: -x[0]):
        path = chunks[i][1]
        if per_file.get(path, 0) >= 2:
            continue
        per_file[path] = per_file.get(path, 0) + 1
        picked.append((s, i))
    picked.sort(key=lambda si: (LABEL_PRIORITY.get(chunks[si[1]][2], 5), -si[0]))
    return picked[:k]


def answer(q, k=6, max_new=512, model=None, tok=None):
    chunks, idx = load_or_build()
    hits = diversify(chunks, idx.search(q, k * 4), k)
    blocks = []
    for s, i in hits:
        text, path, lab, ci = chunks[i]
        blocks.append(f"〔语料{len(blocks)+1}｜{lab}｜{path}〕{text[:400]}")
    ctx = "\n\n".join(blocks) if blocks else "（无检索结果）"
    tools = tool_block(q) or "（本问不涉及历算/卦象工具）"
    boundary = ""
    if PREDICT_RE.search(q):
        boundary = ("\n\n## 边界提示（本问被判定为预测类请求）\n"
                    "本系统不做任何预测。请按系统规则第 4 条作答：先声明不做预测，"
                    "再引'天下之数出于理，违乎理则入于术'，最后可说明本项目的实验负结果。"
                    "不得给出任何预测性、建议性结论（包括间接暗示）。")
    if find_years(q) and "【规则计算·历算】" not in tools:
        boundary += ("\n\n## 工具缺答提示\n问题包含年份但历算工具未识别成功。"
                     "请明确声明「历算工具未能识别该年份，无法给出坐标」，"
                     "严禁自行推算元会运世。")
    guas_in_q = find_gua(q)
    if guas_in_q:
        boundary += (f"\n\n## 卦卡强提示\n本问涉及卦：{'、'.join(guas_in_q)}。"
                     "上方【规则计算·卦象】卡是该卦结构的唯一权威输出（上下卦、爻位、"
                     "二进制值、先天序），涉及该卦结构的问题必须照录卦卡，"
                     "严禁自行另组卦或采用《周易》通行卦序之外的说法。")
    user = (f"## 检索到的语料\n{ctx}\n\n## 确定性工具输出\n{tools}{boundary}\n\n## 问题\n{q}\n\n"
            "请按系统规则回答：标签标注、引用带出处、语料不足要明说。")
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    ids = tok(text, return_tensors="pt").to(model.device)
    t0 = time.time()
    with torch.no_grad():
        out = model.generate(**ids, max_new_tokens=max_new, do_sample=False,
                             pad_token_id=tok.eos_token_id)
    gen = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
    dt = time.time() - t0
    # 引文忠实度后处理：逐字校验，近似者校准为语料原文，转述者去引号
    from quote_guard import verify_quotes
    gen, qlog = verify_quotes(gen)
    refs = [f"{c[1]}（{c[2]}）" for c in (chunks[i] for _, i in hits)]
    return gen, refs, dt, hits, qlog


def load_model():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL_DIR)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_DIR, dtype=torch.bfloat16, device_map="cuda:0")
    model.eval()
    return model, tok


def save_transcript2(q, gen, refs, dt):
    os.makedirs(os.path.dirname(TRANSCRIPT), exist_ok=True)
    with open(TRANSCRIPT, "a", encoding="utf-8") as fh:
        fh.write(f"\n---\n**问**：{q}\n\n**答**：\n\n{gen}\n\n"
                 f"**检索引用**（生成 {dt:.0f}s）：\n" + "\n".join(f"- {r}" for r in refs) + "\n")


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("问", "交互"):
        print(__doc__)
        return
    print("加载模型（首次约 1 分钟）…", flush=True)
    model, tok = load_model()
    if args[0] == "问":
        q = args[1]
        k = int(args[args.index("-k") + 1]) if "-k" in args else 4
        gen, refs, dt, _, qlog = answer(q, k=k, model=model, tok=tok)
        print("\n" + gen)
        print(f"\n[检索引用] " + " | ".join(refs))
        if qlog:
            print("[引文校准] " + "；".join(qlog))
        print(f"[生成 {dt:.0f}s]")
        save_transcript2(q, gen, refs, dt)
    else:
        print("交互模式（q 退出）")
        while True:
            q = input("\n问> ").strip()
            if q.lower() in ("q", "quit", "exit"):
                break
            if not q:
                continue
            gen, refs, dt, _, qlog = answer(q, model=model, tok=tok)
            print("\n" + gen)
            print(f"\n[检索引用] " + " | ".join(refs))
            if qlog:
                print("[引文校准] " + "；".join(qlog))
            save_transcript2(q, gen, refs, dt)


if __name__ == "__main__":
    main()
