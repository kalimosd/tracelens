import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from tracelens.agent.orchestrator import Orchestrator
from tracelens.artifacts.store import InMemoryArtifactStore
from tracelens.config import get_settings
from tracelens.skills.abnormal_windows import AbnormalWindowsSkill
from tracelens.skills.process_thread_discovery import ProcessThreadDiscoverySkill


STORE = InMemoryArtifactStore()
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request,
            "index.html",
            {"app_name": settings.app_name},
        )

    @app.post("/analyze", response_class=HTMLResponse)
    async def analyze(
        request: Request,
        scenario: str = Form(...),
        process: str | None = Form(None),
        trace: UploadFile | None = File(None),
    ) -> HTMLResponse:
        orchestrator = Orchestrator(
            window_skill=AbnormalWindowsSkill(),
            process_thread_skill=ProcessThreadDiscoverySkill(),
        )

        if trace is not None and trace.size and trace.size > 0:
            from tracelens.trace.processor import load_trace

            with tempfile.NamedTemporaryFile(suffix=".perfetto-trace", delete=False) as tmp:
                tmp.write(await trace.read())
                tmp_path = tmp.name

            try:
                with load_trace(tmp_path) as session:
                    result = orchestrator.analyze(
                        scenario=scenario,
                        focused_process=process or None,
                        trace_session=session,
                    )
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        else:
            result = orchestrator.analyze(
                scenario=scenario,
                focused_process=process or None,
                windows=[
                    {"start": 0, "end": 10, "long_tasks": 0, "blocked_threads": 0, "scheduler_delay_ms": 1},
                    {"start": 10, "end": 20, "long_tasks": 2, "blocked_threads": 1, "scheduler_delay_ms": 4},
                ],
                threads=[
                    {"process_name": process or "auto-detect", "thread_name": "main", "role": "app_main"},
                    {"process_name": process or "auto-detect", "thread_name": "RenderThread", "role": "render_thread"},
                ],
            )

        session_id = STORE.save(result)
        return TEMPLATES.TemplateResponse(
            request,
            "result.html",
            {"app_name": settings.app_name, "session_id": session_id, "result": result},
        )

    @app.post("/followup")
    def followup(session_id: str = Form(...), question: str = Form(...)) -> dict[str, str]:
        result = STORE.load(session_id)
        if result is None:
            raise HTTPException(status_code=404, detail="session not found")
        return {"session_id": session_id, "question": question, "status": "accepted"}

    return app
