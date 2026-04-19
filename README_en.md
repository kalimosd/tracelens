# TraceLens

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Perfetto](https://img.shields.io/badge/Perfetto-trace__processor-green.svg)](https://perfetto.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-Server-purple.svg)](https://modelcontextprotocol.io)

**Perfetto trace analysis agent — turn "it feels laggy" into "here's what to fix".**

Drop in a trace file, describe the scenario, and TraceLens automatically locates jank frames, traces root causes, and outputs actionable optimization suggestions that developers can directly act on.

[Features](#features) · [Quick Start](#quick-start) · [Example Output](#example-output) · [MCP Integration](#mcp-integration) · [Architecture](#architecture) · [Roadmap](#roadmap) · [Contributing](#contributing)

[中文](README.md)

## Why This Project

Performance engineers spend hours manually scanning Perfetto traces — dozens of processes, thousands of threads, tens of thousands of slices — just to locate a problem. Then they have to write up the findings for the dev team.

TraceLens automates this: load trace → focus on target process → trace per-frame root causes → output a diagnostic report developers can act on immediately.

No black-box conclusions — every step is traceable. Works with LLM for intelligent analysis, or without LLM using the rule-based engine.

## Features

| Feature | Description |
|---|---|
| **Real trace analysis** | Loads `.perfetto-trace` files via `trace_processor` with SQL safety guards |
| **11 YAML Skills** | Declarative SQL analysis — add new skills by writing YAML files |
| **Per-frame causal chain** | Thread state breakdown + bottleneck function identification for each jank frame |
| **Scene-specific diagnosis** | Identifies rotation, cold start, GC, IO blocking, Binder latency as root causes |
| **Actionable reports** | Root cause chain + prioritized fix suggestions developers can code against |
| **Evidence interpretation** | Every evidence item has severity markers (⚠️) and explanations |
| **LLM-powered analysis** | Supports Claude / OpenAI. Falls back to rule engine without API key |
| **Verification layer** | 7 heuristic rules catch LLM misdiagnosis |
| **Multi-turn follow-up** | Drill down into evidence, CLI interactive mode + Web |
| **MCP Server** | 7 tools callable from Claude Desktop / Kiro / Cursor |
| **CLI + Web** | CLI for scripting, Web UI for interactive use |

## Quick Start

```bash
git clone https://github.com/kalimosd/tracelens.git
cd tracelens
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Analyze (rule engine, no API key needed)
python -m tracelens.main analyze \
  --trace your_trace.perfetto-trace \
  --scenario "scrolling jank" \
  --process com.example.app

# With LLM (optional)
pip install -e ".[llm]"
export TRACELENS_LLM_PROVIDER=anthropic
export TRACELENS_LLM_API_KEY=your-key
python -m tracelens.main analyze \
  --trace your_trace.perfetto-trace \
  --scenario "scrolling jank" \
  --interactive

# Web UI
pip install uvicorn
python -c "
from tracelens.app.api import create_app
import uvicorn
uvicorn.run(create_app(), host='127.0.0.1', port=8000)
"
```

## Example Output

**IO blocking causing list jank:**

```
┌─ Summary ───────────────────────────────────────────┐
│ Process    2 threads, 62 slices
│ Frames     25 frames, avg 19.2ms, 4 over 33ms
│ Bottleneck Choreographer#doFrame=92ms on main
│ Main state Running 55% / Sleep 37% / Runnable 6%
└─────────────────────────────────────────────────────┘

Problem: 4 frames severely janked (>33ms)
Root cause:
  1. Single frame timeout (92ms)
  2. SQLiteDatabase.query (80ms)
  3. SQLiteSession.executeForCursorWindow (76ms)

▸ Frame causal chain
  Frame main@1166666670: 92ms
    State: Running=41ms(44.6%), S=36ms(39.4%), R=14ms(16.0%)
    Bottleneck: SQLiteDatabase.query=80ms
  ⚠️ Severe jank, investigate first
```

**Rotation jank:**

```
Problem: 1 frame severely janked (>33ms)
Root cause:
  1. Screen rotation triggers Activity rebuild (180ms)
  2. Activity launch onCreate/onResume (120ms)
  3. Layout inflate (85ms) ← main bottleneck

Optimization:
  1. [Priority] Cache state to reduce rebuild scope, or use android:configChanges (180ms)
  2. [Priority] Reduce synchronous work in Activity.onCreate (120ms)
  3. [Priority] Simplify layout XML or use ViewStub for lazy loading (inflate 85ms)
  4. [Suggested] Move Binder calls to background thread (max 19ms)
```

## MCP Integration

```bash
pip install -e ".[mcp]"
python -m tracelens.mcp
```

MCP config:
```json
{
  "tracelens": {
    "command": "python",
    "args": ["-m", "tracelens.mcp"]
  }
}
```

**7 tools:** `load_trace_file` / `analyze` / `list_skills` / `invoke_skill` / `execute_sql` / `followup` / `close_trace`

## Architecture

```
tracelens/
├── trace/          # Data access: trace loading, SQL queries, safety guards
├── semantics/      # Thread role identification (Android, Flutter)
├── skills/         # YAML skill engine + 11 declarative analysis capabilities
│   └── definitions/  # .yaml files (add skills without code changes)
├── analysis/       # Window detection, evidence interpreter, analysis chain
├── agent/          # Orchestrator, planner, synthesis, verifier, follow-up
├── llm/            # LLM abstraction (Anthropic / OpenAI compatible)
├── mcp/            # MCP Server (7 tools)
├── artifacts/      # Result storage (in-memory + SQLite)
├── app/            # FastAPI Web UI (Tailwind CSS)
├── output/         # CLI renderer (summary table + structured output)
└── main.py         # CLI entry point (Typer)
```

Design principles:
- **Skill-first** — declarative YAML skills, not ad-hoc SQL
- **Business-oriented** — root cause chains + actionable fix suggestions
- **LLM-optional** — intelligent with LLM, functional without
- **Verification-first** — 7 rules catch LLM misdiagnosis before output
- **Runtime-agnostic** — supports Android and Flutter thread models

## Tests

```bash
python -m pytest tests/unit -q
# 131 passed
```

## Status

TraceLens analyzes real Perfetto traces end-to-end, outputting actionable diagnostic reports.

Verified scenarios: scrolling jank, screen rotation, cold start, GC pressure, IO blocking, CPU contention, animation jank, cross-process Binder latency, Flutter frame jank.

Limitations:
- Flutter dual-pipeline (TextureView vs SurfaceView) not yet auto-detected
- Vendor adaptation (Qualcomm/MediaTek/Samsung) not yet implemented
- Waker chain analysis requires sched_waking events in the trace

## Roadmap

- Flutter dual-pipeline auto-detection
- ArtifactStore summary compression
- More YAML skills: ANR detection, CPU frequency
- Report export (Markdown/PDF)
- Controlled SQL exploration
- Vendor adaptation (.override.yaml)

## Contributing

Feedback, issues, and PRs welcome. Add analysis capabilities by creating `.yaml` files in `tracelens/skills/definitions/` — no Python changes needed.

## License

MIT
