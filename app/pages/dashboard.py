import pandas as pd
import streamlit as st  # redeploy nudge — Streamlit Cloud nezvedlo commit cf24f68 samo

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

# (popisek, barva pozadí, barva textu) pro každý typ výsledku — řídí se
# podle r.result, interní klíče (viz leaderboard.py) zůstávají beze změny.
# Barvy jako v Excelu (Good/Neutral/Bad): světlé pozadí, tmavší text stejného
# odstínu.
RESULT_STYLE: dict[str, tuple[str, str, str]] = {
    "přesný výsledek": ("Přesný výsledek", "#C6EFCE", "#006100"),
    "trefená tendence": ("Trefená tendence", "#FFEB9C", "#9C6500"),
    "netrefeno": ("Netrefeno", "#FFC7CE", "#9C0006"),
    "gól": ("Gól", "#C6EFCE", "#006100"),
    "asistence": ("Asistence", "#C6EFCE", "#006100"),
    "bez G/A": ("Bez G/A", "#FFC7CE", "#9C0006"),
}

rows = get_breakdown_rows(db)
if not rows:
    st.info("Zatím žádné odehrané zápasy — jakmile se odehraje první kolo, zobrazí se tu bodování.")
else:
    vysledky = []
    barvy = []
    for r in rows:
        label, bg, fg = RESULT_STYLE.get(r.result, (r.result, "#444444", "white"))
        vysledky.append(f"{r.tip} - {label}" if r.tip else label)
        barvy.append((bg, fg))

    df = pd.DataFrame(
        [{"Kolo": r.gameweek, "Účastník": r.participant, "Zápas nebo hráč - výsledek": r.label,
          "Výsledek": vysledek, "Body": r.points} for r, vysledek in zip(rows, vysledky)]
    )

    def _style_vysledek(_col: pd.Series) -> list[str]:
        return [f"background-color: {bg}; color: {fg};" for bg, fg in barvy]

    styled = df.style.apply(_style_vysledek, subset=["Výsledek"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

db.close()
