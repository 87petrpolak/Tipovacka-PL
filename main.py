"""Streamlit entrypoint — multi-page app via st.navigation."""
import streamlit as st

from app.db import init_db


@st.cache_resource
def _init_db_once():
    init_db()


_init_db_once()

st.set_page_config(
    page_title="Tipovačka PL 2026/27",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
[data-testid="stMainBlockContainer"] {
    max-width: 1400px;
    margin: 0 auto;
}
@media (max-width: 640px) {
    [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
    [data-testid="stColumn"] {
        width: 100% !important;
        flex: none !important;
        min-width: 100% !important;
    }
}
[data-testid="stDataFrame"] { overflow-x: auto; }

/* Vizuální oddělení sloupců vedle sebe (tipy/nominace po jednotlivých účastnících) */
[data-testid="stColumn"] {
    border-left: 1px solid rgba(250, 250, 250, 0.12);
    padding-left: 1rem !important;
}
[data-testid="stColumn"]:first-child {
    border-left: none;
}

/* Karty zápasů a nominací — jemné podbarvení, ať jde odlišit jedna od druhé */
div[class*="st-key-tipcard"],
div[class*="st-key-nomcard"] {
    background-color: rgba(250, 250, 250, 0.035);
    border-radius: 12px;
    padding: 0.5rem 0.5rem 1rem 0.5rem !important;
    margin-bottom: 0.75rem;
}

.participant-chip {
    display: inline-block;
    width: 100%;
    text-align: center;
    font-weight: 700;
    background-color: rgba(255, 75, 75, 0.15);
    border-radius: 8px;
    padding: 0.2rem 0.4rem;
    margin-bottom: 0.5rem;
}
.participant-chip-lg {
    font-size: 1.1rem;
    padding: 0.4rem 0.6rem;
}
</style>
""", unsafe_allow_html=True)

pages = [
    st.Page("app/pages/dashboard.py", title="Dashboard", icon="🏆"),
    st.Page("app/pages/tipy.py",      title="Zadávání tipů", icon="📝"),
    st.Page("app/pages/pravidla.py",  title="Pravidla", icon="📖"),
]

pg = st.navigation(pages)
pg.run()
