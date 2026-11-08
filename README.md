# StackPilot — Deployment & Docs Copilot

Takes a GitHub repo URL, an uploaded ZIP, or a text description, analyses the
stack, and generates deployment plans (generic / Docker / VM / serverless) and
documentation (README, user, frontend, backend and deployment guides).
See [`memory/PRD.md`](memory/PRD.md) for the full product spec.

## Run locally (from the code in this repo)

```bash
# Backend — FastAPI, port 8000 (see backend/Dockerfile)
cp backend/.env.example backend/.env   # set MONGO_URL, DB_NAME, GEMINI_API_KEY
pip install -r backend/requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000   # from backend/

# Frontend — React (CRA + Craco)
cp frontend/.env.example frontend/.env  # set REACT_APP_BACKEND_URL, REACT_APP_GOOGLE_CLIENT_ID
cd frontend && npm install --legacy-peer-deps && npm start
```

Notes, verified in code (not a live deployment):

- The backend exits at startup unless `MONGO_URL` and `DB_NAME` are set
  (`backend/server.py`).
- All AI generation currently routes to Gemini (`GEMINI_MODEL`, default
  `gemini-2.5-flash`); the GPT-5.2 / Claude / Emergent provider choices in the
  UI are not wired to separate providers.
- There is no Stripe checkout in the current backend. Subscriptions are
  verified through Google Play Billing (`POST /api/billing/verify`); see
  `memory/PRD.md`.
- No live deployment, domain, users or revenue are evidenced in this repo.

## License & Intellectual Property

Proprietary software. © 2026 Poor Dude Holdings LLC. All rights reserved. No license is granted except by separate written agreement.

- License: [`LICENSE`](LICENSE)
- Notices and trademarks: [`NOTICE`](NOTICE)
- What is owned here and how it is protected: [`INTELLECTUAL_PROPERTY.md`](INTELLECTUAL_PROPERTY.md)
- Licensing inquiries: admin@poordudeholdings.com
