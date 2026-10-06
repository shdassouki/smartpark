# Requirements Document

## Introduction

SmartPark is a mobile-friendly web application for university commuter students. Students waste time searching for parking before class — arriving without knowing which lots have availability, walking far from their destination, or parking in lots their permit does not cover. SmartPark solves this by accepting a student's destination building, class/event start time, and parking permit type, then filtering out ineligible lots and scoring eligible ones by balancing predicted availability against walking time. The application recommends one best lot with a plain-language explanation and tells the student when they should arrive at the lot to reach class on time. All availability data is simulated/historical and must always be labeled as such.

---

## Glossary

- **System**: The SmartPark web application, including both frontend and backend components.
- **Frontend**: The React/Vite single-page application served to the student's browser.
- **API**: The Amazon API Gateway endpoint that routes requests to the Lambda backend.
- **Recommendation_Engine**: The AWS Lambda function that filters lots, scores eligible lots, and selects the best recommendation.
- **Bedrock_Client**: The component within the Lambda function that calls Amazon Bedrock to generate a plain-language explanation.
- **Fallback_Explainer**: The deterministic text-generation component used when Amazon Bedrock is unavailable.
- **DynamoDB**: The Amazon DynamoDB database storing parking lot data, building data, and permit eligibility rules.
- **Lot**: A university parking lot with a name, location, permit types accepted, and historical availability data.
- **Building**: A campus destination building with a name and geographic coordinates.
- **Permit_Type**: A category of parking permit that determines which lots a student may use. Valid permit types are defined by the seeded prototype dataset and are configurable — not hardcoded in application logic.
- **Eligibility_Filter**: The hard filter that removes all lots for which the student's permit type is not accepted.
- **Availability_Score**: A numeric value between 0.0 and 1.0 representing predicted parking availability for a lot at a given time, derived from historical data.
- **Walking_Time**: The estimated walking time in minutes from a parking lot to a destination building.
- **Composite_Score**: The final numeric score assigned to each eligible lot, computed by the Recommendation_Engine from Availability_Score and Walking_Time.
- **Recommendation**: The single best lot selected by the Recommendation_Engine, including its name, Composite_Score, arrival time guidance, and plain-language explanation.
- **Arrival_Time**: The time by which the student should arrive at the parking lot to reach their class or event on time, computed as the class/event start time minus Walking_Time minus Parking_Buffer.
- **Parking_Buffer**: A configurable duration subtracted from the class/event start time when computing Arrival_Time, representing additional time for the student to find a spot after arriving at the lot. The prototype default is 5 minutes.
- **Explanation**: A student-friendly, plain-language description of why the recommended lot was chosen over alternatives.

---

## Requirements

### Requirement 1: Student Input Form

**User Story:** As a commuter student, I want to enter my destination building, class start time, and parking permit type, so that SmartPark can find the best available lot for me.

#### Acceptance Criteria

1. THE Frontend SHALL display an input form containing a destination building selector, a class/event start time input, and a parking permit type selector.
2. WHEN the student submits the form with all required fields populated, THE Frontend SHALL send the destination building identifier, class/event start time, and permit type to the API.
3. IF the student submits the form with one or more required fields empty, THEN THE Frontend SHALL display a descriptive validation message identifying each missing field and SHALL NOT submit the request to the API.
4. THE Frontend SHALL present the permit type selector as a discrete list of valid permit types sourced from the available data, not as a free-text field.
5. THE Frontend SHALL present the destination building selector as a discrete list of buildings sourced from the available data, not as a free-text field.

---

### Requirement 2: Permit Eligibility Filtering

**User Story:** As a commuter student, I want the system to automatically exclude lots I am not permitted to use, so that I never receive a recommendation for a lot where I would risk a parking violation.

#### Acceptance Criteria

1. WHEN the Recommendation_Engine receives a request, THE Recommendation_Engine SHALL apply the Eligibility_Filter as the first step before any scoring is performed.
2. THE Eligibility_Filter SHALL remove every Lot whose accepted permit types do not include the student's Permit_Type.
3. IF the Eligibility_Filter removes all Lots and zero eligible lots remain, THEN THE Recommendation_Engine SHALL return an error response indicating no eligible lots are available for the given permit type and time.
4. THE Recommendation_Engine SHALL NOT include any ineligible Lot in the Composite_Score calculation or in the Recommendation.

---

### Requirement 3: Availability and Walking Time Scoring

**User Story:** As a commuter student, I want the system to score parking lots by balancing predicted availability and walking distance, so that the recommendation accounts for both factors rather than optimizing for just one.

#### Acceptance Criteria

1. WHEN the Eligibility_Filter produces a non-empty set of eligible Lots, THE Recommendation_Engine SHALL compute a Composite_Score for each eligible Lot.
2. THE Recommendation_Engine SHALL compute the Composite_Score using both the Lot's Availability_Score at the requested time and the Lot's Walking_Time to the destination Building.
3. THE Composite_Score formula SHALL weight Availability_Score and Walking_Time such that a Lot with a substantially higher Availability_Score can outrank a Lot with a shorter Walking_Time.
4. THE Recommendation_Engine SHALL produce a deterministic Composite_Score: identical inputs SHALL always produce identical scores.
5. THE Recommendation_Engine SHALL select the Lot with the highest Composite_Score as the Recommendation.
6. WHERE multiple Lots share the highest Composite_Score, THE Recommendation_Engine SHALL select the Lot with the shorter Walking_Time as the tiebreaker.

---

### Requirement 4: Parking Lot Arrival Time Guidance

**User Story:** As a commuter student, I want to know what time I need to arrive at the parking lot, so that I can plan my departure and reach class on time.

#### Acceptance Criteria

1. THE Recommendation_Engine SHALL compute the Arrival_Time for the recommended Lot as the class/event start time minus the Lot's Walking_Time to the destination Building minus the Parking_Buffer.
2. THE Parking_Buffer SHALL be a configurable value; the prototype default is 5 minutes.
3. WHEN the Recommendation_Engine returns a Recommendation, THE Recommendation SHALL include the Arrival_Time expressed as a clock time (e.g., "8:45 AM").
4. THE Frontend SHALL display the Arrival_Time to the student using the phrasing: "Arrive at the lot by [Arrival_Time] to make it to class on time, including time to find a spot."

---

### Requirement 5: Plain-Language Recommendation Explanation

**User Story:** As a commuter student, I want a plain-language explanation of why a lot was recommended, so that I understand the tradeoff between availability and walking time.

#### Acceptance Criteria

1. WHEN the Recommendation_Engine has selected the best Lot, THE Bedrock_Client SHALL generate an Explanation by providing the selected Lot's name, Availability_Score, Walking_Time, and the names and scores of up to two runner-up lots to Amazon Bedrock.
2. THE Bedrock_Client SHALL NOT pass the list of Lots to Amazon Bedrock for ranking or selection — the winning Lot SHALL already be determined before Bedrock is called.
3. IF Amazon Bedrock is unavailable or returns an error, THEN THE Fallback_Explainer SHALL generate a deterministic Explanation using the Lot's name, Availability_Score, and Walking_Time without calling Amazon Bedrock.
4. THE Recommendation_Engine SHALL include the Explanation in the Recommendation response regardless of whether it was generated by the Bedrock_Client or the Fallback_Explainer.
5. THE Explanation SHALL describe the tradeoff between the recommended Lot's predicted availability and walking time in plain language understandable to a university student.

---

### Requirement 6: Recommendation Display

**User Story:** As a commuter student, I want to see a clear, single recommendation with all relevant details, so that I can act on it immediately without needing to interpret raw data.

#### Acceptance Criteria

1. WHEN the Frontend receives a successful Recommendation response, THE Frontend SHALL display the recommended Lot's name, the Arrival_Time guidance, and the Explanation on a single results screen.
2. THE Frontend SHALL display a disclaimer on the results screen stating that availability data is simulated/historical and is not live or real-time.
3. THE Frontend SHALL display the disclaimer on every screen where availability information is shown, not only on the results screen.
4. WHEN the Frontend receives an error response indicating no eligible lots are available, THE Frontend SHALL display a message informing the student that no lots are available for their permit type and suggesting they verify their permit type selection.
5. WHEN the Frontend receives an error response for any other reason, THE Frontend SHALL display a descriptive error message and provide the student with the option to return to the input form.

---

### Requirement 7: Mobile-Friendly Responsive Layout

**User Story:** As a commuter student using a smartphone, I want the application to be fully usable on a mobile screen, so that I can look up parking while walking to my car.

#### Acceptance Criteria

1. THE Frontend SHALL render all screens correctly on viewport widths from 320px to 1440px without horizontal scrolling or content overflow.
2. THE Frontend SHALL use touch-friendly interactive elements with tap targets of at least 44px × 44px on all selectors, buttons, and input controls.
3. THE Frontend SHALL display the input form and results on a single page, loading the results section in place without a full-page navigation.

---

### Requirement 8: Data Persistence and Seeding

**User Story:** As a developer, I want parking lot, building, and permit rule data to be stored in DynamoDB and seeded with realistic mock data, so that the recommendation engine has the data it needs to function during the hackathon prototype phase.

#### Acceptance Criteria

1. THE DynamoDB SHALL store at minimum: Lot records (name, accepted permit types, geographic coordinates, historical availability by time-of-day and day-of-week), Building records (name, geographic coordinates), and Permit eligibility rule records.
2. THE System SHALL include seed data containing at least five Lots and at least three Buildings with realistic university campus values.

---

### Requirement 9: API Contract

**User Story:** As a frontend developer, I want a well-defined API contract between the Frontend and the Recommendation_Engine, so that the two components can be developed and tested independently.

#### Acceptance Criteria

1. THE API SHALL expose a single endpoint that accepts a POST request containing the destination building identifier, class/event start time, and permit type.
2. WHEN the API receives a valid request, THE API SHALL return a JSON response containing the recommended Lot name, Arrival_Time, Explanation, and a disclaimer flag indicating that availability data is simulated.
3. WHEN the API receives a request with missing or malformed required fields, THE API SHALL return a 400 status code and a JSON error body describing which fields are invalid.
4. WHEN the Recommendation_Engine encounters an internal error, THE API SHALL return a 500 status code and a JSON error body with a descriptive message.
5. IF no eligible Lots exist for the given permit type and time, THEN THE API SHALL return a 404 status code and a JSON error body indicating no eligible lots were found.
