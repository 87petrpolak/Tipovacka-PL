"""Logika pro e-mailovou připomínku 12 hodin před výkopem prvního zápasu kola."""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.models import Gameweek
from app.services.data_refresh import current_gameweek
from app.services.locking import first_kickoff

REMINDER_BEFORE_KICKOFF = timedelta(hours=12)


def reminder_due(db: Session) -> Gameweek | None:
    """Vrátí Gameweek, pokud je čas poslat připomínku (a ještě nebyla poslána)."""
    gw = current_gameweek(db)
    if gw is None or gw.reminder_sent_at is not None:
        return None
    kickoff = first_kickoff(gw)
    if kickoff is None:
        return None
    window_start = kickoff - REMINDER_BEFORE_KICKOFF
    now = datetime.utcnow()
    if window_start <= now < kickoff:
        return gw
    return None


def mark_reminder_sent(db: Session, gameweek_number: int) -> None:
    gw = db.query(Gameweek).filter(Gameweek.number == gameweek_number).one()
    gw.reminder_sent_at = datetime.utcnow()
    db.commit()
