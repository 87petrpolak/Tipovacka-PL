"""
Jednorázové spuštění synchronizace výsledků z Livesportu — pro automatizaci
(GitHub Actions cron), aby `is_finished`/skóre zápasů neustávaly na starých
datech (na tom pak visel jak dashboard, tak reminder e-mail — oba počítají
"aktuální kolo" jako první kolo s nějakým zápasem, co ještě není is_finished).

Vyžaduje DATABASE_URL v prostředí (stejná hodnota jako v Streamlit Cloud
secrets — přímé Postgres spojení, ne REST API).
"""
import sys

from app.db import init_db, SessionLocal
from app.services.data_refresh import refresh_results


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        log = refresh_results(db)
    finally:
        db.close()

    print(
        f"success={log.success} added={log.records_added} "
        f"updated={log.records_updated} skipped={log.records_skipped} notes={log.notes}"
    )
    if not log.success:
        sys.exit(1)


if __name__ == "__main__":
    main()
