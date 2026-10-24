from database.core.db_url import prepare_async_database_url


def test_supabase_ssl_query_becomes_connect_args() -> None:
    url, args = prepare_async_database_url(
        "postgresql+asyncpg://u:p@host:6543/postgres?ssl=require"
    )
    assert url == "postgresql+asyncpg://u:p@host:6543/postgres"
    assert args == {"ssl": True}


def test_sslmode_require() -> None:
    url, args = prepare_async_database_url(
        "postgresql+asyncpg://u:p@host:5432/db?sslmode=require&application_name=x"
    )
    assert "sslmode" not in url
    assert "application_name=x" in url
    assert args == {"ssl": True}


def test_sqlite_unchanged() -> None:
    url, args = prepare_async_database_url("sqlite+aiosqlite:///./test.db")
    assert url.startswith("sqlite")
    assert args == {"check_same_thread": False}


def test_plain_postgres_no_ssl() -> None:
    raw = "postgresql+asyncpg://postgres:postgres@localhost:5432/freelance"
    url, args = prepare_async_database_url(raw)
    assert url == raw
    assert args == {}
