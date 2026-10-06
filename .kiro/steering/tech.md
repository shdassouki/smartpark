# Tech Stack

## Frontend

- **Framework**: React
- **Target**: Mobile-friendly web (responsive, not a native app)
- **Hosting**: AWS Amplify Hosting
- **Styling**: CSS
- **Build tool**: Vite

## Backend

- **API entry point**: Amazon API Gateway
- **Business logic**: AWS Lambda (Python)
- **Database**: Amazon DynamoDB
- **Generative AI**: Amazon Bedrock (plain-language recommendation explanations only)

## Architecture Summary

```
Browser (React)
    │
    └──▶ Amazon API Gateway
              │
              └──▶ AWS Lambda
                        │
                        ├──▶ Amazon DynamoDB
                        │     (parking + building data)
                        │
                        └──▶ Amazon Bedrock
                              (recommendation explanation)
```

All backend infrastructure is serverless. Keep it simple and cost-conscious — no containers, no long-running servers.

## Key Design Constraints

- Recommendation logic must be deterministic and explainable (no black-box ML)
- Permit eligibility is a hard filter applied before scoring
- Scoring balances predicted availability and walking time (both factors matter)
- Availability data is simulated/historical — never describe it as live or real-time
- Amazon Bedrock may explain a completed recommendation but must not determine parking eligibility or choose the winning lot
- If Bedrock is unavailable, SmartPark must still return the recommendation using a deterministic fallback explanation

## Common Commands

| Purpose | Command |
|---------|---------|
| Install frontend deps | TBD |
| Start frontend dev server | TBD |
| Build frontend | TBD |
| Deploy frontend | TBD |
| Run backend locally | TBD |
| Run tests | TBD |

> Update this section once the project is scaffolded.
