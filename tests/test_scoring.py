from app.services.scoring import compute_match_points, compute_scorer_points


def test_exact_score():
    assert compute_match_points(2, 1, 2, 1) == 10.0


def test_correct_tendency():
    assert compute_match_points(2, 1, 3, 0) == 2.0
    assert compute_match_points(1, 1, 2, 2) == 2.0


def test_wrong_tendency():
    assert compute_match_points(2, 1, 1, 2) == 0.0


def test_missing_data():
    assert compute_match_points(None, None, 2, 1) == 0.0
    assert compute_match_points(2, 1, None, None) == 0.0


def test_scorer_not_nominated():
    assert compute_scorer_points(False, 3, 2, True) == 0.0


def test_scorer_no_goal_no_assist_played():
    assert compute_scorer_points(True, 0, 0, True) == -2.0


def test_scorer_no_goal_no_assist_not_played():
    assert compute_scorer_points(True, 0, 0, False) == 0.0


def test_scorer_single_goal():
    assert compute_scorer_points(True, 1, 0, True) == 5.0


def test_scorer_multiple_goals():
    assert compute_scorer_points(True, 3, 0, True) == 5.0 + 2 * 2.0


def test_scorer_single_assist():
    assert compute_scorer_points(True, 0, 1, True) == 2.0


def test_scorer_multiple_assists():
    assert compute_scorer_points(True, 0, 3, True) == 2.0 + 2 * 1.0


def test_scorer_goal_and_assist():
    assert compute_scorer_points(True, 1, 1, True) == 7.0
