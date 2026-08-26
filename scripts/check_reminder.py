"""
Zkontroluje, jestli je čas poslat připomínku na uzávěrku tipů (12 hodin
před výkopem prvního zápasu aktuálního kola). Vypíše JSON na stdout:

  {"due": false}
  {"due": true, "gameweek": 5, "kickoff_utc": "...", "kickoff_prague": "22.9. 20:00"}

Vyžaduje proměnnou prostředí DATABASE_URL (Supabase connection string).
Spouští se z kořene repa: python scripts/check_reminder.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.services.locking import first_kickoff  # noqa: E402
from app.services.reminders import reminder_due  # noqa: E402
from app.utils.time_local import to_prague_str  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        gw = reminder_due(db)
        if gw is None:
            print(json.dumps({"due": False}))
            return
        kickoff = first_kickoff(gw)
        print(json.dumps({
            "due": True,
            "gameweek": gw.number,
            "kickoff_utc": kickoff.isoformat(),
            "kickoff_prague": to_prague_str(kickoff, "%-d.%-m. %H:%M"),
        }))
    finally:
        db.close()


if __name__ == "__main__":
    main()
