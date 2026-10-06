"""
Arrival time computation — calculates when a student needs to arrive at a
parking lot to reach their class or event on time.

Formula
-------
    candidate_arrival_time = class_start_time
                             - walking_time_minutes
                             - parking_buffer_minutes

parking_buffer_minutes accounts for the time needed to find a spot after
arriving at the lot. It is read from the PARKING_BUFFER_MINUTES environment
variable (default: 5 minutes).

This module is used twice in the pipeline:
  1. Per-lot during scoring — each lot's candidate arrival time determines
     which availability time slot is looked up for that lot.
  2. For the winning lot — the formatted arrival time is shown to the student
     as "Arrive at the lot by X to make it to class on time."
"""

import os
from datetime import datetime, timedelta


def get_parking_buffer() -> int:
    """
    Return the parking buffer in minutes from the PARKING_BUFFER_MINUTES
    environment variable. Defaults to 5 if the variable is not set.
    """
    try:
        return int(os.environ.get("PARKING_BUFFER_MINUTES", 5))
    except ValueError:
        return 5


def compute_arrival_time(
    start_time: datetime,
    walking_time_minutes: float,
    parking_buffer_minutes: int | None = None,
) -> datetime:
    """
    Compute the time a student should arrive at a parking lot.

    Parameters
    ----------
    start_time : datetime
        The class or event start time.
    walking_time_minutes : float
        Walking time from this lot to the destination building.
    parking_buffer_minutes : int | None
        Minutes to reserve for finding a spot. If None, reads from the
        PARKING_BUFFER_MINUTES environment variable (default 5).

    Returns
    -------
    datetime
        The candidate arrival time at the parking lot.
    """
    if parking_buffer_minutes is None:
        parking_buffer_minutes = get_parking_buffer()

    total_minutes = walking_time_minutes + parking_buffer_minutes
    return start_time - timedelta(minutes=total_minutes)


def format_arrival_time(arrival_time: datetime) -> str:
    """
    Format an arrival time as a 12-hour clock string without a leading zero.

    Uses lstrip("0") for cross-platform compatibility (avoids %-I which is
    Unix-only).

    Examples
    --------
    datetime(2025, 9, 15,  8, 45) -> "8:45 AM"
    datetime(2025, 9, 15, 12,  0) -> "12:00 PM"
    datetime(2025, 9, 15, 13, 30) -> "1:30 PM"
    """
    return arrival_time.strftime("%I:%M %p").lstrip("0")
