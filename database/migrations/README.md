# Alembic migrations

This directory contains migration scripts for the FastAPI backend.

To initialize migrations:

```bash
cd fastapi
alembic revision --autogenerate -m "create initial tables"
alembic upgrade head
```

Ensure `DATABASE_URL` is set in `.env`.
