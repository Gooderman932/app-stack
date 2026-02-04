# StackPilot - Deployment & Docs Copilot

## Original Problem Statement
Build a deployment and docs copilot that:
- Takes a GitHub repo URL or uploaded code
- Analyzes the stack (frontend, backend, database, infra files)
- Generates deployment plans, scripts, and step-by-step instructions for Docker, VM, Serverless
- Generates documentation: user-guide.md, frontend-guide.md, backend-guide.md, deployment-guide.md
- Batches work into as few runs as possible
- Produces container path (Dockerfile + Docker Compose), Linux path, PaaS/Serverless path

## User Personas
1. **Developer**: Wants quick deployment scripts and documentation for any codebase
2. **DevOps Engineer**: Needs standardized deployment plans across multiple platforms
3. **Technical Writer**: Needs auto-generated documentation templates to customize

## Core Requirements (Static)
- [x] Home page with recent projects list
- [x] Input Project page with source type selection (GitHub URL, Upload ZIP, Text Only)
- [x] AI Provider selection (GPT-5.2, Claude, Gemini, Emergent Default)
- [x] Emergent LLM Key toggle
- [x] Tech Stack Hints multi-select
- [x] Analysis Results showing detected stack, build steps, config files, env vars
- [x] Generate Both (single AI call for plans + docs)
- [x] 4 Deployment Plans (Generic, Docker, VM, Serverless/PaaS)
- [x] 5 Documentation files (README, user-guide, frontend-guide, backend-guide, deployment-guide)
- [x] Copy to clipboard buttons
- [x] Export as ZIP with proper folder structure
- [x] Dark/Light theme toggle
- [x] Re-analyze button

## Architecture
```
Frontend (React + Tailwind + Shadcn)
    ↓ API calls
Backend (FastAPI + Python)
    ↓ LLM calls
AI Provider (via emergentintegrations)
    ↓ storage
MongoDB (projects collection)
```

## What's Been Implemented (Jan 2026)
- **Jan 21, 2026**: MVP Complete
  - Full 5-page flow: Home → Input → Analysis → Plans → Docs
  - AI-powered code analysis using GPT-5.2/Claude/Gemini
  - GitHub URL fetching and ZIP upload support
  - Rule-based fallback when AI fails
  - Export as ZIP with proper repo structure
  - Dark theme default, theme toggle

- **Feb 4, 2026**: Monetization Complete
  - 3-tier subscription: Free ($0), Pro ($12/mo), Team ($29/mo)
  - Stripe checkout integration with payment success polling
  - User authentication via email (stored in localStorage)
  - Feature gating:
    - Free: 3 projects, Gemini only, no ZIP export, 1 re-analysis
    - Pro: Unlimited projects, all AI providers, ZIP export, unlimited re-analysis
    - Team: + collaboration, priority support, custom templates
  - Upgrade dialogs when hitting tier limits
  - Usage stats card on home page
  - Pricing page with tier comparison

## Data Model
```javascript
Project {
  id, name, sourceType, sourceUrl, uploadRef,
  textDescription, theme, aiProvider, useEmergentKey,
  detectedTechStack: { frontend, backend, database, infra, services },
  buildSteps: { frontendBuild, backendBuild },
  deploymentPlans: { genericPlan, dockerPlan, vmPlan, serverlessPlan },
  docs: { readme, userGuide, frontendGuide, backendGuide, deploymentGuide },
  status, configFiles, envVars, createdAt, updatedAt
}
```

## API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/projects | List all projects |
| GET | /api/projects/:id | Get single project |
| POST | /api/projects | Create new project |
| POST | /api/projects/:id/upload | Upload ZIP file |
| POST | /api/projects/:id/analyze | Run AI analysis |
| POST | /api/projects/:id/generate | Generate plans/docs |
| DELETE | /api/projects/:id | Delete project |
| GET | /api/tiers | Get subscription tiers |
| POST | /api/users | Create/get user |
| GET | /api/users/:id | Get user by ID |
| GET | /api/users/email/:email | Get user by email |
| POST | /api/checkout/create | Start Stripe checkout |
| GET | /api/checkout/status/:session_id | Check payment status |
| POST | /api/webhook/stripe | Stripe webhook |

## Prioritized Backlog

### P0 (Critical) - DONE
- ✅ Project CRUD operations
- ✅ GitHub URL file fetching
- ✅ AI-powered analysis
- ✅ Deployment plans generation
- ✅ Documentation generation
- ✅ Export as ZIP

### P1 (High Priority) - Future
- [ ] Progress streaming for long AI operations
- [ ] Cache analysis results to avoid re-fetching
- [ ] Support for more package managers (pnpm, bun)

### P2 (Medium Priority) - Future
- [ ] Project history with versioning
- [ ] Team collaboration features
- [ ] Custom template support for docs

### P3 (Nice to Have) - Future
- [ ] GitHub integration (auto-push generated docs)
- [ ] CI/CD config generation (GitHub Actions, GitLab CI)
- [ ] Cost estimation for cloud deployments

## Next Tasks
1. Add progress streaming for AI operations
2. Improve error handling for invalid GitHub URLs
3. Add more tech stack detection patterns
