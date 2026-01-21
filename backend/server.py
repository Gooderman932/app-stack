from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import httpx
import zipfile
import io
import json
import aiofiles
import tempfile
import shutil
from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Pydantic Models ---
class DetectedTechStack(BaseModel):
    frontend: str = ""
    backend: str = ""
    database: str = ""
    infra: str = ""
    services: str = ""

class BuildSteps(BaseModel):
    frontendBuild: str = ""
    backendBuild: str = ""

class DeploymentPlans(BaseModel):
    genericPlan: str = ""
    dockerPlan: str = ""
    vmPlan: str = ""
    serverlessPlan: str = ""

class Docs(BaseModel):
    readme: str = ""
    userGuide: str = ""
    frontendGuide: str = ""
    backendGuide: str = ""
    deploymentGuide: str = ""

class Project(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    sourceType: str  # github_url, upload, text_only
    sourceUrl: Optional[str] = None
    uploadRef: Optional[str] = None
    textDescription: Optional[str] = None
    theme: str = "dark"
    aiProvider: str = "gpt_5_2"  # gpt_5_2, claude, gemini, emergent_default
    useEmergentKey: bool = True
    detectedTechStack: DetectedTechStack = Field(default_factory=DetectedTechStack)
    buildSteps: BuildSteps = Field(default_factory=BuildSteps)
    deploymentPlans: DeploymentPlans = Field(default_factory=DeploymentPlans)
    docs: Docs = Field(default_factory=Docs)
    status: str = "pending"  # pending, analyzed, plans_generated, docs_generated
    configFiles: List[str] = []
    envVars: List[str] = []
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ProjectCreate(BaseModel):
    name: str
    sourceType: str
    sourceUrl: Optional[str] = None
    textDescription: Optional[str] = None
    theme: str = "dark"
    aiProvider: str = "gpt_5_2"
    useEmergentKey: bool = True
    techStackHints: List[str] = []

class AnalyzeRequest(BaseModel):
    projectId: str

class GenerateRequest(BaseModel):
    projectId: str
    generateType: str  # plans, docs, both

# --- Helper Functions ---
def get_ai_model(provider: str):
    """Get model config based on provider selection"""
    models = {
        "gpt_5_2": ("openai", "gpt-5.2"),
        "claude": ("anthropic", "claude-sonnet-4-5-20250929"),
        "gemini": ("gemini", "gemini-3-flash-preview"),
        "emergent_default": ("openai", "gpt-5.2")
    }
    return models.get(provider, ("openai", "gpt-5.2"))

async def fetch_github_files(repo_url: str) -> dict:
    """Fetch key files from GitHub repo"""
    # Parse repo URL to get owner/repo
    parts = repo_url.rstrip('/').split('/')
    if 'github.com' in repo_url:
        owner = parts[-2]
        repo = parts[-1].replace('.git', '')
    else:
        return {"error": "Invalid GitHub URL"}
    
    key_files = [
        "package.json", "requirements.txt", "pyproject.toml", "pom.xml",
        "composer.json", "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
        ".env.example", ".env.sample", "Makefile", "go.mod", "Cargo.toml",
        "Gemfile", "build.gradle", "tsconfig.json", "vite.config.js", "webpack.config.js",
        "next.config.js", "nuxt.config.js", "angular.json", "serverless.yml",
        "terraform/main.tf", "k8s/deployment.yaml", "kubernetes/deployment.yaml"
    ]
    
    files_content = {}
    async with httpx.AsyncClient() as client:
        for file_path in key_files:
            try:
                url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{file_path}"
                response = await client.get(url, timeout=10)
                if response.status_code == 200:
                    files_content[file_path] = response.text
                else:
                    # Try master branch
                    url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/{file_path}"
                    response = await client.get(url, timeout=10)
                    if response.status_code == 200:
                        files_content[file_path] = response.text
            except Exception as e:
                logger.warning(f"Failed to fetch {file_path}: {e}")
                continue
    
    return files_content

def parse_uploaded_zip(file_content: bytes) -> dict:
    """Parse uploaded ZIP file and extract key files"""
    files_content = {}
    key_files = [
        "package.json", "requirements.txt", "pyproject.toml", "pom.xml",
        "composer.json", "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
        ".env.example", ".env.sample", "Makefile", "go.mod", "Cargo.toml",
        "Gemfile", "build.gradle", "tsconfig.json", "vite.config.js", "webpack.config.js",
        "next.config.js", "nuxt.config.js", "angular.json", "serverless.yml"
    ]
    
    try:
        with zipfile.ZipFile(io.BytesIO(file_content)) as zf:
            for name in zf.namelist():
                basename = os.path.basename(name)
                if basename in key_files or any(kf in name for kf in key_files):
                    try:
                        content = zf.read(name).decode('utf-8')
                        files_content[basename] = content
                    except:
                        continue
    except Exception as e:
        logger.error(f"Error parsing ZIP: {e}")
    
    return files_content

async def analyze_with_ai(files_content: dict, text_description: str, hints: List[str], provider: str) -> dict:
    """Use AI to analyze the codebase"""
    api_key = os.environ.get('EMERGENT_LLM_KEY')
    provider_name, model_name = get_ai_model(provider)
    
    # Build context from files
    files_summary = ""
    for fname, content in files_content.items():
        files_summary += f"\n--- {fname} ---\n{content[:2000]}\n"
    
    prompt = f"""Analyze this codebase and return a JSON object with the following structure:
{{
  "detectedTechStack": {{
    "frontend": "detected frontend framework/library (e.g., React, Vue, Angular, Next.js) or empty string",
    "backend": "detected backend framework (e.g., FastAPI, Express, Django, Spring Boot) or empty string",
    "database": "detected database/ORM (e.g., PostgreSQL, MongoDB, Prisma, SQLAlchemy) or empty string",
    "infra": "detected infrastructure tools (e.g., Docker, Kubernetes, Terraform) or empty string",
    "services": "detected services (e.g., Redis, RabbitMQ, S3) or empty string"
  }},
  "buildSteps": {{
    "frontendBuild": "commands to build frontend (e.g., npm install && npm run build)",
    "backendBuild": "commands to build/run backend (e.g., pip install -r requirements.txt && uvicorn main:app)"
  }},
  "configFiles": ["list of config files found"],
  "envVars": ["list of environment variables needed based on .env.example or code analysis"]
}}

Files found:
{files_summary}

Additional context from user: {text_description}
Tech stack hints: {', '.join(hints) if hints else 'None provided'}

Return ONLY valid JSON, no markdown or explanation."""

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"analyze-{uuid.uuid4()}",
            system_message="You are a code analysis expert. Always return valid JSON only."
        ).with_model(provider_name, model_name)
        
        response = await chat.send_message(UserMessage(text=prompt))
        
        # Parse JSON from response
        json_str = response.strip()
        if json_str.startswith("```"):
            json_str = json_str.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]
        json_str = json_str.strip()
        
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        # Fallback to rule-based detection
        return rule_based_analysis(files_content)

def rule_based_analysis(files_content: dict) -> dict:
    """Fallback rule-based analysis when AI fails"""
    result = {
        "detectedTechStack": {
            "frontend": "",
            "backend": "",
            "database": "",
            "infra": "",
            "services": ""
        },
        "buildSteps": {
            "frontendBuild": "",
            "backendBuild": ""
        },
        "configFiles": list(files_content.keys()),
        "envVars": []
    }
    
    # Detect frontend
    if "package.json" in files_content:
        pkg = files_content["package.json"]
        if "react" in pkg.lower():
            result["detectedTechStack"]["frontend"] = "React"
        elif "vue" in pkg.lower():
            result["detectedTechStack"]["frontend"] = "Vue.js"
        elif "angular" in pkg.lower():
            result["detectedTechStack"]["frontend"] = "Angular"
        elif "next" in pkg.lower():
            result["detectedTechStack"]["frontend"] = "Next.js"
        result["buildSteps"]["frontendBuild"] = "npm install && npm run build"
    
    # Detect backend
    if "requirements.txt" in files_content:
        req = files_content["requirements.txt"]
        if "fastapi" in req.lower():
            result["detectedTechStack"]["backend"] = "FastAPI"
            result["buildSteps"]["backendBuild"] = "pip install -r requirements.txt && uvicorn main:app --host 0.0.0.0 --port 8000"
        elif "django" in req.lower():
            result["detectedTechStack"]["backend"] = "Django"
            result["buildSteps"]["backendBuild"] = "pip install -r requirements.txt && python manage.py runserver"
        elif "flask" in req.lower():
            result["detectedTechStack"]["backend"] = "Flask"
            result["buildSteps"]["backendBuild"] = "pip install -r requirements.txt && flask run"
    
    # Detect infra
    if "Dockerfile" in files_content:
        result["detectedTechStack"]["infra"] = "Docker"
    if "docker-compose.yml" in files_content or "docker-compose.yaml" in files_content:
        result["detectedTechStack"]["infra"] += ", Docker Compose" if result["detectedTechStack"]["infra"] else "Docker Compose"
    
    # Extract env vars
    for key, content in files_content.items():
        if ".env" in key:
            for line in content.split("\n"):
                if "=" in line and not line.strip().startswith("#"):
                    var = line.split("=")[0].strip()
                    if var:
                        result["envVars"].append(var)
    
    return result

async def generate_plans_and_docs(project: dict, generate_type: str, provider: str) -> dict:
    """Generate deployment plans and/or documentation using AI"""
    api_key = os.environ.get('EMERGENT_LLM_KEY')
    provider_name, model_name = get_ai_model(provider)
    
    tech_stack = project.get("detectedTechStack", {})
    build_steps = project.get("buildSteps", {})
    project_name = project.get("name", "my-project")
    
    context = f"""
Project: {project_name}
Tech Stack:
- Frontend: {tech_stack.get('frontend', 'N/A')}
- Backend: {tech_stack.get('backend', 'N/A')}
- Database: {tech_stack.get('database', 'N/A')}
- Infrastructure: {tech_stack.get('infra', 'N/A')}
- Services: {tech_stack.get('services', 'N/A')}

Build Steps:
- Frontend: {build_steps.get('frontendBuild', 'N/A')}
- Backend: {build_steps.get('backendBuild', 'N/A')}

Config Files: {', '.join(project.get('configFiles', []))}
Environment Variables: {', '.join(project.get('envVars', []))}
"""

    result = {"deploymentPlans": {}, "docs": {}}
    
    if generate_type in ["plans", "both"]:
        plans_prompt = f"""Based on this project context, generate deployment plans.

{context}

Return a JSON object with these deployment plans (each should be a detailed numbered checklist with shell commands):

{{
  "genericPlan": "Generic deployment steps: 1. Clone repo 2. Install dependencies 3. Configure env 4. Build 5. Run 6. Health check",
  "dockerPlan": "Complete Docker deployment: Dockerfile content, docker-compose.yml content, build and run commands, health checks",
  "vmPlan": "Linux VM deployment: Create VM, install runtime, clone repo, configure systemd service, nginx reverse proxy",
  "serverlessPlan": "PaaS/Serverless deployment: Steps for Vercel/Railway/Render/AWS Lambda with env config"
}}

Make each plan comprehensive with actual commands. Mark placeholders with [YOUR_VALUE].
Return ONLY valid JSON."""

        try:
            chat = LlmChat(
                api_key=api_key,
                session_id=f"plans-{uuid.uuid4()}",
                system_message="You are a DevOps expert. Generate detailed deployment plans with actual commands."
            ).with_model(provider_name, model_name)
            
            response = await chat.send_message(UserMessage(text=plans_prompt))
            json_str = response.strip()
            if json_str.startswith("```"):
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
            result["deploymentPlans"] = json.loads(json_str.strip())
        except Exception as e:
            logger.error(f"Plans generation error: {e}")
            result["deploymentPlans"] = generate_fallback_plans(project_name, tech_stack, build_steps)

    if generate_type in ["docs", "both"]:
        docs_prompt = f"""Based on this project context, generate documentation files.

{context}

Return a JSON object with these markdown documents:

{{
  "readme": "# {project_name}\\n\\nProject overview, quick start guide, architecture diagram, features list",
  "userGuide": "# User Guide\\n\\n## Prerequisites\\n## Setup\\n## Run/Use\\n## Verify\\n## Troubleshooting",
  "frontendGuide": "# Frontend Guide\\n\\n## Prerequisites\\n## Setup\\n## Run/Use\\n## Verify\\n## Troubleshooting\\n\\nInclude folder structure, component guide, styling guide",
  "backendGuide": "# Backend Guide\\n\\n## Prerequisites\\n## Setup\\n## Run/Use\\n## Verify\\n## Troubleshooting\\n\\nInclude API endpoints, models, adding new endpoints",
  "deploymentGuide": "# Deployment Guide\\n\\n## Prerequisites\\n## Generic Deployment\\n## Docker Deployment\\n## VM Deployment\\n## Serverless Deployment\\n## Verify\\n## Troubleshooting"
}}

Make each guide comprehensive with the standard template: Prerequisites, Setup, Run/Use, Verify, Troubleshooting.
Return ONLY valid JSON."""

        try:
            chat = LlmChat(
                api_key=api_key,
                session_id=f"docs-{uuid.uuid4()}",
                system_message="You are a technical writer. Generate comprehensive documentation in markdown."
            ).with_model(provider_name, model_name)
            
            response = await chat.send_message(UserMessage(text=docs_prompt))
            json_str = response.strip()
            if json_str.startswith("```"):
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
            result["docs"] = json.loads(json_str.strip())
        except Exception as e:
            logger.error(f"Docs generation error: {e}")
            result["docs"] = generate_fallback_docs(project_name, tech_stack, build_steps)
    
    return result

def generate_fallback_plans(name: str, tech_stack: dict, build_steps: dict) -> dict:
    """Generate fallback deployment plans when AI fails"""
    frontend = tech_stack.get("frontend", "")
    backend = tech_stack.get("backend", "")
    fb = build_steps.get("frontendBuild", "npm install && npm run build")
    bb = build_steps.get("backendBuild", "pip install -r requirements.txt && python main.py")
    
    return {
        "genericPlan": f"""# Generic Deployment Plan for {name}

## 1. Prerequisites
- Git installed
- Node.js 18+ (if frontend)
- Python 3.11+ (if backend)
- Access to target server

## 2. Clone Repository
```bash
git clone [YOUR_REPO_URL]
cd {name}
```

## 3. Install Dependencies
Frontend: `{fb.split('&&')[0] if '&&' in fb else fb}`
Backend: `{bb.split('&&')[0] if '&&' in bb else bb}`

## 4. Configure Environment
```bash
cp .env.example .env
# Edit .env with your values
```

## 5. Build & Run
Frontend: `{fb}`
Backend: `{bb}`

## 6. Health Check
- Frontend: Visit http://localhost:3000
- Backend: curl http://localhost:8000/health
""",
        "dockerPlan": f"""# Docker Deployment Plan for {name}

## 1. Prerequisites
- Docker 20.10+
- Docker Compose v2

## 2. Dockerfile (create if missing)
```dockerfile
FROM node:18-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS backend
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt
COPY backend/ ./
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 3. docker-compose.yml
```yaml
version: '3.8'
services:
  frontend:
    build:
      context: .
      target: frontend
    ports:
      - "3000:3000"
  backend:
    build:
      context: .
      target: backend
    ports:
      - "8000:8000"
    env_file:
      - .env
```

## 4. Build & Run
```bash
docker-compose build
docker-compose up -d
```

## 5. Health Check
```bash
docker-compose ps
curl http://localhost:8000/health
```
""",
        "vmPlan": f"""# VM/Server Deployment Plan for {name}

## 1. Prerequisites
- Linux VM (Ubuntu 22.04 recommended)
- SSH access
- Domain (optional)

## 2. Initial Server Setup
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git nginx certbot python3-certbot-nginx
```

## 3. Install Runtime
```bash
# Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Python
sudo apt install -y python3.11 python3.11-venv python3-pip
```

## 4. Clone & Setup
```bash
cd /var/www
sudo git clone [YOUR_REPO_URL] {name}
cd {name}
```

## 5. Create Systemd Service
```bash
sudo nano /etc/systemd/system/{name}.service
```
```ini
[Unit]
Description={name} Backend
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/{name}/backend
ExecStart=/usr/bin/python3.11 -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

## 6. Enable & Start
```bash
sudo systemctl enable {name}
sudo systemctl start {name}
```

## 7. Configure Nginx
```nginx
server {{
    listen 80;
    server_name [YOUR_DOMAIN];
    
    location /api {{
        proxy_pass http://localhost:8000;
    }}
    
    location / {{
        root /var/www/{name}/frontend/build;
        try_files $uri /index.html;
    }}
}}
```
""",
        "serverlessPlan": f"""# Serverless/PaaS Deployment Plan for {name}

## Option 1: Vercel (Frontend)
1. Connect GitHub repo to Vercel
2. Set build command: `{fb}`
3. Set output directory: `build` or `dist`
4. Add environment variables
5. Deploy

## Option 2: Railway (Full Stack)
1. Create new project on railway.app
2. Connect GitHub repo
3. Add services: web, database
4. Configure environment variables
5. Deploy

## Option 3: Render
1. Create new Web Service on render.com
2. Connect repository
3. Set build command: `{bb.split('&&')[0]}`
4. Set start command: `{bb.split('&&')[-1] if '&&' in bb else bb}`
5. Add environment variables
6. Deploy

## Option 4: AWS Lambda (Backend)
1. Install serverless framework: `npm i -g serverless`
2. Create serverless.yml:
```yaml
service: {name}
provider:
  name: aws
  runtime: python3.11
functions:
  api:
    handler: handler.handler
    events:
      - http: ANY /
      - http: ANY /{{proxy+}}
```
3. Deploy: `serverless deploy`
"""
    }

def generate_fallback_docs(name: str, tech_stack: dict, build_steps: dict) -> dict:
    """Generate fallback documentation when AI fails"""
    frontend = tech_stack.get("frontend", "React")
    backend = tech_stack.get("backend", "FastAPI")
    
    return {
        "readme": f"""# {name}

## Overview
{name} is a full-stack application built with {frontend} and {backend}.

## Quick Start
```bash
# Clone repository
git clone [YOUR_REPO_URL]
cd {name}

# Install dependencies
npm install        # Frontend
pip install -r requirements.txt  # Backend

# Run development
npm start          # Frontend on :3000
uvicorn main:app   # Backend on :8000
```

## Architecture
- **Frontend**: {frontend}
- **Backend**: {backend}
- **Database**: {tech_stack.get('database', 'TBD')}

## Documentation
- [User Guide](docs/user-guide.md)
- [Frontend Guide](docs/frontend-guide.md)
- [Backend Guide](docs/backend-guide.md)
- [Deployment Guide](docs/deployment-guide.md)
""",
        "userGuide": f"""# {name} - User Guide

## Prerequisites
- Modern web browser (Chrome, Firefox, Safari, Edge)
- Internet connection

## Setup
No setup required for end users. Access the application at [YOUR_URL].

## Run / Use
1. Open the application in your browser
2. Create an account or log in
3. Navigate using the main menu
4. [Add specific user flows here]

## Verify
- Successful login shows dashboard
- Features respond to interactions
- Data saves correctly

## Troubleshooting
| Issue | Solution |
|-------|----------|
| Page won't load | Clear browser cache, check internet |
| Login fails | Reset password, check credentials |
| Features not working | Refresh page, try different browser |
""",
        "frontendGuide": f"""# {name} - Frontend Guide

## Prerequisites
- Node.js 18+
- npm or yarn
- Code editor (VS Code recommended)

## Setup
```bash
cd frontend
npm install
cp .env.example .env
# Edit .env with your values
```

## Run / Use
```bash
# Development
npm start

# Build for production
npm run build

# Run tests
npm test
```

## Folder Structure
```
frontend/
├── src/
│   ├── components/    # Reusable components
│   ├── pages/         # Page components
│   ├── hooks/         # Custom hooks
│   ├── utils/         # Utility functions
│   └── App.js         # Main app component
├── public/            # Static assets
└── package.json       # Dependencies
```

## Verify
- `npm start` shows app at localhost:3000
- No console errors
- Components render correctly

## Troubleshooting
| Issue | Solution |
|-------|----------|
| npm install fails | Delete node_modules, run again |
| Build fails | Check for TypeScript/ESLint errors |
| Styles not loading | Check Tailwind config |
""",
        "backendGuide": f"""# {name} - Backend Guide

## Prerequisites
- Python 3.11+
- pip or pipenv
- Database (if required)

## Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\\Scripts\\activate  # Windows
pip install -r requirements.txt
cp .env.example .env
```

## Run / Use
```bash
# Development
uvicorn main:app --reload

# Production
uvicorn main:app --host 0.0.0.0 --port 8000
```

## API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/health | Health check |
| GET | /api/items | List items |
| POST | /api/items | Create item |

## Adding New Endpoint
```python
@router.get("/new-endpoint")
async def new_endpoint():
    return {{"message": "Hello"}}
```

## Verify
- Server starts without errors
- `/api/health` returns 200
- Database connections work

## Troubleshooting
| Issue | Solution |
|-------|----------|
| Import errors | Check virtual environment |
| DB connection fails | Check connection string |
| 500 errors | Check server logs |
""",
        "deploymentGuide": f"""# {name} - Deployment Guide

## Prerequisites
- Source code access
- Server/cloud account
- Domain (optional)

## Generic Deployment
1. Clone repository
2. Install dependencies
3. Configure environment variables
4. Build application
5. Start services
6. Configure reverse proxy

## Docker Deployment
```bash
# Build
docker-compose build

# Run
docker-compose up -d

# Check status
docker-compose ps
```

## VM Deployment
1. Provision Linux VM
2. Install runtime (Node.js, Python)
3. Clone repository
4. Create systemd service
5. Configure Nginx

## Serverless Deployment
- **Vercel**: Connect repo, configure build
- **Railway**: Add services, deploy
- **Render**: Create web service

## Verify
- Application accessible at URL
- All endpoints responding
- Logs show no errors

## Troubleshooting
| Issue | Solution |
|-------|----------|
| 502 Bad Gateway | Check backend service |
| Static files 404 | Check nginx config |
| SSL errors | Renew certificates |
"""
    }

# --- API Routes ---
@api_router.get("/")
async def root():
    return {"message": "Deployment & Docs Copilot API"}

@api_router.get("/projects", response_model=List[Project])
async def get_projects():
    """Get all projects"""
    projects = await db.projects.find({}, {"_id": 0}).sort("createdAt", -1).to_list(100)
    for p in projects:
        if isinstance(p.get('createdAt'), str):
            p['createdAt'] = datetime.fromisoformat(p['createdAt'])
        if isinstance(p.get('updatedAt'), str):
            p['updatedAt'] = datetime.fromisoformat(p['updatedAt'])
    return projects

@api_router.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get a single project"""
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@api_router.post("/projects", response_model=Project)
async def create_project(project_data: ProjectCreate):
    """Create a new project"""
    project = Project(
        name=project_data.name,
        sourceType=project_data.sourceType,
        sourceUrl=project_data.sourceUrl,
        textDescription=project_data.textDescription,
        theme=project_data.theme,
        aiProvider=project_data.aiProvider,
        useEmergentKey=project_data.useEmergentKey
    )
    doc = project.model_dump()
    doc['createdAt'] = doc['createdAt'].isoformat()
    doc['updatedAt'] = doc['updatedAt'].isoformat()
    await db.projects.insert_one(doc)
    return project

@api_router.post("/projects/{project_id}/upload")
async def upload_file(project_id: str, file: UploadFile = File(...)):
    """Upload ZIP file for a project"""
    content = await file.read()
    
    # Store file reference
    file_id = str(uuid.uuid4())
    
    # Save to temp directory
    temp_dir = Path(tempfile.gettempdir()) / "copilot_uploads"
    temp_dir.mkdir(exist_ok=True)
    file_path = temp_dir / f"{file_id}.zip"
    
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)
    
    # Update project with file reference
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {"uploadRef": str(file_path), "updatedAt": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"message": "File uploaded", "fileId": file_id}

@api_router.post("/projects/{project_id}/analyze")
async def analyze_project(project_id: str):
    """Analyze a project's codebase"""
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    files_content = {}
    
    # Fetch files based on source type
    if project["sourceType"] == "github_url" and project.get("sourceUrl"):
        files_content = await fetch_github_files(project["sourceUrl"])
    elif project["sourceType"] == "upload" and project.get("uploadRef"):
        try:
            async with aiofiles.open(project["uploadRef"], 'rb') as f:
                content = await f.read()
            files_content = parse_uploaded_zip(content)
        except Exception as e:
            logger.error(f"Error reading uploaded file: {e}")
    
    # Add text description to context
    text_desc = project.get("textDescription", "")
    hints = []  # Could be stored in project if needed
    
    # Analyze with AI
    analysis = await analyze_with_ai(files_content, text_desc, hints, project.get("aiProvider", "gpt_5_2"))
    
    # Update project
    update_data = {
        "detectedTechStack": analysis.get("detectedTechStack", {}),
        "buildSteps": analysis.get("buildSteps", {}),
        "configFiles": analysis.get("configFiles", []),
        "envVars": analysis.get("envVars", []),
        "status": "analyzed",
        "updatedAt": datetime.now(timezone.utc).isoformat()
    }
    
    await db.projects.update_one({"id": project_id}, {"$set": update_data})
    
    return {**project, **update_data}

@api_router.post("/projects/{project_id}/generate")
async def generate_content(project_id: str, request: GenerateRequest):
    """Generate deployment plans and/or documentation"""
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project["status"] == "pending":
        raise HTTPException(status_code=400, detail="Project must be analyzed first")
    
    # Generate content
    result = await generate_plans_and_docs(project, request.generateType, project.get("aiProvider", "gpt_5_2"))
    
    # Determine new status
    new_status = project["status"]
    if request.generateType == "both":
        new_status = "docs_generated"
    elif request.generateType == "plans" and project["status"] == "analyzed":
        new_status = "plans_generated"
    elif request.generateType == "docs":
        new_status = "docs_generated"
    
    # Update project
    update_data = {"status": new_status, "updatedAt": datetime.now(timezone.utc).isoformat()}
    if result.get("deploymentPlans"):
        update_data["deploymentPlans"] = result["deploymentPlans"]
    if result.get("docs"):
        update_data["docs"] = result["docs"]
    
    await db.projects.update_one({"id": project_id}, {"$set": update_data})
    
    return {**project, **update_data}

@api_router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project"""
    result = await db.projects.delete_one({"id": project_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": "Project deleted"}

# Include router and middleware
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
