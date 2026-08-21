"""Uzamykání kola — tipy a nominace jde upravovat jen do hodiny před výkopem prvního zápasu."""
from datetime import datetime, timedelta

from app.models.models import Gameweek

LOCK_BEFORE_KICKOFF = timedelta(hours=1)


def first_kickoff(gameweek: Gameweek) -> datetime | None:
    kickoffs = [f.kickoff_at for f in gameweek.fixtures if f.kickoff_at]
    return min(kickoffs) if kickoffs else None


def deadline(gameweek: Gameweek) -> datetime | None:
    fk = first_kickoff(gameweek)
    return fk - LOCK_BEFORE_KICKOFF if fk else None


def is_locked(gameweek: Gameweek) -> bool:
    """Bez známého výkopu (kickoff_at ještě nenačtený z Livesportu) kolo neuzamykáme."""
    dl = deadline(gameweek)
    if dl is None:
        return False
    return datetime.utcnow() >= dl
