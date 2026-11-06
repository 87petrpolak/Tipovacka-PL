import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import models as m
from app.services.data_refresh import sync_squad


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _team(db, name):
    t = m.Team(name=name)
    db.add(t)
    db.commit()
    return t


def _p(ext, name="X", pos="FWD"):
    return {"external_id": ext, "name": name, "position": pos}


def test_adds_new_and_deactivates_departed(db):
    t = _team(db, "Chelsea")
    sync_squad(db, t, [_p("a", "Alpha"), _p("b", "Beta")])
    stats = sync_squad(db, t, [_p("a", "Alpha"), _p("c", "Gamma")])
    assert stats["added"] == 1 and stats["deactivated"] == 1
    by = {p.external_id: p.is_active for p in db.query(m.Player).all()}
    assert by == {"a": True, "b": False, "c": True}


def test_empty_scrape_changes_nothing(db):
    t = _team(db, "Chelsea")
    sync_squad(db, t, [_p("a")])
    assert sync_squad(db, t, []) == {"added": 0, "moved": 0, "deactivated": 0, "reactivated": 0}
    assert db.query(m.Player).one().is_active is True


def test_transfer_moves_player_without_nominations(db):
    a, b = _team(db, "Chelsea"), _team(db, "Spurs")
    sync_squad(db, a, [_p("a", "Alpha")])
    sync_squad(db, b, [_p("a", "Alpha")])
    sync_squad(db, a, [_p("z", "Zed")])
    p = db.query(m.Player).filter_by(external_id="a").one()
    assert p.team_id == b.id and p.is_active


def test_transfer_keeps_player_with_nominations_on_old_team(db):
    a, b = _team(db, "Chelsea"), _team(db, "Spurs")
    sync_squad(db, a, [_p("a", "Alpha")])
    player = db.query(m.Player).one()
    part = m.Participant(name="P")
    gw = m.Gameweek(number=1)
    db.add_all([part, gw])
    db.commit()
    db.add(m.ScorerNomination(participant_id=part.id, gameweek_id=gw.id, player_id=player.id))
    db.commit()
    sync_squad(db, b, [_p("a", "Alpha")])
    sync_squad(db, a, [_p("z", "Zed")])
    db.refresh(player)
    assert player.team_id == a.id and player.is_active is False


def test_returning_player_is_reactivated(db):
    t = _team(db, "Chelsea")
    sync_squad(db, t, [_p("a", "Alpha")])
    sync_squad(db, t, [_p("b", "Beta")])
    stats = sync_squad(db, t, [_p("a", "Alpha"), _p("b", "Beta")])
    assert stats["reactivated"] == 1
