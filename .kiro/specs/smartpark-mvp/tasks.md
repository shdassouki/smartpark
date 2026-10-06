# Implementation Plan: SmartPark MVP

## Overview

This plan converts the SmartPark MVP design into incremental coding tasks. The implementation follows the layered architecture: data models and DynamoDB client first, then the recommendation pipeline (eligibility → per-lot candidate arrival time → availability lookup → scoring), then the Bedrock/fallback explanation, then the Lambda handler, and finally the React/Vite frontend. Infrastructure and seed data run in parallel with early backend work. Tasks are ordered so each step has all its dependencies in place before it begins.

---

## Tasks

- [x] 1. Set up project structure and tooling
  - [x] 1.1 Initialise backend Python package layout
    - Create `backend/` directory with `handler.py`, `recommendation/` and `shared/` sub-packages (each with `__init__.py`)
    - Add `requirements.txt` pinning `boto3`, `hypothesis`, and `pytest`
    - Add `pytest.ini` or `pyproject.toml` configuring pytest test discovery under `backend/tests/`
    - _Requirements: 9.1_

  - [x] 1.2 Initialise frontend React/Vite project
    - Scaffold with `npm create vite@latest frontend -- --template react-ts`
    - Install `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`
    - Configure `vite.config.ts` for Vitest
    - _Requirements: 1.1, 7.1_

  - [x] 1.3 Add shared custom exception types
    - Create `backend/shared/exceptions.py` defining `NoEligibleLotsError`, `BuildingNotFoundError`, `BedrockUnavailableError`, `InternalError`
    - _Requirements: 2.3, 9.3, 9.4, 9.5_

- [x] 2. Define core Python data types
  - [x] 2.1 Create `Lot`, `Building`, and `ScoredLot` dataclasses
    - In `backend/shared/models.py` define `Lot(lot_id, name, accepted_permit_types)`, `Building(building_id, name)`, `ScoredLot(lot, composite_score, walking_time_minutes, availability_percentage, candidate_arrival_time)`
    - `candidate_arrival_time` is a `datetime` stored on `ScoredLot` so the handler can use it directly without recomputing
    - _Requirements: 3.1, 4.1_

  - [ ]* 2.2 Write unit tests for data models
    - Verify field types, default values, and that `ScoredLot` stores `candidate_arrival_time` as a `datetime`
    - _Requirements: 3.1, 4.1_

- [ ] 3. Implement DynamoDB client
  - [x] 3.1 Implement `shared/db_client.py`
    - Read `DYNAMODB_TABLE_NAME` from environment; raise `InternalError` at module load if missing
    - Implement `get_all_lots() → list[Lot]`
    - Implement `get_building(building_id: str) → Building`; raise `BuildingNotFoundError` if not found
    - Implement `get_availability(lot_id: str, day_of_week: str, hour: str) → int` (0–100)
    - Implement `get_walking_time(lot_id: str, building_id: str) → float`
    - _Requirements: 8.1, 8.2, 9.1_

  - [ ]* 3.2 Write unit tests for `db_client.py`
    - Mock the boto3 DynamoDB resource; verify each function constructs the correct `PK`/`SK` and parses the response correctly
    - Verify `get_building` raises `BuildingNotFoundError` on a missing key
    - Verify `get_walking_time` returns a float
    - _Requirements: 8.1, 8.2_

- [x] 4. Implement eligibility filter
  - [x] 4.1 Implement `recommendation/eligibility.py`
    - `filter_eligible_lots(lots: list[Lot], permit_type: str) → list[Lot]`
    - Retain only lots whose `accepted_permit_types` contains `permit_type`
    - Raise `NoEligibleLotsError` if the result is empty
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 4.2 Write property test for eligibility filter
    - **Property 1: Eligibility filter produces only permitted lots**
    - **Validates: Requirements 2.1, 2.2, 2.4**
    - Use Hypothesis to generate arbitrary lot lists and permit type strings; assert every returned lot contains the queried permit type and no eligible lot is absent
    - _Requirements: 2.1, 2.2, 2.4_

  - [ ]* 4.3 Write unit tests for eligibility filter
    - Test: lots with matching permit type are retained; lots without are excluded; `NoEligibleLotsError` raised on empty result; mixed permit sets handled correctly
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 5. Implement scoring module
  - [x] 5.1 Implement `recommendation/scoring.py`
    - Define `WALK_PENALTY = 6`, `LOW_AVAIL_THRESHOLD = 40`, and `LOW_AVAIL_PENALTY = 20` as named module-level constants
    - `score_lots(lots_with_data: list[dict]) → list[tuple[Lot, float]]`
      - Each dict contains `lot`, `availability_percentage` (int 0–100), and `walking_time_minutes` (float)
      - Formula: `composite_score = availability_percentage - (WALK_PENALTY * walking_time_minutes)`
      - Apply an additional `LOW_AVAIL_PENALTY` deduction when `availability_percentage < LOW_AVAIL_THRESHOLD`
      - Sort descending by `composite_score`; use `walking_time_minutes` ascending as tiebreaker
    - Pure function — no I/O
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 5.2 Write property test: all eligible lots receive a score
    - **Property 2: All eligible lots receive a composite score**
    - **Validates: Requirements 3.1**
    - Use Hypothesis; assert `len(score_lots(input)) == len(input)` for any non-empty input
    - _Requirements: 3.1_

  - [ ]* 5.3 Write property test: scoring is deterministic
    - **Property 3: Composite score is deterministic**
    - **Validates: Requirements 3.4**
    - Call `score_lots` twice with identical inputs; assert scores and order are identical
    - _Requirements: 3.4_

  - [ ]* 5.4 Write property test: recommended lot has highest composite score
    - **Property 4: The recommended lot has the highest composite score**
    - **Validates: Requirements 3.5**
    - Assert the first element of `score_lots` output has `composite_score ≥` all others
    - _Requirements: 3.5_

  - [ ]* 5.5 Write property test: tiebreaker selects closer lot
    - **Property 5: Tiebreaker selects the closer lot**
    - **Validates: Requirements 3.6**
    - Generate inputs where two or more lots share the maximum score; assert the returned winner has the minimum `walking_time_minutes` among tied lots
    - _Requirements: 3.6_

  - [ ]* 5.6 Write property test: higher walking time lowers score
    - **Property 8: Higher walking time yields a lower composite score (availability held constant)**
    - **Validates: Requirements 3.2, 3.3**
    - Generate pairs of lots with identical `availability_percentage` but differing `walking_time_minutes`; assert the lot with lower walking time has strictly higher `composite_score`
    - _Requirements: 3.2, 3.3_

  - [ ]* 5.7 Write unit tests for scoring
    - Test formula correctness using `WALK_PENALTY` constant (not a hardcoded `10`)
    - Test tiebreaker: equal scores resolve to shorter walk
    - Test degenerate case: single eligible lot returns that lot
    - _Requirements: 3.1, 3.4, 3.5, 3.6_

- [x] 6. Implement arrival time module
  - [x] 6.1 Implement `recommendation/arrival_time.py`
    - `compute_arrival_time(start_time: datetime, walking_time_minutes: float, parking_buffer_minutes: int) → datetime`
    - Formula: `arrival_time = start_time - timedelta(minutes=walking_time_minutes + parking_buffer_minutes)`
    - `format_arrival_time(arrival_time: datetime) → str`
    - Format as 12-hour clock string: `"8:45 AM"` (no leading zero on hour)
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ]* 6.2 Write property test: arrival time is strictly before class start
    - **Property 6: Arrival time is always strictly before class start time**
    - **Validates: Requirements 4.1, 4.2**
    - Use Hypothesis; generate start datetimes and non-negative `walking_time_minutes` + `parking_buffer_minutes` where their sum > 0; assert `compute_arrival_time(...) < start_time`
    - _Requirements: 4.1, 4.2_

  - [ ]* 6.3 Write property test: arrival time matches 12-hour clock format
    - **Property 7: Arrival time output matches 12-hour clock format**
    - **Validates: Requirements 4.3**
    - Use Hypothesis; assert `format_arrival_time(...)` matches regex `^\d{1,2}:\d{2} (AM|PM)$`
    - _Requirements: 4.3_

  - [ ]* 6.4 Write unit tests for arrival time
    - Test correct subtraction for various walking times and buffers
    - Test that buffer defaults to `5` when env var `PARKING_BUFFER_MINUTES` is not set
    - Test output format as 12-hour clock string
    - _Requirements: 4.1, 4.2, 4.3_

- [ ] 7. Checkpoint — backend pipeline units complete
  - Ensure all backend unit and property tests pass. Ask the user if any questions arise before proceeding.

- [ ] 8. Implement Bedrock client and fallback explainer
  - [x] 8.1 Implement `shared/fallback_explainer.py`
    - `generate_fallback_explanation(winner: ScoredLot, runner_ups: list[ScoredLot]) → str`
    - Pure function; no external calls
    - Use `_describe_availability(percentage)`: ≥75 → "high", ≥45 → "moderate", <45 → "low"
    - Append runner-up sentence when `runner_ups` is non-empty
    - _Requirements: 5.3, 5.4, 5.5_

  - [ ] 8.2 Write unit tests for `fallback_explainer.py`
    - Test returns non-empty string for any valid winner
    - Test availability description thresholds (≥75, ≥45, <45)
    - Test runner-up sentence present / absent
    - _Requirements: 5.3, 5.5_

  - [x] 8.3 Implement `shared/bedrock_client.py`
    - Read the Bedrock model ID from the `BEDROCK_MODEL_ID` environment variable; raise a configuration error at module load if the variable is not set
    - `generate_explanation(winner: ScoredLot, runner_ups: list[ScoredLot], building_name: str, start_time_str: str) → str`
    - Build the structured prompt using lot name, availability percentage, walking time, and runner-up data
    - Call Bedrock `invoke_model` passing the model ID from `BEDROCK_MODEL_ID` at runtime — do not hardcode any specific model name
    - Raise `BedrockUnavailableError` on any Bedrock exception
    - _Requirements: 5.1, 5.2, 5.5_

  - [ ]* 8.4 Write unit tests for `bedrock_client.py`
    - Mock `boto3` Bedrock runtime; verify the prompt is well-formed and `invoke_model` is called with the model ID from `BEDROCK_MODEL_ID`
    - Verify `BedrockUnavailableError` is raised on a boto3 exception
    - _Requirements: 5.1, 5.2_

- [ ] 9. Implement Lambda handler with per-lot candidate arrival time pipeline
  - [x] 9.1 Implement request parsing and validation in `handler.py`
    - Parse the API Gateway proxy event body; extract `building_id`, `start_time`, `permit_type`
    - Validate: all fields present and non-empty; `start_time` parseable as ISO 8601 datetime (use current date in campus timezone if time-only)
    - Return 400 with `{"error": "validation_error", "message": "...", "fields": [...]}` on failure
    - Validate `building_id` resolves via `db_client.get_building`; return 400 with `BuildingNotFoundError` mapping if not found
    - _Requirements: 1.2, 1.3, 9.1, 9.3_

  - [ ] 9.2 Implement the per-lot candidate arrival time availability pipeline in `handler.py`
    - After validation, fetch all lots via `db_client.get_all_lots()` and apply `eligibility.filter_eligible_lots()`
    - For each eligible lot, execute this pipeline in order:
      1. Call `db_client.get_walking_time(lot_id, building_id)` to retrieve that lot's `walking_time_minutes`
      2. Read `PARKING_BUFFER_MINUTES` from environment (default `5`) to get `parking_buffer_minutes`
      3. Compute `candidate_arrival_time = class_start_time - timedelta(minutes=walking_time_minutes + parking_buffer_minutes)` using `arrival_time.compute_arrival_time()`
      4. Derive `day_of_week` (e.g., `"MON"`) and `hour` (e.g., `"09"`) from `candidate_arrival_time` — **not** from `class_start_time`
      5. Call `db_client.get_availability(lot_id, day_of_week, hour)` using the derived day/hour to get `availability_percentage`
      6. Collect `{lot, availability_percentage, walking_time_minutes, candidate_arrival_time}` for each lot
    - Pass the collected data to `scoring.score_lots()` to rank lots
    - The winner is `score_lots()` result `[0]`; its `candidate_arrival_time` is the arrival guidance — do not recompute it
    - On `NoEligibleLotsError`, return 404 with `{"error": "no_eligible_lots", "message": "..."}`
    - _Requirements: 2.1, 2.2, 3.1–3.6, 4.1, 4.2_

  - [ ]* 9.3 Write property test: response always contains all required fields and arrival_time matches winner's candidate arrival time
    - **Property 9: Recommendation response always contains all required fields**
    - **Validates: Requirements 5.4, 9.2**
    - Use Hypothesis to generate valid request inputs (known building, parseable start time, permit type matching at least one lot)
    - Assert the response object contains `lot_name` (non-empty str), `arrival_time` (non-empty str), `explanation` (non-empty str), and `simulated_data == True`
    - Assert `arrival_time` corresponds to the winner's `candidate_arrival_time` computed using the winner's `walking_time_minutes` and `parking_buffer_minutes` — not the class start time directly
    - _Requirements: 4.1, 4.2, 4.3, 5.4, 9.2_

  - [ ]* 9.4 Write unit tests for `handler.py` pipeline
    - Test missing field returns 400 with correct `fields` list
    - Test unknown `building_id` returns 400
    - Test `NoEligibleLotsError` returns 404
    - Test unhandled exception returns 500
    - Test happy path: correct lot selected, `arrival_time` string present, `simulated_data` is `true`
    - _Requirements: 1.2, 1.3, 2.3, 9.1–9.5_

- [ ] 10. Checkpoint — full backend pipeline
  - Run the full pytest suite; ensure all unit, property, and integration mocks pass. Ask the user if any questions arise before proceeding.

- [ ] 11. Infrastructure as code (AWS SAM / CDK)
  - [x] 11.1 Define DynamoDB table resource
    - Single table `smartpark` with `PK` (String) partition key and `SK` (String) sort key
    - Billing mode: on-demand
    - _Requirements: 8.1_

  - [x] 11.2 Define Lambda function resource and environment variables
    - Runtime: Python 3.12; handler: `handler.lambda_handler`
    - Environment variables: `DYNAMODB_TABLE_NAME`, `PARKING_BUFFER_MINUTES`, `BEDROCK_MODEL_ID`
    - Grant Lambda IAM permissions: `dynamodb:GetItem`, `dynamodb:Scan`, `bedrock:InvokeModel`
    - _Requirements: 9.1, 4.2, 5.1_

  - [x] 11.3 Define API Gateway REST API
    - Single resource `/recommend` with `POST` method using Lambda proxy integration
    - Enable CORS for the frontend origin
    - _Requirements: 9.1_

  - [ ]* 11.4 Write infrastructure smoke test
    - Deploy to a sandbox environment; `curl POST /recommend` with a seeded valid payload; assert HTTP 200 and presence of all required response fields
    - _Requirements: 9.1, 9.2_

- [x] 12. Seed DynamoDB with prototype data
  - [x] 12.1 Write seed script `scripts/seed_dynamodb.py`
    - Seed at least 5 Lot records with `name`, `accepted_permit_types`
    - Seed at least 3 Building records
    - Seed Availability records for each lot covering MON–FRI, hours `07`–`21`
    - Seed Walking Time records for each (lot, building) pair
    - Seed Permit Type records for each valid permit type
    - _Requirements: 8.1, 8.2_

  - [ ]* 12.2 Write unit test for seed script
    - Mock boto3; verify correct `PK`/`SK` patterns are written for each entity type
    - _Requirements: 8.1_

- [ ] 13. Implement `RecommendationResult` and `DisclaimerBanner` frontend components
  - [ ] 13.1 Implement `DisclaimerBanner` component
    - Render a visually distinct, non-dismissible banner with text: *"Availability data is simulated/historical and is not live or real-time."*
    - _Requirements: 6.2, 6.3_

  - [ ] 13.2 Implement `RecommendationResult` component
    - Render lot name, arrival time using prescribed phrasing: *"Arrive at the lot by [Arrival_Time] to make it to class on time, including time to find a spot."*
    - Render the plain-language explanation
    - Always render `DisclaimerBanner`
    - Provide a "Search again" affordance that calls an `onReset` prop
    - _Requirements: 6.1, 4.4_

- [ ] 14. Implement `ErrorState` frontend component
  - [ ] 14.1 Implement `ErrorState` component
    - Accept `errorType: "no_eligible_lots" | "generic"` and `onReset: () => void` props
    - For `no_eligible_lots`: display message informing no lots are available; suggest verifying permit type
    - For `generic`: display a descriptive error message; provide a button to return to `InputForm`
    - _Requirements: 6.4, 6.5_

  - [ ]* 14.2 Write unit tests for `ErrorState`
    - Render with `no_eligible_lots`; assert correct message rendered
    - Render with `generic`; assert return-to-form button present
    - _Requirements: 6.4, 6.5_

- [ ] 15. Implement `InputForm` frontend component
  - [ ] 15.1 Implement `InputForm` component
    - Controlled selectors for building (loaded from API or static config) and permit type (loaded from API or static config)
    - Controlled time input for class/event start time
    - On submit with missing fields: display field-level error messages; do not call the API
    - On valid submit: POST to `/recommend`; call `onLoading` prop; on response call `onSuccess` or `onError` prop
    - Touch targets ≥ 44px × 44px for all interactive elements
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 7.2_

  - [ ]* 15.2 Write unit tests for `InputForm`
    - Submit empty form: assert field-level errors shown; assert API not called
    - Submit valid form: assert POST fired with correct payload
    - _Requirements: 1.2, 1.3_

- [ ] 16. Implement `App` root component and responsive layout
  - [ ] 16.1 Implement `App` component
    - Manage top-level view state: `idle | loading | success | error`
    - Render `InputForm` in `idle` and `loading` states; `RecommendationResult` in `success`; `ErrorState` in `error`
    - Pass callbacks and API response data to child components
    - _Requirements: 1.1, 6.1, 6.4, 6.5_

  - [ ] 16.2 Apply responsive CSS
    - Layouts render correctly from 320px to 1440px viewport width without horizontal scrolling
    - Use relative units, flexbox or CSS grid
    - _Requirements: 7.1, 7.3_

- [ ] 17. Checkpoint — frontend components complete
  - Run `vitest --run`; ensure all frontend unit tests pass. Ask the user if any questions arise before proceeding.

- [ ] 18. Integration tests
  - [ ] 18.1 Write integration tests against the deployed or locally mocked API
    - POST valid payload → assert HTTP 200 with `lot_name`, `arrival_time`, `explanation`, `simulated_data: true`
    - POST unknown permit type → assert HTTP 404
    - POST missing field → assert HTTP 400 with `fields` list
    - Mock Bedrock returning error → assert HTTP 200 with fallback explanation
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 19. Final checkpoint — all tests pass
  - Run `pytest` (backend) and `vitest --run` (frontend); ensure all tests pass. Ask the user if any questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP; core correctness is covered by non-optional unit tests.
- Each task references specific requirements for traceability.
- Checkpoints ensure incremental validation at meaningful milestones.
- Property tests validate universal correctness properties using Hypothesis (Python backend) and can be run as part of the standard `pytest` suite.
- Unit tests validate specific examples and edge cases.
- `BEDROCK_MODEL_ID` must be configured at deployment time; the specific model is chosen based on supported models, AWS region, and cost — it is not hardcoded anywhere in the application.
- `WALK_PENALTY` is a named constant in `scoring.py`; tests must reference it by name, not as a magic number.
- Availability is looked up using the per-lot `candidate_arrival_time` day-of-week and hour, not the class start time, so each lot's availability reflects the moment the student would actually arrive at that lot.

---

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["2.1", "11.1"] },
    { "id": 2, "tasks": ["2.2", "3.1"] },
    { "id": 3, "tasks": ["3.2", "4.1", "12.1"] },
    { "id": 4, "tasks": ["4.2", "4.3", "5.1", "12.2"] },
    { "id": 5, "tasks": ["5.2", "5.3", "5.4", "5.5", "5.6", "5.7", "6.1"] },
    { "id": 6, "tasks": ["6.2", "6.3", "6.4", "8.1", "11.2"] },
    { "id": 7, "tasks": ["8.2", "8.3", "11.3", "13.1", "14.1", "15.1"] },
    { "id": 8, "tasks": ["8.4", "9.1", "13.2", "14.2", "15.2"] },
    { "id": 9, "tasks": ["9.2", "16.1", "16.2"] },
    { "id": 10, "tasks": ["9.3", "9.4", "11.4"] },
    { "id": 11, "tasks": ["18.1"] }
  ]
}
```
