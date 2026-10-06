# Product: SmartPark

SmartPark is a mobile-friendly web application for university commuter students who waste time searching for parking before class.

## Problem

Students arrive on campus without knowing which lots have availability, end up walking far from class, or park in lots they are not permitted to use.

## How It Works

1. Student enters their destination building, class/event start time, and parking permit type.
2. SmartPark filters out lots the student is not eligible for (hard filter, non-negotiable).
3. Among eligible lots, SmartPark scores each lot by balancing predicted availability and walking time to the destination — not simply the closest lot or the highest availability lot.
4. SmartPark recommends one best lot, explains the tradeoff behind the recommendation, and tells the student when they should aim to arrive at the parking lot to reach class on time.

## Scope (MVP)

**In scope:**
- Destination building input
- Class/event start time input
- Parking permit type selection
- Permit eligibility filtering
- Predicted availability + walking time scoring
- Single best recommendation with plain-language explanation
- Parking-lot arrival time guidance ("arrive at the lot by X to make it to class")

**Explicitly out of scope:**
- User accounts, login, or profiles
- Payments or reservations
- Premium subscriptions
- Individual parking spot tracking
- Live camera feeds or real-time sensor data
- Push notifications

## Data Honesty

This is a hackathon prototype. Parking availability data is simulated/historical. The UI must clearly label data as such at all times. Do not present availability as live or real-time. Do not claim individual spot availability.

## Recommendation Logic

The recommendation must be deterministic and explainable. The scoring balances predicted availability and walking time. Neither factor alone determines the winner — a lot 30 seconds closer that is almost always full should lose to a lot 3 minutes away that is reliably available.
