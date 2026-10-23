"""
Tests for start_time parsing.

The frontend sends only the selected time as a bare `HH:MM`, which the Lambda
resolves to the current date in the campus timezone (read from CAMPUS_TIMEZONE,
default "America/New_York") — not the server's UTC date, so the resolved
weekday is the campus-local one and the old UTC-weekend bug does not return.
Full ISO 8601 datetimes are still accepted. These tests confirm the full-ISO
paths still work on a weekday, that a weekend date is correctly reported as
`no_availability_data`, and that the restored bare `HH:MM` shape is accepted
and resolved using the campus timezone (with a safe fallback on a misconfigured
timezone name).

DynamoDB and Bedrock calls are mocked so no AWS is contacted.
"""

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

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


def test_bare_hhmm_is_accepted(mocked_pipeline):
    """
    A bare HH:MM start_time is accepted again and resolved to the current date
    in the campus timezone. The mocked availability is constant regardless of
    day/hour, so the resolved date does not affect this success path.
    """
    body = {
        "building_id": "bldg_eng",
        "start_time": "09:00",
        "permit_type": "COMMUTER",
    }
    resp = handler.lambda_handler(_event(body), None)
    assert resp["statusCode"] == 200
    rec = json.loads(resp["body"])["recommendation"]
    assert rec["lot_name"] == "North Lot"


def test_bare_hhmm_resolves_in_campus_timezone():
    """
    _parse_start_time resolves a bare HH:MM to the current date in the campus
    timezone and returns a naive datetime. The expected date is computed the
    same way (same ZoneInfo) so the test is deterministic across a midnight
    boundary and never hardcodes a wall-clock date.
    """
    parsed = handler._parse_start_time("09:00")
    assert parsed is not None
    assert parsed.tzinfo is None
    assert parsed.hour == 9
    assert parsed.minute == 0

    campus_tz = os.environ.get("CAMPUS_TIMEZONE", "America/New_York")
    expected_date = datetime.now(ZoneInfo(campus_tz)).date()
    assert parsed.date() == expected_date


def test_bare_hhmm_bad_timezone_falls_back(monkeypatch):
    """
    A misconfigured CAMPUS_TIMEZONE falls back to America/New_York rather than
    failing to parse, so a valid request is never regressed to an error.
    """
    monkeypatch.setenv("CAMPUS_TIMEZONE", "Not/AZone")
    parsed = handler._parse_start_time("09:00")
    assert parsed is not None
    assert parsed.tzinfo is None
    assert parsed.hour == 9
    assert parsed.minute == 0
    assert parsed.date() == datetime.now(ZoneInfo("America/New_York")).date()
