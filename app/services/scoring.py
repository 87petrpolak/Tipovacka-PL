"""
Bodovací logika — 1:1 odpovídá vzorcům v Tipovacka_PL_2026-2027.xlsx.

Zápasy:  přesný výsledek 10 bodů, správná tendence (výhra/remíza/prohra) 2 body, jinak 0.
Střelci: gól 5 bodů, každý další gól +2; asistence 2 body, každá další asistence +1;
         hráč, který byl nominován, hrál, ale nedal gól ani asistenci: -2 body.
         Nenominovaný hráč body/pokutu nedostává.
"""


def compute_match_points(
    home_score: int | None,
    away_score: int | None,
    tip_home: int | None,
    tip_away: int | None,
) -> float:
    if home_score is None or away_score is None or tip_home is None or tip_away is None:
        return 0.0
    if home_score == tip_home and away_score == tip_away:
        return 10.0
    actual_sign = _sign(home_score - away_score)
    tip_sign = _sign(tip_home - tip_away)
    if actual_sign == tip_sign:
        return 2.0
    return 0.0


def compute_scorer_points(nominated: bool, goals: int, assists: int, played: bool) -> float:
    if not nominated:
        return 0.0
    goals = goals or 0
    assists = assists or 0
    points = 0.0
    if goals == 0 and assists == 0 and played:
        points -= 2.0
    if goals > 0:
        points += 5.0 + (goals - 1) * 2.0
    if assists > 0:
        points += 2.0 + (assists - 1) * 1.0
    return points


def _sign(x: int) -> int:
    return (x > 0) - (x < 0)
