"""
Focused tests for the Bedrock explanation integration and its safe fallback.

Covers:
  1. Successful Bedrock explanation (Converse API) flows into the response.
  2. Bedrock failure (any exception) falls back to the deterministic
     fallback_explainer and the endpoint still returns a successful 200.
  3. The deterministic recommendation (winner, availability, walk, arrival,
     alternatives) is IDENTICAL whether Bedrock succeeds or fails — i.e.
     Bedrock never influences the ranking/selection.

The Bedrock boto3 client is mocked at the boto3 layer so the real
bedrock_client.generate_explanation code path (prompt build + Converse call +
response parse) is exercised. No AWS is contacted.
"""

import json
import os

import pytest

os.environ.setdefault("DYNAMODB_TABLE_NAME", "smartpark-test")
os.environ.setdefault("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
os.environ.setdefault("PARKING_BUFFER_MINUTES", "5")

from shared.models import Building, Lot  # noqa: E402
import shared.bedrock_client as bedrock_client  # noqa: E402
import handler  # noqa: E402


BUILDING = Building("bldg_eng", "Engineering Hall")
LOTS = [
    Lot("lot_1", "North Lot", {"COMMUTER"}),
    Lot("lot_2", "South Lot", {"COMMUTER"}),
    Lot("lot_3", "East Lot", {"COMMUTER"}),
]
WALK = {"lot_1": 4.0, "lot_2": 5.0, "lot_3": 6.0}
AVAIL = {"lot_1": 80, "lot_2": 60, "lot_3": 50}

VALID_BODY = {
    "building_id": "bldg_eng",
    "start_time": "2025-09-15T09:00:00",
    "permit_type": "COMMUTER",
}


def _event(body: dict) -> dict:
    return {"body": json.dumps(body)}


def _data_mocks(mocker):
    """Mock the DynamoDB-backed data layer deterministically."""
    mocker.patch("shared.db_client.get_building", return_value=BUILDING)
    mocker.patch("shared.db_client.get_all_lots", return_value=LOTS)
    mocker.patch(
        "shared.db_client.get_walking_time",
        side_effect=lambda lot_id, _bid: WALK[lot_id],
    )
    mocker.patch(
        "shared.db_client.get_availability",
        side_effect=lambda lot_id, _d, _h: AVAIL[lot_id],
    )


def _fake_converse_response(text: str) -> dict:
    """Shape a Bedrock Converse API response body."""
    return {"output": {"message": {"content": [{"text": text}]}}}


# ---------------------------------------------------------------------------
# 1. Successful Bedrock explanation
# ---------------------------------------------------------------------------
def test_successful_bedrock_explanation(mocker):
    _data_mocks(mocker)

    fake_client = mocker.MagicMock()
    fake_client.converse.return_value = _fake_converse_response(
        "North Lot is your best bet — it usually has plenty of space and is "
        "just a short walk to class."
    )
    mocker.patch("shared.bedrock_client.boto3.client", return_value=fake_client)

    resp = handler.lambda_handler(_event(VALID_BODY), None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])

    # The Bedrock-generated text is used verbatim.
    assert body["recommendation"]["explanation"].startswith("North Lot is your best bet")

    # Converse was called once, with the configured model id and a text prompt.
    fake_client.converse.assert_called_once()
    _, kwargs = fake_client.converse.call_args
    assert kwargs["modelId"] == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert kwargs["messages"][0]["role"] == "user"
    assert "North Lot" in kwargs["messages"][0]["content"][0]["text"]


# ---------------------------------------------------------------------------
# 2. Bedrock failure falls back safely (endpoint still succeeds)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "boom",
    [
        RuntimeError("throttled"),
        Exception("AccessDeniedException"),
        TimeoutError("timed out"),
    ],
)
def test_bedrock_failure_falls_back_and_still_succeeds(mocker, boom):
    _data_mocks(mocker)

    # Converse raises -> bedrock_client wraps as BedrockUnavailableError ->
    # handler catches and uses the deterministic fallback explainer.
    fake_client = mocker.MagicMock()
    fake_client.converse.side_effect = boom
    mocker.patch("shared.bedrock_client.boto3.client", return_value=fake_client)

    resp = handler.lambda_handler(_event(VALID_BODY), None)

    # Endpoint still returns a successful recommendation.
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["recommendation"]["lot_name"] == "North Lot"
    # Fallback explanation is non-empty and deterministic in style.
    expl = body["recommendation"]["explanation"]
    assert isinstance(expl, str) and expl
    assert "recommended" in expl.lower()


# ---------------------------------------------------------------------------
# 3. Deterministic recommendation is identical regardless of Bedrock outcome
# ---------------------------------------------------------------------------
def test_recommendation_identical_whether_bedrock_succeeds_or_fails(mocker):
    _data_mocks(mocker)

    # Run A: Bedrock succeeds.
    ok_client = mocker.MagicMock()
    ok_client.converse.return_value = _fake_converse_response("Some Bedrock text.")
    mocker.patch("shared.bedrock_client.boto3.client", return_value=ok_client)
    body_ok = json.loads(handler.lambda_handler(_event(VALID_BODY), None)["body"])

    # Run B: Bedrock fails -> fallback.
    bad_client = mocker.MagicMock()
    bad_client.converse.side_effect = RuntimeError("down")
    mocker.patch("shared.bedrock_client.boto3.client", return_value=bad_client)
    body_fail = json.loads(handler.lambda_handler(_event(VALID_BODY), None)["body"])

    # Everything EXCEPT the explanation text must be identical. The
    # deterministic algorithm chose these — Bedrock never influences them.
    def strip_explanation(resp_body: dict) -> dict:
        r = dict(resp_body["recommendation"])
        r.pop("explanation")
        return {"recommendation": r, "alternatives": resp_body["alternatives"]}

    assert strip_explanation(body_ok) == strip_explanation(body_fail)

    # Sanity: same winner and same alternative ordering.
    assert body_ok["recommendation"]["lot_name"] == body_fail["recommendation"]["lot_name"] == "North Lot"
    assert [a["lot_name"] for a in body_ok["alternatives"]] == [
        a["lot_name"] for a in body_fail["alternatives"]
    ]

    # The explanations themselves differ (Bedrock text vs fallback text).
    assert body_ok["recommendation"]["explanation"] != body_fail["recommendation"]["explanation"]
