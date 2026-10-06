# SmartPark Seed Data

> **IMPORTANT — SIMULATED PROTOTYPE DATA**
>
> All data produced by the seed script in this directory is **simulated
> prototype data created for demonstration purposes only**.
>
> - Walking times are **simulated** estimates. They are not measured, routed,
>   or official distances.
> - Availability percentages are **simulated availability** values. They are
>   not official, historical, measured, or real-time George Mason University
>   parking data.
>
> Nothing here represents real GMU parking conditions. The George Mason
> University building and parking names are used only to give the prototype a
> realistic campus setting.

## Contents

- `seed_dynamo.py` — builds the prototype dataset and (optionally) writes it to
  a DynamoDB table. By default it runs in dry-run mode and writes nothing to AWS.

## Dataset summary

- **3 buildings:** Enterprise Hall, Johnson Center, Exploratory Hall
- **5 parking options:** Shenandoah Parking Deck, Rappahannock Parking Deck,
  Mason Pond Parking Deck, Lot A, Lot K
- **2 permit types:** General, Faculty/Staff
- **Walking times:** one simulated estimate per (lot, building) pair
- **Simulated availability:** one value per (lot, weekday, hour) for Mon–Fri,
  hours 07:00–17:00

## Usage

Dry run (default — prints records, writes nothing to AWS):

    python data/seed_dynamo.py

Write to a local DynamoDB endpoint (e.g. DynamoDB Local):

    python data/seed_dynamo.py --write --table-name smartpark --endpoint-url http://localhost:8000

Write to a real AWS DynamoDB table (requires AWS credentials):

    python data/seed_dynamo.py --write --table-name smartpark
