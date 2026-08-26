"""
Označí připomínku pro dané kolo jako odeslanou (aby se neposílala vícekrát).
Použití: python scripts/mark_reminder_sent.py <cislo_kola>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.services.reminders import mark_reminder_sent  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        print("Použití: python scripts/mark_reminder_sent.py <cislo_kola>")
        sys.exit(1)
    gameweek_number = int(sys.argv[1])
    db = SessionLocal()
    try:
        mark_reminder_sent(db, gameweek_number)
        print(f"Kolo {gameweek_number}: připomínka označena jako odeslaná.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
