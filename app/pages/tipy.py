import streamlit as st

from app.models.models import Gameweek, Participant, Prediction, ScorerNomination, Team
from app.services.data_refresh import current_gameweek, ensure_squad
from app.services.scoring import compute_match_points
from app.services.locking import deadline as gw_deadline
from app.services.locking import first_kickoff, is_locked
from app.state import get_db
from app.utils.responsive import is_desktop_view, render_layout_override_toggle
from app.utils.time_local import to_prague_str

NO_TEAM = "— žádný —"
NO_PLAYER = "— žádný —"

st.title("📝 Zadávání tipů")

db = get_db()
render_layout_override_toggle()
_desktop = is_desktop_view()

participants = db.query(Participant).order_by(Participant.name).all()
gameweeks = db.query(Gameweek).order_by(Gameweek.number).all()
if not participants or not gameweeks:
    st.warning("Chybí účastníci nebo rozlosování.")
    st.stop()

default_gw = current_gameweek(db)
gw_numbers = [g.number for g in gameweeks]
default_gw_number = default_gw.number if default_gw else gw_numbers[0]

# Widget dostává jen číslo kola, ne živý ORM objekt — Streamlit si hodnotu
# widgetu drží ve vlastním stavu napříč rerendery (přežije i tvrdý reload
# stránky) a vracel by tak objekt ze staré, už zavřené DB session. Skutečný
# ORM objekt si proto vždy načteme čerstvě podle klíče (čísla kola).
gw_number = st.selectbox(
    "Kolo", gw_numbers,
    index=gw_numbers.index(default_gw_number),
    format_func=lambda n: f"Kolo {n}" + (" (aktuální)" if n == default_gw_number else ""),
    key="tipy_gameweek",
)
gameweek = db.query(Gameweek).filter(Gameweek.number == gw_number).one()
if gw_number == default_gw_number:
    st.caption("Toto je nejbližší nadcházející kolo.")

locked = is_locked(gameweek)
_first_ko = first_kickoff(gameweek)
_dl = gw_deadline(gameweek)
if locked:
    st.warning(f"🔒 Toto kolo je uzamčené — první zápas začíná {to_prague_str(_first_ko)}. Tipy a nominace už nejde upravovat.")
elif _dl:
    st.caption(f"⏳ Uzávěrka tipů pro toto kolo: {to_prague_str(_dl)} (hodinu před výkopem prvního zápasu).")

fixtures = gameweek.fixtures
teams = db.query(Team).order_by(Team.name).all()
team_names = [t.name for t in teams]

st.divider()


def save_predictions(tip_inputs: dict[tuple[int, int], tuple[int, int]], existing: dict[tuple[int, int], Prediction]) -> None:
    if locked:  # bezpečnostní pojistka, kdyby uzávěrka nastala mezi načtením stránky a odesláním
        return
    for (participant_id, fixture_id), (h, a) in tip_inputs.items():
        fixture = next(f for f in fixtures if f.id == fixture_id)
        pred = existing.get((participant_id, fixture_id))
        if pred is None:
            pred = Prediction(participant_id=participant_id, fixture_id=fixture_id, tip_home=h, tip_away=a)
            db.add(pred)
        else:
            pred.tip_home, pred.tip_away = h, a
        pred.points = compute_match_points(fixture.home_score, fixture.away_score, h, a)
    db.commit()


def save_nominations(participant_id: int, chosen_player_ids: list[int]) -> bool:
    if locked:
        return False
    if len(chosen_player_ids) != len(set(chosen_player_ids)):
        return False
    current = db.query(ScorerNomination).filter(
        ScorerNomination.participant_id == participant_id,
        ScorerNomination.gameweek_id == gameweek.id,
    ).all()
    current_by_player = {n.player_id: n for n in current}
    for n in current:
        if n.player_id not in chosen_player_ids:
            db.delete(n)
    for player_id in chosen_player_ids:
        if player_id not in current_by_player:
            db.add(ScorerNomination(participant_id=participant_id, gameweek_id=gameweek.id, player_id=player_id))
    db.commit()
    return True


def nomination_slot(key_prefix: str, nom: ScorerNomination | None, label_team: str = "Tým", label_player: str = "Hráč") -> int | None:
    """Vykreslí pár Tým/Hráč selectboxů, vrátí zvolené player_id (nebo None)."""
    default_team_name = nom.player.team.name if (nom and nom.player.team) else NO_TEAM
    team_options = [NO_TEAM] + team_names
    team_name = st.selectbox(
        label_team, team_options,
        index=team_options.index(default_team_name) if default_team_name in team_options else 0,
        key=f"{key_prefix}_team",
        disabled=locked,
    )
    if team_name == NO_TEAM:
        st.selectbox(label_player, [NO_PLAYER], key=f"{key_prefix}_player_disabled", disabled=True)
        return None

    team = next(t for t in teams if t.name == team_name)
    squad = sorted(ensure_squad(db, team), key=lambda p: p.name)
    squad_names = [p.name for p in squad]
    default_player_name = nom.player.name if (nom and nom.player.team_id == team.id) else NO_PLAYER
    player_options = [NO_PLAYER] + squad_names
    player_name = st.selectbox(
        label_player, player_options,
        index=player_options.index(default_player_name) if default_player_name in player_options else 0,
        key=f"{key_prefix}_player",
        disabled=locked,
    )
    if player_name == NO_PLAYER:
        return None
    return next(p.id for p in squad if p.name == player_name)


# ----------------------------------------------------------------------
# Mobil: jeden účastník po druhém
# ----------------------------------------------------------------------
def render_mobile() -> None:
    participant_name = st.selectbox(
        "Kdo tipuje?", [p.name for p in participants], key="tipy_participant",
    )
    participant = next(p for p in participants if p.name == participant_name)

    st.subheader("⚽ Tipy na výsledky")
    existing_preds = {
        (participant.id, p.fixture_id): p
        for p in db.query(Prediction).filter(
            Prediction.participant_id == participant.id,
            Prediction.fixture_id.in_([f.id for f in fixtures]),
        ).all()
    }

    with st.form("tips_form_mobile"):
        tip_inputs = {}
        for fixture in fixtures:
            existing = existing_preds.get((participant.id, fixture.id))
            st.markdown(f"**{fixture.home_team.name}** – **{fixture.away_team.name}**")
            c1, c2 = st.columns(2)
            with c1:
                h = st.number_input(
                    f"⚽ {fixture.home_team.name}", min_value=0, max_value=15, step=1,
                    value=existing.tip_home if existing else 0,
                    key=f"home_{participant.id}_{fixture.id}",
                    disabled=locked,
                )
            with c2:
                a = st.number_input(
                    f"⚽ {fixture.away_team.name}", min_value=0, max_value=15, step=1,
                    value=existing.tip_away if existing else 0,
                    key=f"away_{participant.id}_{fixture.id}",
                    disabled=locked,
                )
            tip_inputs[(participant.id, fixture.id)] = (h, a)
            if fixture.is_finished:
                st.caption(f"Výsledek: {fixture.home_score}:{fixture.away_score}")
            st.divider()

        if st.form_submit_button("💾 Uložit tipy na zápasy", type="primary", disabled=locked):
            if locked:
                st.error("Kolo je už uzamčené, tipy nešly uložit.")
            else:
                save_predictions(tip_inputs, existing_preds)
                st.success("Tipy uloženy.")
                st.rerun()

    st.divider()
    st.subheader("🎯 Nominace střelců (0–3 hráči)")
    st.caption(
        "Gól 5 bodů (další +2), asistence 2 body (další +1). "
        "Hráč, který hrál a nedal gól ani asistenci, dostane -2 body."
    )

    existing_noms = db.query(ScorerNomination).filter(
        ScorerNomination.participant_id == participant.id,
        ScorerNomination.gameweek_id == gameweek.id,
    ).all()
    existing_noms_by_slot = existing_noms + [None] * (3 - len(existing_noms))

    chosen_player_ids = []
    for i in range(3):
        st.markdown(f"**Hráč {i + 1}**")
        pid = nomination_slot(f"mob_{participant.id}_{i}", existing_noms_by_slot[i])
        if pid is not None:
            chosen_player_ids.append(pid)

    if st.button("💾 Uložit nominace střelců", type="primary", disabled=locked):
        if save_nominations(participant.id, chosen_player_ids):
            st.success("Nominace uloženy.")
            st.rerun()
        else:
            st.error("Stejného hráče nelze nominovat dvakrát." if not locked else "Kolo je už uzamčené.")


# ----------------------------------------------------------------------
# Počítač: všichni účastníci najednou, jedno kolo na jedné obrazovce
# ----------------------------------------------------------------------
def render_desktop() -> None:
    st.subheader("⚽ Tipy na výsledky — všichni najednou")

    existing_preds = {
        (p.participant_id, p.fixture_id): p
        for p in db.query(Prediction).filter(Prediction.fixture_id.in_([f.id for f in fixtures])).all()
    }

    with st.form("tips_form_desktop"):
        tip_inputs = {}
        for fixture in fixtures:
            with st.container(border=True, key=f"tipcard_{fixture.id}"):
                st.markdown(f"**{fixture.home_team.name}** – **{fixture.away_team.name}**")
                if fixture.is_finished:
                    st.caption(f"Výsledek: {fixture.home_score}:{fixture.away_score}")

                p_cols = st.columns(len(participants))
                for i, participant in enumerate(participants):
                    with p_cols[i]:
                        st.markdown(
                            f"<div class='participant-chip'>{participant.name}</div>",
                            unsafe_allow_html=True,
                        )
                        existing = existing_preds.get((participant.id, fixture.id))
                        sub1, sub2 = st.columns(2)
                        h = sub1.number_input(
                            fixture.home_team.name, min_value=0, max_value=15, step=1,
                            value=existing.tip_home if existing else 0,
                            key=f"desk_home_{participant.id}_{fixture.id}",
                            label_visibility="collapsed",
                            disabled=locked,
                        )
                        a = sub2.number_input(
                            fixture.away_team.name, min_value=0, max_value=15, step=1,
                            value=existing.tip_away if existing else 0,
                            key=f"desk_away_{participant.id}_{fixture.id}",
                            label_visibility="collapsed",
                            disabled=locked,
                        )
                        tip_inputs[(participant.id, fixture.id)] = (h, a)

        if st.form_submit_button("💾 Uložit tipy všech", type="primary", disabled=locked):
            if locked:
                st.error("Kolo je už uzamčené, tipy nešly uložit.")
            else:
                save_predictions(tip_inputs, existing_preds)
                st.success("Tipy uloženy.")
                st.rerun()

    st.divider()
    st.subheader("🎯 Nominace střelců — všichni najednou")
    st.caption(
        "Gól 5 bodů (další +2), asistence 2 body (další +1). "
        "Hráč, který hrál a nedal gól ani asistenci, dostane -2 body."
    )

    existing_noms_by_participant: dict[int, list] = {p.id: [] for p in participants}
    for n in db.query(ScorerNomination).filter(ScorerNomination.gameweek_id == gameweek.id).all():
        existing_noms_by_participant[n.participant_id].append(n)

    nom_cols = st.columns(len(participants))
    chosen_by_participant: dict[int, list[int]] = {}
    for i, participant in enumerate(participants):
        with nom_cols[i]:
            with st.container(border=True, key=f"nomcard_{participant.id}"):
                st.markdown(f"<div class='participant-chip participant-chip-lg'>{participant.name}</div>", unsafe_allow_html=True)
                st.markdown("")
                slots = existing_noms_by_participant[participant.id] + [None] * 3
                chosen: list[int] = []
                for slot_idx in range(3):
                    pid = nomination_slot(
                        f"desk_{participant.id}_{slot_idx}", slots[slot_idx],
                        label_team=f"Tým {slot_idx + 1}", label_player=f"Hráč {slot_idx + 1}",
                    )
                    if pid is not None:
                        chosen.append(pid)
                    st.markdown("")
            chosen_by_participant[participant.id] = chosen

    if st.button("💾 Uložit nominace všech", type="primary", disabled=locked):
        errors = []
        for participant in participants:
            if not save_nominations(participant.id, chosen_by_participant[participant.id]):
                errors.append(participant.name)
        if errors and not locked:
            st.error(f"Stejného hráče nelze nominovat dvakrát ({', '.join(errors)}).")
        elif locked:
            st.error("Kolo je už uzamčené, nominace nešly uložit.")
        else:
            st.success("Nominace uloženy.")
            st.rerun()


if _desktop:
    render_desktop()
else:
    render_mobile()
