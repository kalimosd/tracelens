from pathlib import Path

import typer

from tracelens.agent.orchestrator import Orchestrator
from tracelens.config import get_settings
from tracelens.output.cli_renderer import render_analysis
from tracelens.skills.abnormal_windows import AbnormalWindowsSkill
from tracelens.skills.process_thread_discovery import ProcessThreadDiscoverySkill


settings = get_settings()
app = typer.Typer(help=f"{settings.app_name} CLI")


@app.command()
def analyze(
    scenario: str = typer.Option(..., "--scenario"),
    process: str | None = typer.Option(None, "--process"),
    trace: Path | None = typer.Option(None, "--trace", help="Path to a .perfetto-trace file"),
) -> None:
    """Run a TraceLens analysis."""
    orchestrator = Orchestrator(
        window_skill=AbnormalWindowsSkill(),
        process_thread_skill=ProcessThreadDiscoverySkill(),
    )

    if trace is not None:
        if not trace.exists():
            typer.echo(f"Error: trace file not found: {trace}", err=True)
            raise typer.Exit(code=1)
        from tracelens.trace.processor import load_trace

        with load_trace(str(trace)) as session:
            result = orchestrator.analyze(
                scenario=scenario,
                focused_process=process,
                trace_session=session,
            )
    else:
        # Demo fallback
        result = orchestrator.analyze(
            scenario=scenario,
            focused_process=process,
            windows=[
                {"start": 0, "end": 10, "long_tasks": 0, "blocked_threads": 0, "scheduler_delay_ms": 1},
                {"start": 10, "end": 20, "long_tasks": 2, "blocked_threads": 1, "scheduler_delay_ms": 4},
            ],
            threads=[
                {"process_name": process or "auto-detect", "thread_name": "main", "role": "app_main"},
                {"process_name": process or "auto-detect", "thread_name": "RenderThread", "role": "render_thread"},
            ],
        )

    typer.echo(render_analysis(result))


@app.callback(invoke_without_command=True)
def main() -> None:
    """TraceLens entrypoint."""
    return None
