# AIHub 集成运行台账（皇极经世）

> 生成：2026-09-13 · 记录对外 Agent API 的验证结果与引擎侧运行状况。
> 客户端：`aihub_client.py`（Key 只从 `AIHUB_API_KEY` 环境变量或 `~/.aihub_key` 读取，不入库）。

## 一、API 层验证（全部通过 ✓）

| 能力 | 接口 | 结果 |
|---|---|---|
| 鉴权 | Bearer Key | ✓ 401 无 / 200 正常 |
| 列项目 | GET /api/v1/projects | ✓ 38 项目，定位本项目 `p_local_20260913095915590980` |
| 上传 | POST /api/v1/files/upload | ✓ 13 个交付件（docs/output/huangji/代码）全部 200 |
| 列文件 | GET /api/v1/files | ✓ 目录结构与本地一致（fs_client 双通道同步） |
| 读文件 | GET /api/v1/files/read | ✓ 中文路径需 URL 编码（客户端已修复） |
| 发起任务 | POST /api/v1/run | ✓ 202 受理，仅接受 4 字段（多余字段 400） |
| 查询/轮询 | GET /api/v1/jobs/<id> | ✓ 状态机 queued→running→{error/interrupted/…} |
| 取消 | POST …/cancel | ✓ 200，记 interrupted 并释放项目锁 |
| 任务锁 | 同项目单活跃任务 | ✓ 第二个任务返回 409 |
| 任务清单 | GET …/todos | ✓（引擎回合收尾前为空） |
| 沉淀记忆 | GET …/memory | ✓ 记录 prompt 摘要/终态/用量（思考流不返回） |
| GPU 配方 | GET /api/v1/gpu/recipes | ✓ gpu:read 可用（b409-smoke / b409-full，固定配方） |

## 二、引擎回合执行状况（平台侧问题，如实记录）

四次任务提交，引擎均未产出 answer：

| 任务 | 配置 | 结果 |
|---|---|---|
| api_job_…1111… | execute + deep_explore（三部分审阅） | 运行 2h+ 无回合收尾，调用方取消（interrupted） |
| api_job_…5843… | discussion + none（同上） | 40 min 后平台判 **error**："引擎回合零产出……疑似深度阅读耗尽回合预算后空转收尾；请把任务拆到『每次只需理解一个局部』的粒度" |
| api_job_…9696… | discussion + none（单文件、500字、拆分后） | 提交成功，运行 40+ min 仍未收尾（轮询超时时仍 running） |

对照：期间 11:15 服务出现过一次连接拒绝（重启）；工作台显示 GPU 99% / CPU 74% 高负载。
零产出回合按平台规则自动退回，无 credit 损失。

## 三、引擎恢复后的取回/重跑方式

```bash
python aihub_client.py job api_job_2026091313395229696f0219   # 查看遗留任务是否终态
python aihub_client.py poll api_job_2026091313395229696f0219 30   # 若完成则自动落盘 output/aihub_review.md
# 或重跑拆分版审阅（每任务只读一个文件、只答一问，逐个执行避免 409）：
bash /tmp/review_driver.sh   # 若临时目录已清，见 aihub_client.py run 用法手工分三条提交
```

结论：**对外 API 集成本身端到端可用**（鉴权/文件/任务/台账全链路验证通过）；
当前阻塞在平台引擎回合执行侧，已按其建议改为拆分粒度并留存重跑入口。
