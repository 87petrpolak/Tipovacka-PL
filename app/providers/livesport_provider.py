"""
Livesport.cz / Flashscore scraper pro anglickou Premier League 2026/27.

Stejná technika jako v předchozím projektu (MS 2026) — interní Flashscore
feed API (flashscore.ninja), ¬/÷/~ oddělený formát, token x-fsign je
statický, uložený v jejich JS. Podrobnosti k formátu viz komentáře níže.

Tournament ID a team ID/slug byly zjištěny přímým dotazem na dnešní feed
(21.8.2026) a soupisky týmů — viz app/providers/team_ids.py.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

_BASE = "https://1.flashscore.ninja/1/x/feed"
_LIVESPORT_BASE = "https://www.livesport.cz"
_HEADERS = {
    "x-fsign": "SW9D1eZo",
    "Referer": "https://www.livesport.cz/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}
_HTML_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "cs-CZ,cs;q=0.9",
    "Referer": "https://www.livesport.cz/",
}
_REQUEST_DELAY = 0.3

# Premier League 2026/27 (ne PL2/U21 = CfcJv4MD)
PL_TOURNAMENT_ID = "dYlOSQOD"

# (název v naší DB) -> (slug, flashscore team id)
TEAM_IDS: dict[str, tuple[str, str]] = {
    "Arsenal": ("arsenal", "hA1Zm19f"),
    "Aston Villa": ("aston-villa", "W00wmLO0"),
    "Bournemouth": ("bournemouth", "OtpNdwrc"),
    "Brentford": ("brentford", "xYe7DwID"),
    "Brighton": ("brighton", "2XrRecc3"),
    "Chelsea": ("chelsea", "4fGZN2oK"),
    "Coventry": ("coventry", "GOvB22xg"),
    "Crystal Palace": ("crystal-palace", "AovF1Mia"),
    "Everton": ("everton", "KluSTr9s"),
    "Fulham": ("fulham", "69ZiU2Om"),
    "Hull": ("hull", "S66R0t75"),
    "Ipswich": ("ipswich", "thqhB2MB"),
    "Leeds": ("leeds", "tUxUbLR2"),
    "Liverpool": ("liverpool", "lId4TMwf"),
    "Man City": ("manchester-city", "Wtn9Stg0"),
    "Man U": ("manchester-utd", "ppjDR086"),
    "Newcastle": ("newcastle", "p6ahwuwJ"),
    "Nottingham": ("nottingham", "UsushcZr"),
    "Sunderland": ("sunderland", "WSzc94ws"),
    "Spurs": ("tottenham", "UDg08Ohm"),
}

_POS_MAP = {
    "brankáři": "GK",
    "brankář": "GK",
    "obránci": "DEF",
    "obránce": "DEF",
    "záložníci": "MID",
    "záložník": "MID",
    "útočníci": "FWD",
    "útočník": "FWD",
}

_INCIDENT_GOALS = {"Gól", "Penalta"}
_INCIDENT_OWN_GOAL = "Vlastní gól"
_INCIDENT_SUB_IN = "Střídání"


def _fetch(path: str) -> str:
    url = f"{_BASE}/{path}"
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    time.sleep(_REQUEST_DELAY)
    return resp.text


def _fetch_html(url: str) -> str:
    resp = requests.get(url, headers=_HTML_HEADERS, timeout=15)
    resp.raise_for_status()
    time.sleep(_REQUEST_DELAY)
    return resp.text


def _parse_feed(raw: str) -> list[dict]:
    records = []
    for block in raw.split("~"):
        block = block.strip()
        if not block:
            continue
        record: dict[str, str] = {}
        for pair in block.split("¬"):
            if "÷" in pair:
                key, _, val = pair.partition("÷")
                record[key] = val
        if record:
            records.append(record)
    return records


def _parse_minute(minute_str: str) -> int:
    s = minute_str.replace("'", "").strip()
    if "+" in s:
        base, extra = s.split("+", 1)
        try:
            return int(base) + int(extra)
        except ValueError:
            pass
    try:
        return int(s)
    except ValueError:
        return 0


class ScrapedFixture:
    def __init__(self, external_id, home_team_ext_id, away_team_ext_id,
                 home_score, away_score, kickoff_at, is_finished):
        self.external_id = external_id
        self.home_team_ext_id = home_team_ext_id
        self.away_team_ext_id = away_team_ext_id
        self.home_score = home_score
        self.away_score = away_score
        self.kickoff_at = kickoff_at
        self.is_finished = is_finished


def fetch_pl_matches(day_offsets: range) -> list[ScrapedFixture]:
    """Projde denní feedy pro dané offsety (0=dnes, -1=včera, 1=zítra, ...)
    a vrátí zápasy Premier League 2026/27 (živé, dokončené i naplánované)."""
    matches: dict[str, ScrapedFixture] = {}

    for day_offset in day_offsets:
        try:
            raw = _fetch(f"f_1_{day_offset}_2_cs_1")
        except Exception:
            continue
        records = _parse_feed(raw)
        current_tournament_id = None

        for rec in records:
            if "ZEE" in rec:
                current_tournament_id = rec.get("ZEE", "")
                continue
            if "AA" not in rec:
                continue
            if current_tournament_id != PL_TOURNAMENT_ID:
                continue

            match_id = rec["AA"]
            status = rec.get("AB")  # 1=naplánováno, 2=live, 3=dokončeno

            kickoff_at = None
            raw_ts = rec.get("AD", "")
            if raw_ts:
                try:
                    kickoff_at = datetime.fromtimestamp(int(raw_ts), tz=timezone.utc).replace(tzinfo=None)
                except (ValueError, OSError):
                    pass

            matches[match_id] = ScrapedFixture(
                external_id=match_id,
                home_team_ext_id=rec.get("PX", ""),
                away_team_ext_id=rec.get("PY", ""),
                home_score=int(rec.get("AG", 0) or 0) if status in ("2", "3") else None,
                away_score=int(rec.get("AH", 0) or 0) if status in ("2", "3") else None,
                kickoff_at=kickoff_at,
                is_finished=status == "3",
            )

    return list(matches.values())


def scrape_squad(team_slug: str, team_id: str) -> list[dict]:
    """
    Stáhne soupisku týmu. Vrátí [{name, position, external_id}, ...].

    Stránka /soupiska/ obsahuje na jedné HTML stránce víc tabulek
    (aktuální soupiska přes všechny soutěže + zvlášť soupisky soupeřů
    z pohárových zápasů pod id "national-cup-*-table"). Chceme jen
    kompletní soupisku vlastního týmu, ta je vždy pod #overall-all-table.
    """
    url = f"{_LIVESPORT_BASE}/tym/{team_slug}/{team_id}/soupiska/"
    html = _fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    container = soup.select_one("#overall-all-table") or soup

    players = []
    seen_ids: set[str] = set()
    current_pos = None
    in_players_section = False

    for el in container.select(".lineupTable__title, .lineupTable__row"):
        if "lineupTable__title" in el.get("class", []):
            title = el.get_text().strip().lower()
            pos = _POS_MAP.get(title)
            if pos:
                current_pos = pos
                in_players_section = True
            else:
                in_players_section = False
            continue

        if not in_players_section:
            continue

        link = el.select_one('a[href*="/hrac/"]')
        if not link:
            continue

        name = link.get_text().strip()
        href = link.get("href", "")
        m = re.search(r"/hrac/[^/]+/([A-Za-z0-9]+)/", href)
        player_id = m.group(1) if m else None

        if not name or not player_id or player_id in seen_ids:
            continue
        seen_ids.add(player_id)

        players.append({"name": name, "position": current_pos, "external_id": player_id})

    return players


def fetch_match_player_events(match_id: str) -> dict[str, dict]:
    """
    Vrátí pro daný zápas {player_external_id: {name, goals, assists, played}}
    kombinací sestav (df_li_) a incidentů (df_sui_).
    """
    lineup_raw = _fetch(f"df_li_1_{match_id}")
    players = _parse_lineup(lineup_raw)

    incidents_raw = _fetch(f"df_sui_1_{match_id}")
    _apply_incidents(incidents_raw, players)

    return players


def _parse_lineup(raw: str) -> dict:
    players: dict[str, dict] = {}

    for block in raw.split("~"):
        kv: dict[str, str] = {}
        for pair in block.split("¬"):
            if "÷" in pair:
                k, _, v = pair.partition("÷")
                kv[k] = v

        if "LP" not in kv or "LI" not in kv:
            continue
        if kv.get("LK") != "1":  # jen základní sestava
            continue

        pid = kv["LP"]
        name = kv["LI"].strip()
        key = pid or name
        players[key] = {
            "player_external_id": pid or None,
            "player_name": name,
            "goals": 0,
            "assists": 0,
            "played": True,
        }

    return players


def _apply_incidents(raw: str, players: dict) -> None:
    def _get_or_create(key: str, name: str, pid: str) -> dict:
        if key not in players:
            players[key] = {
                "player_external_id": pid or None,
                "player_name": name,
                "goals": 0,
                "assists": 0,
                "played": True,
            }
        return players[key]

    for block in raw.split("~"):
        if "III÷" not in block:
            continue

        kv: dict[str, list[str]] = {}
        for pair in block.split("¬"):
            if "÷" not in pair:
                continue
            k, _, v = pair.partition("÷")
            kv.setdefault(k, []).append(v)

        if_list = kv.get("IF", [])
        im_list = kv.get("IM", [])
        ik_list = kv.get("IK", [])

        ib_str = kv.get("IB", [""])[0]
        _base_m = re.match(r"(\d+)", ib_str)
        _base_int = int(_base_m.group(1)) if _base_m else 0
        ic_val = kv.get("IC", [""])[0]
        is_shootout = _base_int > 120 or ic_val in ("5", "6", "7")

        for i, ik in enumerate(ik_list):
            name = (if_list[i] if i < len(if_list) else "").strip()
            pid = (im_list[i] if i < len(im_list) else "").strip()
            if not name:
                continue
            key = pid or name

            if ik in _INCIDENT_GOALS:
                if is_shootout:
                    continue
                p = _get_or_create(key, name, pid)
                p["goals"] += 1
            elif ik in ("Asistence", "Asistace"):
                p = _get_or_create(key, name, pid)
                p["assists"] += 1
            elif ik == _INCIDENT_SUB_IN:
                _get_or_create(key, name, pid)
