from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.models import Fixture, Gameweek, Team
from app.services.locking import is_fixture_locked, is_locked


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_gameweek_with_fixtures(db, number: int, kickoffs: list[datetime]) -> Gameweek:
    gw = Gameweek(number=number)
    db.add(gw)
    db.flush()
    for i, ko in enumerate(kickoffs):
        home = Team(name=f"Home{number}_{i}")
        away = Team(name=f"Away{number}_{i}")
        db.add_all([home, away])
        db.flush()
        db.add(Fixture(gameweek_id=gw.id, home_team_id=home.id, away_team_id=away.id, kickoff_at=ko))
    db.commit()
    db.refresh(gw)
    return gw


def test_early_fixture_locks_without_locking_later_ones(db):
    gw = _make_gameweek_with_fixtures(db, 1, [
        datetime.utcnow() - timedelta(minutes=30),  # výkop byl před 30 min -> uzamčeno (lock je hodinu před)
        datetime.utcnow() + timedelta(days=2),       # další zápas kola je ještě daleko -> otevřeno
    ])
    locked_flags = [is_fixture_locked(f) for f in gw.fixtures]
    assert locked_flags == [True, False]


def test_gameweek_is_locked_only_when_every_fixture_locked(db):
    gw = _make_gameweek_with_fixtures(db, 1, [
        datetime.utcnow() - timedelta(minutes=30),
        datetime.utcnow() + timedelta(days=2),
    ])
    assert is_locked(gw) is False  # jeden zápas ještě otevřený

    gw2 = _make_gameweek_with_fixtures(db, 2, [
        datetime.utcnow() - timedelta(minutes=30),
        datetime.utcnow() - timedelta(minutes=5),
    ])
    assert is_locked(gw2) is True  # oba zápasy už uzamčené


def test_fixture_without_kickoff_is_not_locked(db):
    gw = _make_gameweek_with_fixtures(db, 1, [None])
    assert is_fixture_locked(gw.fixtures[0]) is False
