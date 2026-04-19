# TraceLens

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Perfetto](https://img.shields.io/badge/Perfetto-trace__processor-green.svg)](https://perfetto.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-Server-purple.svg)](https://modelcontextprotocol.io)

**Perfetto trace analysis agent — turn "it feels laggy" into "here's why it's laggy".**

Drop in a trace file, describe the scenario, and TraceLens automatically locates abnormal windows, identifies key threads, chains evidence together, and suggests optimization directions. Supports multi-turn follow-up and MCP protocol for AI tool integration.

[Features](#features) · [Quick Start](#quick-start) · [MCP Integration](#mcp-integration) · [Example Output](#example-output) · [Architecture](#architecture) · [Roadmap](#roadmap) · [Contributing](#contributing)

[中文](README.md)

## Why This Project

When a performance engineer gets a trace file, they typically spend time manually scanning dozens of processes, thousands of threads, and tens of thousands of slices in the Perfetto UI to locate the problem.

TraceLens automates this: load trace → focus on the target process → run a set of analysis skills → output a structured evidence chain with optimization directions.

No black-box conclusions — every step is traceable. Works with LLM for intelligent analysis, or without LLM using the rule-based engine.

## Features

| Feature | Description |
|---|---|
| **Real trace analysis** | Loads `.perfetto-trace` files, queries via `trace_processor` with SQL safety guards |
| **Automatic process inference** | Selects the most likely app process when none is specified |
| **Thread role identification** | Recognizes main thread (handles Android 15-char truncation), RenderThread, Flutter UI/Raster |
| **10 YAML Skills** | Declarative SQL analysis capabilities — add new skills by writing YAML files |
| **Per-frame deep dive** | Per-frame duration + thread state breakdown for jank frames |
| **Waker chain tracking** | Who wakes blocked threads + blocked_function identification |
| **Binder analysis** | Cross-process call counts, total latency, max latency |
| **LLM-powered analysis** | Supports Claude / OpenAI, auto-generates analysis plans and conclusions. Falls back to rule engine without API key |
| **Scene routing** | Auto-selects analysis strategy by keywords (scrolling/startup/general) |
| **Verification layer** | 7 heuristic rules catch LLM misdiagnosis (anti-hallucination, severity validation) |
| **Multi-turn follow-up** | Drill down into existing evidence, CLI interactive mode + Web |
| **MCP Server** | 7 MCP tools, callable from Claude Desktop / Kiro / Cursor |
| **Session persistence** | SQLite storage, survives restarts |
| **CLI + Web** | CLI for scripting and debugging, Web UI for interactive use |

## Quick Start

```bash
# Clone and install
git clone https://github.com/kalimosd/tracelens.git
cd tracelens
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# CLI analysis (rule engine, no API key needed)
python -m tracelens.main analyze \
  --trace your_trace.perfetto-trace \
  --scenario "scrolling jank" \
  --process com.example.app

# With LLM (optional)
pip install -e ".[llm]"
export TRACELENS_LLM_PROVIDER=anthropic
export TRACELENS_LLM_API_KEY=your-key
export TRACELENS_LLM_MODEL=claude-sonnet-4-5-20250929
python -m tracelens.main analyze \
  --trace your_trace.perfetto-trace \
  --scenario "scrolling jank" \
  --interactive  # enter follow-up mode after analysis

# Start Web UI
pip install uvicorn
python -c "
from tracelens.app.api import create_app
import uvicorn
uvicorn.run(create_app(), host='127.0.0.1', port=8000)
"
```

## MCP Integration

TraceLens runs as an MCP Server, letting Claude Desktop, Kiro, Cursor and other AI tools call its analysis capabilities directly.

```bash
pip install -e ".[mcp]"
python -m tracelens.mcp
```

Add to your AI tool's MCP config:

```json
{
  "tracelens": {
    "command": "python",
    "args": ["-m", "tracelens.mcp"]
  }
}
```

**7 MCP tools:**

| Tool | Description |
|---|---|
| `load_trace_file` | Load a trace file, returns trace_id |
| `analyze` | Full analysis pipeline |
| `list_skills` | List available YAML skills |
| `invoke_skill` | Execute a specific skill |
| `execute_sql` | Controlled SQL query (with safety guards) |
| `followup` | Ask follow-up questions on previous analysis |
| `close_trace` | Free resources |

## Example Output

```
Analysis: long slices detected on critical threads; scheduling delays present;
thread blocking observed.

Evidence:
  Process overview — 3 threads, 66 slices
  Frame rhythm — 30 frames, avg 14.8ms, 3 over 16ms, 3 over 33ms
  Long slices — Choreographer#doFrame=77ms; inflate=65ms
  Scheduling delay — main=75ms
  Blocked threads — RenderThread: total=210ms, max_single=14ms, count=19
  Binder transactions — Binder:5000_1: 8 calls, total=243ms, max=37ms

Optimization directions:
  - Investigate long slices — break up heavy work or move off main thread
  - Check CPU contention — scheduling pressure on main thread
  - Examine RenderThread blocking — GPU pipeline sync waits
  - Check cross-process binder call latency
```

## Architecture

```
tracelens/
├── trace/          # Data access: trace loading, SQL queries, safety guards
├── semantics/      # Thread role identification (Android, Flutter)
├── skills/         # YAML skill engine + 10 declarative analysis capabilities
│   └── definitions/  # .yaml skill files (add skills without code changes)
├── analysis/       # Window detection, evidence, analysis chain
├── agent/          # Orchestrator, planner, synthesis, verifier, follow-up
├── llm/            # LLM abstraction (Anthropic / OpenAI compatible)
├── mcp/            # MCP Server (7 tools)
├── artifacts/      # Result storage (in-memory + SQLite)
├── app/            # FastAPI Web UI
├── output/         # CLI renderer, web view model
└── main.py         # CLI entry point (Typer)
```

Design principles:
- **Skill-first** — stable analysis paths are declarative YAML skills, not ad-hoc SQL
- **LLM-optional** — intelligent analysis with LLM, rule engine without
- **Layered architecture** — interaction, orchestration, analysis, semantics, and data access are separated
- **Verification-first** — 7 heuristic rules catch LLM misdiagnosis before output
- **Process-centered** — analysis focuses on the user's target process
- **Explainable** — every conclusion traces back to evidence and analysis steps
- **Runtime-agnostic** — architecture supports both Android and Flutter thread models

## Running Tests

```bash
python -m pytest tests/unit -q
# 111 passed
```

## Current Status

TraceLens can analyze real Perfetto traces end-to-end with LLM-powered analysis and multi-turn follow-up.

Current limitations:
- Flutter dual-pipeline (TextureView vs SurfaceView) not yet auto-detected
- Vendor adaptation (Qualcomm/MediaTek/Samsung) not yet implemented
- Web UI is minimal

## Roadmap

- Flutter dual-pipeline auto-detection and analysis branching
- ArtifactStore summary compression (reduce LLM token usage)
- More YAML skills: GC analysis, CPU frequency, ANR detection
- Web UI enhancement: tables, collapsible evidence
- Report export (Markdown/PDF)
- Controlled SQL exploration (LLM-driven custom queries when skills are insufficient)
- Vendor adaptation (.override.yaml)

## Contributing

Feedback, issues, and PRs are welcome.

Adding new analysis capabilities only requires a `.yaml` file in `tracelens/skills/definitions/` — no Python code changes needed.

## License

MIT
