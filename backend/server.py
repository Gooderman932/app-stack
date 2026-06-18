import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from rate_limit import limiter, check_and_consume_gemini_quota
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import re
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
import uuid
from datetime import datetime, timezone
import httpx
import zipfile
import io
import json
import aiofiles
import tempfile
import asyncio
from google import genai
from google.genai import types
from google.oauth2 import id_token
from google.oauth2 import service_account as google_service_account
from googleapiclient.discovery import build as google_api_build
from google.auth.transport import requests as google_requests

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection. Use .get() with a clear error so a missing env var fails
# at startup with a helpful message instead of raising KeyError mid-import.
mongo_url = os.environ.get('MONGO_URL')
db_name = os.environ.get('DB_NAME')
if not mongo_url or not db_name:
    sys.stderr.write(
        "FATAL: MONGO_URL and DB_NAME environment variables are required.\n"
    )
    raise SystemExit(1)

client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

# Gemini model used for all AI generation (overridable via env)
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')

# Google Play Billing config
PLAY_PACKAGE_NAME = os.environ.get('GOOGLE_PLAY_PACKAGE_NAME', 'com.poordudeholdings.appstack')
PLAY_SERVICE_ACCOUNT_FILE = os.environ.get('GOOGLE_PLAY_SERVICE_ACCOUNT_FILE')
# Map Play Store subscription product IDs -> internal tier names
PLAY_PRODUCT_TIERS = {
    "pro": "pro",
    "team": "team",
}

# Create the main app using a lifespan context manager. @app.on_event is
# deprecated in FastAPI >=0.93 and slated for removal; lifespan is the
# current way to wire startup/shutdown hooks.
@asynccontextmanager
async def lifespan(_app: FastAPI):
    # startup: nothing to do today
    yield
    # shutdown: close the Mongo client
    client.close()


app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
api_router = APIRouter(prefix="/api")


_JSON_FENCE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)


def _strip_json_fence(text: str) -> str:
    """Remove a leading/trailing ```json ... ``` fence from an LLM response.

    The previous in-line logic only stripped the *leading* fence: it split on
    '```' and took element [1], but never trimmed the trailing fence, so
    json.loads always failed when the model used a code fence and the API
    silently fell back to the rule-based stub.
    """
    if not text:
        return text
    text = text.strip()
    match = _JSON_FENCE.match(text)
    if match:
        return match.group(1).strip()
    # Fallback: trim only obvious leading ``` / ```json markers
    if text.startswith("```"):
        text = text.split("```", 2)[-1] if text.count("```") >= 2 else text.lstrip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`").strip()
    return text

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Subscription Tiers ---
SUBSCRIPTION_TIERS = {
    "free": {
        "name": "Free",
        "price": 0.00,
        "project_limit": 3,
        "ai_providers": ["gemini"],
        "can_export_zip": False,
        "reanalyze_limit": 1,
        "features": ["3 projects", "Gemini AI only", "View docs online", "1 re-analysis per project"]
    },
    "pro": {
        "name": "Pro",
        "price": 12.00,
        "project_limit": -1,  # unlimited
        "ai_providers": ["gpt_5_2", "claude", "gemini", "emergent_default"],
        "can_export_zip": True,
        "reanalyze_limit": -1,  # unlimited
        "features": ["Unlimited projects", "All AI providers", "ZIP export", "Unlimited re-analysis", "Priority generation"]
    },
    "team": {
        "name": "Team",
        "price": 29.00,
        "project_limit": -1,
        "ai_providers": ["gpt_5_2", "claude", "gemini", "emergent_default"],
        "can_export_zip": True,
        "reanalyze_limit": -1,
        "features": ["Everything in Pro", "Team collaboration", "Priority support", "Custom templates"]
    }
}

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
    sourceType: str
    sourceUrl: Optional[str] = None
    uploadRef: Optional[str] = None
    textDescription: Optional[str] = None
    theme: str = "dark"
    aiProvider: str = "gemini"
    useEmergentKey: bool = True
    detectedTechStack: DetectedTechStack = Field(default_factory=DetectedTechStack)
    buildSteps: BuildSteps = Field(default_factory=BuildSteps)
    deploymentPlans: DeploymentPlans = Field(default_factory=DeploymentPlans)
    docs: Docs = Field(default_factory=Docs)
    status: str = "pending"
    configFiles: List[str] = []
    envVars: List[str] = []
    reanalyzeCount: int = 0
    userId: Optional[str] = None
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ProjectCreate(BaseModel):
    name: str
    sourceType: str
    sourceUrl: Optional[str] = None
    textDescription: Optional[str] = None
    theme: str = "dark"
    aiProvider: str = "gemini"
    useEmergentKey: bool = True
    techStackHints: List[str] = []
    userId: Optional[str] = None

class GenerateRequest(BaseModel):
    projectId: str
    generateType: str

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    name: Optional[str] = None
    subscription: str = "free"  # free, pro, team
    stripeCustomerId: Optional[str] = None
    subscriptionId: Optional[str] = None
    subscriptionStatus: str = "active"  # active, canceled, past_due
    projectCount: int = 0
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    email: str
    name: Optional[str] = None

class PlayVerifyRequest(BaseModel):
    userId: str
    productId: str  # Play Store subscription product ID (e.g. "pro", "team")
    purchaseToken: str

class PaymentTransaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    userId: str
    sessionId: str
    tier: str
    amount: float
    currency: str = "usd"
    status: str = "pending"  # pending, paid, failed, expired
    paymentStatus: str = "initiated"
    metadata: Dict = {}
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# --- Helper Functions ---
def get_ai_model(provider: str) -> str:
    """All providers currently route to Gemini (the configured free model)."""
    return GEMINI_MODEL


async def call_llm(system_message: str, prompt: str, provider: str) -> str:
    """Send a single prompt to Gemini and return the text response (JSON-formatted)."""
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not configured on this server")

    model_name = get_ai_model(provider)
    genai_client = genai.Client(api_key=api_key)
    response = await genai_client.aio.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_message,
            response_mime_type="application/json",
        ),
    )
    return response.text or ""

async def get_user_tier_limits(user_id: str) -> dict:
    """Get user's subscription tier and limits"""
    if not user_id:
        return SUBSCRIPTION_TIERS["free"]
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        return SUBSCRIPTION_TIERS["free"]
    
    tier = user.get("subscription", "free")
    return SUBSCRIPTION_TIERS.get(tier, SUBSCRIPTION_TIERS["free"])

async def check_project_limit(user_id: str) -> bool:
    """Check if user can create more projects"""
    limits = await get_user_tier_limits(user_id)
    if limits["project_limit"] == -1:
        return True
    
    count = await db.projects.count_documents({"userId": user_id})
    return count < limits["project_limit"]

async def check_ai_provider_access(user_id: str, provider: str) -> bool:
    """Check if user can use the selected AI provider"""
    limits = await get_user_tier_limits(user_id)
    return provider in limits["ai_providers"]

async def check_export_access(user_id: str) -> bool:
    """Check if user can export ZIP"""
    limits = await get_user_tier_limits(user_id)
    return limits["can_export_zip"]

async def check_reanalyze_access(user_id: str, project_id: str) -> bool:
    """Check if user can re-analyze project"""
    limits = await get_user_tier_limits(user_id)
    if limits["reanalyze_limit"] == -1:
        return True
    
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        return False
    
    return project.get("reanalyzeCount", 0) < limits["reanalyze_limit"]

async def fetch_github_files(repo_url: str) -> dict:
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
        "next.config.js", "nuxt.config.js", "angular.json", "serverless.yml"
    ]
    
    files_content = {}
    async with httpx.AsyncClient() as http_client:
        for file_path in key_files:
            try:
                url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{file_path}"
                response = await http_client.get(url, timeout=10)
                if response.status_code == 200:
                    files_content[file_path] = response.text
                else:
                    url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/{file_path}"
                    response = await http_client.get(url, timeout=10)
                    if response.status_code == 200:
                        files_content[file_path] = response.text
            except Exception as e:
                logger.warning(f"Failed to fetch {file_path}: {e}")
    
    return files_content

def parse_uploaded_zip(file_content: bytes) -> dict:
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
    files_summary = ""
    for fname, content in files_content.items():
        files_summary += f"\n--- {fname} ---\n{content[:2000]}\n"
    
    prompt = f"""Analyze this codebase and return a JSON object with the following structure:
{{
  "detectedTechStack": {{
    "frontend": "detected frontend framework/library or empty string",
    "backend": "detected backend framework or empty string",
    "database": "detected database/ORM or empty string",
    "infra": "detected infrastructure tools or empty string",
    "services": "detected services or empty string"
  }},
  "buildSteps": {{
    "frontendBuild": "commands to build frontend",
    "backendBuild": "commands to build/run backend"
  }},
  "configFiles": ["list of config files found"],
  "envVars": ["list of environment variables needed"]
}}

Files found:
{files_summary}

Additional context: {text_description}
Tech stack hints: {', '.join(hints) if hints else 'None'}

Return ONLY valid JSON."""

    try:
        response = await call_llm(
            system_message="You are a code analysis expert. Always return valid JSON only.",
            prompt=prompt,
            provider=provider,
        )
        json_str = _strip_json_fence(response)

        return json.loads(json_str)
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        return rule_based_analysis(files_content)

def rule_based_analysis(files_content: dict) -> dict:
    result = {
        "detectedTechStack": {"frontend": "", "backend": "", "database": "", "infra": "", "services": ""},
        "buildSteps": {"frontendBuild": "", "backendBuild": ""},
        "configFiles": list(files_content.keys()),
        "envVars": []
    }
    
    if "package.json" in files_content:
        pkg = files_content["package.json"]
        if "react" in pkg.lower():
            result["detectedTechStack"]["frontend"] = "React"
        elif "vue" in pkg.lower():
            result["detectedTechStack"]["frontend"] = "Vue.js"
        elif "next" in pkg.lower():
            result["detectedTechStack"]["frontend"] = "Next.js"
        result["buildSteps"]["frontendBuild"] = "npm install && npm run build"
    
    if "requirements.txt" in files_content:
        req = files_content["requirements.txt"]
        if "fastapi" in req.lower():
            result["detectedTechStack"]["backend"] = "FastAPI"
            result["buildSteps"]["backendBuild"] = "pip install -r requirements.txt && uvicorn main:app --host 0.0.0.0 --port 8000"
        elif "django" in req.lower():
            result["detectedTechStack"]["backend"] = "Django"
            result["buildSteps"]["backendBuild"] = "pip install -r requirements.txt && python manage.py runserver"
    
    if "Dockerfile" in files_content:
        result["detectedTechStack"]["infra"] = "Docker"
    
    return result

async def generate_plans_and_docs(project: dict, generate_type: str, provider: str) -> dict:
    tech_stack = project.get("detectedTechStack", {})
    build_steps = project.get("buildSteps", {})
    project_name = project.get("name", "my-project")
    
    context = f"""
Project: {project_name}
Tech Stack: Frontend: {tech_stack.get('frontend', 'N/A')}, Backend: {tech_stack.get('backend', 'N/A')}, Database: {tech_stack.get('database', 'N/A')}, Infra: {tech_stack.get('infra', 'N/A')}
Build Steps: Frontend: {build_steps.get('frontendBuild', 'N/A')}, Backend: {build_steps.get('backendBuild', 'N/A')}
"""

    result = {"deploymentPlans": {}, "docs": {}}
    
    if generate_type in ["plans", "both"]:
        plans_prompt = f"""Based on this project, generate deployment plans as JSON:
{context}

{{
  "genericPlan": "Generic deployment steps with commands",
  "dockerPlan": "Docker deployment with Dockerfile and docker-compose",
  "vmPlan": "Linux VM deployment with systemd service",
  "serverlessPlan": "Serverless/PaaS deployment steps"
}}

Make each plan comprehensive. Return ONLY valid JSON."""

        try:
            response = await call_llm(system_message="DevOps expert. Return JSON only.", prompt=plans_prompt, provider=provider)
            json_str = _strip_json_fence(response)
            result["deploymentPlans"] = json.loads(json_str)
        except Exception as e:
            logger.error(f"Plans generation error: {e}")
            result["deploymentPlans"] = generate_fallback_plans(project_name, tech_stack, build_steps)

    if generate_type in ["docs", "both"]:
        docs_prompt = f"""Based on this project, generate documentation as JSON:
{context}

{{
  "readme": "# {project_name}\\n\\nProject overview and quick start",
  "userGuide": "# User Guide\\n\\n## Prerequisites\\n## Setup\\n## Run/Use\\n## Verify\\n## Troubleshooting",
  "frontendGuide": "# Frontend Guide with same sections",
  "backendGuide": "# Backend Guide with same sections",
  "deploymentGuide": "# Deployment Guide with all paths"
}}

Return ONLY valid JSON."""

        try:
            response = await call_llm(system_message="Technical writer. Return JSON only.", prompt=docs_prompt, provider=provider)
            json_str = _strip_json_fence(response)
            result["docs"] = json.loads(json_str)
        except Exception as e:
            logger.error(f"Docs generation error: {e}")
            result["docs"] = generate_fallback_docs(project_name, tech_stack, build_steps)
    
    return result

def generate_fallback_plans(name: str, tech_stack: dict, build_steps: dict) -> dict:
    fb = build_steps.get("frontendBuild", "npm install && npm run build")
    bb = build_steps.get("backendBuild", "pip install -r requirements.txt && python main.py")
    
    return {
        "genericPlan": f"# Generic Deployment for {name}\n\n1. Clone repo\n2. Install deps: `{fb.split('&&')[0]}`\n3. Configure .env\n4. Build & run\n5. Health check",
        "dockerPlan": f"# Docker Deployment\n\n```dockerfile\nFROM python:3.11-slim\nWORKDIR /app\nCOPY . .\nRUN pip install -r requirements.txt\nCMD [\"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\"]\n```\n\nRun: `docker build -t {name} . && docker run -p 8000:8000 {name}`",
        "vmPlan": f"# VM Deployment\n\n1. Create Linux VM\n2. Install runtime\n3. Clone repo\n4. Create systemd service\n5. Configure nginx",
        "serverlessPlan": f"# Serverless Deployment\n\n**Vercel**: Connect repo, set build command\n**Railway**: Add services, deploy\n**Render**: Create web service"
    }

def generate_fallback_docs(name: str, tech_stack: dict, build_steps: dict) -> dict:
    return {
        "readme": f"# {name}\n\nFull-stack application.\n\n## Quick Start\n```bash\ngit clone [repo]\ncd {name}\nnpm install && pip install -r requirements.txt\n```",
        "userGuide": f"# User Guide\n\n## Prerequisites\n- Browser\n\n## Setup\nNo setup needed.\n\n## Run/Use\nAccess at [URL]\n\n## Verify\nCheck login works\n\n## Troubleshooting\nClear cache if issues",
        "frontendGuide": f"# Frontend Guide\n\n## Prerequisites\n- Node.js 18+\n\n## Setup\n`npm install`\n\n## Run\n`npm start`\n\n## Verify\nVisit localhost:3000\n\n## Troubleshooting\nDelete node_modules and retry",
        "backendGuide": f"# Backend Guide\n\n## Prerequisites\n- Python 3.11+\n\n## Setup\n`pip install -r requirements.txt`\n\n## Run\n`uvicorn main:app`\n\n## Verify\nCurl /api/health\n\n## Troubleshooting\nCheck logs",
        "deploymentGuide": f"# Deployment Guide\n\n## Docker\nBuild and run container\n\n## VM\nSystemd service\n\n## Serverless\nVercel/Railway/Render"
    }

# --- API Routes ---
@api_router.get("/")
async def root():
    return {"message": "Deployment & Docs Copilot API"}

# --- User & Subscription Routes ---
@api_router.get("/tiers")
async def get_tiers():
    """Get all subscription tiers"""
    return SUBSCRIPTION_TIERS

@api_router.post("/users", response_model=User)
async def create_or_get_user(user_data: UserCreate):
    """Create or get existing user"""
    existing = await db.users.find_one({"email": user_data.email}, {"_id": 0})
    if existing:
        return existing
    
    user = User(email=user_data.email, name=user_data.name)
    doc = user.model_dump()
    doc['createdAt'] = doc['createdAt'].isoformat()
    doc['updatedAt'] = doc['updatedAt'].isoformat()
    await db.users.insert_one(doc)
    return user

@api_router.get("/users/{user_id}")
async def get_user(user_id: str):
    """Get user by ID"""
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get project count
    project_count = await db.projects.count_documents({"userId": user_id})
    user["projectCount"] = project_count
    user["tierLimits"] = SUBSCRIPTION_TIERS.get(user.get("subscription", "free"))
    
    return user

@api_router.get("/users/email/{email}")
async def get_user_by_email(email: str):
    """Get user by email"""
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    project_count = await db.projects.count_documents({"userId": user["id"]})
    user["projectCount"] = project_count
    user["tierLimits"] = SUBSCRIPTION_TIERS.get(user.get("subscription", "free"))
    
    return user

# --- Google OAuth Route ---
@api_router.post("/auth/google")
async def auth_with_google(request: Request):
    """Verify a Google ID token and create/return the user"""
    body = await request.json()
    credential = body.get("credential")
    if not credential:
        raise HTTPException(status_code=400, detail="Missing Google credential")

    google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
    if not google_client_id:
        raise HTTPException(status_code=500, detail="Google OAuth not configured on this server")

    try:
        idinfo = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            google_client_id
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {str(e)}")

    email = idinfo["email"]
    name = idinfo.get("name", email.split("@")[0])

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        project_count = await db.projects.count_documents({"userId": existing["id"]})
        existing["projectCount"] = project_count
        existing["tierLimits"] = SUBSCRIPTION_TIERS.get(existing.get("subscription", "free"))
        return existing

    user = User(email=email, name=name)
    doc = user.model_dump()
    doc["createdAt"] = doc["createdAt"].isoformat()
    doc["updatedAt"] = doc["updatedAt"].isoformat()
    await db.users.insert_one(doc)

    user_dict = user.model_dump()
    user_dict["projectCount"] = 0
    user_dict["tierLimits"] = SUBSCRIPTION_TIERS["free"]
    return user_dict

# --- Google Play Billing ---
# Cache the authenticated client so we don't rebuild credentials on every call.
_play_publisher_lock = asyncio.Lock()
_play_publisher_instance = None


def _build_play_publisher():
    """Synchronous builder — expensive (cred file read + HTTP discovery doc)."""
    creds = google_service_account.Credentials.from_service_account_file(
        PLAY_SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/androidpublisher"],
    )
    return google_api_build(
        "androidpublisher", "v3", credentials=creds, cache_discovery=False
    )


async def _play_publisher():
    """Return a cached Android Publisher API client, building it off-loop.

    Previously this was a sync function called *inside* the async endpoint, so
    every request did the credential read + discovery doc fetch on the event
    loop. Now we cache + use asyncio.to_thread for the first build.
    """
    global _play_publisher_instance
    if _play_publisher_instance is not None:
        return _play_publisher_instance
    async with _play_publisher_lock:
        if _play_publisher_instance is None:
            _play_publisher_instance = await asyncio.to_thread(_build_play_publisher)
    return _play_publisher_instance


@api_router.post("/billing/verify")
async def verify_play_purchase(request: PlayVerifyRequest):
    """Verify a Google Play subscription purchase token and grant the matching tier."""
    if not PLAY_SERVICE_ACCOUNT_FILE:
        raise HTTPException(status_code=500, detail="Play billing not configured on this server")

    tier = PLAY_PRODUCT_TIERS.get(request.productId)
    if not tier:
        raise HTTPException(status_code=400, detail="Unknown product")

    user = await db.users.find_one({"id": request.userId}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate the purchase token against the Play Developer API (subscriptions v2)
    try:
        service = await _play_publisher()
        result = await asyncio.to_thread(
            lambda: service.purchases().subscriptionsv2().get(
                packageName=PLAY_PACKAGE_NAME,
                token=request.purchaseToken,
            ).execute()
        )
    except Exception as e:
        logger.error(f"Play verification error: {e}")
        raise HTTPException(status_code=400, detail="Could not verify purchase")

    state = result.get("subscriptionState")
    active = state in ("SUBSCRIPTION_STATE_ACTIVE", "SUBSCRIPTION_STATE_IN_GRACE_PERIOD")
    if not active:
        raise HTTPException(status_code=400, detail=f"Subscription not active ({state})")

    # Record the transaction and upgrade the user's tier
    now_iso = datetime.now(timezone.utc).isoformat()
    transaction = PaymentTransaction(
        userId=request.userId,
        sessionId=request.purchaseToken,
        tier=tier,
        amount=SUBSCRIPTION_TIERS.get(tier, {}).get("price", 0.0),
        currency="usd",
        status="paid",
        paymentStatus="paid",
        metadata={"productId": request.productId, "source": "google_play"},
    )
    tx_doc = transaction.model_dump()
    tx_doc["createdAt"] = tx_doc["createdAt"].isoformat()
    tx_doc["updatedAt"] = tx_doc["updatedAt"].isoformat()
    await db.payment_transactions.update_one(
        {"sessionId": request.purchaseToken},
        {"$set": tx_doc},
        upsert=True,
    )

    await db.users.update_one(
        {"id": request.userId},
        {"$set": {"subscription": tier, "subscriptionStatus": "active", "updatedAt": now_iso}},
    )

    return {"status": "active", "tier": tier}


@api_router.get("/checkout/status/{session_id}")
async def get_checkout_status(session_id: str):
    """Return the status of a checkout session.

    The frontend's PaymentSuccessPage polls this endpoint after the user
    returns from the payment provider. Previously this route did not exist,
    so the frontend always rendered 'Payment Failed'.

    Resolution: look up the payment_transactions row that the Play verify
    endpoint (and any future Stripe webhook) writes by sessionId.
    """
    tx = await db.payment_transactions.find_one(
        {"sessionId": session_id}, {"_id": 0}
    )
    if not tx:
        # No record yet — frontend should keep polling for a bounded number of
        # attempts. We respond 200 with a pending status so the polling loop
        # is driven by data, not HTTP errors.
        return {"sessionId": session_id, "status": "pending", "paymentStatus": "pending"}
    return {
        "sessionId": session_id,
        "status": tx.get("status", "pending"),
        "paymentStatus": tx.get("paymentStatus", tx.get("status", "pending")),
        "tier": tx.get("tier"),
        "amount": tx.get("amount"),
        "currency": tx.get("currency"),
    }


# --- Project Routes ---
@api_router.get("/projects", response_model=List[Project])
async def get_projects(userId: Optional[str] = None):
    """Get all projects, optionally filtered by user"""
    query = {}
    if userId:
        query["userId"] = userId
    
    projects = await db.projects.find(query, {"_id": 0}).sort("createdAt", -1).to_list(100)
    for p in projects:
        if isinstance(p.get('createdAt'), str):
            p['createdAt'] = datetime.fromisoformat(p['createdAt'])
        if isinstance(p.get('updatedAt'), str):
            p['updatedAt'] = datetime.fromisoformat(p['updatedAt'])
    return projects

@api_router.get("/projects/{project_id}")
async def get_project(project_id: str):
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@api_router.post("/projects", response_model=Project)
async def create_project(project_data: ProjectCreate):
    user_id = project_data.userId
    
    # Check project limit
    if user_id and not await check_project_limit(user_id):
        raise HTTPException(status_code=403, detail="Project limit reached. Please upgrade to Pro.")
    
    # Check AI provider access
    if user_id and not await check_ai_provider_access(user_id, project_data.aiProvider):
        raise HTTPException(status_code=403, detail=f"AI provider '{project_data.aiProvider}' requires Pro subscription.")
    
    project = Project(
        name=project_data.name,
        sourceType=project_data.sourceType,
        sourceUrl=project_data.sourceUrl,
        textDescription=project_data.textDescription,
        theme=project_data.theme,
        aiProvider=project_data.aiProvider,
        useEmergentKey=project_data.useEmergentKey,
        userId=user_id
    )
    doc = project.model_dump()
    doc['createdAt'] = doc['createdAt'].isoformat()
    doc['updatedAt'] = doc['updatedAt'].isoformat()
    await db.projects.insert_one(doc)
    
    # Update user project count
    if user_id:
        await db.users.update_one({"id": user_id}, {"$inc": {"projectCount": 1}})
    
    return project

@api_router.post("/projects/{project_id}/upload")
async def upload_file(project_id: str, file: UploadFile = File(...)):
    content = await file.read()
    file_id = str(uuid.uuid4())
    temp_dir = Path(tempfile.gettempdir()) / "copilot_uploads"
    temp_dir.mkdir(exist_ok=True)
    file_path = temp_dir / f"{file_id}.zip"
    
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)
    
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {"uploadRef": str(file_path), "updatedAt": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"message": "File uploaded", "fileId": file_id}

@api_router.post("/projects/{project_id}/analyze")
@limiter.limit("10/minute")
async def analyze_project(request: Request, project_id: str, reanalyze: bool = False):
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    user_id = project.get("userId")
    
    # Check re-analyze limit
    if reanalyze and user_id and not await check_reanalyze_access(user_id, project_id):
        raise HTTPException(status_code=403, detail="Re-analysis limit reached. Upgrade to Pro for unlimited re-analysis.")

    # Per-user daily Gemini quota (tier-aware).
    if user_id:
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "subscription": 1})
        tier = (user or {}).get("subscription", "free")
        allowed, used, quota = await check_and_consume_gemini_quota(db, user_id, tier)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Daily AI quota exceeded ({used}/{quota}). Resets at 00:00 UTC.",
            )
    
    files_content = {}
    
    if project["sourceType"] == "github_url" and project.get("sourceUrl"):
        files_content = await fetch_github_files(project["sourceUrl"])
    elif project["sourceType"] == "upload" and project.get("uploadRef"):
        try:
            async with aiofiles.open(project["uploadRef"], 'rb') as f:
                content = await f.read()
            files_content = parse_uploaded_zip(content)
        except Exception as e:
            logger.error(f"Error reading uploaded file: {e}")
    
    text_desc = project.get("textDescription", "")
    analysis = await analyze_with_ai(files_content, text_desc, [], project.get("aiProvider", "gemini"))
    
    update_data = {
        "detectedTechStack": analysis.get("detectedTechStack", {}),
        "buildSteps": analysis.get("buildSteps", {}),
        "configFiles": analysis.get("configFiles", []),
        "envVars": analysis.get("envVars", []),
        "status": "analyzed",
        "updatedAt": datetime.now(timezone.utc).isoformat()
    }
    
    if reanalyze:
        update_data["reanalyzeCount"] = project.get("reanalyzeCount", 0) + 1
    
    await db.projects.update_one({"id": project_id}, {"$set": update_data})
    
    return {**project, **update_data}

@api_router.post("/projects/{project_id}/generate")
@limiter.limit("10/minute")
async def generate_content(http_request: Request, project_id: str, request: GenerateRequest):
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project["status"] == "pending":
        raise HTTPException(status_code=400, detail="Project must be analyzed first")
    
    # Per-user daily Gemini quota (tier-aware) — same accounting as /analyze.
    user_id = project.get("userId")
    if user_id:
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "subscription": 1})
        tier = (user or {}).get("subscription", "free")
        allowed, used, quota = await check_and_consume_gemini_quota(db, user_id, tier)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Daily AI quota exceeded ({used}/{quota}). Resets at 00:00 UTC.",
            )
    
    result = await generate_plans_and_docs(project, request.generateType, project.get("aiProvider", "gemini"))
    
    new_status = project["status"]
    if request.generateType == "both":
        new_status = "docs_generated"
    elif request.generateType == "plans" and project["status"] == "analyzed":
        new_status = "plans_generated"
    elif request.generateType == "docs":
        new_status = "docs_generated"
    
    update_data = {"status": new_status, "updatedAt": datetime.now(timezone.utc).isoformat()}
    if result.get("deploymentPlans"):
        update_data["deploymentPlans"] = result["deploymentPlans"]
    if result.get("docs"):
        update_data["docs"] = result["docs"]
    
    await db.projects.update_one({"id": project_id}, {"$set": update_data})
    
    return {**project, **update_data}

@api_router.get("/projects/{project_id}/can-export")
async def check_can_export(project_id: str):
    """Check if user can export this project"""
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    user_id = project.get("userId")
    can_export = await check_export_access(user_id) if user_id else False
    
    return {"canExport": can_export}

@api_router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    result = await db.projects.delete_one({"id": project_id})
    
    # Update user project count
    user_id = project.get("userId")
    if user_id:
        await db.users.update_one({"id": user_id}, {"$inc": {"projectCount": -1}})
    
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

# Shutdown is handled by the `lifespan` context manager above. The old
# @app.on_event("shutdown") hook is deprecated in FastAPI >=0.93 and was
# removed in favor of the lifespan API.
