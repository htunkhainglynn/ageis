# FastAPI Backend Template

A production-ready FastAPI backend scaffold with async SQLAlchemy, PostgreSQL, Redis, JWT authentication, structured logging, and Alembic migrations.

## Tech Stack

- Python 3.11+
- FastAPI
- SQLAlchemy 2.0 (async) + asyncpg
- Alembic
- Pydantic v2
- Redis (async client)
- python-jose (JWT)
- passlib (bcrypt)
- Loguru

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy environment values:

```bash
cp .env.example .env
```

4. Start the API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Database Migrations

Create a migration:

```bash
alembic revision --autogenerate -m "init"
```

Run migrations:

```bash
alembic upgrade head
```

## API Docs

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
