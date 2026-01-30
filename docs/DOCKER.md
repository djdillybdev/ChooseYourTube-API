# Docker — Local Development

This repository uses Docker Compose to run infrastructure dependencies (PostgreSQL and Redis) locally while the FastAPI app and arq worker run on the host for fast hot-reload during development.

Prerequisites

- Docker Engine and Docker Compose

Quick start

```bash
# 1. Copy env template
cp .env.example .env
# Edit `.env` with your real values (set `YOUTUBE_API_KEY`)

# 2. Start infrastructure
docker compose up -d

# 3. Apply migrations
uv run alembic upgrade head

# 4. Run API server (terminal 1)
uv run uvicorn app.main:app --reload

# 5. Run worker (terminal 2)
uv run arq app.worker.WorkerSettings
```

Daily workflow

```bash
docker compose up -d
uv run uvicorn app.main:app --reload
uv run arq app.worker.WorkerSettings

# When done
docker compose down
```

Utility commands

```bash
# Follow logs
docker compose logs -f postgres
docker compose logs -f redis

# Reset database (destroys data)
docker compose down -v
docker compose up -d
uv run alembic upgrade head

# PostgreSQL CLI
docker compose exec postgres psql -U postgres -d chooseyourtube

# Check container status
docker compose ps
```

Notes

- The app/worker run on the host and connect to `localhost` for Postgres/Redis.
- `.env` is intentionally ignored by Git — use `.env.example` as a template.
