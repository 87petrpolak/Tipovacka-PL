"""Zjištění, jestli je prohlížeč dost široký na "desktopové" rozložení.

Streamlit běží na serveru a nezná šířku okna klienta sám od sebe, proto ji
zjišťujeme přes malý JS dotaz (streamlit_javascript). Výsledek se cachuje
v session_state, aby se po prvním zjištění dál neposílal při každém rerunu.
Uživatel si navíc může zobrazení vynutit ručně (přepínač v sidebaru).
"""
import streamlit as st
from streamlit_javascript import st_javascript

DESKTOP_BREAKPOINT_PX = 900


def is_desktop_view() -> bool:
    override = st.session_state.get("layout_override", "Auto")
    if override == "Mobil":
        return False
    if override == "Počítač":
        return True

    if "viewport_width" not in st.session_state:
        st.session_state.viewport_width = None

    width = st_javascript("window.top.innerWidth", key="_viewport_width_probe")
    if isinstance(width, (int, float)) and width > 0:
        st.session_state.viewport_width = width

    return (st.session_state.viewport_width or 0) >= DESKTOP_BREAKPOINT_PX


def render_layout_override_toggle() -> None:
    st.sidebar.radio(
        "Zobrazení",
        ["Auto", "Mobil", "Počítač"],
        key="layout_override",
        help="Auto rozpozná šířku okna sama. Přepni ručně, pokud ti to nesedí.",
    )
