"""FastAPI web server with SSE progress streaming for the Requirements-to-Code Agent."""

import asyncio
import json
import uuid
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse

from pydantic import BaseModel

from src.models.artifacts import AgentContext
from src.orchestrator.pipeline import Pipeline, PipelineProgress
from src.output.formatters import OutputWriter
from src.config import OUTPUT_DIR, load_settings, save_settings, get_api_key, get_model, get_base_url


class SettingsModel(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    temperature: float = 0.3
    max_tokens: int = 8192

app = FastAPI(title="需求到代码 Agent", version="1.0.0")

# In-memory storage for runs
runs: dict[str, dict] = {}
HTML_TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"


# ── SSE-enabled Pipeline Progress ─────────────────────────────────────

class SSEProgress(PipelineProgress):
    """Pipeline progress that sends events to an asyncio queue for SSE."""

    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self._phase_map = {
            "Phase 1/4": 1, "Phase 2/4": 2, "Phase 3/4": 3, "Phase 4/4": 4,
        }

    async def _emit(self, event: str, data: dict):
        await self.queue.put({"event": event, "data": json.dumps(data, ensure_ascii=False)})

    def on_phase_start(self, phase: str, agent_name: str):
        phase_num = self._phase_map.get(phase, 0)
        asyncio.create_task(self._emit("phase_start", {
            "phase": phase,
            "agent": agent_name,
            "phase_num": phase_num,
        }))

    def on_phase_end(self, phase: str, agent_name: str, duration_ms: float):
        asyncio.create_task(self._emit("phase_end", {
            "phase": phase,
            "agent": agent_name,
            "duration_ms": duration_ms,
        }))

    def on_error(self, phase: str, error: str):
        asyncio.create_task(self._emit("error", {"phase": phase, "error": error}))


# ── Routes ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main web UI."""
    html_path = HTML_TEMPLATE_PATH
    if not html_path.exists():
        # Fallback: serve the template from src directory
        alt_path = Path(__file__).parent.parent / "templates" / "index.html"
        if alt_path.exists():
            html_path = alt_path
        else:
            return HTMLResponse("<h1>Template not found. Run the app from the project root.</h1>", status_code=500)
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.post("/api/run")
async def run_pipeline(
    prd_text: str = Form(...),
    project_name: str = Form("Unnamed Project"),
):
    """Start a pipeline run and return a run ID."""
    run_id = uuid.uuid4().hex[:12]
    queue = asyncio.Queue()

    runs[run_id] = {
        "id": run_id,
        "status": "pending",
        "queue": queue,
        "context": None,
        "output_dir": None,
        "created_at": datetime.now().isoformat(),
    }

    # Launch pipeline in background
    asyncio.create_task(_execute_pipeline(run_id, prd_text, project_name, queue))

    return {"run_id": run_id, "status": "started"}


@app.get("/api/run/{run_id}/stream")
async def stream_progress(run_id: str):
    """SSE endpoint for real-time pipeline progress."""
    run = runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    queue: asyncio.Queue = run["queue"]

    async def event_generator():
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30)
                yield msg
                if msg.get("event") in ("complete", "error"):
                    break
            except asyncio.TimeoutError:
                yield {"event": "heartbeat", "data": "{}"}
                # Check if run completed externally
                if runs.get(run_id, {}).get("status") in ("completed", "failed"):
                    break

    return EventSourceResponse(event_generator())


@app.get("/api/run/{run_id}/results")
async def get_results(run_id: str):
    """Get the final results of a pipeline run."""
    run = runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run["status"] not in ("completed", "failed"):
        return {"status": run["status"]}

    ctx: AgentContext = run["context"]
    if not ctx:
        return {"status": run["status"], "error": "No context available"}

    return {
        "status": run["status"],
        "project_name": ctx.project_name,
        "summary": ctx.summary(),
        "functional_modules": [m.model_dump() for m in ctx.functional_modules],
        "user_stories": [s.model_dump() for s in ctx.user_stories],
        "db_schema": [t.model_dump() for t in ctx.db_schema],
        "api_contracts": [a.model_dump() for a in ctx.api_contracts],
        "code_artifacts": [c.model_dump() for c in ctx.code_artifacts],
        "test_cases": [
            {
                "id": tc.id, "title": tc.title, "type": tc.type.value,
                "description": tc.description, "setup": tc.setup,
                "steps": tc.steps, "expected_result": tc.expected_result,
                "related_api": tc.related_api, "related_user_story": tc.related_user_story,
                "test_data": tc.test_data, "code": tc.code,
            }
            for tc in ctx.test_cases
        ],
        "review_report": ctx.review_report.model_dump() if ctx.review_report else None,
        "output_dir": run.get("output_dir"),
    }


@app.get("/api/output/{run_id}/{filename:path}")
async def get_output_file(run_id: str, filename: str):
    """Serve a specific output file."""
    run = runs.get(run_id)
    if not run or not run.get("output_dir"):
        raise HTTPException(status_code=404, detail="Output not found")
    file_path = Path(run["output_dir"]) / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


# ── Settings ────────────────────────────────────────────────────────────

@app.get("/api/settings")
async def get_settings():
    """Get current settings (mask sensitive fields)."""
    stored = load_settings()
    current = {
        "api_key": _mask_key(stored.get("api_key", "") or get_api_key()),
        "base_url": stored.get("base_url", "") or get_base_url(),
        "model": stored.get("model", "") or get_model(),
        "temperature": stored.get("temperature", 0.3),
        "max_tokens": stored.get("max_tokens", 8192),
    }
    # Check if api_key is from settings file or env
    current["has_custom_api_key"] = bool(stored.get("api_key", ""))
    current["has_custom_base_url"] = bool(stored.get("base_url", ""))
    return current


@app.put("/api/settings")
async def update_settings(settings: SettingsModel):
    """Update settings and persist to file."""
    stored = load_settings()

    # Only update api_key if a non-masked value is provided
    if settings.api_key and not settings.api_key.startswith("sk-***"):
        stored["api_key"] = settings.api_key

    if settings.base_url:
        stored["base_url"] = settings.base_url
    else:
        stored.pop("base_url", None)

    if settings.model:
        stored["model"] = settings.model
    else:
        stored.pop("model", None)

    stored["temperature"] = settings.temperature
    stored["max_tokens"] = settings.max_tokens

    save_settings(stored)

    return {
        "status": "saved",
        "has_custom_api_key": bool(stored.get("api_key")),
        "has_custom_base_url": bool(stored.get("base_url")),
        "model": stored.get("model", "") or get_model(),
    }


@app.post("/api/settings/test")
async def test_connection():
    """Test the API connection with current settings."""
    import anthropic
    api_key = get_api_key()
    if not api_key:
        return {"status": "error", "message": "未配置 API Key"}

    base_url = get_base_url()
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url

    try:
        client = anthropic.Anthropic(**kwargs)
        model = get_model()
        response = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Say 'ok'"}],
        )
        return {"status": "ok", "message": f"连接成功 (模型: {model})"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 12:
        return "*" * len(key)
    return key[:7] + "***" + key[-4:]


# ── Pipeline execution ────────────────────────────────────────────────

async def _execute_pipeline(run_id: str, prd_text: str, project_name: str, queue: asyncio.Queue):
    """Execute the full pipeline in the background, pushing events to the queue."""
    try:
        run = runs[run_id]
        run["status"] = "running"

        progress = SSEProgress(queue)
        pipeline = Pipeline(progress=progress)

        # Run pipeline in a thread to not block the event loop
        context = await asyncio.to_thread(pipeline.run, prd_text, project_name)

        # Write output files
        writer = OutputWriter(OUTPUT_DIR)
        output_dir = writer.write_all(context)

        run["status"] = "completed"
        run["context"] = context
        run["output_dir"] = str(output_dir)

        await queue.put({
            "event": "complete",
            "data": json.dumps({
                "output_dir": str(output_dir),
                "summary": context.summary(),
            }, ensure_ascii=False),
        })

    except Exception as e:
        runs[run_id]["status"] = "failed"
        await queue.put({
            "event": "error",
            "data": json.dumps({"error": str(e)}, ensure_ascii=False),
        })


# ── Entry point ───────────────────────────────────────────────────────

def start():
    """Start the web server."""
    import uvicorn
    uvicorn.run("src.web_server:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    start()
