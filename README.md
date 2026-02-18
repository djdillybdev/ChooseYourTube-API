# ChooseYourTube API

Backend API for managing YouTube channels, videos, playlists, folders, and tags with per-user data isolation and background synchronization jobs.

## What This Service Does

- Stores selected YouTube channels and their videos.
- Lets users organize channels in folders and attach tags.
- Supports manual and system playlists with ordered video positions.
- Syncs channel videos and channel playlists in the background.
- Exposes JWT-based authentication and user management.

## Tech Stack

- Python 3.12+
- FastAPI + Uvicorn
- SQLAlchemy 2 (async) + Alembic
- PostgreSQL 16
- Redis 7 + arq worker/cron jobs
- fastapi-users (JWT bearer auth)
- YouTube Data API + YouTube RSS feed parsing
- Tooling: `uv`, `pytest`, `ruff`, `mypy`

## Architecture

### Runtime Components

- API process: FastAPI app in `app/main.py`
- Worker process: arq worker in `app/worker.py`
- Database: PostgreSQL
- Queue backend: Redis

API and worker both run on the host in local development and connect to Dockerized PostgreSQL/Redis over `localhost`.

### Layered Backend Structure

- `app/routers/`: HTTP endpoints and request parsing.
- `app/services/`: orchestration/business rules.
- `app/db/crud/`: query-focused data access.
- `app/db/models/`: SQLAlchemy models and relationships.
- `app/schemas/`: Pydantic request/response schemas.
- `app/auth/`: fastapi-users integration, auth backend, user model.
- `app/clients/`: external integrations (YouTube API client).

### Data and Execution Flow

1. Channel creation flow
- `POST /channels` creates a channel in DB (scoped to current user).
- API enqueues background jobs:
  - `fetch_and_store_all_channel_videos_task`
  - `sync_channel_playlists_task`
- Worker executes jobs and writes channel/video/playlist data.

2. Periodic refresh flow
- Worker cron runs hourly (`enqueue_channel_refreshes`).
- One refresh job per saved channel is enqueued with staggered delay.
- Job checks RSS/API and updates latest videos.

### Tenancy Model

- Core entities include `owner_id`.
- Routers resolve current authenticated user and pass `owner_id` into services.
- Queries are scoped by `owner_id` for user-level isolation.

### Search

- Video full-text search uses a PostgreSQL functional GIN index added in migration `20260217_add_video_fts`.

## Prerequisites

- Docker + Docker Compose
- Python 3.12+
- `uv` installed
- YouTube Data API key

## Environment Configuration

Create local environment file:

```bash
cp .env.example .env
```

Required variables:

- `DATABASE_URL`: async SQLAlchemy PostgreSQL DSN
- `REDIS_URL`: Redis DSN
- `API_ORIGIN`: frontend origin (for CORS/context)
- `YOUTUBE_API_KEY`: key for YouTube API calls
- `AUTH_SECRET`: JWT signing secret

Use a strong `AUTH_SECRET` outside local development.

## Local Setup (First Run)

1. Install dependencies:

```bash
uv sync
```

2. Start infrastructure:

```bash
docker compose up -d
```

3. Apply database migrations:

```bash
uv run alembic upgrade head
```

4. Run API server (terminal 1):

```bash
uv run uvicorn app.main:app --reload
```

5. Run worker (terminal 2):

```bash
uv run arq app.worker.WorkerSettings
```

Default API URL: `http://127.0.0.1:8000`

## Daily Development Workflow

Start everything:

```bash
docker compose up -d
uv run uvicorn app.main:app --reload
uv run arq app.worker.WorkerSettings
```

Stop infrastructure:

```bash
docker compose down
```

Useful commands:

```bash
# Check service state
docker compose ps

# Follow infra logs
docker compose logs -f postgres
docker compose logs -f redis

# PostgreSQL shell
docker compose exec postgres psql -U postgres -d chooseyourtube
```

Reset local DB (destructive):

```bash
docker compose down -v
docker compose up -d
uv run alembic upgrade head
```

## API Usage

OpenAPI docs:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

Auth routes:

- `POST /auth/register`
- `POST /auth/jwt/login`
- `POST /auth/jwt/logout`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `GET /users/me`

Send bearer token:

```http
Authorization: Bearer <token>
```

Main route groups:

- `/channels`
- `/videos`
- `/playlists`
- `/folders`
- `/tags`
- `/health`

## Background Jobs and Scheduling

Worker functions:

- `fetch_and_store_all_channel_videos_task`
- `refresh_latest_channel_videos_task`
- `sync_channel_playlists_task`

Scheduler:

- Hourly cron enqueues channel refresh jobs.
- Redis is required for enqueueing and worker execution.

## Testing and Quality Checks

Run all tests:

```bash
uv run pytest
```

Run subsets:

```bash
uv run pytest -m unit
uv run pytest -m integration
```

Lint and type check:

```bash
uv run ruff check
uv run mypy app
```

## Database Migrations

Apply latest migrations:

```bash
uv run alembic upgrade head
```

Create a new migration after model changes:

```bash
uv run alembic revision --autogenerate -m "describe_change"
```

Include migration files with schema changes in commits.

## Production Basics

- Provide secure values for secrets and all required env vars.
- Run API and worker as separate processes/services.
- Use managed PostgreSQL and Redis.
- Run `alembic upgrade head` during deployment.
- Restrict CORS to trusted frontend origins.
- Monitor health endpoints and worker process health.

This README intentionally focuses on local development and production essentials, not a full deployment runbook.

## Troubleshooting

- `DATABASE_URL` connection errors:
  - ensure `docker compose up -d` is running and port `5432` is available.
- Redis/queue errors:
  - verify Redis container is up and `REDIS_URL` matches local port `6379`.
- Auth errors:
  - check `AUTH_SECRET` is set and stable between restarts.
- YouTube sync failures:
  - confirm `YOUTUBE_API_KEY` is valid and has quota.
- Migration mismatch:
  - run `uv run alembic upgrade head` and verify migration chain.

## Project Layout

```text
app/
  auth/         # Authentication and user management
  clients/      # External API clients (YouTube)
  core/         # Settings/config
  db/           # Models, session, CRUD
  routers/      # FastAPI route handlers
  schemas/      # Pydantic schemas
  services/     # Business logic orchestration
  main.py       # FastAPI app entrypoint
  worker.py     # arq worker + cron configuration
migration/      # Alembic env and migration versions
tests/          # Unit, CRUD, services, routers, integration, worker, property tests
```
