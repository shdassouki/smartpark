"""
Custom exceptions for the SmartPark recommendation pipeline.

Each exception maps to a specific failure condition so that handler.py
can return the correct HTTP status code and error message without
inspecting generic exception types.
"""


class NoEligibleLotsError(Exception):
    """
    Raised by the eligibility filter when no parking lots are available
    for the student's permit type. Maps to HTTP 404.
    """


class BuildingNotFoundError(Exception):
    """
    Raised by the DynamoDB client when the requested building ID does not
    exist in the database. Maps to HTTP 400.
    """


class BedrockUnavailableError(Exception):
    """
    Raised by the Bedrock client when Amazon Bedrock cannot be reached or
    returns an error. The handler catches this and uses the fallback
    explainer instead, so the recommendation is still returned (HTTP 200).
    """


class InternalError(Exception):
    """
    Raised for unexpected failures within SmartPark's own code, such as
    a missing required environment variable or a DynamoDB read failure.
    Maps to HTTP 500.
    """
