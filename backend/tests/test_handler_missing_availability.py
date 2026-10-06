"""
Tests for how the handler treats missing availability data (None).

- Lots whose availability is None must be skipped before scoring.
- If every eligible lot lacks data, the existing no-eligible-lots path (404)
  is reused.
- Normal daytime behavior (all lots have data) is unaffected.

DynamoDB and Bedrock are mocked — no AWS is contacted.
"""

import json
import os

import pytest

os.environ.setdefault("DYNAMODB_TABLE_NAME", "smartpark-test")
os.environ.setdefault("BEDROCK_MODEL_ID", "test-model")
os.environ.setdefault("PARKING_BUFFER_MINUTES", "5")

from shared.models import Building, Lot  # noqa: E402
import handler  # noqa: E402


BUILDING = Building("bldg_eng", "Engineering Hall")
LOTS = [
    Lot("lot_1", "North Lot", {"COMMUTER"}),
    Lot("lot_2", "South Lot", {"COMMUTER"}),
    Lot("lot_3", "East Lot", {"COMMUTER"}),
]
WALK = {"lot_1": 4.0, "lot_2": 5.0, "lot_3": 6.0}

VALID_BODY = {
    "building_id": "bldg_eng",
    "start_time": "2025-09-15T09:00:00",
    "permit_type": "COMMUTER",
}


def _event(body: dict) -> dict:
    return {"body": json.dumps(body)}


def _base_mocks(mocker):
    mocker.patch("shared.db_client.get_building", return_value=BUILDING)
    mocker.patch("shared.db_client.get_all_lots", return_value=LOTS)
    mocker.patch(
        "shared.db_client.get_walking_time",
        side_effect=lambda lot_id, _bid: WALK[lot_id],
    )
    mocker.patch(
        "shared.bedrock_client.generate_explanation",
        return_value="Explanation.",
    )


def test_lots_with_missing_availability_are_skipped(mocker):
    """
    lot_2 has availability data; lot_1 and lot_3 are missing (None).
    Only lot_2 should be scored and therefore recommended, and there should
    be no alternatives (the other two were skipped, not scored as 0%).
    """
    _base_mocks(mocker)
    avail_map = {"lot_1": None, "lot_2": 70, "lot_3": None}
    mocker.patch(
        "shared.db_client.get_availability",
        side_effect=lambda lot_id, _d, _h: avail_map[lot_id],
    )

    resp = handler.lambda_handler(_event(VALID_BODY), None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])

    # Only the lot with data is recommended.
    assert body["recommendation"]["lot_name"] == "South Lot"
    assert body["recommendation"]["availability_percentage"] == 70
    # The two missing-data lots were skipped, not surfaced as 0% alternatives.
    assert body["alternatives"] == []


def test_all_missing_availability_returns_422_time_specific(mocker):
    """
    If eligible lots exist but NONE have availability data for the requested
    time, return the distinct 422 no_availability_data response (not the 404
    no_eligible_lots path), with the time-specific user message.
    """
    _base_mocks(mocker)
    mocker.patch("shared.db_client.get_availability", return_value=None)

    resp = handler.lambda_handler(_event(VALID_BODY), None)
    assert resp["statusCode"] == 422
    body = json.loads(resp["body"])
    assert body["error"] == "no_availability_data"
    # Exact user-facing message, including the supported time window.
    assert body["message"] == (
        "Availability estimates aren't available for this time yet. "
        "Please choose a time between 7:00 AM and 5:00 PM."
    )
    # Must NOT be conflated with the no-eligible-lots case.
    assert body["error"] != "no_eligible_lots"


def test_real_zero_availability_is_still_scored(mocker):
    """
    A genuine 0% (stored, not missing) must still participate in scoring —
    it is a real prediction, not missing data.
    """
    _base_mocks(mocker)
    # lot_1 real 0, lot_2 real 60, lot_3 real 50.
    avail_map = {"lot_1": 0, "lot_2": 60, "lot_3": 50}
    mocker.patch(
        "shared.db_client.get_availability",
        side_effect=lambda lot_id, _d, _h: avail_map[lot_id],
    )

    resp = handler.lambda_handler(_event(VALID_BODY), None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])

    # All three were scored, so there are two alternatives.
    assert len(body["alternatives"]) == 2
    # The 0% lot appears somewhere in the response (scored, not skipped).
    names = [body["recommendation"]["lot_name"]] + [
        a["lot_name"] for a in body["alternatives"]
    ]
    assert "North Lot" in names  # the real-0% lot


def test_normal_daytime_behavior_unaffected(mocker):
    """All lots have data -> winner + two alternatives, as before."""
    _base_mocks(mocker)
    avail_map = {"lot_1": 80, "lot_2": 60, "lot_3": 50}
    mocker.patch(
        "shared.db_client.get_availability",
        side_effect=lambda lot_id, _d, _h: avail_map[lot_id],
    )

    resp = handler.lambda_handler(_event(VALID_BODY), None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])

    # North Lot: 80-6*4=56 wins; South 60-6*5=30; East 50-6*6=14.
    assert body["recommendation"]["lot_name"] == "North Lot"
    assert body["recommendation"]["availability_percentage"] == 80
    assert len(body["alternatives"]) == 2


def test_no_eligible_lots_still_returns_404(mocker):
    """
    A genuinely ineligible permit (matches no lots) must still return the
    404 no_eligible_lots path — distinct from the 422 availability-time case.
    """
    mocker.patch("shared.db_client.get_building", return_value=BUILDING)
    mocker.patch("shared.db_client.get_all_lots", return_value=LOTS)
    # No AWS calls needed beyond eligibility; permit matches nothing.
    body_req = {**VALID_BODY, "permit_type": "NOPE"}

    resp = handler.lambda_handler(_event(body_req), None)
    assert resp["statusCode"] == 404
    body = json.loads(resp["body"])
    assert body["error"] == "no_eligible_lots"
    assert body["error"] != "no_availability_data"
