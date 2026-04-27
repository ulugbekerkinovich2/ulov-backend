# ULOV+ Backend

FastAPI + SQLAlchemy + Redis backend for the ULOV+ platform. Serves both `front-user` and `front-admin`.

> Stack is fixed by product: **Python 3.8.10**, **FastAPI 0.103.x**, **Pydantic v1**, **SQLAlchemy 1.4**, **Redis 7**, **PostgreSQL 14+ (PostGIS)**, **Arq** workers. See [../SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) for the full architecture and [../README.md](../README.md) for the phased roadmap.

## Quick start

```bash
cp backend/.env.example backend/.env   # once
make dev                               # builds and starts the full stack
# → http://localhost:8000/docs    (Swagger)
# → http://localhost:8000/redoc
# → http://localhost:8000/health/live
```

That's it. The stack includes Postgres (with PostGIS), Redis, MinIO (with bucket auto-created), and a hot-reloading API + Arq worker.

## Common commands

```bash
make dev            # start full stack, tail api logs
make up             # same, background
make down           # stop (keep volumes)
make nuke           # stop + drop all volumes

make migrate                               # alembic upgrade head
make migration m="add users table"         # autogenerate new migration
make seed                                  # load reference data

make psql           # psql shell inside postgres container
make redis-cli      # redis-cli inside redis container
make shell          # bash shell inside api container

make fmt            # isort + black
make lint           # ruff + mypy + bandit
make test           # pytest with coverage
make audit          # pip-audit
make check          # lint + test (what CI runs)
```

## Layout

```
backend/
├── app/
│   ├── main.py            # FastAPI factory, middlewares, routers
│   ├── config.py          # pydantic BaseSettings
│   ├── deps.py            # shared FastAPI dependencies
│   ├── core/              # security, rbac, errors, logging, pagination, events, rate_limit
│   ├── db/                # base, session
│   ├── api/v1.py          # aggregates module routers under /api/v1
│   ├── modules/           # one folder per bounded context (auth, users, cars, ...)
│   ├── workers/           # arq worker + tasks
│   └── integrations/      # eskiz, playmobile, payme, click, s3, sentry
├── alembic/               # migrations
├── tests/                 # pytest suite
├── scripts/               # seed.py, dump_openapi.py
├── pyproject.toml
├── Dockerfile
└── .env.example
```

Each module follows a strict layering:

```
router → schemas (pydantic) → service (domain) → repository (SQLAlchemy) → models (ORM)
```

Rules:
1. Routers never import `models` directly — always via `service`.
2. Services never import another module's `repository` — only another module's `service`.
3. Cross-module writes go through events (Redis pub-sub or Arq jobs) to keep dependencies acyclic.

## Running without Docker (bare-metal, less common)

```bash
cd backend
poetry install
# Bring up postgres, redis, minio by hand (or via `docker compose up -d postgres redis minio`)
cp .env.example .env
# Point DATABASE_URL and REDIS_URL to your local services
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload --port 8000
```

## Testing

```bash
make test               # full suite with coverage
make test-fast          # skip integration tests
cd backend && poetry run pytest tests/modules/auth  # single module
```

Coverage report is emitted to `backend/coverage.xml` (CI reads it).

## Python 3.8.10 ground rules (must-read)

- `from __future__ import annotations` is **required** in every module file. Enables forward refs and lazy evaluation.
- **No PEP 604**: write `Optional[X]` / `Union[X, Y]`, never `X | None`.
- **No `match` statement**. Use `if/elif`.
- **No `asyncio.TaskGroup`**. Use `asyncio.gather`.
- Type hints in generics must be quoted or deferred via `__future__` import (e.g. `List["User"]`).
- `typing.Protocol` works; `typing.TypedDict` works; `typing.Literal` works.
- Pydantic v1 API: `BaseSettings`, `validator`, `Config` class — not v2 syntax.
- SQLAlchemy 1.4: use `future=True` + 2.0-style `select()` queries to ease a future upgrade.

CI enforces py3.8 syntax via `ruff --target-version=py38`.

## Environment variables

See [.env.example](.env.example). Fill in before `make dev`. Sensible defaults are provided for local dev. Required in prod: `JWT_SECRET`, `DATABASE_URL`, `REDIS_URL`, `SENTRY_DSN`, `ESKIZ_*`, `PAYME_*`, `CLICK_*`.

## Deployment

Container-based. One image, two command variants:

- API: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers`
- Worker: `arq app.workers.arq_worker.WorkerSettings`

Health endpoints (used by load balancer / k8s):

- `GET /health/live` — process is up
- `GET /health/ready` — DB + Redis reachable

See [../SYSTEM_ARCHITECTURE.md §16](../SYSTEM_ARCHITECTURE.md#16-deployment-architecture) for the deployment topology.
