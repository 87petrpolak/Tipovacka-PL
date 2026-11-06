"""Denní synchronizace soupisek z Livesportu (GitHub Actions cron).

Přidá nové hráče, odešlé skryje (historie nominací zůstává). Vyžaduje DATABASE_URL."""
import os
import socket
import sys

_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only_getaddrinfo

if not os.environ.get("DATABASE_URL"):
    print("DATABASE_URL není nastavené — zkontroluj GitHub repo secret.", file=sys.stderr)
    sys.exit(1)

from app.db import init_db, SessionLocal  # noqa: E402
from app.services.data_refresh import refresh_squads  # noqa: E402


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        totals = refresh_squads(db)
    finally:
        db.close()
    print(" ".join(f"{k}={v}" for k, v in totals.items()))
    if totals["failed_teams"] > 5:
        sys.exit(1)


if __name__ == "__main__":
    main()
