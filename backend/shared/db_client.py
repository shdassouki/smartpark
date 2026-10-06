"""
DynamoDB client — all database reads for the SmartPark pipeline go through
this module. Other modules never access DynamoDB directly.

Table name is read from the DYNAMODB_TABLE_NAME environment variable when
a database function is first called. This allows the module to be imported
freely in tests without requiring the variable to be set at import time.
"""

import os

import boto3
from boto3.dynamodb.conditions import Attr

from shared.exceptions import BuildingNotFoundError, InternalError
from shared.models import Building, Lot

# ---------------------------------------------------------------------------
# Lazy table accessor — reads env var and initialises boto3 on first use
# ---------------------------------------------------------------------------

_table = None


def _get_table():
    """
    Return the boto3 DynamoDB Table resource, initialising it on first call.

    Raises InternalError if DYNAMODB_TABLE_NAME is not set in the environment.
    Subsequent calls reuse the cached _table object (module-level singleton).
    """
    global _table
    if _table is not None:
        return _table

    table_name = os.environ.get("DYNAMODB_TABLE_NAME")
    if not table_name:
        raise InternalError(
            "DYNAMODB_TABLE_NAME environment variable is not set. "
            "Set it to the DynamoDB table name before calling database functions."
        )

    _table = boto3.resource("dynamodb").Table(table_name)
    return _table


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def get_all_lots() -> list[Lot]:
    """
    Return all parking lot records from DynamoDB.

    Scans for items where PK begins with 'LOT#' and SK equals 'METADATA'.
    Returns an empty list if no lots are found (the eligibility filter will
    then raise NoEligibleLotsError).
    """
    response = _get_table().scan(
        FilterExpression=Attr("SK").eq("METADATA") & Attr("PK").begins_with("LOT#")
    )
    items = response.get("Items", [])

    lots = []
    for item in items:
        lots.append(
            Lot(
                lot_id=item["lot_id"],
                name=item["name"],
                accepted_permit_types=set(item["accepted_permit_types"]),
            )
        )
    return lots


def get_building(building_id: str) -> Building:
    """
    Return the building record for the given building_id.

    Raises BuildingNotFoundError if no matching record exists.
    """
    response = _get_table().get_item(
        Key={
            "PK": f"BUILDING#{building_id}",
            "SK": "METADATA",
        }
    )
    item = response.get("Item")
    if item is None:
        raise BuildingNotFoundError(
            f"Building '{building_id}' was not found in the database."
        )
    return Building(
        building_id=item["building_id"],
        name=item["name"],
    )


def get_availability(lot_id: str, day_of_week: str, hour: str) -> int | None:
    """
    Return the historical availability percentage (0–100) for a lot at a
    specific day-of-week and hour.

    day_of_week: three-letter uppercase string, e.g. 'MON', 'TUE'
    hour: zero-padded 24-hour string, e.g. '07', '14'

    This is called with the candidate arrival time's day/hour for each lot —
    not the class start time — so availability reflects when the student
    would actually arrive at that lot.

    Returns None if no availability record exists for the given slot. None
    means "we have no simulated data for this time", which is distinct from a
    real stored value of 0 (a genuine prediction that the lot is full). The
    caller is responsible for deciding how to handle missing data; it must not
    be treated as a real 0% prediction.
    """
    response = _get_table().get_item(
        Key={
            "PK": f"LOT#{lot_id}",
            "SK": f"AVAIL#{day_of_week}#{hour}",
        }
    )
    item = response.get("Item")
    if item is None:
        return None
    return int(item["availability_score"])


def get_walking_time(lot_id: str, building_id: str) -> float:
    """
    Return the precomputed simulated walking time in minutes from a parking
    lot to a destination building.

    Raises InternalError if no walking time record exists for the pair,
    since this indicates incomplete seed data rather than a user error.
    """
    response = _get_table().get_item(
        Key={
            "PK": f"WALK#{lot_id}#{building_id}",
            "SK": "ESTIMATE",
        }
    )
    item = response.get("Item")
    if item is None:
        raise InternalError(
            f"No walking time record found for lot '{lot_id}' → "
            f"building '{building_id}'. Check that seed data is complete."
        )
    return float(item["walking_time_minutes"])
