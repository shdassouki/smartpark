"""
Focused tests for db_client.get_availability missing-data behavior.

Verifies that a missing availability record returns None (distinct from a
real stored 0), so the pipeline never treats "no data" as a real 0%
prediction. DynamoDB is mocked — no AWS is contacted.
"""

import os

os.environ.setdefault("DYNAMODB_TABLE_NAME", "smartpark-test")

import shared.db_client as db_client  # noqa: E402


def test_missing_availability_returns_none(mocker):
    """No matching item -> None (unknown), not 0."""
    fake_table = mocker.MagicMock()
    fake_table.get_item.return_value = {}  # no "Item" key => missing
    mocker.patch("shared.db_client._get_table", return_value=fake_table)

    result = db_client.get_availability("lot_1", "MON", "00")

    assert result is None


def test_real_zero_availability_returns_zero(mocker):
    """A genuinely stored 0 must be preserved as 0, not turned into None."""
    fake_table = mocker.MagicMock()
    fake_table.get_item.return_value = {"Item": {"availability_score": 0}}
    mocker.patch("shared.db_client._get_table", return_value=fake_table)

    result = db_client.get_availability("lot_1", "MON", "09")

    assert result == 0
    assert result is not None


def test_normal_availability_returns_int(mocker):
    """A normal stored value comes back as an int."""
    fake_table = mocker.MagicMock()
    fake_table.get_item.return_value = {"Item": {"availability_score": 75}}
    mocker.patch("shared.db_client._get_table", return_value=fake_table)

    result = db_client.get_availability("lot_1", "MON", "09")

    assert result == 75
