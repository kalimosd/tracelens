# TraceLens

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Perfetto](https://img.shields.io/badge/Perfetto-trace__processor-green.svg)](https://perfetto.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Perfetto Trace 分析 Agent，把性能问题从"感觉卡"变成"知道为什么卡"。**

丢进一个 trace 文件，说一句场景描述，TraceLens 自动定位异常窗口、识别关键线程、串联证据链，给出初步优化方向。

[功能](#功能) · [快速开始](#快速开始) · [示例输出](#示例输出) · [架构](#架构) · [路线图](#路线图) · [参与贡献](#参与贡献)

[English](README_en.md)

## 为什么做这个项目

性能工程师拿到一个 trace 文件后，通常要在 Perfetto UI 里手动翻找几十个进程、上千个线程、几万条 slice，才能定位到问题。

TraceLens 把这个过程自动化：加载 trace → 聚焦目标进程 → 跑一组分析 skill → 输出结构化的证据链和优化方向。

不是黑盒结论，每一步都可追溯。

## 功能

| 功能 | 说明 |
|---|---|
| **真实 Trace 分析** | 加载 `.perfetto-trace` 文件，通过 `trace_processor` 执行 SQL 查询 |
| **自动进程推断** | 未指定 process 时自动选择最可能的应用进程 |
| **线程角色识别** | 识别主线程（含 Android 15 字符截断）、RenderThread、Flutter UI/Raster |
| **异常窗口检测** | 按 100ms 窗口切分，基于长任务、阻塞、调度延迟综合评分 |
| **长 Slice 检测** | 找出超过 16ms 的耗时操作 |
| **调度延迟分析** | 统计线程在 Runnable 状态的等待时间 |
| **阻塞链分析** | 识别线程阻塞（Sleep/D 状态），含总时长、最长单次、次数 |
| **帧节奏分析** | 基于 `Choreographer#doFrame` 检测 jank 帧 |
| **跨进程依赖** | 发现与目标进程相关的系统进程和 binder 调用 |
| **结构化输出** | 结论、关键证据、分析链、优化方向、不确定性 |
| **CLI + Web** | CLI 用于脚本和调试，Web UI 用于交互使用 |

## 快速开始

```bash
# 克隆并安装
git clone https://github.com/kalimosd/tracelens.git
cd tracelens
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# CLI 分析
python -m tracelens.main analyze \
  --trace your_trace.perfetto-trace \
  --scenario "滑动卡顿" \
  --process com.example.app

# 启动 Web UI
pip install uvicorn
python -c "
from tracelens.app.api import create_app
import uvicorn
uvicorn.run(create_app(), host='127.0.0.1', port=8000)
"
# 打开 http://127.0.0.1:8000，上传 trace 文件
```

## 示例输出

```
Analysis: long slices detected on critical threads; scheduling delays present;
thread blocking observed.

证据:
  Top abnormal window — window score=62; primary role=app_main
  Thread state distribution — Running=466ms, S=402ms, R=64ms
  Long slices — Choreographer#doFrame=77ms on main; inflate=65ms on main
  Scheduling delay — main=75ms
  Blocked threads — RenderThread: total=210ms, max_single=14ms, count=19
  Frame rhythm — 30 frames, avg interval 16ms, 0 jank(s)
  Cross-process dependencies — surfaceflinger; system_server

优化方向:
  - 检查长 slice — 考虑拆分耗时操作或移到非主线程
  - 检查 CPU 竞争 — 线程在 Runnable 状态等待说明调度压力大
  - 检查阻塞原因 — 关注锁竞争、binder 调用或 I/O 等待
```

## 架构

```
tracelens/
├── trace/          # 数据访问：trace 加载、SQL 查询、安全守卫
├── semantics/      # 线程角色识别（Android、Flutter）
├── skills/         # 可复用的分析能力（Skill-first 设计）
├── analysis/       # 窗口检测、证据、分析链
├── agent/          # 编排器、策略器、综合器
├── artifacts/      # 结果存储（内存版，后续：SQLite）
├── app/            # FastAPI Web UI
├── output/         # CLI 渲染、Web 视图模型
└── main.py         # CLI 入口（Typer）
```

设计原则：
- **Skill-first** — 稳定的分析路径是可复用的 skill，不是临时 SQL
- **分层架构** — 交互、编排、分析、语义、数据访问各自独立
- **以进程为中心** — 分析围绕用户指定的目标进程展开
- **强可解释性** — 每个结论都能追溯到证据和分析步骤
- **运行时无关** — 架构同时支持 Android 和 Flutter 线程模型

## 运行测试

```bash
python -m pytest tests/unit -q
# 57 passed
```

## 当前状态

TraceLens 可以端到端分析真实 Perfetto trace。当前限制：

- Follow-up 追问功能是占位实现
- 结果存储在内存中，重启后丢失
- 暂无 LLM 集成 — 所有分析基于规则
- 帧节奏检测依赖 trace 中存在 `Choreographer#doFrame` slice

## 路线图

- 基于已有证据的多轮追问
- SQLite 持久化存储
- 更多 skill：ANR 检测、GPU 渲染分析
- LLM 辅助归因和结论生成
- Flutter 框架语义适配
- 批量 trace 分析和对比

## 参与贡献

欢迎反馈、提 issue 和 PR。

如果你想改进分析能力、测试输出质量、或者提产品方向建议 — 开个 issue 或发起讨论。

## License

MIT
