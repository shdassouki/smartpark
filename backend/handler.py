# Lambda entry point — request parsing and recommendation pipeline orchestration

import json
import os
from datetime import datetime, date

import shared.db_client as db_client
import shared.bedrock_client as bedrock_client
import shared.fallback_explainer as fallback_explainer
from recommendation import eligibility, scoring
from recommendation import arrival_time
from shared.exceptions import (
    BedrockUnavailableError,
    BuildingNotFoundError,
    NoEligibleLotsError,
)
from shared.models import ScoredLot


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _build_headers() -> dict:
    """
    Build the response headers, including the CORS allow-origin header.

    With API Gateway proxy integration, the actual POST response is passed
    through verbatim, so the Access-Control-Allow-Origin header must be set
    here (the SAM Cors config only covers the OPTIONS preflight).

    The allowed origin is read from the CORS_ALLOW_ORIGIN environment variable
    at call time, defaulting to "*" for local development. In production it can
    be set to the deployed Amplify frontend origin without changing this code.
    """
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": os.environ.get("CORS_ALLOW_ORIGIN", "*"),
    }


def _alternative(scored: "ScoredLot") -> dict:
    """
    Serialise a runner-up ScoredLot into an API alternative entry.

    Uses values already computed by the pipeline. The internal composite_score
    is intentionally omitted. permit_eligible is always True because the lot
    already passed the eligibility hard filter.
    """
    return {
        "lot_name": scored.lot.name,
        "availability_percentage": scored.availability_percentage,
        "walking_time_minutes": scored.walking_time_minutes,
        "permit_eligible": True,
    }


def _ok(body: dict) -> dict:
    """Return a 200 Lambda proxy response."""
    return {
        "statusCode": 200,
        "headers": _build_headers(),
        "body": json.dumps(body),
    }


def _error(status: int, error_code: str, message: str, fields: list[str] | None = None) -> dict:
    """Return a 4xx/5xx Lambda proxy response."""
    body: dict = {"error": error_code, "message": message}
    if fields:
        body["fields"] = fields
    return {
        "statusCode": status,
        "headers": _build_headers(),
        "body": json.dumps(body),
    }


# ---------------------------------------------------------------------------
# Request parsing helpers
# ---------------------------------------------------------------------------

def _parse_start_time(start_time_str: str) -> datetime | None:
    """
    Parse a start time string into a datetime.

    Accepts:
      - HH:MM (24-hour), e.g. "09:00" — date defaults to today
      - ISO 8601 datetime, e.g. "2025-09-15T09:00:00"

    Returns None if the string cannot be parsed.
    """
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(start_time_str, fmt)
        except ValueError:
            pass

    try:
        t = datetime.strptime(start_time_str, "%H:%M").time()
        return datetime.combine(date.today(), t)
    except ValueError:
        pass

    return None


def _parse_request(event: dict) -> tuple[dict | None, dict | None]:
    """
    Parse and validate the Lambda proxy event.

    Returns (parsed_data, error_response).
    Exactly one of these will be None.

    parsed_data keys: building_id (str), start_time (datetime), permit_type (str)
    """
    raw_body = event.get("body") or ""
    try:
        body = json.loads(raw_body)
    except (json.JSONDecodeError, TypeError):
        return None, _error(400, "validation_error", "Request body must be valid JSON.")

    if not isinstance(body, dict):
        return None, _error(400, "validation_error", "Request body must be a JSON object.")

    missing = []
    for field in ("building_id", "start_time", "permit_type"):
        value = body.get(field)
        if not value or not str(value).strip():
            missing.append(field)

    if missing:
        return None, _error(
            400,
            "validation_error",
            f"Missing or empty required field(s): {', '.join(missing)}.",
            fields=missing,
        )

    start_time = _parse_start_time(str(body["start_time"]).strip())
    if start_time is None:
        return None, _error(
            400,
            "validation_error",
            "Invalid start_time format. Use HH:MM (e.g. '09:00') or ISO 8601 (e.g. '2025-09-15T09:00:00').",
            fields=["start_time"],
        )

    parsed = {
        "building_id": str(body["building_id"]).strip(),
        "start_time": start_time,
        "permit_type": str(body["permit_type"]).strip(),
    }
    return parsed, None


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------

def lambda_handler(event: dict, context) -> dict:
    """
    AWS Lambda entry point — full recommendation pipeline.
    """
    # Step 1: parse and validate request
    parsed, err = _parse_request(event)
    if err:
        return err

    building_id: str = parsed["building_id"]
    start_time: datetime = parsed["start_time"]
    permit_type: str = parsed["permit_type"]

    try:
        # Step 2: validate building exists
        building = db_client.get_building(building_id)

        # Step 3: load all lots
        all_lots = db_client.get_all_lots()

        # Step 4: permit eligibility hard filter
        eligible_lots = eligibility.filter_eligible_lots(all_lots, permit_type)

        # Step 5: per-lot candidate arrival time and availability
        parking_buffer = arrival_time.get_parking_buffer()
        lots_with_data = []
        for lot in eligible_lots:
            walk = db_client.get_walking_time(lot.lot_id, building_id)
            candidate_dt = arrival_time.compute_arrival_time(start_time, walk, parking_buffer)
            day_of_week = candidate_dt.strftime("%a").upper()[:3]  # e.g. "MON"
            hour = candidate_dt.strftime("%H")                      # e.g. "09"
            avail = db_client.get_availability(lot.lot_id, day_of_week, hour)
            # None means we have no simulated availability data for this time
            # slot (e.g. a candidate arrival time outside the dataset's hours).
            # Skip the lot so missing data never reaches scoring and is never
            # presented as a real 0% prediction.
            if avail is None:
                continue
            lots_with_data.append({
                "lot": lot,
                "walking_time_minutes": walk,
                "candidate_arrival_time": candidate_dt,
                "availability_percentage": avail,
            })

        # If every eligible lot lacked availability data for the requested
        # time, there is nothing to recommend. Reuse the existing
        # no-eligible-lots path (404).
        if not lots_with_data:
            raise NoEligibleLotsError(
                f"No availability data is available for permit type "
                f"'{permit_type}' at the requested time."
            )

        # Step 6: score and select winner
        scored_lots = scoring.score_lots(lots_with_data)
        winner: ScoredLot = scoring.select_winner(scored_lots)
        runner_ups: list[ScoredLot] = scored_lots[1:3]

        # Step 7: generate explanation (Bedrock with fallback)
        start_time_str = arrival_time.format_arrival_time(start_time)
        try:
            explanation = bedrock_client.generate_explanation(
                winner, runner_ups, building.name, start_time_str
            )
        except BedrockUnavailableError:
            explanation = fallback_explainer.generate_fallback_explanation(
                winner, runner_ups
            )

        # Step 8: format and return response.
        # Every lot here (winner and runner-ups) already passed the permit
        # eligibility hard filter in Step 4, so permit_eligible is always True.
        # The internal composite_score is intentionally NOT exposed.
        arrival_str = arrival_time.format_arrival_time(winner.candidate_arrival_time)
        return _ok({
            "recommendation": {
                "lot_name": winner.lot.name,
                "availability_percentage": winner.availability_percentage,
                "walking_time_minutes": winner.walking_time_minutes,
                "permit_eligible": True,
                "arrival_time": arrival_str,
                "explanation": explanation,
                "simulated_data": True,
            },
            "alternatives": [_alternative(s) for s in runner_ups],
        })

    except BuildingNotFoundError:
        return _error(
            400,
            "building_not_found",
            f"Building '{building_id}' was not found. Please check your selection.",
        )

    except NoEligibleLotsError:
        return _error(
            404,
            "no_eligible_lots",
            f"No parking lots are available for permit type '{permit_type}'.",
        )

    except Exception as exc:
        # Log for CloudWatch; return generic 500 to client
        print(f"ERROR: Unhandled exception: {type(exc).__name__}: {exc}")
        return _error(500, "internal_error", "An unexpected error occurred. Please try again.")
