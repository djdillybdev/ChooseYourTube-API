# ChooseYourTube-API

Quick start — local development using Docker for dependencies

1. Copy environment template and edit:

```bash
cp .env.example .env
# edit .env and set YOUTUBE_API_KEY
```

2. Start infrastructure (Postgres + Redis):

```bash
docker compose up -d
```

3. Apply migrations:

```bash
uv run alembic upgrade head
```

4. Run the API and worker on the host for fast development:

```bash
uv run uvicorn app.main:app --reload
uv run arq app.worker.WorkerSettings
```

See `docs/DOCKER.md` for full instructions and helper commands.
