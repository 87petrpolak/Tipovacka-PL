"""
Jednorázové spuštění synchronizace výsledků z Livesportu — pro automatizaci
(GitHub Actions cron), aby `is_finished`/skóre zápasů neustávaly na starých
datech (na tom pak visel jak dashboard, tak reminder e-mail — oba počítají
"aktuální kolo" jako první kolo s nějakým zápasem, co ještě není is_finished).

Vyžaduje DATABASE_URL v prostředí (stejná hodnota jako v Streamlit Cloud
secrets — přímé Postgres spojení, ne REST API).
"""
import os
import sys

if not os.environ.get("DATABASE_URL"):
    # app.db._get_db_url() by bez DATABASE_URL tiše spadlo na lokální SQLite
    # (prázdnou, jednorázovou) — v CI chceme hlasitě selhat, ne "uspět" naprázdno.
    print("DATABASE_URL není nastavené — zkontroluj GitHub repo secret.", file=sys.stderr)
    sys.exit(1)

from app.db import init_db, SessionLocal  # noqa: E402
from app.services.data_refresh import refresh_results  # noqa: E402


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
