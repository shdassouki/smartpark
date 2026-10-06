# Project Structure

> Project is in early setup. Update this file as the structure is established.

## Planned Layout

```
smartpark/
├── frontend/               # React application
│   ├── src/
│   │   ├── components/     # UI components
│   │   ├── pages/          # Page-level views
│   │   └── utils/          # Shared helpers
│   └── public/
├── backend/                # Lambda function(s)
│   ├── recommendation/     # Core recommendation logic
│   └── shared/             # Shared utilities (permit rules, scoring, etc.)
├── infra/                  # Infrastructure config (API Gateway, DynamoDB, Amplify) — TBD
├── data/                   # Seed/mock data for DynamoDB (lots, buildings, permit rules)
├── .kiro/                  # Kiro configuration
│   └── steering/
└── README.md
```

## Conventions

- Frontend and backend live in separate top-level folders
- Recommendation logic is isolated in its own module so it can be tested independently
- Seed/mock data lives in `data/` and is clearly labeled as simulated
- Do not co-locate infrastructure config with application code unless a framework requires it
- Keep Lambda functions small and focused — one function per logical responsibility
- Update this file as the real structure evolves
