# -*- coding: utf-8 -*-
"""指挥 AIHub 引擎做「极致探索」—— 皇极模型 v2 设计思路征集。

策略（吸取此前四次零产出教训）：
  * 所有上下文直接嵌入提示词，引擎零文件读取，只思考不翻书；
  * 每任务一问、限定字数，避免回合预算耗尽；
  * 默认 cognitive_mode=deep_explore（极致探索）；若超时/零产出，自动降级 none 重试一次；
  * 轮询超限即取消（可审计、零产出自动退回），避免占用项目单任务锁；
  * 各任务回答落盘 output/explore/，供汇总成设计方案。

用法: python aihub_explore.py
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aihub_client import request, PROJECT  # noqa: E402

OUT_DIR = os.path.join("output", "explore")
POLL_INTERVAL = 20          # 秒
POLL_CAP = 12 * 60          # 单任务轮询上限
TERMINAL = {"completed", "error", "interrupted", "failed", "cancelled", "done"}

VOICE_EXCERPT = """皇極經世卷第八之下樂六（道藏本卷20 · 發音清和律三之九）
　　　(/多可个舌)(思三星/坎坎坎坎)
九音(/禾火化八)九音(寺象/坎坎坎坎)
一聲(/開宰愛○)七聲(/坎坎坎坎)
　　　(/回毎退○)(/坎坎坎坎)
　　　(/良兩向○)(山手/坎坎坎坎)
九音(/光廣况○)十音(士石/坎坎坎坎)
二聲(/丁井亘○)七聲(耳/坎坎坎坎)
　　　(/千典亘○)(莊震/坎坎坎坎)
九音(/元犬半○)十一音(乍/坎坎坎坎)
三聲(/臣引艮○)七聲(义赤/坎坎坎坎)
　　　(/君允巽○)　(崇辰/坎坎坎坎)
　　　(/刀早孝岳)(卓中/坎坎坎坎)
九音(/毛寶報霍)十二音(宅直/坎坎坎坎)
四聲(/牛斗奏六)七聲(坼丑/坎坎坎坎)"""

V1_SUMMARY = """项目背景：《皇极经世》项目用邵雍思想建可计算的世界理解模型 v1。
v1 已有：① 六十四卦=6比特状态空间（初爻为最高位v0-63，先天序=64-v，与莱布尼茨二进制同构）；
② 元会运世宇宙钟（129600=12×30×12×30年，尧甲辰=午会1运1世元年）；
③ 特征：运(360年)/世(30年)周期sin/cos相位（物观）与王朝已行年比例（我观）对照；
④ 目标：中国历史4019年逐年治乱三分类（乱966/平2601/盛452）。
v1 结果：运转留一（360年一折×12折）：物观0.669/基线0.681/我观0.689——均不超基线；
置换检验×3=0.657/0.642/0.652（与真实无异）；尾部外推=基线；
唯一边缘发现：12个盛世区段全部避开运首与运末四分之一相位桶，(8/12)^12≈0.008。
负结果结论：逐年治乱不由绝对年相位驱动；六爻/阳息特征在4000年窗内是时代标签。"""

CORPUS_SUMMARY = """语料库现状（corpus/，公有领域古籍数字化文本）：
①《皇极经世》正统道藏本23卷43.8万字（全书完整：以元经会/以会经运/以运经世/
声音律吕唱和图/观物内篇/观物外篇，繁体OCR）；四库本6半卷（残）；
《邵子全书》简体辑校本9万字；四库整理本10.8万字；张行成《观物外篇衍义》2.4万字。
②《伊川击壤集》两个完整版本：kanripo本20卷8.9万字+四库本21文件7.7万字（邵雍诗集1500余首）。
③《渔樵问对》0.75万字；《梅花易数》（托名）4.2万字；衍生托名《心易发微》3万字等。"""

JOBS = [
    {
        "key": "j1_实验v2设计",
        "mode": "discussion",
        "cog": "deep_explore",
        "prompt": f"""你是计算历史学/机器学习方法论专家。下面是一个已完成实验的完整摘要（无需读任何文件）：

【实验摘要】
{V1_SUMMARY}

【任务】给出「皇极模型 v2」实验设计的 3-5 个最值得做的改进，要求：
1) 统计上更严谨（如区段选择偏差、多重比较校正、竞争假设设计）；
2) 信息量更大（如改用区段级生存分析/相位回归、引入多文明对照数据）；
3) 每条给：改进点、具体做法（2-3句）、预期风险。
总字数≤700字，直接输出条目，不要客套。""",
    },
    {
        "key": "j2_语料模型机会",
        "mode": "discussion",
        "cog": "deep_explore",
        "prompt": f"""你是 NLP/语料工程专家。下面是某项目语料库清单（无需读任何文件）：

【语料清单】
{CORPUS_SUMMARY}

项目目标：用邵雍思想（六十四卦状态空间、元会运世时钟、以物观物认识论、声音唱和组合编码）设计可计算的"世界理解模型"。

【任务】基于这份语料，提出 3-4 个具体可训练/可检验的模型设计，每个含：
训练目标、输入输出、评估方式、主要风险（各2-3行）；最后指出哪个最值得先做、为什么。
总字数≤650字，直接输出条目。""",
    },
    {
        "key": "j3_声音唱和编码设计",
        "mode": "discussion",
        "cog": "deep_explore",
        "prompt": f"""你是音韵学+数据工程专家。下面是邵雍《皇极经世·声音唱和图》道藏本的真实文本样例（繁体OCR，无需读任何文件）：

【样例】
{VOICE_EXCERPT}

背景：邵雍以"音"（声母类）与"声"（韵类）各十六交叉唱和得256组合，配以卦象（样例中括号内"坎坎坎坎"即所配之卦），用以"唱和万物"。

【任务】设计把该图转为结构化数据表的方案：
1) 表结构 schema（字段名+类型+示例JSON一行）；
2) 从上述OCR文本提取字段的解析规则（如何切分"(/多可个舌)(思三星/坎坎坎坎)"这类行）；
3) 与现代音韵学对齐的思路（声母清浊/韵摄/声调）；
4) 两个下游用途（如：宋代音系构拟检验、十六音×十六声组合空间的向量编码用于模型）。
总字数≤700字，直接输出。""",
    },
    {
        "key": "j4_v2总体架构",
        "mode": "discussion",
        "cog": "deep_explore",
        "prompt": f"""你是系统架构师，擅长符号-神经混合系统。背景材料（无需读任何文件）：

【v1 已有】
{V1_SUMMARY}

【语料与素材】
{CORPUS_SUMMARY}
另有：声音唱和图原件（十六声×十六音×卦配，见道藏本卷19-20）。

【任务】输出「皇极模型 v2」总体架构蓝图：
1) 模块划分（每个模块：输入/输出/一句话职责）；
2) 模块间数据流（文字描述箭头）；
3) 训练目标分层：自监督（语料）/监督（历史标签）/符号规则（卦序与时钟），各给一例；
4) 评估体系（含"以物观物"原则如何成为评估约束）；
5) 三阶段路线图（各阶段2-3周可完成的最小闭环）。
总字数≤800字，直接输出。""",
    },
]


def submit(prompt, mode, cog, tries=3):
    for k in range(tries):
        st, resp = request("POST", "/api/v1/run", json_body={
            "project": PROJECT, "prompt": prompt, "work_mode": mode, "cognitive_mode": cog})
        if st == 202:
            return resp["job_id"]
        print(f"    提交[{st}] {str(resp)[:120]}，60s 后重试")
        time.sleep(60)
    return None


def cancel(job_id):
    request("POST", f"/api/v1/jobs/{job_id}/cancel", json_body={})


def run_job(spec):
    job_id = submit(spec["prompt"], spec["mode"], spec["cog"])
    if not job_id:
        return None
    print(f"    任务 {job_id}（{spec['cog']}）")
    deadline = time.time() + POLL_CAP
    last = None
    while time.time() < deadline:
        try:
            st, d = request("GET", f"/api/v1/jobs/{job_id}")
        except Exception as e:
            print(f"      连接异常重试: {type(e).__name__}")
            time.sleep(30)
            continue
        status = d.get("status")
        if status != last:
            print(f"      [{time.strftime('%H:%M:%S')}] {status}")
            last = status
        if status in TERMINAL:
            return job_id, d
        time.sleep(POLL_INTERVAL)
    print("      轮询超限 → 取消（零产出自动退回）")
    cancel(job_id)
    return job_id, {"status": "cancelled_by_timeout", "result": {}}


def save_answer(key, job_id, d):
    r = d.get("result") or {}
    ans = (r.get("answer") or "").strip()
    status = d.get("status")
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{key}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"# {key}\n\n- job: `{job_id}` · status={status} · usage={r.get('usage')}\n\n")
        fh.write(ans if ans else f"> 零产出：{d.get('error', '')}")
    print(f"    → {path}（{len(ans)}字，{status}）")
    return ans, status


def main():
    results = []
    for spec in JOBS:
        print(f"\n=== {spec['key']} ===")
        out = run_job(spec)
        if out is None:
            results.append((spec["key"], None, "submit_fail"))
            continue
        job_id, d = out
        ans, status = save_answer(spec["key"], job_id, d)
        # 零产出 → 降级 none 重试一次
        if not ans and spec["cog"] != "none":
            print("    降级 cognitive_mode=none 重试一次")
            spec2 = dict(spec, cog="none")
            out = run_job(spec2)
            if out:
                job_id, d = out
                ans, status = save_answer(spec2["key"] + "_retry", job_id, d)
        results.append((spec["key"], job_id, status))
    print("\n=== 探索完成 ===")
    for k, j, s in results:
        print(f"  {k}: {s} ({j})")


if __name__ == "__main__":
    main()
