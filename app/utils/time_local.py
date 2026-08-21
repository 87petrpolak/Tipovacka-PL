"""Zobrazení UTC časů v pražském čase."""
from datetime import datetime
from zoneinfo import ZoneInfo

PRAGUE = ZoneInfo("Europe/Prague")


def to_prague_str(dt_utc: datetime | None, fmt: str = "%-d.%-m. %H:%M") -> str:
    if dt_utc is None:
        return "?"
    return dt_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(PRAGUE).strftime(fmt)
