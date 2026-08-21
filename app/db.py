import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase


def _get_db_url() -> str:
    # 1. Streamlit secrets (produkce — Supabase/Postgres)
    try:
        import streamlit as st
        url = st.secrets.get("DATABASE_URL", "")
        if url:
            return url.replace("postgres://", "postgresql://", 1)
    except Exception:
        pass

    # 2. Env proměnná (lokální vývoj s Postgres)
    url = os.environ.get("DATABASE_URL", "")
    if url:
        return url.replace("postgres://", "postgresql://", 1)

    # 3. SQLite fallback (lokální vývoj)
    db_path = os.environ.get("TIPOVACKA_PL_DB", "tipovacka_pl.db")
    return f"sqlite:///{db_path}"


_DB_URL = _get_db_url()
_is_sqlite = _DB_URL.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(
        _DB_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
else:
    engine = create_engine(
        _DB_URL,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=3,
        pool_recycle=300,
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models import models  # noqa: F401 — registers all models
    Base.metadata.create_all(engine)
    from app.services.seed import seed_if_empty
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
