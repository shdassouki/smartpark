"""
Regression tests for start_time parsing in the weekend date/time bug fix.

The frontend now always sends a full ISO datetime (combining a date input
and a time input), so the bare `HH:MM` fallback — which silently used the
Lambda's current UTC date — has been removed from `_parse_start_time`.
These tests confirm the full-ISO paths still work on a weekday, that a
weekend date is correctly reported as `no_availability_data` rather than
crashing or silently succeeding, and that the removed bare `HH:MM` shape
is now a validation error instead of a UTC-today guess.

DynamoDB and Bedrock calls are mocked so no AWS is contacted.
"""

import json
import os

import pytest

# The db/bedrock clients read these at call time; set before importing handler.
os.environ.setdefault("DYNAMODB_TABLE_NAME", "smartpark-test")
os.environ.setdefault("BEDROCK_MODEL_ID", "test-model")
os.environ.setdefault("PARKING_BUFFER_MINUTES", "5")

from shared.models import Building, Lot  # noqa: E402
import handler  # noqa: E402


BUILDING = Building("bldg_eng", "Engineering Hall")

LOTS = [
    Lot("lot_1", "North Lot", {"COMMUTER"}),
    Lot("lot_2", "South Lot", {"COMMUTER"}),
]

WALK = {"lot_1": 4.0, "lot_2": 5.0}
AVAIL = {"lot_1": 80, "lot_2": 60}


def _event(body: dict) -> dict:
    return {"body": json.dumps(body)}


@pytest.fixture
def mocked_pipeline(mocker):
    """Mock all AWS-touching calls with deterministic availability data."""
    mocker.patch("shared.db_client.get_building", return_value=BUILDING)
    mocker.patch("shared.db_client.get_all_lots", return_value=LOTS)
    mocker.patch(
        "shared.db_client.get_walking_time",
        side_effect=lambda lot_id, _bid: WALK[lot_id],
    )
    mocker.patch(
        "shared.db_client.get_availability",
        side_effect=lambda lot_id, _day, _hour: AVAIL[lot_id],
    )
    mocker.patch(
        "shared.bedrock_client.generate_explanation",
        return_value="North Lot is the best balance of availability and distance.",
    )


@pytest.fixture
def mocked_pipeline_no_availability(mocker):
    """Mock the pipeline with no simulated availability data for any lot."""
    mocker.patch("shared.db_client.get_building", return_value=BUILDING)
    mocker.patch("shared.db_client.get_all_lots", return_value=LOTS)
    mocker.patch(
        "shared.db_client.get_walking_time",
        side_effect=lambda lot_id, _bid: WALK[lot_id],
    )
    mocker.patch("shared.db_client.get_availability", return_value=None)


def test_full_iso_with_seconds_on_weekday_succeeds(mocked_pipeline):
    """A full ISO start_time (with seconds) on a Monday still works."""
    body = {
        "building_id": "bldg_eng",
        "start_time": "2025-09-15T09:00:00",
        "permit_type": "COMMUTER",
    }
    resp = handler.lambda_handler(_event(body), None)
    assert resp["statusCode"] == 200
    rec = json.loads(resp["body"])["recommendation"]
    assert rec["lot_name"] == "North Lot"


def test_full_iso_without_seconds_on_weekday_succeeds(mocked_pipeline):
    """A full ISO start_time without seconds on the same Monday still parses."""
    body = {
        "building_id": "bldg_eng",
        "start_time": "2025-09-15T09:00",
        "permit_type": "COMMUTER",
    }
    resp = handler.lambda_handler(_event(body), None)
    assert resp["statusCode"] == 200
    rec = json.loads(resp["body"])["recommendation"]
    assert rec["lot_name"] == "North Lot"


def test_weekend_date_returns_no_availability_data(mocked_pipeline_no_availability):
    """
    A Saturday date with no simulated availability data for any eligible lot
    returns 422 no_availability_data — the regression test for the weekend bug.
    """
    body = {
        "building_id": "bldg_eng",
        "start_time": "2025-09-13T09:00:00",
        "permit_type": "COMMUTER",
    }
    resp = handler.lambda_handler(_event(body), None)
    assert resp["statusCode"] == 422
    err = json.loads(resp["body"])
    assert err["error"] == "no_availability_data"


def test_legacy_bare_hhmm_is_rejected():
    """
    The removed bare HH:MM fallback no longer silently uses the server's
    current UTC date — it's now a 400 validation error.
    """
    body = {
        "building_id": "bldg_eng",
        "start_time": "09:00",
        "permit_type": "COMMUTER",
    }
    resp = handler.lambda_handler(_event(body), None)
    assert resp["statusCode"] == 400
    err = json.loads(resp["body"])
    assert err["error"] == "validation_error"
    assert "start_time" in err["fields"]
