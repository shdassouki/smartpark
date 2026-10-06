"""
Composite score computation — ranks eligible parking lots by balancing
predicted availability and walking time.

Scoring formula
---------------
    composite_score = availability_percentage - (WALK_PENALTY * walking_time_minutes)

If availability_percentage is below LOW_AVAIL_THRESHOLD, an additional
LOW_AVAIL_PENALTY is deducted to discourage recommending lots that are
likely too full to be worth attempting.

All three constants are configurable prototype parameters. They are defined
here as named constants and can be adjusted without changing formula logic.

Tiebreaker
----------
When two lots share the same composite_score, the lot with the shorter
walking_time_minutes is ranked higher.
"""

from shared.models import Lot, ScoredLot

# Walking time penalty per minute.
# Each additional minute of walking costs this many score points.
WALK_PENALTY: float = 6

# Availability threshold below which a lot is considered low-availability.
# Lots below this percentage receive an extra score deduction.
LOW_AVAIL_THRESHOLD: int = 40

# Extra deduction applied to lots below LOW_AVAIL_THRESHOLD.
# Discourages recommending lots that are likely too full to be worth attempting.
LOW_AVAIL_PENALTY: float = 20


def score_lots(lots_with_data: list[dict]) -> list[ScoredLot]:
    """
    Score and rank eligible parking lots.

    Parameters
    ----------
    lots_with_data : list[dict]
        Each dict must contain:
          - 'lot': Lot dataclass instance
          - 'availability_percentage': int 0–100
          - 'walking_time_minutes': float
          - 'candidate_arrival_time': datetime

    Returns
    -------
    list[ScoredLot]
        Scored lots sorted best-first. Ties broken by walking_time_minutes
        ascending (closer lot wins).
    """
    scored: list[ScoredLot] = []
    for entry in lots_with_data:
        lot: Lot = entry["lot"]
        p: int = entry["availability_percentage"]
        walk: float = entry["walking_time_minutes"]
        candidate_arrival_time = entry["candidate_arrival_time"]

        composite_score = p - (WALK_PENALTY * walk)
        if p < LOW_AVAIL_THRESHOLD:
            composite_score -= LOW_AVAIL_PENALTY

        scored.append(ScoredLot(
            lot=lot,
            composite_score=composite_score,
            walking_time_minutes=walk,
            availability_percentage=p,
            candidate_arrival_time=candidate_arrival_time,
        ))

    scored.sort(key=lambda x: (-x.composite_score, x.walking_time_minutes))

    return scored


def select_winner(scored_lots: list[ScoredLot]) -> ScoredLot:
    """
    Return the top-ranked ScoredLot from a scored list.

    Parameters
    ----------
    scored_lots : list[ScoredLot]
        Output of score_lots() — must be non-empty.

    Returns
    -------
    ScoredLot
        The lot with the highest composite score.
    """
    return scored_lots[0]
