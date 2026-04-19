# TraceLens

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Perfetto](https://img.shields.io/badge/Perfetto-trace__processor-green.svg)](https://perfetto.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-Server-purple.svg)](https://modelcontextprotocol.io)

**Perfetto Trace 分析 Agent，把性能问题从"感觉卡"变成"知道为什么卡"。**

丢进一个 trace 文件，说一句场景描述，TraceLens 自动定位异常窗口、识别关键线程、串联证据链，给出初步优化方向。支持多轮追问，支持 MCP 协议接入 AI 工具。

[功能](#功能) · [快速开始](#快速开始) · [MCP 接入](#mcp-接入) · [示例输出](#示例输出) · [架构](#架构) · [路线图](#路线图) · [参与贡献](#参与贡献)

[English](README_en.md)

## 为什么做这个项目

性能工程师拿到一个 trace 文件后，通常要在 Perfetto UI 里手动翻找几十个进程、上千个线程、几万条 slice，才能定位到问题。

TraceLens 把这个过程自动化：加载 trace → 聚焦目标进程 → 跑一组分析 skill → 输出结构化的证据链和优化方向。

不是黑盒结论，每一步都可追溯。有 LLM 时智能分析，没有 LLM 时规则引擎同样可用。

## 功能

| 功能 | 说明 |
|---|---|
| **真实 Trace 分析** | 加载 `.perfetto-trace` 文件，通过 `trace_processor` 执行 SQL 查询 |
| **自动进程推断** | 未指定 process 时自动选择最可能的应用进程 |
| **线程角色识别** | 识别主线程（含 Android 15 字符截断）、RenderThread、Flutter UI/Raster |
| **10 个 YAML Skill** | 声明式 SQL 分析能力，新增 skill 只需写 YAML 文件 |
| **逐帧深钻** | 每帧耗时 + jank 帧的线程状态分布 |
| **唤醒链追踪** | 谁唤醒了被阻塞的线程 + blocked_function 识别 |
| **Binder 分析** | 跨进程调用次数、总延迟、最大延迟 |
| **LLM 智能分析** | 支持 Claude / OpenAI，自动生成分析计划和结论，无 Key 时降级到规则引擎 |
| **场景路由** | 根据关键词自动选择分析策略（滑动/启动/通用） |
| **验证层** | 7 条启发式规则拦截 LLM 误判（防幻觉、防误标严重等级） |
| **多轮追问** | 基于已有证据继续下钻，CLI 交互模式 + Web |
| **MCP Server** | 7 个 MCP 工具，可被 Claude Desktop / Kiro / Cursor 直接调用 |
| **Session 持久化** | SQLite 存储分析结果，重启不丢失 |
| **CLI + Web** | CLI 用于脚本和调试，Web UI 用于交互使用 |

## 快速开始

```bash
# 克隆并安装
git clone https://github.com/kalimosd/tracelens.git
cd tracelens
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# CLI 分析（规则引擎，无需 API Key）
python -m tracelens.main analyze \
  --trace your_trace.perfetto-trace \
  --scenario "滑动卡顿" \
  --process com.example.app

# 带 LLM 分析（可选）
pip install -e ".[llm]"
export TRACELENS_LLM_PROVIDER=anthropic
export TRACELENS_LLM_API_KEY=your-key
export TRACELENS_LLM_MODEL=claude-sonnet-4-5-20250929
python -m tracelens.main analyze \
  --trace your_trace.perfetto-trace \
  --scenario "滑动卡顿" \
  --interactive  # 分析后进入追问模式

# 启动 Web UI
pip install uvicorn
python -c "
from tracelens.app.api import create_app
import uvicorn
uvicorn.run(create_app(), host='127.0.0.1', port=8000)
"
```

## MCP 接入

TraceLens 可以作为 MCP Server 运行，让 Claude Desktop、Kiro、Cursor 等 AI 工具直接调用分析能力。

```bash
pip install -e ".[mcp]"
python -m tracelens.mcp
```

在 AI 工具的 MCP 配置中添加：

```json
{
  "tracelens": {
    "command": "python",
    "args": ["-m", "tracelens.mcp"]
  }
}
```

**7 个 MCP 工具：**

| 工具 | 说明 |
|---|---|
| `load_trace_file` | 加载 trace 文件，返回 trace_id |
| `analyze` | 完整分析流水线 |
| `list_skills` | 列出可用 YAML Skill |
| `invoke_skill` | 执行指定 Skill |
| `execute_sql` | 受控 SQL 查询（带安全守卫） |
| `followup` | 基于已有结果追问 |
| `close_trace` | 释放资源 |

## 示例输出

```
Analysis: long slices detected on critical threads; scheduling delays present;
thread blocking observed.

证据:
  Process overview — 3 threads, 66 slices
  Frame rhythm — 30 frames, avg 14.8ms, 3 over 16ms, 3 over 33ms
  Long slices — Choreographer#doFrame=77ms; inflate=65ms
  Scheduling delay — main=75ms
  Blocked threads — RenderThread: total=210ms, max_single=14ms, count=19
  Binder transactions — Binder:5000_1: 8 calls, total=243ms, max=37ms

优化方向:
  - 优化主线程 inflate 操作，考虑异步预加载或 ViewStub 延迟加载
  - 排查调度延迟根因，检查 CPU 资源竞争
  - 分析 RenderThread 阻塞，检查 GPU 渲染管线同步等待
  - 检查跨进程 Binder 调用延迟
```

## 架构

```
tracelens/
├── trace/          # 数据访问：trace 加载、SQL 查询、安全守卫
├── semantics/      # 线程角色识别（Android、Flutter）
├── skills/         # YAML Skill 引擎 + 10 个声明式分析能力
│   └── definitions/  # .yaml skill 文件（新增 skill 只需加文件）
├── analysis/       # 窗口检测、证据、分析链
├── agent/          # 编排器、策略器、综合器、验证层、追问引擎
├── llm/            # LLM 抽象层（Anthropic / OpenAI 兼容）
├── mcp/            # MCP Server（7 个工具）
├── artifacts/      # 结果存储（内存 + SQLite）
├── app/            # FastAPI Web UI
├── output/         # CLI 渲染、Web 视图模型
└── main.py         # CLI 入口（Typer）
```

设计原则：
- **Skill-first** — 稳定的分析路径是声明式 YAML Skill，不是临时 SQL
- **LLM 可选** — 有 LLM 时智能分析，无 LLM 时规则引擎同样可用
- **分层架构** — 交互、编排、分析、语义、数据访问各自独立
- **验证优先** — 7 条启发式规则拦截 LLM 误判，防止幻觉和误标
- **以进程为中心** — 分析围绕用户指定的目标进程展开
- **强可解释性** — 每个结论都能追溯到证据和分析步骤
- **运行时无关** — 架构同时支持 Android 和 Flutter 线程模型

## 运行测试

```bash
python -m pytest tests/unit -q
# 111 passed
```

## 当前状态

TraceLens 可以端到端分析真实 Perfetto trace，支持 LLM 智能分析和多轮追问。

当前限制：
- Flutter 双管线（TextureView vs SurfaceView）尚未自动识别
- 厂商适配（高通/联发科/三星等）尚未实现
- Web UI 比较简陋

## 路线图

- Flutter 双管线自动识别和分析分支
- ArtifactStore 摘要压缩（降低 LLM token 消耗）
- 更多 YAML Skill：GC 分析、CPU 频率、ANR 检测
- Web UI 增强：表格化、evidence 可折叠
- 报告导出（Markdown/PDF）
- 受控 SQL 探索（LLM 在 Skill 不够时自定义 SQL）
- 厂商适配（.override.yaml）

## 参与贡献

欢迎反馈、提 issue 和 PR。

新增分析能力只需在 `tracelens/skills/definitions/` 下添加 `.yaml` 文件，不需要改 Python 代码。

## License

MIT
