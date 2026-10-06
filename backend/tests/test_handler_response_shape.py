"""
Focused tests for the POST /recommend success response SHAPE.

These verify the enriched nested response (recommendation + alternatives)
without re-testing the scoring/eligibility/arrival logic, which have their
own coverage. The DynamoDB and Bedrock calls are mocked so no AWS is contacted.
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

# Three eligible lots so the response has a winner + two alternatives.
LOTS = [
    Lot("lot_1", "North Lot", {"COMMUTER"}),
    Lot("lot_2", "South Lot", {"COMMUTER"}),
    Lot("lot_3", "East Lot", {"COMMUTER"}),
]

# Chosen so North Lot wins clearly: 80 - 6*4 = 56 vs South 60-6*5=30 vs East 50-6*6=14.
WALK = {"lot_1": 4.0, "lot_2": 5.0, "lot_3": 6.0}
AVAIL = {"lot_1": 80, "lot_2": 60, "lot_3": 50}

VALID_BODY = {
    "building_id": "bldg_eng",
    "start_time": "2025-09-15T09:00:00",
    "permit_type": "COMMUTER",
}


def _event(body: dict) -> dict:
    return {"body": json.dumps(body)}


@pytest.fixture
def mocked_pipeline(mocker):
    """Mock all AWS-touching calls with deterministic data."""
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


def test_success_response_top_level_shape(mocked_pipeline):
    resp = handler.lambda_handler(_event(VALID_BODY), None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])

    # Top-level keys are exactly recommendation + alternatives.
    assert set(body.keys()) == {"recommendation", "alternatives"}


def test_recommendation_object_fields(mocked_pipeline):
    body = json.loads(handler.lambda_handler(_event(VALID_BODY), None)["body"])
    rec = body["recommendation"]

    # Exact field set — no internal score leaked.
    assert set(rec.keys()) == {
        "lot_name",
        "availability_percentage",
        "walking_time_minutes",
        "permit_eligible",
        "arrival_time",
        "explanation",
        "simulated_data",
    }
    assert "composite_score" not in rec
    assert "score" not in rec

    # Winner is North Lot with its pipeline-computed values.
    assert rec["lot_name"] == "North Lot"
    assert rec["availability_percentage"] == 80
    assert rec["walking_time_minutes"] == 4.0  # not rounded
    assert rec["permit_eligible"] is True
    assert rec["simulated_data"] is True
    assert isinstance(rec["arrival_time"], str) and rec["arrival_time"]
    assert isinstance(rec["explanation"], str) and rec["explanation"]


def test_alternatives_shape_and_order(mocked_pipeline):
    body = json.loads(handler.lambda_handler(_event(VALID_BODY), None)["body"])
    alts = body["alternatives"]

    # Up to two runner-ups; here exactly two.
    assert isinstance(alts, list)
    assert len(alts) == 2

    for alt in alts:
        assert set(alt.keys()) == {
            "lot_name",
            "availability_percentage",
            "walking_time_minutes",
            "permit_eligible",
        }
        assert "composite_score" not in alt
        assert "score" not in alt
        assert alt["permit_eligible"] is True

    # Runner-ups in score order: South Lot (30) then East Lot (14).
    assert alts[0]["lot_name"] == "South Lot"
    assert alts[1]["lot_name"] == "East Lot"
    # Raw walking times preserved (not rounded).
    assert alts[0]["walking_time_minutes"] == 5.0
    assert alts[1]["walking_time_minutes"] == 6.0


def test_fallback_explanation_preserves_response_shape(mocked_pipeline, mocker):
    """If Bedrock fails, response shape is identical and still has an explanation."""
    from shared.exceptions import BedrockUnavailableError

    mocker.patch(
        "shared.bedrock_client.generate_explanation",
        side_effect=BedrockUnavailableError("down"),
    )

    resp = handler.lambda_handler(_event(VALID_BODY), None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])

    assert set(body.keys()) == {"recommendation", "alternatives"}
    rec = body["recommendation"]
    assert rec["lot_name"] == "North Lot"
    # Fallback explainer still produces a non-empty explanation.
    assert isinstance(rec["explanation"], str) and rec["explanation"]
    assert "recommended" in rec["explanation"].lower()
