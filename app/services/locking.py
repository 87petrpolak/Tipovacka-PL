"""Uzamykání zápasů — každý zápas jde tipovat/nominovat jen do hodiny před jeho vlastním výkopem.

Zápasy stejného kola se zamykají postupně (podle svého výkopu), ne všechny najednou —
dřív začínající zápas uzamčený nebrání tipování na pozdější zápasy toho kola."""
from datetime import datetime, timedelta

from app.models.models import Fixture, Gameweek

LOCK_BEFORE_KICKOFF = timedelta(hours=1)


def first_kickoff(gameweek: Gameweek) -> datetime | None:
    kickoffs = [f.kickoff_at for f in gameweek.fixtures if f.kickoff_at]
    return min(kickoffs) if kickoffs else None


def deadline(gameweek: Gameweek) -> datetime | None:
    """Uzávěrka prvního zápasu kola — jen informativní (např. pro reminder e-mail)."""
    fk = first_kickoff(gameweek)
    return fk - LOCK_BEFORE_KICKOFF if fk else None


def is_locked(gameweek: Gameweek) -> bool:
    """Celé kolo uzamčené = i poslední zápas kola už se zamkl."""
    kickoffs = [f.kickoff_at for f in gameweek.fixtures if f.kickoff_at]
    if not kickoffs:
        return False
    return all(datetime.utcnow() >= ko - LOCK_BEFORE_KICKOFF for ko in kickoffs)


def fixture_deadline(fixture: Fixture) -> datetime | None:
    return fixture.kickoff_at - LOCK_BEFORE_KICKOFF if fixture.kickoff_at else None


def is_fixture_locked(fixture: Fixture) -> bool:
    """Bez známého výkopu (kickoff_at ještě nenačtený z Livesportu) zápas neuzamykáme."""
    dl = fixture_deadline(fixture)
    if dl is None:
        return False
    return datetime.utcnow() >= dl
