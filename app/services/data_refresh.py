"""Orchestrace synchronizace s Livesportem: týmy, výsledky, soupisky, střelci."""
from sqlalchemy.orm import Session

from app.models.models import DataRefreshLog, Fixture, Gameweek, Player, Prediction, ScorerNomination, Team
from app.providers import livesport_provider as lp
from app.services.scoring import compute_match_points, compute_scorer_points


def sync_teams(db: Session) -> None:
    """Přiřadí Flashscore external_id/slug našim týmům (jednorázově, idempotentní)."""
    for name, (slug, team_id) in lp.TEAM_IDS.items():
        team = db.query(Team).filter(Team.name == name).first()
        if team and (team.external_id != team_id or team.slug != slug):
            team.external_id = team_id
            team.slug = slug
    db.commit()


def refresh_results(db: Session, day_offsets: range = range(-14, 8)) -> DataRefreshLog:
    """Stáhne aktuální/dokončené zápasy Premier League a promítne je do Fixture."""
    sync_teams(db)

    teams_by_ext_id = {t.external_id: t for t in db.query(Team).filter(Team.external_id.isnot(None)).all()}
    added, updated, skipped = 0, 0, 0
    notes = []

    try:
        scraped = lp.fetch_pl_matches(day_offsets)
    except Exception as e:
        log = DataRefreshLog(provider="livesport", success=False, notes=f"Chyba stahování: {e}")
        db.add(log)
        db.commit()
        return log

    for m in scraped:
        home_team = teams_by_ext_id.get(m.home_team_ext_id)
        away_team = teams_by_ext_id.get(m.away_team_ext_id)
        if not home_team or not away_team:
            skipped += 1
            continue

        fixture = db.query(Fixture).filter(
            Fixture.home_team_id == home_team.id,
            Fixture.away_team_id == away_team.id,
        ).first()
        if not fixture:
            skipped += 1
            continue

        changed = False
        if fixture.external_id != m.external_id:
            fixture.external_id = m.external_id
            changed = True
        if m.kickoff_at and fixture.kickoff_at != m.kickoff_at:
            fixture.kickoff_at = m.kickoff_at
            changed = True
        if fixture.home_score != m.home_score or fixture.away_score != m.away_score:
            fixture.home_score = m.home_score
            fixture.away_score = m.away_score
            changed = True
        if fixture.is_finished != m.is_finished:
            fixture.is_finished = m.is_finished
            changed = True

        if changed:
            updated += 1
            _recompute_predictions(db, fixture)

    log = DataRefreshLog(
        provider="livesport",
        records_added=added,
        records_updated=updated,
        records_skipped=skipped,
        success=True,
        notes="; ".join(notes) or None,
    )
    db.add(log)
    db.commit()

    # Po aktualizaci výsledků dotáhni i statistiky střelců pro dokončené zápasy.
    refresh_scorer_stats(db)

    return log


def _recompute_predictions(db: Session, fixture: Fixture) -> None:
    predictions = db.query(Prediction).filter(Prediction.fixture_id == fixture.id).all()
    for pred in predictions:
        pred.points = compute_match_points(fixture.home_score, fixture.away_score, pred.tip_home, pred.tip_away)
    db.commit()


def ensure_squad(db: Session, team: Team) -> list[Player]:
    """Načte soupisku týmu z Livesportu, pokud ji ještě nemáme v DB."""
    existing = db.query(Player).filter(Player.team_id == team.id).all()
    if existing:
        return existing

    if not team.slug or not team.external_id:
        sync_teams(db)
        db.refresh(team)
    if not team.slug or not team.external_id:
        return []

    try:
        scraped = lp.scrape_squad(team.slug, team.external_id)
    except Exception:
        return []

    players = []
    for p in scraped:
        player = db.query(Player).filter(Player.external_id == p["external_id"]).first()
        if not player:
            player = Player(
                name=p["name"],
                position=p["position"],
                external_id=p["external_id"],
                team_id=team.id,
            )
            db.add(player)
        players.append(player)
    db.commit()
    return db.query(Player).filter(Player.team_id == team.id).all()


def refresh_scorer_stats(db: Session) -> None:
    """Pro všechny dokončené zápasy s nominacemi dotáhne góly/asistence/nastoupení a přepočítá body."""
    finished_fixtures = db.query(Fixture).filter(
        Fixture.is_finished == True,  # noqa: E712
        Fixture.external_id.isnot(None),
    ).all()

    for fixture in finished_fixtures:
        nominations = (
            db.query(ScorerNomination)
            .join(Player, ScorerNomination.player_id == Player.id)
            .filter(
                ScorerNomination.gameweek_id == fixture.gameweek_id,
                Player.team_id.in_([fixture.home_team_id, fixture.away_team_id]),
            )
            .all()
        )
        if not nominations:
            continue

        try:
            events = lp.fetch_match_player_events(fixture.external_id)
        except Exception:
            continue

        events_by_ext_id = {k: v for k, v in events.items() if v.get("player_external_id")}

        for nom in nominations:
            player = db.get(Player, nom.player_id)
            if not player or not player.external_id:
                continue
            ev = events_by_ext_id.get(player.external_id)
            if ev is None:
                nom.goals, nom.assists, nom.played = 0, 0, False
            else:
                nom.goals, nom.assists, nom.played = ev["goals"], ev["assists"], ev["played"]
            nom.points = compute_scorer_points(True, nom.goals, nom.assists, nom.played)

    db.commit()


def current_gameweek(db: Session) -> Gameweek | None:
    """První kolo, které ještě nemá všechny zápasy dohrané — kolo pro tipování."""
    gameweeks = db.query(Gameweek).order_by(Gameweek.number).all()
    for gw in gameweeks:
        if any(not f.is_finished for f in gw.fixtures):
            return gw
    return gameweeks[-1] if gameweeks else None
