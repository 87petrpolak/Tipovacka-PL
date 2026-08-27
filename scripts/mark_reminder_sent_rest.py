"""
Označí připomínku pro dané kolo jako odeslanou — přes Supabase REST API.
Použití: python scripts/mark_reminder_sent_rest.py <cislo_kola>

Vyžaduje proměnné prostředí SUPABASE_URL a SUPABASE_API_KEY (viz
check_reminder_rest.py).
"""
import os
import sys
from datetime import datetime, timezone

import requests


def main() -> None:
    if len(sys.argv) != 2:
        print("Použití: python scripts/mark_reminder_sent_rest.py <cislo_kola>")
        sys.exit(1)
    gameweek_number = int(sys.argv[1])

    base_url = os.environ["SUPABASE_URL"].rstrip("/")
    api_key = os.environ["SUPABASE_API_KEY"]

    resp = requests.patch(
        f"{base_url}/rest/v1/gameweeks",
        headers={
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        params={"number": f"eq.{gameweek_number}"},
        json={"reminder_sent_at": datetime.now(timezone.utc).isoformat()},
        timeout=15,
    )
    resp.raise_for_status()
    updated = resp.json()
    if not updated:
        print(f"Kolo {gameweek_number}: nenalezeno, nic se neaktualizovalo.")
        sys.exit(1)
    print(f"Kolo {gameweek_number}: připomínka označena jako odeslaná.")


if __name__ == "__main__":
    main()
