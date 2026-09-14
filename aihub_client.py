# -*- coding: utf-8 -*-
"""AIHub 对外 Agent API 客户端 —— 皇极经世项目的同步与任务驱动。

用法：
    python aihub_client.py push                 # 上传项目交付件与代码到 AIHub
    python aihub_client.py files                # 列出远端文件
    python aihub_client.py run "审阅提示词" [--mode execute|discussion|plan]
                                               [--cog deep_explore|brainstorm|none]
    python aihub_client.py job <job_id>         # 查询任务
    python aihub_client.py jobs                 # 本 Key 的任务列表
    python aihub_client.py todos                # 读取引擎任务清单
    python aihub_client.py memory [limit]       # 读取最近沉淀记忆

Key 保管（依《AIHub 对外 Agent API 操作手册》§1）：
    优先环境变量 AIHUB_API_KEY，否则读取 ~/.aihub_key；
    绝不写入代码仓库、日志或项目文件。本文件不含任何明文 Key。
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = "http://127.0.0.1:15722"
PROJECT = "p_local_20260913095915590980"  # 皇极经世

# 上传清单：(远端目录, 本地相对路径)。root 用 ""。
PUSH_MANIFEST = [
    ("", "README.md"),
    ("docs", "docs/邵雍思想深度调研.md"),
    ("docs", "docs/模型设计与实验报告.md"),
    ("output", "output/训练报告.txt"),
    ("output", "output/moxing.json"),
    ("huangji", "huangji/__init__.py"),
    ("huangji", "huangji/gua.py"),
    ("huangji", "huangji/lishu.py"),
    ("huangji", "huangji/guanwu.py"),
    ("huangji", "huangji/shuju.py"),
    ("huangji", "huangji/moxing.py"),
    ("", "guanwu.py"),
    ("", "test_huangji.py"),
]


def get_key():
    k = os.environ.get("AIHUB_API_KEY")
    if not k:
        p = os.path.expanduser("~/.aihub_key")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                k = fh.read().strip()
    if not k:
        sys.exit("未找到 API Key：请设置 AIHUB_API_KEY 或写入 ~/.aihub_key")
    return k


def request(method, path, json_body=None, raw_body=None, headers=None, timeout=30):
    from urllib.parse import urlsplit, urlunsplit, quote
    parts = urlsplit(path)
    path = urlunsplit((parts.scheme, parts.netloc,
                       quote(parts.path, safe="/"),
                       quote(parts.query, safe="=&"), ""))
    h = {"Authorization": "Bearer " + get_key()}
    if headers:
        h.update(headers)
    data = None
    if json_body is not None:
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        h["Content-Type"] = "application/json"
    elif raw_body is not None:
        data = raw_body
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, body


def multipart_upload(project, path, filepath):
    boundary = "----huangji" + uuid.uuid4().hex
    fname = os.path.basename(filepath)
    with open(filepath, "rb") as fh:
        content = fh.read()

    def field(name, value):
        return (f"--{boundary}\r\nContent-Disposition: form-data; "
                f"name=\"{name}\"\r\n\r\n{value}\r\n").encode("utf-8")

    body = field("project", project) + field("path", path or "")
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
             f"filename=\"{fname}\"\r\nContent-Type: application/octet-stream\r\n\r\n"
             ).encode("utf-8") + content + b"\r\n"
    body += f"--{boundary}--\r\n".encode("utf-8")

    return request("POST", "/api/v1/files/upload", raw_body=body, headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}"}, timeout=120)


# ------------------------------------------------------------ 子命令 ----

def cmd_projects(_):
    st, data = request("GET", "/api/v1/projects")
    print(st, json.dumps(data, ensure_ascii=False, indent=1)[:400])


def cmd_push(_):
    ok = fail = 0
    for remote_dir, local in PUSH_MANIFEST:
        if not os.path.exists(local):
            print(f"  跳过（本地不存在）：{local}")
            continue
        st, resp = multipart_upload(PROJECT, remote_dir, local)
        mark = "✓" if st in (200, 201) else "✗"
        if st in (200, 201):
            ok += 1
        else:
            fail += 1
        print(f"  {mark} [{st}] {local} → {remote_dir or '(root)'}"
              + ("" if st in (200, 201) else f"  {str(resp)[:200]}"))
    print(f"上传完成：成功 {ok} · 失败 {fail}")


def cmd_files(_):
    st, data = request("GET", f"/api/v1/files?project={PROJECT}&path=")
    print(st, json.dumps(data, ensure_ascii=False, indent=1)[:3000])


def cmd_run(argv):
    prompt = argv[0]
    work_mode, cog = "execute", "deep_explore"
    if "--mode" in argv:
        work_mode = argv[argv.index("--mode") + 1]
    if "--cog" in argv:
        cog = argv[argv.index("--cog") + 1]
    st, resp = request("POST", "/api/v1/run", json_body={
        "project": PROJECT, "prompt": prompt,
        "work_mode": work_mode, "cognitive_mode": cog})
    print(st, json.dumps(resp, ensure_ascii=False))
    if st == 202:
        print("JOB_ID=" + resp["job_id"])
        print("POLL=" + resp.get("poll_url", f"/api/v1/jobs/{resp['job_id']}"))


def cmd_job(job_id):
    st, resp = request("GET", f"/api/v1/jobs/{job_id}")
    print(json.dumps(resp, ensure_ascii=False, indent=1))


def cmd_jobs(_):
    st, resp = request("GET", f"/api/v1/jobs?project={PROJECT}")
    print(json.dumps(resp, ensure_ascii=False, indent=1)[:4000])


def cmd_poll(job_id, timeout_min=30):
    """轮询至终态，落盘结果。"""
    deadline = time.time() + timeout_min * 60
    states = {"queued", "running", "pending"}
    last = None
    while time.time() < deadline:
        try:
            st, resp = request("GET", f"/api/v1/jobs/{job_id}")
        except (urllib.error.URLError, OSError) as e:
            print(f"[{time.strftime('%H:%M:%S')}] 连接异常，30s 后重试：{e}")
            time.sleep(30)
            continue
        if st != 200:
            print(f"[poll {st}] {str(resp)[:200]}")
            time.sleep(15)
            continue
        status = resp.get("status")
        if status != last:
            print(f"[{time.strftime('%H:%M:%S')}] status = {status}")
            last = status
        if status not in states:
            result = resp.get("result") or {}
            answer = result.get("answer", "")
            os.makedirs("output", exist_ok=True)
            out = os.path.join("output", "aihub_review.md")
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(f"# AIHub Agent 审阅纪要（job {job_id}，status={status}）\n\n")
                fh.write(answer or "（无 answer 字段）\n")
            usage = result.get("usage", {})
            print(f"终态 {status} · 用量 {usage} · 工具 {result.get('tools_used')}")
            print(f"答复已写入 {out}（{len(answer)} 字）")
            return
        time.sleep(20)
    print("轮询超时")


def cmd_todos(_):
    st, resp = request("GET", f"/api/v1/projects/{PROJECT}/todos")
    print(json.dumps(resp, ensure_ascii=False, indent=1))


def cmd_memory(argv):
    limit = int(argv[0]) if argv else 10
    st, resp = request("GET", f"/api/v1/projects/{PROJECT}/memory?limit={limit}")
    print(json.dumps(resp, ensure_ascii=False, indent=1)[:6000])


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "help"
    rest = args[1:]
    if cmd == "push":
        cmd_push(rest)
    elif cmd == "files":
        cmd_files(rest)
    elif cmd == "run":
        cmd_run(rest)
    elif cmd == "job":
        cmd_job(rest[0])
    elif cmd == "jobs":
        cmd_jobs(rest)
    elif cmd == "poll":
        cmd_poll(rest[0], int(rest[1]) if len(rest) > 1 else 30)
    elif cmd == "todos":
        cmd_todos(rest)
    elif cmd == "memory":
        cmd_memory(rest)
    else:
        print(__doc__)
