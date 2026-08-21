"""Shared Streamlit session-state helpers."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db import SessionLocal


def get_db() -> Session:
    """Vrátí novou DB session pro tento běh skriptu.

    Streamlit spouští celý skript znovu při každé interakci i po
    reconnectu (např. po tvrdém přechodu na jinou stránku), takže cachování
    session v st.session_state napříč běhy vede k DetachedInstanceError na
    objektech načtených v předchozím běhu. Nová session na běh je levná a
    bezpečná.
    """
    return SessionLocal()
