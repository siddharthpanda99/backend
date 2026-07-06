"""Conftest for Admin DB integration tests.

Requires a running PostgreSQL database. Set env vars:
  TEST_DB_HOST=localhost
  TEST_DB_PORT=5432
  TEST_DB_NAME=test_admin_db
  TEST_DB_USER=postgres
  TEST_DB_PASSWORD=postgres
"""
import os
import sys
import uuid
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "Python Libs"))

# Skip all tests in this directory if psycopg is not installed
try:
    import psycopg
except ImportError:
    pytest.skip("psycopg not installed", allow_module_level=True)

DB_HOST = os.environ.get("TEST_DB_HOST", "localhost")
DB_PORT = int(os.environ.get("TEST_DB_PORT", "5432"))
DB_NAME = os.environ.get("TEST_DB_NAME", "test_admin_db")
DB_USER = os.environ.get("TEST_DB_USER", "postgres")
DB_PASSWORD = os.environ.get("TEST_DB_PASSWORD", "postgres")
TEST_SCHEMA = "test_admin_db_schema"


@pytest.fixture(scope="session", autouse=True)
def ensure_database():
    """Create the test database and schema if they don't exist."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    engine = create_engine(
        f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres",
        poolclass=NullPool, connect_args={"connect_timeout": 5},
    )
    try:
        with engine.connect() as conn:
            conn.execute(text("COMMIT"))
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": DB_NAME}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{DB_NAME}"'))
    except Exception as e:
        pytest.skip(f"PostgreSQL not available at {DB_HOST}:{DB_PORT}: {e}")
    finally:
        engine.dispose()

    engine = create_engine(
        f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
        poolclass=NullPool, connect_args={"connect_timeout": 5},
    )
    try:
        with engine.connect() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{TEST_SCHEMA}"'))
            conn.commit()
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def db_url():
    """Database URL for the test database."""
    return f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


@pytest.fixture(scope="session")
def db_engine(db_url):
    """SQLAlchemy engine for the test database."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    engine = create_engine(db_url, poolclass=NullPool, connect_args={"connect_timeout": 5})
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def connection_profile_id():
    """Create and return a connection profile ID for the test DB."""
    from common_lib.modules.admin_db.service import ConnectionService
    from common_lib.modules.admin_db.schemas import ConnectionProfileCreate

    profile = ConnectionService.create_profile(ConnectionProfileCreate(
        name=f"test_profile_{uuid.uuid4().hex[:6]}",
        db_type="postgresql",
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        username=DB_USER,
        password=DB_PASSWORD,
    ))
    yield profile.id
    try:
        ConnectionService.delete_profile(profile.id)
    except Exception:
        pass


@pytest.fixture(scope="function")
def test_table_name():
    """Unique table name per test for isolation."""
    return f"test_tbl_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="function")
def setup_test_table(db_engine, test_table_name):
    """Create a test table with sample data, yield the name, then drop it."""
    from sqlalchemy import text

    schema = TEST_SCHEMA
    with db_engine.connect() as conn:
        conn.execute(text(f"""
            CREATE TABLE "{schema}"."{test_table_name}" (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(200),
                age INTEGER,
                score NUMERIC(5,2),
                active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT now()
            )
        """))
        for i in range(25):
            conn.execute(text(
                f'INSERT INTO "{schema}"."{test_table_name}" (name, email, age, score, active) '
                f'VALUES (:name, :email, :age, :score, :active)'
            ), {
                "name": f"User {i}",
                "email": f"user{i}@example.com",
                "age": 20 + (i % 30),
                "score": round(50.0 + i * 2.5, 2),
                "active": i % 3 == 0,
            })
        conn.commit()
    yield test_table_name
    with db_engine.connect() as conn:
        conn.execute(text(f'DROP TABLE IF EXISTS "{schema}"."{test_table_name}"'))
        conn.commit()
