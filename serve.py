# -*- coding: utf-8 -*-
"""serve.py —— 观物工作台本地服务（纯标准库，零外部依赖）。

API:
  /api/lishu?year=&scheme=        皇极历读数（单方案）
  /api/lishu/compare?year=        双方案对照
  /api/coordinate?hui=&yun=&shi=&nian=&scheme=   逆运算
  /api/gua?name=                  卦卡      /api/gua/list  全部卦
  /api/xiaoxi                     十二消息卦
  /api/rag?q=&k=                  语料检索（BM25+繁简归一）
  /api/corpus/list & /api/corpus/file?path=   语料浏览（限 corpus 内）
  /api/changhe                    唱和图结构化数据与核验
  /api/report?year=&topic=        研究报告（确定性+检索，markdown）
  /api/ai  (POST {q})             AI 问答（懒加载本地模型，首次约 1 分钟）

运行: python serve.py  →  http://127.0.0.1:8899
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.setdefault("tensorflow", None)

from huangji import gua, guanwu, lishu      # noqa: E402
from rag import load_or_build                # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "webapp")
CORPUS = os.path.join(ROOT, "corpus")
PORT = 8899

MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".json": "application/json",
        ".md": "text/markdown; charset=utf-8", ".txt": "text/plain; charset=utf-8",
        ".jsonl": "text/plain; charset=utf-8"}

_idx = None
_model = {"m": None, "t": None}


def get_idx():
    global _idx
    if _idx is None:
        _idx = load_or_build()
    return _idx


def corpus_safe(rel):
    rel = rel.replace("\\", "/").lstrip("/")
    p = os.path.normpath(os.path.join(CORPUS, rel))
    if not p.startswith(CORPUS) or ".." in rel.split("/"):
        return None
    return p


def read_text(p):
    return open(p, encoding="utf-8", errors="replace").read()


def api_report(qs):
    """研究报告台：确定性引擎 + 检索 → markdown（四类标注框架）。"""
    md = ["# 观物研究报告", "",
          f"> 生成时间：{__import__('time').strftime('%F %T')} · "
          "内容按四类标注（原典记述/注家解释/规则计算/现代推演），供观不供占。", ""]
    year = qs.get("year", [None])[0]
    topic = qs.get("topic", [""])[0].strip()
    if year:
        y = int(year)
        c = lishu.compare_schemes(y)
        r1 = c["schemes"]["尧甲辰通行"]
        r2 = c["schemes"]["赵友钦夏禹说"]
        md += ["## 一、历算坐标（规则计算）", "",
               f"**{r1['label']}（{r1['ganzhi']}年）**",
               f"- 尧甲辰通行方案：{r1['hui_branch']}会（{r1['hui_gua']}卦）"
               f"第{r1['yun_index']}运（{r1['yun_gua'].name}卦）第{r1['shi_index']}世"
               f"第{r1['nian_index']}年（元历第 {r1['pos']} 年）",
               f"- 赵友钦夏禹说方案：{r2['hui_branch']}会 第{r2['yun_index']}运"
               f"（{r2['yun_gua'].name}卦）第{r2['shi_index']}世第{r2['nian_index']}年",
               "", "两方案相差 140 年——坐标必须连带起算方案报告。", ""]
        h = r1["yun_gua"]
        xi = gua.xiaoxi_phase(h)
        cm = guanwu.XIAOXI_COMMENT[gua.XIAOXI[xi].name] if xi >= 0 else ""
        md += [f"- {h.name}卦{h.unicode_char}：上{h.upper}下{h.lower}，v={h.v}，"
               f"先天序 {h.xiantian_index}，阳爻 {h.yang_count}/6",
               f"- 消息相位：{cm}", ""]
    if topic:
        chunks, idxm = get_idx()
        hits = idxm.search(topic, 6)
        md += [f"## 二、语料检索（主题：{topic}）", ""]
        for s, i in hits:
            text, path, lab, ci = chunks[i]
            md += [f"### 〔{lab}｜{path}〕", "", text[:300] + ("…" if len(text) > 300 else ""), ""]
    md += ["## 三、边界与声明", "",
           "本报告不含预测。《观物外篇》：“天下之数出于理，违乎理则入于术。”",
           "本项目实验结论：四千年治乱与绝对年相位无可学习关系（供观，不供占）。",
           "", "---", "*观物工作台 · 皇极经世项目*"]
    return "\n".join(md)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, code=200, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._send({"error": "bad json"}, 400)
        if urlparse(self.path).path == "/api/ai":
            q = (data.get("q") or "").strip()
            if not q:
                return self._send({"error": "empty q"}, 400)
            if _model["m"] is None:
                from guanwu_rag import load_model
                _model["m"], _model["t"] = load_model()
            from guanwu_rag import answer
            a, refs, dt, _, qlog = answer(q, model=_model["m"], tok=_model["t"])
            return self._send({"answer": a, "refs": refs, "calib": qlog, "sec": round(dt)})
        self._send({"error": "unknown"}, 404)

    def do_GET(self):
        u = urlparse(self.path)
        # http.server 按 latin-1 解码请求行；中文查询参数需还原为 UTF-8
        query = u.query
        try:
            query = u.query.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        q = parse_qs(query)
        p = u.path
        try:
            if p == "/" or p == "/index.html":
                fp = os.path.join(WEB, "index.html")
                return self._send(read_text(fp), ctype=MIME[".html"])
            if p.startswith("/api/"):
                return self.route_api(p, q)
            fp = os.path.normpath(os.path.join(WEB, unquote(p).lstrip("/")))
            if fp.startswith(WEB) and os.path.isfile(fp):
                ext = os.path.splitext(fp)[1]
                return self._send(read_text(fp), ctype=MIME.get(ext, "text/plain"))
            self._send({"error": "not found"}, 404)
        except Exception as e:
            self._send({"error": str(e)}, 500)

    def route_api(self, p, q):
        if p == "/api/lishu":
            y = int(q["year"][0])
            scheme = q.get("scheme", ["尧甲辰通行"])[0]
            return self._send(lishu.year_reading(y, scheme=scheme) |
                              {"yun_gua": None})
        if p == "/api/lishu/rich":
            y = int(q["year"][0])
            r = lishu.year_reading(y, scheme=q.get("scheme", ["尧甲辰通行"])[0])
            h = r["yun_gua"]
            xi = gua.xiaoxi_phase(h)
            r["yun_gua"] = {"name": h.name, "char": h.unicode_char, "bits": h.bits,
                            "v": h.v, "xt": h.xiantian_index, "upper": h.upper,
                            "lower": h.lower, "yang": h.yang_count}
            r["xiaoxi"] = ({"name": gua.XIAOXI[xi].name, "pos": xi + 1,
                            "comment": guanwu.XIAOXI_COMMENT[gua.XIAOXI[xi].name]}
                           if xi >= 0 else None)
            return self._send(r)
        if p == "/api/lishu/compare":
            c = lishu.compare_schemes(int(q["year"][0]))
            for v in c["schemes"].values():
                h = v["yun_gua"]
                v["yun_gua"] = {"name": h.name, "char": h.unicode_char, "v": h.v,
                                "xt": h.xiantian_index}
            return self._send(c)
        if p == "/api/coordinate":
            y = lishu.coordinate_to_year(int(q["hui"][0]), int(q["yun"][0]),
                                         int(q["shi"][0]), int(q["nian"][0]),
                                         scheme=q.get("scheme", ["尧甲辰通行"])[0])
            return self._send({"year": y, "label": lishu.bc_ad_label(y),
                               "ganzhi": lishu.ganzhi(y)})
        if p == "/api/gua":
            h = gua.by_name[q["name"][0]]
            return self._send({"name": h.name, "char": h.unicode_char, "bits": h.bits,
                               "v": h.v, "xt": h.xiantian_index, "upper": h.upper,
                               "lower": h.lower, "yang": h.yang_count, "kwn": h.kwn})
        if p == "/api/gua/list":
            return self._send([{"name": h.name, "char": h.unicode_char, "bits": h.bits,
                                "v": h.v, "xt": h.xiantian_index, "upper": h.upper,
                                "lower": h.lower, "yang": h.yang_count} for h in gua.ALL])
        if p == "/api/xiaoxi":
            return self._send([{"name": x.name, "pos": i + 1, "yang": x.yang_count,
                                "bits": x.bits,
                                "comment": guanwu.XIAOXI_COMMENT[x.name]}
                               for i, x in enumerate(gua.XIAOXI)])
        if p == "/api/rag":
            chunks, idxm = get_idx()
            hits = idxm.search(q["q"][0], int(q.get("k", [6])[0]))
            return self._send([{"score": round(s, 2), "text": chunks[i][0][:400],
                                "path": chunks[i][1], "label": chunks[i][2]}
                               for s, i in hits])
        if p == "/api/corpus/list":
            rel = q.get("path", [""])[0]
            base = corpus_safe(rel)
            items = []
            for root, dirs, files in os.walk(base or CORPUS):
                for d in dirs:
                    rel_d = os.path.relpath(os.path.join(root, d), CORPUS)
                    items.append({"name": d, "type": "dir",
                                  "path": rel_d.replace("\\", "/")})
                for f in files:
                    if "_src" in root or "_src" in f:
                        continue
                    rel_f = os.path.relpath(os.path.join(root, f), CORPUS)
                    items.append({"name": f, "type": "file",
                                  "path": rel_f.replace("\\", "/"),
                                  "size": os.path.getsize(os.path.join(root, f))})
                break
            return self._send(sorted(items, key=lambda x: (x["type"] != "dir", x["name"])))
        if p == "/api/corpus/file":
            fp = corpus_safe(q["path"][0])
            if not fp or not os.path.isfile(fp):
                return self._send({"error": "not found"}, 404)
            return self._send({"path": q["path"][0],
                               "text": read_text(fp)[:200000]})
        if p == "/api/changhe":
            d = os.path.join(CORPUS, "07_唱和图结构化")
            return self._send({
                "summary_v0": read_text(os.path.join(d, "summary.md"))[:3000],
                "summary_v1": read_text(os.path.join(d, "summary_v1.md"))[:4000],
                "gua_test": read_text(os.path.join(d, "gua_test.md"))[:3000],
                "blocks": json.load(open(os.path.join(d, "blocks_v1.json"),
                                         encoding="utf-8"))})
        if p == "/api/report":
            return self._send({"markdown": api_report(q)},
                              ctype="text/markdown; charset=utf-8")
        if p == "/api/meta":
            return self._send({"name": "观物工作台", "version": "1.0",
                               "corpus_chunks": len(get_idx()[0]),
                               "disclaimer": lishu.DISCLAIMER})
        return self._send({"error": "unknown api"}, 404)


if __name__ == "__main__":
    print(f"观物工作台 → http://127.0.0.1:{PORT}（Ctrl+C 停止）")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
