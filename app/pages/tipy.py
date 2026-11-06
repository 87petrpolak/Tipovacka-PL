import streamlit as st

from app.models.models import Gameweek, Participant, Player, Prediction, ScorerNomination, Team
from app.services.data_refresh import current_gameweek, ensure_squad
from app.services.scoring import compute_match_points
from app.services.locking import deadline as gw_deadline
from app.services.locking import first_kickoff, fixture_deadline, is_fixture_locked
from app.state import get_db
from app.utils.responsive import is_desktop_view, render_layout_override_toggle
from app.utils.time_local import to_prague_str

NO_PLAYER = "— žádný —"

st.title("📝 Zadávání tipů")

db = get_db()
render_layout_override_toggle()
_desktop = is_desktop_view()

participants = db.query(Participant).order_by(Participant.name).all()
gameweeks = db.query(Gameweek).order_by(Gameweek.number).all()
if not participants or not gameweeks:
    st.warning("Chybí účastníci nebo rozlosování.")
    db.close()
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

fixtures = gameweek.fixtures
teams = db.query(Team).order_by(Team.name).all()
team_names = [t.name for t in teams]

# Zápasy se zamykají postupně, každý hodinu před svým vlastním výkopem —
# ne všechny najednou podle prvního zápasu kola.
locked_fixture_ids = {f.id for f in fixtures if is_fixture_locked(f)}
locked_team_ids = {
    team_id for f in fixtures if f.id in locked_fixture_ids for team_id in (f.home_team_id, f.away_team_id)
}
all_locked = bool(fixtures) and len(locked_fixture_ids) == len(fixtures)
any_locked = bool(locked_fixture_ids)

_first_ko = first_kickoff(gameweek)
_dl = gw_deadline(gameweek)
if all_locked:
    st.warning("🔒 Všechny zápasy tohoto kola už začaly (nebo brzy začnou) — tipy ani nominace už nejde upravovat.")
elif any_locked:
    st.info("🔒 Část zápasů tohoto kola je už uzamčená (hodinu před výkopem) — na zbývající zápasy pořád jde tipovat.")
elif _dl:
    st.caption(f"⏳ První uzávěrka v tomto kole: {to_prague_str(_dl)}. Každý zápas se zamyká zvlášť, hodinu před svým výkopem.")

st.divider()


def save_predictions(
    tip_inputs: dict[tuple[int, int], tuple[int, int]], existing: dict[tuple[int, int], Prediction]
) -> list[str]:
    """Uloží tipy na zápasy, které ještě nejsou uzamčené. Vrátí popisky zápasů, které se
    mezitím (mezi načtením stránky a odesláním) uzamkly a tip se na ně neuložil."""
    skipped = []
    for (participant_id, fixture_id), (h, a) in tip_inputs.items():
        fixture = next(f for f in fixtures if f.id == fixture_id)
        if fixture.id in locked_fixture_ids:
            skipped.append(f"{fixture.home_team.name} – {fixture.away_team.name}")
            continue
        pred = existing.get((participant_id, fixture_id))
        if pred is None:
            pred = Prediction(participant_id=participant_id, fixture_id=fixture_id, tip_home=h, tip_away=a)
            db.add(pred)
        else:
            pred.tip_home, pred.tip_away = h, a
        pred.points = compute_match_points(fixture.home_score, fixture.away_score, h, a)
    db.commit()
    return list(dict.fromkeys(skipped))


def save_nominations(participant_id: int, chosen_player_ids: list[int]) -> tuple[bool, list[str]]:
    """Uloží nominace. Nová nominace na hráče, jehož zápas je už uzamčený, se přeskočí
    (vrátí jména přeskočených hráčů); existující (i uzamčená) nominace zůstává beze změny."""
    if len(chosen_player_ids) != len(set(chosen_player_ids)):
        return False, []

    current = db.query(ScorerNomination).filter(
        ScorerNomination.participant_id == participant_id,
        ScorerNomination.gameweek_id == gameweek.id,
    ).all()
    current_by_player = {n.player_id: n for n in current}

    skipped_names = []
    valid_ids = []
    for player_id in chosen_player_ids:
        if player_id in current_by_player:
            valid_ids.append(player_id)
            continue
        player = db.get(Player, player_id)
        if player and player.team_id in locked_team_ids:
            skipped_names.append(player.name)
            continue
        valid_ids.append(player_id)

    for n in current:
        if n.player_id not in valid_ids:
            db.delete(n)
    for player_id in valid_ids:
        if player_id not in current_by_player:
            db.add(ScorerNomination(participant_id=participant_id, gameweek_id=gameweek.id, player_id=player_id))
    db.commit()
    return True, skipped_names


def save_all(
    tip_inputs: dict[tuple[int, int], tuple[int, int]],
    existing_preds: dict[tuple[int, int], Prediction],
    chosen_by_participant: dict[int, list[int]],
) -> None:
    """Uloží tipy i nominace jedním tahem a zprávy o výsledku uloží do session_state
    (po st.rerun() by se jinak ztratily)."""
    flash: list[tuple[str, str]] = []

    skipped_tips = save_predictions(tip_inputs, existing_preds)
    if skipped_tips:
        flash.append(("warning", f"Tyhle zápasy mezitím začaly, tipy na ně se neuložily: {', '.join(skipped_tips)}."))

    dup_names, skipped_players = [], []
    names = {p.id: p.name for p in participants}
    for participant_id, chosen in chosen_by_participant.items():
        ok, skipped = save_nominations(participant_id, chosen)
        if not ok:
            dup_names.append(names[participant_id])
        skipped_players.extend(skipped)
    if skipped_players:
        flash.append((
            "warning",
            f"Tihle hráči mají zápas, co už začal, nominace na ně se neuložila: {', '.join(dict.fromkeys(skipped_players))}.",
        ))
    if dup_names:
        flash.append((
            "error",
            f"Nominace se neuložily ({', '.join(dup_names)}): stejného hráče nelze nominovat dvakrát. Tipy na zápasy jsou uložené.",
        ))
    if not flash:
        flash.append(("success", "Vše uloženo — tipy i nominace."))
    st.session_state["tipy_flash"] = flash


for _kind, _text in st.session_state.pop("tipy_flash", []):
    getattr(st, _kind)(_text)


# Jeden vyhledávací výběr hráče ("Tým · Jméno") místo dvojice Tým → Hráč: v selectboxu jde psát
# jméno hráče i název týmu ("Chelsea" vyfiltruje celý tým), a protože na sobě výběry nezávisí,
# můžou být v jednom formuláři s tipy (= jedno tlačítko Uložit).
_team_name_by_id = {t.id: t.name for t in teams}
_active_team_ids = {
    tid for (tid,) in db.query(Player.team_id).filter(Player.is_active == True).distinct()  # noqa: E712
}
for _t in teams:
    if _t.id not in _active_team_ids:
        ensure_squad(db, _t)  # tým bez soupisky v DB — stáhne se při prvním otevření

_all_players = sorted(
    db.query(Player).filter(Player.is_active == True, Player.team_id.isnot(None)).all(),  # noqa: E712
    key=lambda p: (_team_name_by_id.get(p.team_id, ""), p.name),
)
_selectable_ids = [p.id for p in _all_players if p.team_id not in locked_team_ids]
_label_by_id: dict[int, str] = {p.id: f"{_team_name_by_id.get(p.team_id, '?')} · {p.name}" for p in _all_players}


def _player_label(player_id: int | None) -> str:
    if player_id is None:
        return NO_PLAYER
    if player_id not in _label_by_id:
        p = db.get(Player, player_id)
        _label_by_id[player_id] = f"{_team_name_by_id.get(p.team_id, '?')} · {p.name}" if p else "?"
    return _label_by_id[player_id]


def nomination_slot(key_prefix: str, nom: ScorerNomination | None, label: str = "Hráč") -> int | None:
    """Vykreslí vyhledávací výběr hráče, vrátí zvolené player_id (nebo None).

    Hráči týmů s už uzamčeným zápasem se nově vybrat nedají (nejsou v nabídce); pokud je takový
    hráč už nominovaný, zůstane vidět, jen needitovatelný."""
    nom_player_id = nom.player_id if nom else None
    locked = nom.player.team_id in locked_team_ids if nom else False

    options: list[int | None] = [None] + list(_selectable_ids)
    if nom_player_id is not None and nom_player_id not in options:
        options.append(nom_player_id)  # uzamčený nebo mezitím ze soupisky odešlý hráč

    return st.selectbox(
        label, options,
        index=options.index(nom_player_id) if nom_player_id in options else 0,
        format_func=_player_label,
        key=f"{key_prefix}_gw{gameweek.id}_pick",
        disabled=locked,
        help="Piš jméno hráče nebo název týmu (např. „Chelsea“) a nabídka se vyfiltruje.",
    )


NOMINATION_CAPTION = (
    "Gól 5 bodů (další +2), asistence 2 body (další +1). "
    "Hráč, který hrál a nedal gól ani asistenci, dostane -2 body. "
    "Do pole piš jméno hráče nebo název týmu."
)


# ----------------------------------------------------------------------
# Mobil: jeden účastník po druhém
# ----------------------------------------------------------------------
def render_mobile() -> None:
    participant_name = st.selectbox(
        "Kdo tipuje?", [p.name for p in participants], key="tipy_participant",
    )
    participant = next(p for p in participants if p.name == participant_name)

    existing_preds = {
        (participant.id, p.fixture_id): p
        for p in db.query(Prediction).filter(
            Prediction.participant_id == participant.id,
            Prediction.fixture_id.in_([f.id for f in fixtures]),
        ).all()
    }
    existing_noms = db.query(ScorerNomination).filter(
        ScorerNomination.participant_id == participant.id,
        ScorerNomination.gameweek_id == gameweek.id,
    ).all()
    existing_noms_by_slot = existing_noms + [None] * (3 - len(existing_noms))

    with st.form("tips_form_mobile"):
        st.subheader("⚽ Tipy na výsledky")
        tip_inputs = {}
        for fixture in fixtures:
            fixture_locked = fixture.id in locked_fixture_ids
            existing = existing_preds.get((participant.id, fixture.id))
            st.markdown(f"**{fixture.home_team.name}** – **{fixture.away_team.name}**")
            c1, c2 = st.columns(2)
            with c1:
                h = st.number_input(
                    f"⚽ {fixture.home_team.name}", min_value=0, max_value=15, step=1,
                    value=existing.tip_home if existing else 0,
                    key=f"home_{participant.id}_{fixture.id}",
                    disabled=fixture_locked,
                )
            with c2:
                a = st.number_input(
                    f"⚽ {fixture.away_team.name}", min_value=0, max_value=15, step=1,
                    value=existing.tip_away if existing else 0,
                    key=f"away_{participant.id}_{fixture.id}",
                    disabled=fixture_locked,
                )
            tip_inputs[(participant.id, fixture.id)] = (h, a)
            if fixture.is_finished:
                st.caption(f"Výsledek: {fixture.home_score}:{fixture.away_score}")
            elif fixture_locked:
                st.caption("🔒 Uzamčeno — zápas už začal nebo brzy začne.")
            else:
                fdl = fixture_deadline(fixture)
                if fdl:
                    st.caption(f"⏳ Uzávěrka: {to_prague_str(fdl)}")
            st.divider()

        st.subheader("🎯 Nominace střelců (0–3 hráči)")
        st.caption(NOMINATION_CAPTION)
        chosen_player_ids = []
        for i in range(3):
            pid = nomination_slot(f"mob_{participant.id}_{i}", existing_noms_by_slot[i], label=f"Hráč {i + 1}")
            if pid is not None:
                chosen_player_ids.append(pid)

        if st.form_submit_button("💾 Uložit vše", type="primary", use_container_width=True):
            save_all(tip_inputs, existing_preds, {participant.id: chosen_player_ids})
            st.rerun()


# ----------------------------------------------------------------------
# Počítač: všichni účastníci najednou, jedno kolo na jedné obrazovce
# ----------------------------------------------------------------------
def render_desktop() -> None:
    existing_preds = {
        (p.participant_id, p.fixture_id): p
        for p in db.query(Prediction).filter(Prediction.fixture_id.in_([f.id for f in fixtures])).all()
    }
    existing_noms_by_participant: dict[int, list] = {p.id: [] for p in participants}
    for n in db.query(ScorerNomination).filter(ScorerNomination.gameweek_id == gameweek.id).all():
        existing_noms_by_participant[n.participant_id].append(n)

    with st.form("tips_form_desktop"):
        st.subheader("⚽ Tipy na výsledky — všichni najednou")
        tip_inputs = {}
        for fixture in fixtures:
            fixture_locked = fixture.id in locked_fixture_ids
            with st.container(border=True, key=f"tipcard_{fixture.id}"):
                st.markdown(f"**{fixture.home_team.name}** – **{fixture.away_team.name}**")
                if fixture.is_finished:
                    st.caption(f"Výsledek: {fixture.home_score}:{fixture.away_score}")
                elif fixture_locked:
                    st.caption("🔒 Uzamčeno — zápas už začal nebo brzy začne.")
                else:
                    fdl = fixture_deadline(fixture)
                    if fdl:
                        st.caption(f"⏳ Uzávěrka: {to_prague_str(fdl)}")

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
                            disabled=fixture_locked,
                        )
                        a = sub2.number_input(
                            fixture.away_team.name, min_value=0, max_value=15, step=1,
                            value=existing.tip_away if existing else 0,
                            key=f"desk_away_{participant.id}_{fixture.id}",
                            label_visibility="collapsed",
                            disabled=fixture_locked,
                        )
                        tip_inputs[(participant.id, fixture.id)] = (h, a)

        st.divider()
        st.subheader("🎯 Nominace střelců — všichni najednou")
        st.caption(NOMINATION_CAPTION)

        nom_cols = st.columns(len(participants))
        chosen_by_participant: dict[int, list[int]] = {}
        for i, participant in enumerate(participants):
            chosen: list[int] = []
            with nom_cols[i]:
                with st.container(border=True, key=f"nomcard_{participant.id}"):
                    st.markdown(
                        f"<div class='participant-chip participant-chip-lg'>{participant.name}</div>",
                        unsafe_allow_html=True,
                    )
                    slots = existing_noms_by_participant[participant.id] + [None] * 3
                    for slot_idx in range(3):
                        pid = nomination_slot(
                            f"desk_{participant.id}_{slot_idx}", slots[slot_idx], label=f"Hráč {slot_idx + 1}",
                        )
                        if pid is not None:
                            chosen.append(pid)
            chosen_by_participant[participant.id] = chosen

        if st.form_submit_button("💾 Uložit vše", type="primary", use_container_width=True):
            save_all(tip_inputs, existing_preds, chosen_by_participant)
            st.rerun()


if _desktop:
    render_desktop()
else:
    render_mobile()

db.close()
