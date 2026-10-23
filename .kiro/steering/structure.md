# Project Structure

## Current Layout

```
smartpark/
├── .kiro/
│   ├── hooks/                   # Agent hooks: backend tests on save, data-honesty copy review, AWS-change confirmation
│   ├── settings/
│   │   └── mcp.json             # Project MCP servers (aws-documentation, aws-serverless)
│   ├── specs/
│   │   └── smartpark-mvp/       # requirements.md, design.md, tasks.md, .config.kiro
│   └── steering/                # product.md, tech.md, structure.md
├── backend/                     # Lambda source (SAM CodeUri: ../backend/)
│   ├── handler.py               # Lambda entry point: request parsing, pipeline, HTTP status mapping
│   ├── recommendation/          # Pure logic, no I/O: eligibility.py, scoring.py, arrival_time.py
│   ├── shared/                  # db_client.py, bedrock_client.py, fallback_explainer.py, models.py, exceptions.py
│   ├── tests/                   # pytest suite; DynamoDB and Bedrock are mocked
│   ├── pyproject.toml           # pytest config (testpaths = tests)
│   ├── requirements.txt         # Lambda runtime deps only (boto3)
│   └── requirements-dev.txt     # -r requirements.txt plus pytest, pytest-mock, hypothesis
├── data/                        # Simulated seed data
│   ├── README.md                # Dataset description and simulated-data notice
│   └── seed_dynamo.py           # Builds seed items; dry run by default, --write to DynamoDB
├── frontend/                    # React + TypeScript + Vite app (Amplify app root)
│   ├── public/                  # Static assets (favicon.svg)
│   ├── src/
│   │   ├── components/          # InputForm, RecommendationResult, ErrorState, DisclaimerBanner, icons
│   │   ├── utils/               # api.ts (POST /recommend client and types), options.ts (building and permit options)
│   │   ├── test/                # Vitest setup only (no test files yet)
│   │   ├── App.tsx              # View state: idle | loading | success | error
│   │   ├── main.tsx             # React entry point
│   │   └── App.css, index.css   # Styles
│   ├── .env.example             # VITE_API_URL template (copy to .env.local)
│   └── index.html, package.json, package-lock.json, vite.config.ts, tsconfig*.json, .eslintrc.cjs
├── infra/
│   └── template.yaml            # SAM template: DynamoDB table, Lambda function, API Gateway REST API
├── samconfig.toml               # SAM deploy settings (stack smartpark, us-east-1); run sam commands from the repo root
├── .gitignore
└── README.md                    # Technical write-up and setup, deploy, and test instructions
```

- There is no `frontend/src/pages/` folder. The app is a single page, and `App.tsx` switches between view components.
- Amplify Hosting is configured in the Amplify console; there's no `amplify.yml` in the repo.
- Local-only, gitignored paths: `backend/.venv/`, `frontend/node_modules/`, `frontend/.env.local`, `.aws-sam/`, `.agents/`.

## Conventions

- Frontend and backend live in separate top-level folders
- Recommendation logic is isolated in its own module so it can be tested independently
- Seed/mock data lives in `data/` and is clearly labeled as simulated
- Do not co-locate infrastructure config with application code unless a framework requires it
- Keep Lambda functions small and focused — one function per logical responsibility
- Update this file as the real structure evolves
