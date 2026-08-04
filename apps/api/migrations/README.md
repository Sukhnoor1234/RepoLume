# Database migrations

Alembic migrations for the RepoLume API are intentionally scoped to PostgreSQL.
Set `REPOLUME_DATABASE_URL` to a `postgresql+psycopg://` URL before running:

```bash
python -m alembic upgrade head
```

To review generated PostgreSQL without connecting to a database:

```bash
python -m alembic upgrade head --sql
```

Do not commit database credentials or place them in `alembic.ini`.
