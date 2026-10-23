# Tech Stack

## Frontend

- **Framework**: React 18 with TypeScript
- **Target**: Mobile-friendly web (responsive, not a native app)
- **Hosting**: AWS Amplify Hosting (monorepo app root `frontend`, build output `dist`)
- **Styling**: CSS
- **Build tool**: Vite 5
- **Linting**: ESLint 8 with typescript-eslint (`frontend/.eslintrc.cjs`)
- **API client**: `frontend/src/utils/api.ts`; the endpoint URL comes from `VITE_API_URL`

## Backend

- **API entry point**: Amazon API Gateway (REST API, `POST /recommend`, stage `prod`)
- **Business logic**: AWS Lambda (Python 3.12, single function `smartpark-recommend`)
- **Database**: Amazon DynamoDB (single table `smartpark`, on-demand billing)
- **Generative AI**: Amazon Bedrock (plain-language recommendation explanations only; Converse API with Claude Haiku 4.5 through the US inference profile)
- **Infrastructure as code**: AWS SAM (`infra/template.yaml`; deploy settings in the root `samconfig.toml`: stack `smartpark`, region `us-east-1`)
- **Runtime dependencies**: `backend/requirements.txt` (boto3 only, because SAM bundles this file into the Lambda)
- **Tests**: pytest and pytest-mock from `backend/requirements-dev.txt`; DynamoDB and Bedrock are mocked

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

Run from the repo root. The Status column records what was checked during submission prep.

| Purpose | Command | Status |
|---------|---------|--------|
| Set up backend dev env (once) | `python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements-dev.txt` | Setup step, not re-run (venv already existed) |
| Run backend tests | `cd backend && .venv/bin/python -m pytest -q` | Verified: 17 passed |
| Install frontend deps (once) | `cd frontend && npm ci` | Setup step, not re-run (`node_modules` already existed) |
| Start frontend dev server | `cd frontend && npm run dev` | Standard Vite script, not run (long-running) |
| Type-check and lint frontend | `cd frontend && node_modules/.bin/tsc -b && npm run lint` | Verified |
| Build frontend | `cd frontend && npm run build` | Verified |
| Preview seed data (dry run) | `python3 data/seed_dynamo.py` | Verified: 300 items, nothing written |
| Lint SAM template | `sam validate --lint -t infra/template.yaml` | Verified |

### Deploy and AWS commands (not executed during submission prep)

These match `infra/template.yaml` and `samconfig.toml` but weren't run during submission prep. Most of them create, change, or delete AWS resources.

| Purpose | Command |
|---------|---------|
| Build backend | `sam build -t infra/template.yaml` |
| Deploy backend | `sam deploy` (from the repo root after `sam build`, without `-t`, so SAM uses the built template and the root `samconfig.toml`) |
| Seed DynamoDB | `AWS_DEFAULT_REGION=us-east-1 backend/.venv/bin/python data/seed_dynamo.py --write --table-name smartpark` |
| Run backend locally | `sam local start-api -t infra/template.yaml --env-vars env.json` (needs Docker; `env.json` sets `DYNAMODB_TABLE_NAME` to `smartpark`) |
| Deploy frontend | AWS Amplify Hosting: app root `frontend`, build `npm run build`, output `dist`, env var `VITE_API_URL` |
| Tear down backend | `sam delete` (reads the stack name and region from `samconfig.toml`) |

Notes:

- There are no frontend tests yet. `npm test` exits with "No test files found", so don't use it as a check.
- System `python3` doesn't have pytest; use `backend/.venv/bin/python`.
