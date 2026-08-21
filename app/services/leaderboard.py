"""Agregace bodů pro dashboard: celkové skóre a rozpad po jednotlivých položkách."""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.models import Fixture, Participant, Player, Prediction, ScorerNomination


@dataclass
class BreakdownRow:
    participant: str
    gameweek: int
    label: str
    result: str
    points: float


def get_totals(db: Session) -> dict[str, float]:
    totals = {p.name: 0.0 for p in db.query(Participant).all()}
    for pred in db.query(Prediction).all():
        totals[pred.participant.name] = totals.get(pred.participant.name, 0.0) + pred.points
    for nom in db.query(ScorerNomination).all():
        totals[nom.participant.name] = totals.get(nom.participant.name, 0.0) + nom.points
    return totals


def get_breakdown_rows(db: Session) -> list[BreakdownRow]:
    rows: list[BreakdownRow] = []

    predictions = (
        db.query(Prediction)
        .join(Fixture, Prediction.fixture_id == Fixture.id)
        .filter(Fixture.is_finished == True)  # noqa: E712
        .all()
    )
    for pred in predictions:
        fixture = pred.fixture
        label = f"{fixture.home_team.name} {fixture.home_score}:{fixture.away_score} {fixture.away_team.name}"
        if pred.points == 10:
            result = "přesný výsledek"
        elif pred.points == 2:
            result = "trefená tendence"
        else:
            result = "netrefeno"
        rows.append(BreakdownRow(pred.participant.name, fixture.gameweek.number, label, result, pred.points))

    nominations = (
        db.query(ScorerNomination)
        .join(Player, ScorerNomination.player_id == Player.id)
        .all()
    )
    for nom in nominations:
        if not nom.played and nom.goals == 0 and nom.assists == 0:
            continue  # hráč nenastoupil — bez dopadu na skóre, nezobrazujeme
        player_name = nom.player.name
        if nom.goals > 0:
            pts = 5.0 + (nom.goals - 1) * 2.0
            label = f"{player_name}" + (f" ({nom.goals}x gól)" if nom.goals > 1 else "")
            rows.append(BreakdownRow(nom.participant.name, nom.gameweek.number, label, "gól", pts))
        if nom.assists > 0:
            pts = 2.0 + (nom.assists - 1) * 1.0
            label = f"{player_name}" + (f" ({nom.assists}x asistence)" if nom.assists > 1 else "")
            rows.append(BreakdownRow(nom.participant.name, nom.gameweek.number, label, "asistence", pts))
        if nom.goals == 0 and nom.assists == 0 and nom.played:
            rows.append(BreakdownRow(nom.participant.name, nom.gameweek.number, player_name, "bez G/A", -2.0))

    rows.sort(key=lambda r: (-r.gameweek, r.participant))
    return rows
