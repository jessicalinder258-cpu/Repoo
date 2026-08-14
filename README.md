# Tasks

A small task manager written in Python. FastAPI serves both a JSON API and a
single-page web UI, and tasks are stored in a local SQLite file, so there is no
database server to run and nothing to sign up for.

## Features

- Add tasks with a priority (low / medium / high) and an optional due date
- Tick tasks off, rename them by clicking the title, and delete them
- Filter by all / active / completed, and clear finished tasks in one click
- A progress ring and counts showing how much is left
- Due dates render as friendly text ("Due tomorrow", "3 days late")
- Sorted so unfinished and urgent work floats to the top
- Light and dark themes, following your system setting
- Interactive API documentation at `/docs`

## Requirements

Python 3.10 or newer.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If `python3 -m venv` is unavailable on your machine, install into your user
directory instead:

```bash
pip install --user -r requirements.txt
```

## Running

```bash
uvicorn app.main:app --reload
```

Then open <http://127.0.0.1:8000>.

The database file is created automatically at `data/tasks.db`. Point the
`TASKS_DB` environment variable somewhere else to change that:

```bash
TASKS_DB=/tmp/my-tasks.db uvicorn app.main:app
```

## Tests

```bash
pytest
```

## API

| Method   | Path                    | Description                                        |
| -------- | ----------------------- | -------------------------------------------------- |
| `GET`    | `/api/tasks`            | List tasks; `?status=all\|active\|completed`        |
| `POST`   | `/api/tasks`            | Create a task                                       |
| `GET`    | `/api/tasks/{id}`       | Fetch one task                                      |
| `PATCH`  | `/api/tasks/{id}`       | Update any subset of fields                         |
| `DELETE` | `/api/tasks/{id}`       | Delete a task                                       |
| `DELETE` | `/api/tasks/completed`  | Delete every completed task                         |
| `GET`    | `/api/stats`            | Totals for active, completed and all tasks          |
| `GET`    | `/api/health`           | Health check                                        |

Creating a task:

```bash
curl -X POST http://127.0.0.1:8000/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{"title": "Buy milk", "priority": "high", "due_date": "2030-01-15"}'
```

Because updates are `PATCH`, omitted fields keep their current value, while an
explicit `null` clears a due date:

```bash
curl -X PATCH http://127.0.0.1:8000/api/tasks/1 \
  -H 'Content-Type: application/json' \
  -d '{"completed": true}'
```

## Layout

```
app/
  main.py        FastAPI app factory, routes
  models.py      Pydantic request/response schemas
  repository.py  SQL queries for tasks
  database.py    Connection handling and schema
  templates/     index.html
  static/        style.css, app.js
tests/           pytest suite covering the API
```

The app is built with a `create_app(db_path)` factory, so tests run against a
throwaway database and never touch your real one.
