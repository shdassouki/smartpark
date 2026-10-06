"""
Bedrock client — generates a plain-language explanation of the parking
recommendation using Amazon Bedrock.

The winning lot is determined entirely by the deterministic scoring module
before this function is called. Bedrock only writes an explanation — it
never selects or changes the recommendation.

The model ID is read from the BEDROCK_MODEL_ID environment variable.
Raises InternalError at call time if the variable is not set.

Uses the Bedrock Converse API, which provides a single request/response
shape that works across all supported Bedrock model families.
"""

import os

import boto3

from shared.exceptions import BedrockUnavailableError, InternalError
from shared.models import ScoredLot


def _get_model_id() -> str:
    """
    Return the Bedrock model ID from the BEDROCK_MODEL_ID environment variable.
    Raises InternalError if the variable is not set.
    """
    model_id = os.environ.get("BEDROCK_MODEL_ID")
    if not model_id:
        raise InternalError(
            "BEDROCK_MODEL_ID environment variable is not set. "
            "Set it to a supported Bedrock model ID before calling this function."
        )
    return model_id


def _build_prompt(
    winner: ScoredLot,
    runner_ups: list[ScoredLot],
    building_name: str,
    start_time_str: str,
) -> str:
    """
    Build the structured prompt sent to Bedrock.

    Availability is presented as a percentage. The prompt explicitly states
    that data is simulated/historical and instructs the model not to invent
    any facts not provided.
    """
    runner_up_lines = ""
    for ru in runner_ups[:2]:
        runner_up_lines += (
            f"- {ru.lot.name}: availability {ru.availability_percentage}%, "
            f"walking {ru.walking_time_minutes:.0f} min\n"
        )
    if not runner_up_lines:
        runner_up_lines = "- None\n"

    prompt = (
        f"You are a helpful parking assistant for a university campus.\n\n"
        f"A student needs to park near {building_name} for a class starting at {start_time_str}.\n"
        f"The recommended parking lot is {winner.lot.name}.\n\n"
        f"Here is why this lot was recommended:\n"
        f"- Predicted availability: {winner.availability_percentage}% (higher is better)\n"
        f"- Estimated walking time: {winner.walking_time_minutes:.0f} minutes\n\n"
        f"Runner-up lots considered:\n"
        f"{runner_up_lines}\n"
        "IMPORTANT: The availability data above is simulated/historical prototype data, "
        "not live or real-time information. Do not invent, infer, or describe any parking "
        "conditions, lot details, or facts that are not explicitly provided above.\n\n"
        f"Write a 2-3 sentence explanation for the student describing why {winner.lot.name} "
        "was recommended over the alternatives. Focus on the tradeoff between availability "
        "and walking time. Keep the language friendly and direct. Do not mention numerical "
        'scores or percentages — describe availability in plain language (e.g. "tends to '
        'have plenty of space" or "is usually quite full"). Do not make up any details.'
    )

    return prompt


def generate_explanation(
    winner: ScoredLot,
    runner_ups: list[ScoredLot],
    building_name: str,
    start_time_str: str,
) -> str:
    """
    Call Amazon Bedrock to generate a plain-language explanation of the
    parking recommendation.

    The winning lot has already been selected by the scoring module before
    this function is called. This function only generates explanatory text.

    Parameters
    ----------
    winner : ScoredLot
        The top-ranked lot selected by the scoring module.
    runner_ups : list[ScoredLot]
        Up to two other scored lots for context (may be empty).
    building_name : str
        Human-readable name of the destination building.
    start_time_str : str
        Formatted class start time string, e.g. "9:00 AM".

    Returns
    -------
    str
        A plain-language explanation string.

    Raises
    ------
    BedrockUnavailableError
        If Bedrock cannot be reached or returns an unexpected response.
        The caller should fall back to fallback_explainer.
    """
    model_id = _get_model_id()
    prompt = _build_prompt(winner, runner_ups, building_name, start_time_str)

    try:
        client = boto3.client("bedrock-runtime")
        response = client.converse(
            modelId=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ],
            inferenceConfig={
                "maxTokens": 300,
                "temperature": 0.3,
            },
        )
        explanation = response["output"]["message"]["content"][0]["text"].strip()
        if not explanation:
            raise BedrockUnavailableError("Bedrock returned an empty response.")
        return explanation

    except BedrockUnavailableError:
        raise
    except Exception as exc:
        raise BedrockUnavailableError(
            f"Bedrock call failed: {type(exc).__name__}: {exc}"
        ) from exc
