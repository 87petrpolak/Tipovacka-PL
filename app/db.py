import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase


def _normalize_pg_url(url: str) -> str:
    """Vynutí driver psycopg (v3) explicitně — bez toho si SQLAlchemy může
    na nepodporované verzi Pythonu zvolit dialekt, pro který chybí balíček
    (viděno: zkusilo `psycopg`, ale nainstalovaný byl jen psycopg2-binary)."""
    url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _get_db_url() -> str:
    # 1. Streamlit secrets (produkce — Supabase/Postgres)
    try:
        import streamlit as st
        url = st.secrets.get("DATABASE_URL", "")
        if url:
            return _normalize_pg_url(url)
    except Exception:
        pass

    # 2. Env proměnná (lokální vývoj s Postgres)
    url = os.environ.get("DATABASE_URL", "")
    if url:
        return _normalize_pg_url(url)

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
        connect_args={"connect_timeout": 10},
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
    _migrate_additive()
    from app.services.seed import seed_if_empty
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()


def _migrate_additive():
    """Přídavné migrace pro sloupce přidané po prvním nasazení."""
    with engine.connect() as conn:
        if _is_sqlite:
            cols = {row[1] for row in conn.execute(text("PRAGMA table_info(gameweeks)"))}
            if "reminder_sent_at" not in cols:
                conn.execute(text("ALTER TABLE gameweeks ADD COLUMN reminder_sent_at DATETIME"))
                conn.commit()
        else:
            conn.execute(text("ALTER TABLE gameweeks ADD COLUMN IF NOT EXISTS reminder_sent_at TIMESTAMP"))
            conn.commit()
