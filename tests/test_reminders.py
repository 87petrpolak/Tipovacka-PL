from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.models import Fixture, Gameweek, Team
from app.services.reminders import mark_reminder_sent, reminder_due


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_gameweek(db, number, kickoff):
    home = Team(name=f"Home{number}")
    away = Team(name=f"Away{number}")
    db.add_all([home, away])
    db.flush()
    gw = Gameweek(number=number)
    db.add(gw)
    db.flush()
    db.add(Fixture(gameweek_id=gw.id, home_team_id=home.id, away_team_id=away.id, kickoff_at=kickoff))
    db.commit()
    return gw


def test_not_due_when_kickoff_far_away(db):
    _make_gameweek(db, 1, datetime.utcnow() + timedelta(days=3))
    assert reminder_due(db) is None


def test_due_within_12h_window(db):
    _make_gameweek(db, 1, datetime.utcnow() + timedelta(hours=6))
    gw = reminder_due(db)
    assert gw is not None
    assert gw.number == 1


def test_not_due_after_kickoff_passed(db):
    _make_gameweek(db, 1, datetime.utcnow() - timedelta(hours=1))
    assert reminder_due(db) is None


def test_not_due_once_already_sent(db):
    _make_gameweek(db, 1, datetime.utcnow() + timedelta(hours=6))
    mark_reminder_sent(db, 1)
    assert reminder_due(db) is None
