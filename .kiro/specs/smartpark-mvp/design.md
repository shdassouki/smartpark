# Design Document: SmartPark MVP

## Overview

SmartPark is a serverless, mobile-friendly web application that helps university commuter students find the best available parking lot before class. A student enters their destination building, class start time, and permit type. The system filters ineligible lots, scores eligible ones by balancing predicted availability against walking time, and returns a single recommendation with a plain-language explanation and an arrival time.

This document covers the technical design for the MVP, grounded in the approved requirements and the constraints defined in the steering files.

### Key Design Decisions

- **Single Lambda function** — all backend logic lives in one Lambda, organized into discrete Python modules. This keeps infrastructure minimal while preserving testability of each module in isolation.
- **DynamoDB single-table design** — all entity types (Lots, Buildings, permit rules, availability, walking times) share one table, differentiated by a `PK`/`SK` scheme. The prototype has a small dataset and known access patterns, so a single table keeps infrastructure simple.
- **Deterministic scoring** — the Composite_Score formula uses a fixed, documented constant. Identical inputs always produce identical outputs.
- **Bedrock after selection** — Amazon Bedrock is called only after the winning lot is already determined. It generates a plain-language explanation and has no influence on the ranking.
- **Fallback path always available** — if Bedrock is unreachable or returns an error, a deterministic `Fallback_Explainer` generates the explanation from the same structured data.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Browser (React/Vite)               │
│   ┌─────────────┐   ┌──────────────────────────┐    │
│   │  InputForm  │   │  RecommendationResult /  │    │
│   │  Component  │   │  ErrorState Component    │    │
│   └──────┬──────┘   └───────────▲──────────────┘    │
│          │  POST /recommend      │ JSON response      │
└──────────┼───────────────────────┼───────────────────┘
           │                       │
           ▼                       │
┌──────────────────────────────────────────────────────┐
│              Amazon API Gateway (REST API)            │
│              POST /recommend                         │
└──────────────────────┬───────────────────────────────┘
                       │ Lambda Proxy Integration
                       ▼
┌──────────────────────────────────────────────────────┐
│              AWS Lambda (Python)                     │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │  handler.py  (entry point, request parsing) │    │
│  └───────────────────┬─────────────────────────┘    │
│                      │                               │
│         ┌────────────▼────────────┐                 │
│         │  recommendation/        │                 │
│         │  ├── eligibility.py     │                 │
│         │  ├── scoring.py         │                 │
│         │  └── arrival_time.py    │                 │
│         └────────────┬────────────┘                 │
│                      │                               │
│         ┌────────────▼────────────┐                 │
│         │  shared/                │                 │
│         │  ├── db_client.py       │                 │
│         │  ├── bedrock_client.py  │                 │
│         │  └── fallback_explainer.py│               │
│         └─────────┬────────────┬──┘                 │
└───────────────────┼────────────┼────────────────────┘
                    │            │
          ┌─────────▼──┐   ┌────▼──────────┐
          │  Amazon    │   │  Amazon        │
          │  DynamoDB  │   │  Bedrock       │
          │  (data)    │   │  (explanation) │
          └────────────┘   └───────────────┘
```

AWS Amplify Hosting serves the compiled React/Vite frontend as static assets. All backend infrastructure is serverless — no containers, no EC2 instances, no long-running servers.

---

## Components and Interfaces

### Frontend Components

#### `InputForm`
- Renders three controlled inputs: destination building selector, class/event start time picker, and permit type selector.
- Building and permit type options are loaded from the API at startup (or from a static configuration file seeded from DynamoDB export) — they are never free-text fields.
- On submit, validates that all three fields are populated. Displays a field-level error message for each missing field without submitting to the API.
- On valid submit, fires a POST request to the API and transitions to a loading state.

#### `RecommendationResult`
- Receives the successful API response and renders: lot name, arrival time guidance (using the prescribed phrasing from Req 4.4), and the plain-language explanation.
- Always renders `DisclaimerBanner`.
- Provides a "Search again" affordance to return to `InputForm`.

#### `ErrorState`
- Renders for both the "no eligible lots" error (404) and any other error (4xx/5xx).
- For the no-eligible-lots case: informs the student no lots are available and suggests verifying their permit type.
- For all other errors: shows a descriptive message and a button that returns to `InputForm`.

#### `DisclaimerBanner`
- A persistent, visually distinct banner rendered on every screen where availability information is present.
- Text: *"Availability data is simulated/historical and is not live or real-time."*
- Must not be dismissible.

#### `App` (root)
- Manages top-level view state: `idle | loading | success | error`.
- Passes callbacks down to `InputForm`; passes API response data to `RecommendationResult` or `ErrorState`.

### Backend Modules

#### `handler.py`
- Lambda entry point. Parses the API Gateway proxy event, validates the request body, invokes the recommendation pipeline, and serializes the response.
- Responsible for mapping internal errors to the correct HTTP status codes.

#### `recommendation/eligibility.py`
- Implements the `Eligibility_Filter`.
- Input: list of all Lot records, student's `permit_type`.
- Output: filtered list of Lots whose `accepted_permit_types` includes the student's permit type.
- Raises `NoEligibleLotsError` if the filtered list is empty.

#### `recommendation/scoring.py`
- Implements the `Composite_Score` formula (see Data Models section for the formula).
- Input: list of eligible Lots with their precomputed walking times to the destination building, and availability percentages for the requested time slot.
- Output: list of `(lot, composite_score)` tuples, sorted descending by score, with walking time as tiebreaker.
- Pure function — no I/O, fully deterministic.
- Defines `WALK_PENALTY` as a named constant (default `10`); this constant can be adjusted without changing formula logic.

#### `recommendation/arrival_time.py`
- Computes `Arrival_Time` from `start_time`, `walking_time_minutes`, and `parking_buffer_minutes`.
- `parking_buffer_minutes` is read from an environment variable; defaults to `5`.
- Returns a formatted clock time string (e.g., `"8:45 AM"`).

#### `shared/db_client.py`
- Wraps DynamoDB reads. Exposes:
  - `get_all_lots()` → list of Lot records
  - `get_building(building_id)` → single Building record
  - `get_availability(lot_id, day_of_week, hour)` → `availability_percentage` (integer 0–100)
  - `get_walking_time(lot_id, building_id)` → `walking_time_minutes` (float)

#### `shared/bedrock_client.py`
- Calls Amazon Bedrock (Claude model via Bedrock's `invoke_model` API) with a structured prompt.
- Returns the explanation string.
- Raises `BedrockUnavailableError` on any Bedrock exception.

#### `shared/fallback_explainer.py`
- Pure function. Takes `winner_lot`, `runner_up_lots` (up to 2), and returns a deterministic explanation string.
- No external calls. Always succeeds.

---

## Data Models

### DynamoDB Table Design

**Table name:** `smartpark`
**Billing mode:** On-demand (pay-per-request).
**Design rationale:** The prototype has a small dataset and known access patterns, so a single table keeps infrastructure simple.

All entities share one table using a generic `PK` / `SK` key scheme.

#### Lot Record

| Attribute | Type | Description |
|---|---|---|
| `PK` | String | `"LOT#<lot_id>"` |
| `SK` | String | `"METADATA"` |
| `lot_id` | String | Unique lot identifier |
| `name` | String | Human-readable lot name |
| `accepted_permit_types` | StringSet | Set of permit type strings from the seed dataset |

#### Availability Record (historical, by time slot)

| Attribute | Type | Description |
|---|---|---|
| `PK` | String | `"LOT#<lot_id>"` |
| `SK` | String | `"AVAIL#<day_of_week>#<hour>"` (e.g., `"AVAIL#MON#09"`) |
| `availability_score` | Number | Integer 0–100; higher = more available |

`day_of_week` values: `MON`, `TUE`, `WED`, `THU`, `FRI`, `SAT`, `SUN`
`hour` values: zero-padded 24-hour integer, `"07"` through `"21"`.

> Note: `availability_score` is stored as an integer 0–100 (availability_percentage) to match the scoring formula directly, avoiding a unit conversion step at query time.

#### Building Record

| Attribute | Type | Description |
|---|---|---|
| `PK` | String | `"BUILDING#<building_id>"` |
| `SK` | String | `"METADATA"` |
| `building_id` | String | Unique building identifier |
| `name` | String | Human-readable building name |

#### Walking Time Record

| Attribute | Type | Description |
|---|---|---|
| `PK` | String | `"WALK#<lot_id>#<building_id>"` |
| `SK` | String | `"ESTIMATE"` |
| `lot_id` | String | Lot identifier |
| `building_id` | String | Building identifier |
| `walking_time_minutes` | Number | Simulated walking time estimate (e.g., `3.5`) |

> Walking times are precomputed simulated estimates stored at seed time. A production version could replace these with a routing service (e.g., Google Maps Distance Matrix API or AWS Location Service).

#### Permit Type Record

| Attribute | Type | Description |
|---|---|---|
| `PK` | String | `"PERMIT_TYPE#<permit_type>"` |
| `SK` | String | `"METADATA"` |
| `permit_type` | String | Permit type string |
| `display_name` | String | Human-readable label for the frontend selector |

#### Access Patterns

| Use case | Key condition |
|---|---|
| Load all lots | Scan with `begins_with(PK, "LOT#")` and `SK = "METADATA"` |
| Load availability for one lot at a time slot | `PK = "LOT#<id>"`, `SK = "AVAIL#<day>#<hour>"` |
| Load a building | `PK = "BUILDING#<id>"`, `SK = "METADATA"` |
| Load all buildings (for frontend selector) | Scan with `begins_with(PK, "BUILDING#")` |
| Load all permit types (for frontend selector) | Scan with `begins_with(PK, "PERMIT_TYPE#")` |
| Get walking time for lot→building pair | `PK = "WALK#<lot_id>#<building_id>"`, `SK = "ESTIMATE"` |

> Scans are acceptable for MVP because the dataset is small (≤ 20 lots, ≤ 10 buildings). If the dataset grows, a GSI on entity type should be added.

### Composite_Score Formula

The scoring formula balances two factors: predicted availability (higher is better) and walking time (lower is better).

Walking time for each (lot, building) pair is a precomputed simulated estimate stored in DynamoDB as `walking_time_minutes`. No geographic coordinate calculation is performed at query time.

**Composite_Score formula:**

```
composite_score = availability_percentage - (WALK_PENALTY * walking_time_minutes)
```

Where:
- `availability_percentage` is an integer 0–100 from the Availability Record (higher = more available)
- `walking_time_minutes` is the precomputed simulated estimate from the Walking Time Record
- `WALK_PENALTY` is a named constant defined in `scoring.py`, default value `10`

**Walk Penalty calibration:**

`WALK_PENALTY = 10` is a configurable prototype parameter, not an empirically validated constant. It was chosen to make availability differences of ~10 percentage points comparable in weight to a 1-minute difference in walking time. It is defined as a named constant in `scoring.py` and can be adjusted without changing formula logic.

**Example scores:**
- Lot A: availability=80, walk=3 min → 80 − (10×3) = **50**
- Lot B: availability=60, walk=1 min → 60 − (10×1) = **50** → tie; Lot B wins (shorter walk)
- Lot C: availability=90, walk=5 min → 90 − (10×5) = **40** → loses to both despite highest availability

**Tiebreaker:** When two lots share the same `composite_score`, the lot with the smaller `walking_time_minutes` is ranked higher (Req 3.6).

**Determinism guarantee:** The formula uses only stored integer/float values from DynamoDB — no random elements, no geographic calculations, no time-dependent values beyond the availability slot lookup.

### Arrival_Time Calculation

```
arrival_time = start_time - timedelta(minutes=walking_time_minutes + parking_buffer_minutes)
```

- `parking_buffer_minutes` is sourced from the `PARKING_BUFFER_MINUTES` environment variable (default: `5`).
- The result is formatted as a 12-hour clock string with AM/PM: `"8:45 AM"`.
- `start_time` is passed as an ISO 8601 string (e.g., `"2025-09-15T09:00:00"`) and parsed in the Lambda handler. If the student provides only a time-of-day (HH:MM), the handler uses the current date in the local campus timezone.

---

## API Contract

### Endpoint

```
POST /recommend
```

Content-Type: `application/json`

### Request Body

```json
{
  "building_id": "string",
  "start_time": "string",
  "permit_type": "string"
}
```

### Success Response — 200 OK

```json
{
  "lot_name": "string",
  "arrival_time": "string",
  "explanation": "string",
  "simulated_data": true
}
```

### Error Responses

| HTTP Status | Condition | Response body shape |
|---|---|---|
| `400 Bad Request` | Missing or malformed required field(s) | `{"error": "validation_error", "message": "...", "fields": ["field1", ...]}` |
| `404 Not Found` | No eligible lots for the given permit type | `{"error": "no_eligible_lots", "message": "No parking lots are available for permit type <X> at this time."}` |
| `500 Internal Server Error` | Unhandled Lambda exception | `{"error": "internal_error", "message": "An unexpected error occurred. Please try again."}` |

### Validation Rules (enforced by `handler.py`)

- `building_id`: must be a non-empty string that resolves to a record in DynamoDB. Returns 400 if not found.
- `start_time`: must be parseable as a time or datetime. Returns 400 if unparseable.
- `permit_type`: must be a non-empty string. Returns 400 if missing or empty. An unknown permit type will naturally result in a 404 (zero eligible lots) rather than a 400.

---

## Bedrock Integration

### When Bedrock Is Called

Bedrock is called **only after** the recommendation winner has been selected and `Arrival_Time` has been computed. It receives structured data and returns only an explanation string. It has no influence on ranking or selection.

### Prompt Structure

The prompt uses availability as a percentage (0–100) throughout. Decimal scores are not used.

```
You are a helpful parking assistant for a university campus.

A student needs to park near [Building Name] for a class starting at [Start Time].
The recommended parking lot is [Lot Name].

Here is why this lot was recommended:
- Predicted availability: [XX]% (higher is better)
- Estimated walking time: [N] minutes

Runner-up lots considered:
- [Lot 2 Name]: availability [XX]%, walking [N] min
- [Lot 3 Name]: availability [XX]%, walking [N] min  (if applicable)

Write a 2–3 sentence explanation for the student describing why [Lot Name] was recommended
over the alternatives. Focus on the tradeoff between availability and walking time.
Keep the language friendly and direct. Do not mention scores — describe them in plain language.
```

### Fallback Path

If `bedrock_client.py` raises any exception, the Lambda catches it and calls `fallback_explainer.py` instead.

```python
def generate_fallback_explanation(winner, runner_ups):
    avail_desc = _describe_availability(winner.availability_percentage)
    walk_desc = f"{winner.walking_time_minutes} minute walk"
    explanation = (
        f"{winner.name} is recommended because it has {avail_desc} predicted availability "
        f"and is a {walk_desc} from your destination."
    )
    if runner_ups:
        explanation += (
            f" Compared to nearby alternatives, it offers the best balance of "
            f"availability and walking distance."
        )
    return explanation

def _describe_availability(percentage):
    if percentage >= 75:
        return "high"
    elif percentage >= 45:
        return "moderate"
    else:
        return "low"
```

---

## Error Handling

| Error condition | Handler | HTTP response |
|---|---|---|
| Missing request field | `handler.py` validation | 400, field list in body |
| Unknown `building_id` | `db_client.get_building()` raises `BuildingNotFoundError` | 400 |
| No eligible lots | `eligibility.py` raises `NoEligibleLotsError` | 404 |
| DynamoDB read failure | Logged; re-raised as `InternalError` | 500 |
| Bedrock unavailable | `BedrockUnavailableError` caught; fallback invoked | 200 (recommendation still returned) |
| Unhandled exception | Lambda top-level try/except logs and returns 500 | 500 |

---

## Testing Strategy

### Unit Tests (pytest)

**`recommendation/eligibility.py`**
- Lots with matching permit type are retained
- Lots without matching permit type are excluded
- `NoEligibleLotsError` raised when filter produces empty list
- Mixed permit type sets handled correctly

**`recommendation/scoring.py`**
- Composite score formula: `composite_score = availability_percentage - (WALK_PENALTY * walking_time_minutes)`
- `WALK_PENALTY` constant is used (not hardcoded in tests — reference it by name)
- Tiebreaker: equal scores resolved by shorter walking time
- Degenerate case: single eligible lot returns that lot

**`recommendation/arrival_time.py`**
- Arrival time computed correctly for various walking times and buffer values
- Output formatted as 12-hour clock string
- Buffer defaults to 5 when environment variable not set

**`shared/db_client.py`**
- `get_walking_time(lot_id, building_id)` returns a float

**`shared/fallback_explainer.py`**
- Returns non-empty string for any valid winner input
- Availability descriptions map correctly to percentage ranges (≥75 = high, ≥45 = moderate, <45 = low)
- Runner-up sentence included when runner-ups present; omitted otherwise

**Frontend (Vitest + React Testing Library)**
- `InputForm` shows field-level errors when submitted empty
- `InputForm` does not call the API when fields are missing
- `RecommendationResult` renders lot name, arrival time, explanation, and disclaimer
- `ErrorState` renders correct message for no-eligible-lots vs. generic error
- `DisclaimerBanner` is present in `RecommendationResult` render tree

### Property-Based Tests (Hypothesis — Python)

Each property is implemented as a single Hypothesis test configured to run a minimum of 100 examples.

### Integration Tests

- POST `/recommend` with a valid seeded dataset returns a 200 with all required fields.
- POST `/recommend` with an unknown permit type returns a 404.
- POST `/recommend` with a missing field returns a 400.
- Bedrock mock returning an error results in a 200 using the fallback explanation.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Each test is tagged with the format:
```python
# Feature: smartpark-mvp, Property N: <property title>
```

### Property 1: Eligibility filter produces only permitted lots

*For any* list of lots (each with an arbitrary set of accepted permit types) and any permit type string, every lot returned by the `Eligibility_Filter` must have the queried permit type in its `accepted_permit_types` set. No ineligible lot may appear in the filtered result, and no eligible lot may be absent from it.

**Validates: Requirements 2.1, 2.2, 2.4**

---

### Property 2: All eligible lots receive a composite score

*For any* non-empty list of lots that all pass the `Eligibility_Filter` for a given permit type, the scoring function must return exactly one scored entry per input lot — no eligible lot may be silently dropped from the scoring output.

**Validates: Requirements 3.1**

---

### Property 3: Composite score is deterministic

*For any* list of eligible lots with precomputed walking times and availability percentages, calling the scoring function twice with identical inputs must return identical `composite_score` values for all lots and produce the same ranked order.

**Validates: Requirements 3.4**

---

### Property 4: The recommended lot has the highest composite score

*For any* non-empty list of eligible lots with computed composite scores, the lot returned as the recommendation must have a `composite_score` greater than or equal to every other lot's score. No unselected lot may have a strictly higher score than the recommended lot.

**Validates: Requirements 3.5**

---

### Property 5: Tiebreaker selects the closer lot

*For any* configuration of eligible lots where two or more share the same maximum `composite_score`, the recommended lot must be the one with the minimum `walking_time_minutes` among all tied lots.

**Validates: Requirements 3.6**

---

### Property 6: Arrival time is always strictly before class start time

*For any* class start datetime and any `walking_time_minutes` ≥ 0, combined with any `parking_buffer_minutes` ≥ 0 where `walking_time_minutes + parking_buffer_minutes > 0`, the computed `Arrival_Time` must be strictly earlier than the class start time.

**Validates: Requirements 4.1, 4.2**

---

### Property 7: Arrival time output matches 12-hour clock format

*For any* valid `Arrival_Time` datetime value, the formatted string returned by `arrival_time.py` must match the pattern `H:MM AM` or `H:MM PM` (e.g., `"8:45 AM"`, `"12:00 PM"`). No other format is acceptable.

**Validates: Requirements 4.3**

---

### Property 8: Higher walking time yields a lower composite score (availability held constant)

*For any* two lots with the same `availability_percentage` but different `walking_time_minutes`, the lot with the shorter walking time must have a strictly higher `composite_score`. This property holds for any positive value of `WALK_PENALTY`.

**Validates: Requirements 3.2, 3.3**

---

### Property 9: Recommendation response always contains all required fields

*For any* valid request (known building, parseable start time, permit type that matches at least one lot), the pipeline must return a response object that contains all four required fields — `lot_name` (non-empty string), `arrival_time` (non-empty string), `explanation` (non-empty string), and `simulated_data` (always `true`) — regardless of whether the explanation was generated by Bedrock or the `Fallback_Explainer`.

**Validates: Requirements 5.4, 9.2**
