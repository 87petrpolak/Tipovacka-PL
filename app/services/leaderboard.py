"""Agregace bodů pro dashboard: celkové skóre a rozpad po jednotlivých položkách."""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.models import Fixture, Participant, Player, Prediction, ScorerNomination


@dataclass
class BreakdownRow:
    participant: str
    gameweek: int
    label: str
    result: str
    points: float
    match_id: int
    match_label: str
    match_time: datetime | None
    kind: int = 0  # 0 = tip na zápas, 1 = nominace střelce — jen pro řazení, nezobrazuje se


def get_totals(db: Session) -> dict[str, float]:
    totals = {p.name: 0.0 for p in db.query(Participant).all()}
    for pred in db.query(Prediction).all():
        totals[pred.participant.name] = totals.get(pred.participant.name, 0.0) + pred.points
    for nom in db.query(ScorerNomination).all():
        totals[nom.participant.name] = totals.get(nom.participant.name, 0.0) + nom.points
    return totals


def get_breakdown_rows(db: Session) -> list[BreakdownRow]:
    """Vrátí řádky seřazené podle skutečného času zápasu (nejnovější nahoře),
    a v rámci jednoho zápasu pohromadě — tipy i střelce."""
    rows: list[BreakdownRow] = []

    predictions = (
        db.query(Prediction)
        .join(Fixture, Prediction.fixture_id == Fixture.id)
        .filter(Fixture.is_finished == True)  # noqa: E712
        .all()
    )
    # Podle zápasu dohledáme kontext (čas výkopu, label) i pro nominace střelců —
    # nominovaný hráč patří k tomu zápasu, který jeho tým odehrál v daném kole.
    fixture_by_team_gw: dict[tuple[int, int], Fixture] = {}

    for pred in predictions:
        fixture = pred.fixture
        label = f"{fixture.home_team.name} {fixture.home_score}:{fixture.away_score} {fixture.away_team.name}"
        fixture_by_team_gw[(fixture.gameweek_id, fixture.home_team_id)] = fixture
        fixture_by_team_gw[(fixture.gameweek_id, fixture.away_team_id)] = fixture
        if pred.points == 10:
            result = "přesný výsledek"
        elif pred.points == 2:
            result = "trefená tendence"
        else:
            result = "netrefeno"
        rows.append(BreakdownRow(
            pred.participant.name, fixture.gameweek.number, label, result, pred.points,
            fixture.id, label, fixture.kickoff_at,
        ))

    nominations = (
        db.query(ScorerNomination)
        .join(Player, ScorerNomination.player_id == Player.id)
        .all()
    )
    for nom in nominations:
        if not nom.played and nom.goals == 0 and nom.assists == 0:
            continue  # hráč nenastoupil — bez dopadu na skóre, nezobrazujeme
        fixture = fixture_by_team_gw.get((nom.gameweek_id, nom.player.team_id))
        match_id = fixture.id if fixture else -nom.gameweek_id  # bez zápasu spadne na konec svého kola
        match_label = (
            f"{fixture.home_team.name} {fixture.home_score}:{fixture.away_score} {fixture.away_team.name}"
            if fixture else f"Kolo {nom.gameweek.number}"
        )
        match_time = fixture.kickoff_at if fixture else None
        player_name = nom.player.name
        if nom.goals > 0:
            pts = 5.0 + (nom.goals - 1) * 2.0
            label = f"{player_name}" + (f" ({nom.goals}x gól)" if nom.goals > 1 else "")
            rows.append(BreakdownRow(nom.participant.name, nom.gameweek.number, label, "gól", pts, match_id, match_label, match_time, kind=1))
        if nom.assists > 0:
            pts = 2.0 + (nom.assists - 1) * 1.0
            label = f"{player_name}" + (f" ({nom.assists}x asistence)" if nom.assists > 1 else "")
            rows.append(BreakdownRow(nom.participant.name, nom.gameweek.number, label, "asistence", pts, match_id, match_label, match_time, kind=1))
        if nom.goals == 0 and nom.assists == 0 and nom.played:
            rows.append(BreakdownRow(nom.participant.name, nom.gameweek.number, player_name, "bez G/A", -2.0, match_id, match_label, match_time, kind=1))

    # Nejnovější zápas nahoře; zápasy bez známého času (staré/chybějící kickoff_at)
    # padnou na konec podle čísla kola. V rámci stejného zápasu nejdřív všechny tipy
    # (podle účastníka), pak všechny nominace střelců (podle účastníka).
    rows.sort(key=lambda r: (
        r.match_time is None,
        -(r.match_time.timestamp() if r.match_time else 0),
        -r.gameweek,
        r.match_label,
        r.kind,
        r.participant,
    ))
    return rows
