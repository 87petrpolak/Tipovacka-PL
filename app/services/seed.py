"""Naplní prázdnou DB účastníky, týmy a rozlosováním 2026/27 ze seed JSON."""
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.models import Fixture, Gameweek, Participant, Team

PARTICIPANTS = ["Chajda", "Saša", "Vojta", "Poli"]

_SEED_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "seed" / "fixtures_2026_27.json"


def seed_if_empty(db: Session) -> None:
    _seed_participants(db)
    _seed_teams_and_fixtures(db)


def _seed_participants(db: Session) -> None:
    existing = {p.name for p in db.query(Participant).all()}
    for name in PARTICIPANTS:
        if name not in existing:
            db.add(Participant(name=name))
    db.commit()


def _seed_teams_and_fixtures(db: Session) -> None:
    if db.query(Gameweek).count() > 0:
        return  # už naplněno

    with open(_SEED_PATH, encoding="utf-8") as fh:
        data = json.load(fh)

    teams_by_name = {}
    for name in data["teams"]:
        team = db.query(Team).filter(Team.name == name).first()
        if not team:
            team = Team(name=name)
            db.add(team)
            db.flush()
        teams_by_name[name] = team

    for gw in data["gameweeks"]:
        gameweek = Gameweek(number=gw["number"])
        db.add(gameweek)
        db.flush()
        for fx in gw["fixtures"]:
            db.add(Fixture(
                gameweek_id=gameweek.id,
                home_team_id=teams_by_name[fx["home"]].id,
                away_team_id=teams_by_name[fx["away"]].id,
            ))

    db.commit()
