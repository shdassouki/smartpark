"""
Permit eligibility filter — the first step in the SmartPark recommendation
pipeline.

Removes every parking lot that does not accept the student's permit type.
This is a hard filter: ineligible lots are excluded entirely before any
scoring takes place. A lot can never be recommended to a student whose
permit type is not in its accepted_permit_types set.
"""

from shared.exceptions import NoEligibleLotsError
from shared.models import Lot


def filter_eligible_lots(lots: list[Lot], permit_type: str) -> list[Lot]:
    """
    Return only the lots whose accepted_permit_types includes permit_type.

    Parameters
    ----------
    lots : list[Lot]
        The full list of parking lots retrieved from the database.
    permit_type : str
        The student's permit type, e.g. 'COMMUTER_A'.

    Returns
    -------
    list[Lot]
        Lots that accept the given permit type, in their original order.
        Order does not matter here — the scoring step will rank them.

    Raises
    ------
    NoEligibleLotsError
        If no lots remain after filtering. The handler catches this and
        returns a 404 response to the student.
    """
    eligible = [lot for lot in lots if permit_type in lot.accepted_permit_types]

    if not eligible:
        raise NoEligibleLotsError(
            f"No parking lots are available for permit type '{permit_type}'."
        )

    return eligible
