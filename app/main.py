"""FastAPI application: JSON API plus the single-page web UI."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import __version__
from .database import Database
from .models import Stats, Task, TaskCreate, TaskFilter, TaskUpdate
from .repository import TaskRepository

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = os.environ.get("TASKS_DB", "data/tasks.db")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def create_app(db_path: str | Path = DEFAULT_DB_PATH) -> FastAPI:
    database = Database(db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database.initialize()
        yield
        database.close()

    app = FastAPI(
        title="Tasks",
        description="A small task manager.",
        version=__version__,
        lifespan=lifespan,
    )
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    repository = TaskRepository(database)

    def get_repository() -> TaskRepository:
        return repository

    app.state.database = database
    app.state.repository = repository

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "index.html")

    @app.get("/api/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/stats", response_model=Stats, tags=["tasks"])
    async def get_stats(repo: TaskRepository = Depends(get_repository)) -> Stats:
        return repo.stats()

    @app.get("/api/tasks", response_model=list[Task], tags=["tasks"])
    async def list_tasks(
        status_filter: TaskFilter = Query(TaskFilter.all, alias="status"),
        repo: TaskRepository = Depends(get_repository),
    ) -> list[Task]:
        return repo.list(status_filter)

    @app.post(
        "/api/tasks",
        response_model=Task,
        status_code=status.HTTP_201_CREATED,
        tags=["tasks"],
    )
    async def create_task(
        payload: TaskCreate, repo: TaskRepository = Depends(get_repository)
    ) -> Task:
        return repo.create(payload)

    # Declared before /api/tasks/{task_id} so "completed" is not read as an id.
    @app.delete(
        "/api/tasks/completed",
        status_code=status.HTTP_200_OK,
        tags=["tasks"],
    )
    async def clear_completed(
        repo: TaskRepository = Depends(get_repository),
    ) -> dict[str, int]:
        return {"deleted": repo.delete_completed()}

    @app.get("/api/tasks/{task_id}", response_model=Task, tags=["tasks"])
    async def get_task(
        task_id: int, repo: TaskRepository = Depends(get_repository)
    ) -> Task:
        task = repo.get(task_id)
        if task is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
        return task

    @app.patch("/api/tasks/{task_id}", response_model=Task, tags=["tasks"])
    async def update_task(
        task_id: int,
        payload: TaskUpdate,
        repo: TaskRepository = Depends(get_repository),
    ) -> Task:
        task = repo.update(task_id, payload)
        if task is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
        return task

    @app.delete(
        "/api/tasks/{task_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["tasks"],
    )
    async def delete_task(
        task_id: int, repo: TaskRepository = Depends(get_repository)
    ) -> Response:
        if not repo.delete(task_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return app


app = create_app()
