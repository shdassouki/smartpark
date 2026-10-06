"""
Core data models for the SmartPark recommendation pipeline.

Using dataclasses instead of plain dicts gives each stage of the pipeline
a fixed, typed structure — making the code easier to follow and reducing
the risk of silent bugs from misspelled keys.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Lot:
    """
    A parking lot record as stored in DynamoDB.
    Used by the eligibility filter and as the basis for ScoredLot.
    """

    lot_id: str
    name: str
    accepted_permit_types: set[str]


@dataclass
class Building:
    """
    A campus destination building record as stored in DynamoDB.
    Looked up once by the handler and passed through the pipeline.
    """

    building_id: str
    name: str


@dataclass
class ScoredLot:
    """
    A parking lot that has been through the full per-lot pipeline:
    walking time retrieved, candidate arrival time computed, availability
    looked up, and composite score calculated.

    candidate_arrival_time is stored here so the handler can use it
    directly as the arrival guidance without recomputing it.
    """

    lot: Lot
    composite_score: float
    walking_time_minutes: float
    availability_percentage: int
    candidate_arrival_time: datetime
