"""
Jednorázové spuštění synchronizace výsledků z Livesportu — pro automatizaci
(GitHub Actions cron), aby `is_finished`/skóre zápasů neustávaly na starých
datech (na tom pak visel jak dashboard, tak reminder e-mail — oba počítají
"aktuální kolo" jako první kolo s nějakým zápasem, co ještě není is_finished).

Vyžaduje DATABASE_URL v prostředí (stejná hodnota jako v Streamlit Cloud
secrets — přímé Postgres spojení, ne REST API).
"""
import os
import socket
import sys

# GitHub Actions runnery umí IPv6 jen naoko — AAAA záznam Supabase poolu
# se jim ale "Network is unreachable". Donutíme resolver vracet jen IPv4.
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only_getaddrinfo

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
        # Hodnoty si vytáhneme, dokud je session otevřená — po db.close() by
        # přístup k atributům spadl na DetachedInstanceError.
        success, added, updated, skipped, notes = (
            log.success, log.records_added, log.records_updated, log.records_skipped, log.notes,
        )
    finally:
        db.close()

    print(f"success={success} added={added} updated={updated} skipped={skipped} notes={notes}")
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
