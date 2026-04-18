# TraceLens

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Perfetto](https://img.shields.io/badge/Perfetto-trace__processor-green.svg)](https://perfetto.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Perfetto trace analysis agent — turn "it feels laggy" into "here's why it's laggy".**

Drop in a trace file, describe the scenario, and TraceLens automatically locates abnormal windows, identifies key threads, chains evidence together, and suggests optimization directions.

[Features](#features) · [Quick Start](#quick-start) · [Example Output](#example-output) · [Architecture](#architecture) · [Roadmap](#roadmap) · [Contributing](#contributing)

[中文](README.md)

## Why This Project

When a performance engineer gets a trace file, they typically spend time manually scanning dozens of processes, thousands of threads, and tens of thousands of slices in the Perfetto UI to locate the problem.

TraceLens automates this: load trace → focus on the target process → run a set of analysis skills → output a structured evidence chain with optimization directions.

No black-box conclusions — every step is traceable.

## Features

| Feature | Description |
|---|---|
| **Real trace analysis** | Loads `.perfetto-trace` files, queries via `trace_processor` with SQL safety guards |
| **Automatic process inference** | Selects the most likely app process when none is specified |
| **Thread role identification** | Recognizes main thread (handles Android 15-char truncation), RenderThread, Flutter UI/Raster |
| **Abnormal window detection** | Splits trace into 100ms windows, scores by long tasks, blocking, and scheduling delay |
| **Long slice detection** | Finds operations exceeding 16ms |
| **Scheduling delay analysis** | Measures time threads spend in Runnable state waiting to be scheduled |
| **Blocking chain analysis** | Identifies thread blocking (Sleep/D state) with total duration, max single, and count |
| **Frame rhythm analysis** | Detects jank frames based on `Choreographer#doFrame` intervals |
| **Cross-process dependencies** | Discovers related system processes and binder calls |
| **Structured output** | Conclusion, key evidence, analysis chain, optimization directions, uncertainties |
| **CLI + Web** | CLI for scripting and debugging, Web UI for interactive use |

## Quick Start

```bash
# Clone and install
git clone https://github.com/kalimosd/tracelens.git
cd tracelens
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# CLI analysis
python -m tracelens.main analyze \
  --trace your_trace.perfetto-trace \
  --scenario "scrolling jank" \
  --process com.example.app

# Start Web UI
pip install uvicorn
python -c "
from tracelens.app.api import create_app
import uvicorn
uvicorn.run(create_app(), host='127.0.0.1', port=8000)
"
# Open http://127.0.0.1:8000 and upload a trace file
```

## Example Output

```
Analysis: long slices detected on critical threads; scheduling delays present;
thread blocking observed.

Evidence:
  Top abnormal window — window score=62; primary role=app_main
  Thread state distribution — Running=466ms, S=402ms, R=64ms
  Long slices — Choreographer#doFrame=77ms on main; inflate=65ms on main
  Scheduling delay — main=75ms
  Blocked threads — RenderThread: total=210ms, max_single=14ms, count=19
  Frame rhythm — 30 frames, avg interval 16ms, 0 jank(s)
  Cross-process dependencies — surfaceflinger; system_server

Optimization directions:
  - Investigate long slices — consider breaking up heavy work or moving it off the main thread
  - Check CPU contention — threads waiting in runnable state suggest scheduling pressure
  - Examine blocking causes — look for lock contention, binder calls, or I/O waits
```

## Architecture

```
tracelens/
├── trace/          # Data access: trace loading, SQL queries, safety guards
├── semantics/      # Thread role identification (Android, Flutter)
├── skills/         # Reusable analysis capabilities (skill-first design)
├── analysis/       # Window detection, evidence, analysis chain
├── agent/          # Orchestrator, planner, synthesis
├── artifacts/      # Result storage (in-memory, future: SQLite)
├── app/            # FastAPI Web UI
├── output/         # CLI renderer, web view model
└── main.py         # CLI entry point (Typer)
```

Design principles:
- **Skill-first** — stable analysis paths are reusable skills, not ad-hoc SQL
- **Layered architecture** — interaction, orchestration, analysis, semantics, and data access are separated
- **Process-centered** — analysis focuses on the user's target process
- **Explainable** — every conclusion traces back to evidence and analysis steps
- **Runtime-agnostic** — architecture supports both Android and Flutter thread models

## Running Tests

```bash
python -m pytest tests/unit -q
# 57 passed
```

## Current Status

TraceLens can analyze real Perfetto traces end-to-end. Current limitations:

- Follow-up questioning is placeholder only
- Result storage is in-memory (no persistence across restarts)
- No LLM integration yet — all analysis is rule-based
- Frame rhythm detection depends on `Choreographer#doFrame` slices being present

## Roadmap

- Multi-turn follow-up based on existing evidence
- SQLite persistent storage
- More skills: ANR detection, GPU rendering analysis
- LLM-assisted attribution and conclusion generation
- Flutter runtime semantic adaptation
- Batch trace analysis and comparison

## Contributing

Feedback, issues, and PRs are welcome.

If you want to improve analysis capabilities, test output quality, or suggest product direction — open an issue or start a discussion.

## License

MIT
