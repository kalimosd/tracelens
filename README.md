# TraceLens

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Perfetto](https://img.shields.io/badge/Perfetto-trace__processor-green.svg)](https://perfetto.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-Server-purple.svg)](https://modelcontextprotocol.io)

**Perfetto Trace 分析 Agent，把性能问题从"感觉卡"变成"知道卡在哪、怎么改"。**

丢进一个 trace 文件，说一句场景描述，TraceLens 自动定位掉帧、追踪根因链、输出业务可操作的优化建议。支持多轮追问，支持 MCP 协议接入 AI 工具。

[功能](#功能) · [快速开始](#快速开始) · [示例输出](#示例输出) · [MCP 接入](#mcp-接入) · [架构](#架构) · [路线图](#路线图) · [参与贡献](#参与贡献)

[English](README_en.md)

## 为什么做这个项目

性能工程师拿到一个 trace 文件后，通常要在 Perfetto UI 里手动翻找几十个进程、上千个线程、几万条 slice，才能定位到问题。定位完了还要自己整理证据、写分析报告给业务。

TraceLens 把这个过程自动化：加载 trace → 聚焦目标进程 → 逐帧追踪根因 → 输出业务能直接用的诊断报告。

不是黑盒结论，每一步都可追溯。有 LLM 时智能分析，没有 LLM 时规则引擎同样可用。

## 功能

| 功能 | 说明 |
|---|---|
| **真实 Trace 分析** | 加载 `.perfetto-trace` 文件，通过 `trace_processor` 执行 SQL |
| **11 个 YAML Skill** | 声明式分析能力，新增 skill 只需写 YAML 文件 |
| **逐帧因果链** | 每个 jank 帧的线程状态分布 + 帧内耗时操作定位 |
| **场景化诊断** | 识别横竖屏切换、冷启动、GC、IO 阻塞、Binder 等具体根因 |
| **业务可操作报告** | 根因链 + 【优先/建议】标记的优化方向，业务直接能改代码 |
| **证据解读** | 每条证据带严重程度标记（⚠️）和中文解释 |
| **LLM 智能分析** | 支持 Claude / OpenAI，无 Key 时降级到规则引擎 |
| **验证层** | 7 条启发式规则拦截 LLM 误判（防幻觉、防误标严重等级） |
| **多轮追问** | 基于已有证据继续下钻，CLI 交互模式 + Web |
| **MCP Server** | 7 个 MCP 工具，可被 Claude Desktop / Kiro / Cursor 直接调用 |
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

## 示例输出

**IO 阻塞导致列表卡顿：**

```
┌─ 分析概览 ──────────────────────────────────────────┐
│ 进程概览   2 threads, 62 slices
│ 帧统计    25 frames, avg 19.2ms, 6 over 16ms, 4 over 33ms
│ 最长耗时   Choreographer#doFrame=92ms on main
│ 主线程状态  Running 55% / Sleep 37% / Runnable 6%
└──────────────────────────────────────────────────────┘

📋 问题：4 帧严重掉帧（>33ms，用户可感知卡顿）
根因：
  1. 单帧处理超时（92ms）
  2. SQLiteDatabase.query（80ms）
  3. SQLiteSession.executeForCursorWindow（76ms）

▸ 帧因果链
  帧 main@1166666670: 92ms
    状态: Running=41ms(44.6%), S=36ms(39.4%), R=14ms(16.0%)
    耗时操作: SQLiteDatabase.query=80ms
  ⚠️ 严重掉帧，需要优先排查
```

**横竖屏切换卡顿：**

```
📋 问题：1 帧严重掉帧（>33ms，用户可感知卡顿）
根因：
  1. 横竖屏切换触发 Activity 重建（180ms）
  2. Activity 启动 onCreate/onResume（120ms）
  3. 布局加载 inflate（85ms）← 主要瓶颈

── 优化方向 ────────────────────────────────────────
  1. 【优先】缓存状态减少重建范围，或用 android:configChanges 避免重建（当前 180ms）
  2. 【优先】减少 Activity.onCreate 中的同步操作（当前 120ms）
  3. 【优先】简化布局 XML 或用 ViewStub 延迟加载非关键区域（当前 inflate 85ms）
  4. 【建议】将耗时 Binder 调用移到后台线程或预加载（最长 19ms）
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

**7 个 MCP 工具：** `load_trace_file` / `analyze` / `list_skills` / `invoke_skill` / `execute_sql` / `followup` / `close_trace`

## 架构

```
tracelens/
├── trace/          # 数据访问：trace 加载、SQL 查询、安全守卫
├── semantics/      # 线程角色识别（Android、Flutter）
├── skills/         # YAML Skill 引擎 + 11 个声明式分析能力
│   └── definitions/  # .yaml skill 文件（新增 skill 只需加文件）
├── analysis/       # 窗口检测、证据解读器、分析链
├── agent/          # 编排器、策略器、综合器、验证层、追问引擎
├── llm/            # LLM 抽象层（Anthropic / OpenAI 兼容）
├── mcp/            # MCP Server（7 个工具）
├── artifacts/      # 结果存储（内存 + SQLite）
├── app/            # FastAPI Web UI（Tailwind CSS）
├── output/         # CLI 渲染器（概览表 + 结构化输出）
└── main.py         # CLI 入口（Typer）
```

设计原则：
- **Skill-first** — 稳定的分析路径是声明式 YAML Skill，不是临时 SQL
- **业务导向** — 输出根因链 + 可操作的优化建议，业务直接能改代码
- **LLM 可选** — 有 LLM 时智能分析，无 LLM 时规则引擎同样可用
- **验证优先** — 7 条启发式规则拦截 LLM 误判，防止幻觉和误标
- **运行时无关** — 架构同时支持 Android 和 Flutter 线程模型

## 运行测试

```bash
python -m pytest tests/unit -q
# 131 passed
```

## 当前状态

TraceLens 可以端到端分析真实 Perfetto trace，输出业务可操作的诊断报告。

已验证场景：滑动卡顿、横竖屏切换、冷启动、GC 压力、IO 阻塞、CPU 竞争、动画卡顿、跨进程 Binder 延迟、Flutter 帧卡顿。

当前限制：
- Flutter 双管线（TextureView vs SurfaceView）尚未自动识别
- 厂商适配（高通/联发科/三星等）尚未实现
- 唤醒链分析依赖 trace 中的 sched_waking 事件

## 路线图

- Flutter 双管线自动识别和分析分支
- ArtifactStore 摘要压缩（降低 LLM token 消耗）
- 更多 YAML Skill：ANR 检测、CPU 频率分析
- 报告导出（Markdown/PDF）
- 受控 SQL 探索（LLM 在 Skill 不够时自定义 SQL）
- 厂商适配（.override.yaml）

## 参与贡献

欢迎反馈、提 issue 和 PR。

新增分析能力只需在 `tracelens/skills/definitions/` 下添加 `.yaml` 文件，不需要改 Python 代码。

## License

MIT
