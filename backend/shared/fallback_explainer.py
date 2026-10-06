"""
Fallback explainer — generates a plain-language recommendation explanation
without calling any external service.

Used when Amazon Bedrock is unavailable. The output is deterministic:
identical inputs always produce identical explanations.
"""

from shared.models import ScoredLot


def _describe_availability(percentage: int) -> str:
    """
    Convert an availability percentage to a plain-language descriptor.

        >= 75  -> "high"
        >= 45  -> "moderate"
        <  45  -> "low"
    """
    if percentage >= 75:
        return "high"
    elif percentage >= 45:
        return "moderate"
    else:
        return "low"


def generate_fallback_explanation(
    winner: ScoredLot,
    runner_ups: list[ScoredLot],
) -> str:
    """
    Generate a plain-language explanation for the recommended parking lot.

    Parameters
    ----------
    winner : ScoredLot
        The top-ranked lot selected by the scoring module.
    runner_ups : list[ScoredLot]
        Up to two other lots that were scored but not selected.
        May be empty if only one eligible lot existed.

    Returns
    -------
    str
        A non-empty explanation string suitable for display to the student.
    """
    avail_desc = _describe_availability(winner.availability_percentage)
    walk_desc = f"{winner.walking_time_minutes:.0f}-minute walk"

    explanation = (
        f"{winner.lot.name} is recommended because it has {avail_desc} "
        f"predicted availability and is a {walk_desc} from your destination."
    )

    if runner_ups:
        explanation += (
            " Compared to nearby alternatives, it offers the best balance "
            "of availability and walking distance."
        )

    return explanation
