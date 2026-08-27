"""
Stejná logika jako check_reminder.py, ale přes Supabase REST API (HTTPS/443)
místo přímého připojení k Postgresu (port 5432) — pro prostředí, kde je
přímé DB spojení nespolehlivé/blokované (např. cloudová naplánovaná úloha).

Vyžaduje proměnné prostředí:
  SUPABASE_URL       např. https://zftqaeorhqdbbxeifaqf.supabase.co
  SUPABASE_API_KEY   publishable/anon klíč

Vypíše JSON na stdout, stejný tvar jako check_reminder.py:
  {"due": false}
  {"due": true, "gameweek": 5, "kickoff_utc": "...", "kickoff_prague": "..."}
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

REMINDER_BEFORE_KICKOFF = timedelta(hours=12)


def _rest(base_url: str, api_key: str, path: str, params: dict) -> list[dict]:
    resp = requests.get(
        f"{base_url}/rest/v1/{path}",
        headers={"apikey": api_key, "Authorization": f"Bearer {api_key}"},
        params=params,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    base_url = os.environ["SUPABASE_URL"].rstrip("/")
    api_key = os.environ["SUPABASE_API_KEY"]

    unfinished = _rest(base_url, api_key, "fixtures", {
        "select": "gameweek_id,kickoff_at",
        "is_finished": "eq.false",
        "order": "gameweek_id.asc,kickoff_at.asc.nullslast",
    })
    if not unfinished:
        print(json.dumps({"due": False}))
        return

    current_gw_id = unfinished[0]["gameweek_id"]
    kickoffs = [
        row["kickoff_at"] for row in unfinished
        if row["gameweek_id"] == current_gw_id and row["kickoff_at"]
    ]
    if not kickoffs:
        print(json.dumps({"due": False}))
        return
    def _parse_utc(raw: str) -> datetime:
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    kickoff = min(_parse_utc(k) for k in kickoffs)

    gw_rows = _rest(base_url, api_key, "gameweeks", {
        "select": "number,reminder_sent_at",
        "id": f"eq.{current_gw_id}",
    })
    if not gw_rows:
        print(json.dumps({"due": False}))
        return
    gw = gw_rows[0]
    if gw["reminder_sent_at"] is not None:
        print(json.dumps({"due": False}))
        return

    now = datetime.now(timezone.utc)
    window_start = kickoff - REMINDER_BEFORE_KICKOFF
    if not (window_start <= now < kickoff):
        print(json.dumps({"due": False}))
        return

    prague = kickoff.astimezone(ZoneInfo("Europe/Prague"))
    print(json.dumps({
        "due": True,
        "gameweek": gw["number"],
        "kickoff_utc": kickoff.isoformat(),
        "kickoff_prague": prague.strftime("%-d.%-m. %H:%M"),
    }))


if __name__ == "__main__":
    main()
