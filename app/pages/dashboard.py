import pandas as pd
import streamlit as st

from app.services.data_refresh import refresh_results
from app.services.leaderboard import get_breakdown_rows, get_totals
from app.state import get_db

st.title("⚽ Tipovačka PL 2026/27")

db = get_db()

col_refresh, _ = st.columns([1, 3])
with col_refresh:
    if st.button("🔄 Aktualizovat data z Livesportu", use_container_width=True):
        with st.spinner("Stahuji nejnovější výsledky…"):
            log = refresh_results(db)
        if log.success:
            st.success(f"Hotovo — aktualizováno {log.records_updated} zápasů.")
        else:
            st.error(f"Aktualizace selhala: {log.notes}")
        st.rerun()

st.divider()

totals = get_totals(db)
ranked = sorted(totals.items(), key=lambda kv: -kv[1])

cols = st.columns(len(ranked)) if ranked else []
medals = ["🥇", "🥈", "🥉", "4️⃣"]
for i, (name, pts) in enumerate(ranked):
    with cols[i]:
        st.markdown(
            f"""
            <div style="text-align:center; padding: 1rem 0;">
                <div style="font-size:1.3rem;">{medals[i] if i < len(medals) else ""} {name}</div>
                <div style="font-size:3rem; font-weight:800;">{pts:.0f}</div>
                <div style="color:gray;">bodů</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.divider()
st.subheader("📋 Co se dělo")

rows = get_breakdown_rows(db)
if not rows:
    st.info("Zatím žádné odehrané zápasy — jakmile se odehraje první kolo, zobrazí se tu bodování.")
else:
    df = pd.DataFrame(
        [{"Kolo": r.gameweek, "Účastník": r.participant, "Zápas nebo hráč": r.label,
          "Výsledek": r.result, "Body": r.points} for r in rows]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)
