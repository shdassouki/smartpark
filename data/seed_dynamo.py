"""
SmartPark seed data generator.

Builds the simulated prototype dataset for the SmartPark MVP and optionally
writes it to a DynamoDB table.

IMPORTANT: All walking times and availability values produced here are
SIMULATED prototype data. They are not official, measured, historical, or
real-time George Mason University parking data. GMU building and lot names are
used only to give the prototype a realistic campus setting.

By default this script runs in DRY-RUN mode and writes nothing to AWS.
Pass --write to actually write to a DynamoDB table.
"""

import argparse
import json

# ---------------------------------------------------------------------------
# Static reference data
# ---------------------------------------------------------------------------

BUILDINGS = [
    {"building_id": "bldg_enterprise", "name": "Enterprise Hall"},
    {"building_id": "bldg_johnson", "name": "Johnson Center"},
    {"building_id": "bldg_exploratory", "name": "Exploratory Hall"},
]

PERMIT_TYPES = [
    {"permit_type": "GENERAL", "display_name": "General"},
    {"permit_type": "FACULTY_STAFF", "display_name": "Faculty/Staff"},
]

LOTS = [
    {"lot_id": "deck_shenandoah",   "name": "Shenandoah Parking Deck",   "accepted_permit_types": ["GENERAL", "FACULTY_STAFF"]},
    {"lot_id": "deck_rappahannock", "name": "Rappahannock Parking Deck", "accepted_permit_types": ["GENERAL", "FACULTY_STAFF"]},
    {"lot_id": "deck_mason_pond",   "name": "Mason Pond Parking Deck",   "accepted_permit_types": ["GENERAL", "FACULTY_STAFF"]},
    {"lot_id": "lot_a",             "name": "Lot A",                     "accepted_permit_types": ["FACULTY_STAFF"]},
    {"lot_id": "lot_k",             "name": "Lot K",                     "accepted_permit_types": ["GENERAL"]},
]

# Simulated walking-time estimates in minutes, keyed (lot_id, building_id).
# NOT measured or official distances.
WALKING_TIMES = {
    ("deck_shenandoah",   "bldg_enterprise"):  10,
    ("deck_shenandoah",   "bldg_johnson"):      6,
    ("deck_shenandoah",   "bldg_exploratory"):  4,
    ("deck_rappahannock", "bldg_enterprise"):   5,
    ("deck_rappahannock", "bldg_johnson"):       8,
    ("deck_rappahannock", "bldg_exploratory"):   9,
    ("deck_mason_pond",   "bldg_enterprise"):   12,
    ("deck_mason_pond",   "bldg_johnson"):        7,
    ("deck_mason_pond",   "bldg_exploratory"):   10,
    ("lot_a",             "bldg_enterprise"):     3,
    ("lot_a",             "bldg_johnson"):        11,
    ("lot_a",             "bldg_exploratory"):    14,
    ("lot_k",             "bldg_enterprise"):      8,
    ("lot_k",             "bldg_johnson"):         5,
    ("lot_k",             "bldg_exploratory"):     6,
}

WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI"]
HOURS = [f"{h:02d}" for h in range(7, 18)]  # "07" .. "17"

# Simulated hourly availability shape per lot. Each entry maps hour -> percent.
# Values reflect a prototype weekday pattern: popular/close decks fill during
# the 09:00-11:00 rush and recover after ~13:00; peripheral lots stay more
# available throughout. SIMULATED — not real GMU data.
_AVAIL_SHAPES = {
    # Close & popular: fills hard mid-morning, recovers afternoon.
    "deck_shenandoah": {
        "07": 85, "08": 70, "09": 25, "10": 20, "11": 25, "12": 40,
        "13": 55, "14": 75, "15": 80, "16": 85, "17": 90,
    },
    # Moderate demand deck.
    "deck_rappahannock": {
        "07": 80, "08": 65, "09": 40, "10": 35, "11": 40, "12": 50,
        "13": 60, "14": 70, "15": 75, "16": 80, "17": 85,
    },
    # Moderate-high demand deck, fills by 09:00.
    "deck_mason_pond": {
        "07": 82, "08": 60, "09": 30, "10": 28, "11": 32, "12": 45,
        "13": 58, "14": 68, "15": 78, "16": 82, "17": 88,
    },
    # Peripheral Faculty/Staff lot — reliably available.
    "lot_a": {
        "07": 90, "08": 80, "09": 70, "10": 65, "11": 65, "12": 70,
        "13": 72, "14": 78, "15": 82, "16": 88, "17": 92,
    },
    # Peripheral General lot — stays available through the morning rush.
    "lot_k": {
        "07": 88, "08": 75, "09": 65, "10": 60, "11": 60, "12": 65,
        "13": 70, "14": 76, "15": 82, "16": 86, "17": 90,
    },
}

# Friday is modestly more available than Mon-Thu across all lots.
_FRIDAY_BONUS = 8


# ---------------------------------------------------------------------------
# Record builders
# ---------------------------------------------------------------------------

def _clamp(value: int) -> int:
    """Keep an availability percentage within 0-100."""
    return max(0, min(100, value))


def build_building_items() -> list[dict]:
    return [
        {
            "PK": f"BUILDING#{b['building_id']}",
            "SK": "METADATA",
            "building_id": b["building_id"],
            "name": b["name"],
        }
        for b in BUILDINGS
    ]


def build_permit_type_items() -> list[dict]:
    return [
        {
            "PK": f"PERMIT_TYPE#{p['permit_type']}",
            "SK": "METADATA",
            "permit_type": p["permit_type"],
            "display_name": p["display_name"],
        }
        for p in PERMIT_TYPES
    ]


def build_lot_items() -> list[dict]:
    return [
        {
            "PK": f"LOT#{lot['lot_id']}",
            "SK": "METADATA",
            "lot_id": lot["lot_id"],
            "name": lot["name"],
            # Stored as a DynamoDB string set; represented as a Python set so
            # boto3 serialises it to SS. JSON preview converts to a sorted list.
            "accepted_permit_types": set(lot["accepted_permit_types"]),
        }
        for lot in LOTS
    ]


def build_walking_time_items() -> list[dict]:
    items = []
    for (lot_id, building_id), minutes in WALKING_TIMES.items():
        items.append({
            "PK": f"WALK#{lot_id}#{building_id}",
            "SK": "ESTIMATE",
            "lot_id": lot_id,
            "building_id": building_id,
            # Simulated walking-time estimate in minutes.
            "walking_time_minutes": minutes,
        })
    return items


def build_availability_items() -> list[dict]:
    """
    Build one simulated-availability record per (lot, weekday, hour).

    SK format: AVAIL#<DAY>#<HH>, matching db_client.get_availability which is
    called with each lot's candidate ARRIVAL time day/hour (not class start).
    """
    items = []
    for lot_id, shape in _AVAIL_SHAPES.items():
        for day in WEEKDAYS:
            bonus = _FRIDAY_BONUS if day == "FRI" else 0
            for hour in HOURS:
                pct = _clamp(shape[hour] + bonus)
                items.append({
                    "PK": f"LOT#{lot_id}",
                    "SK": f"AVAIL#{day}#{hour}",
                    # Simulated availability percentage (0-100).
                    "availability_score": pct,
                })
    return items


def build_all_items() -> list[dict]:
    return (
        build_building_items()
        + build_permit_type_items()
        + build_lot_items()
        + build_walking_time_items()
        + build_availability_items()
    )


# ---------------------------------------------------------------------------
# DynamoDB write (only runs with --write)
# ---------------------------------------------------------------------------

def write_items(items: list[dict], table_name: str, endpoint_url: str | None) -> None:
    import boto3  # imported lazily so dry-run needs no AWS SDK configured

    kwargs = {}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    table = boto3.resource("dynamodb", **kwargs).Table(table_name)

    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
    print(f"Wrote {len(items)} items to table '{table_name}'.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _json_safe(item: dict) -> dict:
    """Convert sets to sorted lists for JSON preview."""
    out = {}
    for k, v in item.items():
        out[k] = sorted(v) if isinstance(v, set) else v
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="SmartPark seed data generator (simulated prototype data).")
    parser.add_argument("--write", action="store_true", help="Write to DynamoDB. Omit for a dry run.")
    parser.add_argument("--table-name", default="smartpark", help="DynamoDB table name.")
    parser.add_argument("--endpoint-url", default=None, help="DynamoDB endpoint URL (e.g. http://localhost:8000).")
    args = parser.parse_args()

    items = build_all_items()

    if not args.write:
        print("DRY RUN — no data written to AWS. Pass --write to persist.")
        print(f"Total records that would be written: {len(items)}")
        print("\nFirst 5 records (preview):")
        for item in items[:5]:
            print(json.dumps(_json_safe(item)))
        return

    write_items(items, args.table_name, args.endpoint_url)


if __name__ == "__main__":
    main()
