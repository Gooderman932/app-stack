import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Request, Depends
from fastapi.security import HTTPBearer
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
from datetime import datetime, timezone, timedelta
import httpx
import zipfile
import io
import json
import secrets
import hashlib
import jwt as pyjwt
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

# --- Authentication: server-issued session tokens ---------------------------
# POST /api/auth/google verifies a Google ID token and issues a short-lived
# JWT session token. Every other user/project/billing route requires that
# token (Authorization: Bearer <token>) and only ever acts on the user the
# token identifies — client-supplied userId/email values are never trusted.
# SESSION_SECRET must be set to a long random value in production; if it is
# unset we generate an ephemeral one so local dev still works, but sessions
# then do not survive a restart (a warning is logged).
SESSION_SECRET = os.environ.get('SESSION_SECRET')
if not SESSION_SECRET:
    SESSION_SECRET = secrets.token_urlsafe(32)
    logger_warning = logging.getLogger(__name__)
    logger_warning.warning(
        "SESSION_SECRET not set — using an ephemeral secret; "
        "sessions will not survive a restart. Set SESSION_SECRET in production."
    )
SESSION_TTL = timedelta(days=7)

# --- Upload limits -----------------------------------------------------------
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB per uploaded ZIP
MAX_UPLOAD_UNCOMPRESSED_BYTES = 100 * 1024 * 1024  # 100 MB total when unzipped
ALLOWED_UPLOAD_CONTENT_TYPES = {
    "application/zip",
    "application/x-zip-compressed",
    "application/octet-stream",
}


def _cors_origins() -> list:
    """Safe CORS default: never '*' with credentials.

    Unset CORS_ORIGINS -> local dev frontend only. An explicit '*' is
    dropped (with a warning) because Starlette refuses/ignores '*' together
    with allow_credentials=True and it would expose authenticated APIs to
    any origin. Deploy-time: set CORS_ORIGINS to the exact frontend origin(s).
    """
    raw = os.environ.get('CORS_ORIGINS', '')
    if not raw.strip():
        return ["http://localhost:3000"]
    origins = [o.strip() for o in raw.split(',') if o.strip()]
    if '*' in origins:
        logging.getLogger(__name__).warning(
            "CORS_ORIGINS contains '*' with credentials — '*' dropped; "
            "set explicit origins instead."
        )
        origins = [o for o in origins if o != '*'] or ["http://localhost:3000"]
    return origins
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
    # One Google Play purchase token pays for one account. The verify route
    # checks that; this unique index makes it hold even when two accounts
    # race to claim the same token. Built in the background so a slow or
    # unreachable database does not block startup.
    async def _ensure_indexes():
        try:
            await db.payment_transactions.create_index(
                "sessionId", unique=True,
                partialFilterExpression={"sessionId": {"$type": "string"}},
            )
        except Exception as e:  # noqa: BLE001 - logged, never fatal
            logging.getLogger(__name__).error(
                "Could not ensure unique payment_transactions.sessionId: %s", e)
    index_task = asyncio.create_task(_ensure_indexes())
    yield
    index_task.cancel()
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
    # Legacy field — no Stripe integration exists in this codebase
    # (billing is Google Play only); kept only so stored user documents
    # still validate. Do not treat it as evidence of a Stripe customer.
    stripeCustomerId: Optional[str] = None
    subscriptionId: Optional[str] = None
    subscriptionStatus: str = "active"  # active, canceled, past_due
    projectCount: int = 0
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    email: str
    name: Optional[str] = None


# --- Authentication helpers -------------------------------------------------
def create_session_token(user: dict) -> str:
    """Issue a signed JWT session token for an already-verified user."""
    now = datetime.now(timezone.utc)
    return pyjwt.encode(
        {
            "sub": user["id"],
            "email": user.get("email"),
            # Session version: POST /api/auth/logout bumps the user's
            # sessionVersion, which invalidates every token issued before it.
            "ver": user.get("sessionVersion", 0),
            "iat": now,
            "exp": now + SESSION_TTL,
        },
        SESSION_SECRET,
        algorithm="HS256",
    )


async def get_current_user(request: Request) -> dict:
    """Dependency: resolve the caller from a Bearer session token.

    The token is issued only by POST /api/auth/google after Google verifies
    the ID token. A missing, malformed, expired, or forged token is 401;
    a token whose user no longer exists is also 401. Nothing in the request
    body/query can substitute for this check.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = auth[len("Bearer "):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    try:
        payload = pyjwt.decode(
            token, SESSION_SECRET, algorithms=["HS256"],
            options={"require": ["sub", "exp"]},
        )
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired session token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Session user not found")
    if payload.get("ver", 0) != user.get("sessionVersion", 0):
        raise HTTPException(status_code=401, detail="Session has been signed out")
    return user


async def require_project_owner(project_id: str, current_user: dict) -> dict:
    """Load a project and enforce ownership. 404 if missing, 403 if another
    user's. Returns the project document."""
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("userId") != current_user["id"]:
        raise HTTPException(status_code=403, detail="You do not own this project")
    return project


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
    
    tier = await effective_tier(user)
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
            # Zip-bomb guard: refuse archives whose uncompressed total
            # exceeds MAX_UPLOAD_UNCOMPRESSED_BYTES.
            total_uncompressed = sum(info.file_size for info in zf.infolist())
            if total_uncompressed > MAX_UPLOAD_UNCOMPRESSED_BYTES:
                logger.error("Uploaded ZIP exceeds uncompressed size limit")
                return {}
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
# SECURITY: the old email-only POST /api/users (log in as anyone by email)
# and the unauthenticated GET /api/users/email/{email} were removed.
# The only way to obtain an account/session is POST /api/auth/google,
# which verifies a Google ID token server-side and issues a session token.
@api_router.get("/tiers")
async def get_tiers():
    """Get all subscription tiers"""
    return SUBSCRIPTION_TIERS


@api_router.post("/auth/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Sign out everywhere: every session token issued before now stops working."""
    await db.users.update_one({"id": current_user["id"]}, {"$inc": {"sessionVersion": 1}})
    return {"ok": True}


@api_router.get("/users/me")
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """Get the authenticated caller's own profile."""
    user = dict(current_user)
    project_count = await db.projects.count_documents({"userId": user["id"]})
    user["projectCount"] = project_count
    await _apply_effective_tier(user)
    return user


@api_router.get("/users/{user_id}")
async def get_user(user_id: str, current_user: dict = Depends(get_current_user)):
    """Get a user by ID — only your own record."""
    if user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="You can only view your own profile")
    user = dict(current_user)
    project_count = await db.projects.count_documents({"userId": user_id})
    user["projectCount"] = project_count
    await _apply_effective_tier(user)
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

    # Only a Google-verified email may own an account: an unverified address
    # could belong to someone else, and accounts are keyed by email.
    if not idinfo.get("email") or idinfo.get("email_verified") is not True:
        raise HTTPException(status_code=401, detail="Google account email is not verified")

    email = idinfo["email"]
    name = idinfo.get("name", email.split("@")[0])

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        project_count = await db.projects.count_documents({"userId": existing["id"]})
        existing["projectCount"] = project_count
        await _apply_effective_tier(existing)
        existing["sessionToken"] = create_session_token(existing)
        return existing

    user = User(email=email, name=name)
    doc = user.model_dump()
    doc["createdAt"] = doc["createdAt"].isoformat()
    doc["updatedAt"] = doc["updatedAt"].isoformat()
    await db.users.insert_one(doc)

    user_dict = user.model_dump()
    user_dict["projectCount"] = 0
    user_dict["tierLimits"] = SUBSCRIPTION_TIERS["free"]
    user_dict["sessionToken"] = create_session_token(user_dict)
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


# Subscription states in which Google Play grants access. CANCELED means
# auto-renew is off but the paid period has not ended yet.
PLAY_ACCESS_STATES = {"SUBSCRIPTION_STATE_ACTIVE", "SUBSCRIPTION_STATE_IN_GRACE_PERIOD"}
# While Google cannot be reached to confirm a renewal, a lapsed subscription
# keeps its tier this long (outage tolerance, not free time).
PLAY_RENEWAL_CHECK_GRACE = timedelta(hours=72)
# User-document fields the effective-tier check needs.
TIER_FIELDS = {"id": 1, "subscription": 1, "subscriptionExpiresAt": 1, "playPurchaseToken": 1}

_PLAY_TIME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:\d{2})$")


def _parse_play_time(value) -> Optional[datetime]:
    """Parse an RFC 3339 timestamp from the Play Developer API (up to 9 fractional digits)."""
    if not isinstance(value, str):
        return None
    m = _PLAY_TIME_RE.match(value)
    if not m:
        return None
    base, frac, tz = m.groups()
    frac = ((frac or "") + "000000")[:6]
    return datetime.fromisoformat(f"{base}.{frac}{'+00:00' if tz == 'Z' else tz}")


def _parse_stored_time(value) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def play_account_id(user_id: str) -> str:
    """The obfuscatedAccountId the Android app attaches to this user's purchases.

    Mirrors cordova-plugin-purchase's 'uuid' obfuscator (App.js sets
    store.obfuscator = 'uuid' and applicationUsername = the user id): the MD5
    of the user id, formatted as a UUID with version nibble 3 and variant 8.
    """
    h = hashlib.md5(user_id.encode("utf-8"), usedforsecurity=False).hexdigest()
    return f"{h[0:8]}-{h[8:12]}-3{h[13:16]}-8{h[17:20]}-{h[20:32]}"


async def _fetch_play_subscription(purchase_token: str) -> dict:
    service = await _play_publisher()
    return await asyncio.to_thread(
        lambda: service.purchases().subscriptionsv2().get(
            packageName=PLAY_PACKAGE_NAME,
            token=purchase_token,
        ).execute()
    )


def _play_line_item(result: dict, product_id: Optional[str] = None) -> Optional[dict]:
    """The line item for one of our subscription products (optionally a given one)."""
    for item in result.get("lineItems") or []:
        pid = item.get("productId")
        if pid in PLAY_PRODUCT_TIERS and (product_id is None or pid == product_id):
            return item
    return None


def _play_access_until(result: dict, item: dict, now: datetime) -> Optional[datetime]:
    """When this Play subscription's access ends, or None if it grants none now."""
    state = result.get("subscriptionState")
    expiry = _parse_play_time(item.get("expiryTime"))
    if state in PLAY_ACCESS_STATES:
        # In a grace period Google keeps access past expiryTime: check again tomorrow.
        return expiry if expiry and expiry > now else now + timedelta(days=1)
    if state == "SUBSCRIPTION_STATE_CANCELED" and expiry and expiry > now:
        return expiry
    return None


async def effective_tier(user: Optional[dict]) -> str:
    """The tier this user is entitled to right now.

    Google Play subscriptions carry an expiry. Once it passes, ask Google
    whether the subscription renewed (renewals keep the same purchase token,
    and the app does not re-send purchases it already acknowledged): extend it
    if so, drop the account to free if not. Grants without an expiry (made
    before expiry tracking, or set by hand) are left as they are.
    """
    if not user:
        return "free"
    tier = user.get("subscription") or "free"
    if tier == "free" or tier not in SUBSCRIPTION_TIERS:
        return "free"
    expires_at = _parse_stored_time(user.get("subscriptionExpiresAt"))
    now = datetime.now(timezone.utc)
    if expires_at is None or now < expires_at:
        return tier

    token = user.get("playPurchaseToken")
    if token and PLAY_SERVICE_ACCOUNT_FILE:
        try:
            result = await _fetch_play_subscription(token)
        except Exception as e:  # noqa: BLE001 - outage handling below
            logger.warning("Play renewal check failed for user %s: %s", user.get("id"), e)
            return tier if now - expires_at < PLAY_RENEWAL_CHECK_GRACE else "free"
        item = _play_line_item(result)
        access_until = _play_access_until(result, item, now) if item else None
        if access_until:
            renewed_tier = PLAY_PRODUCT_TIERS[item["productId"]]
            await db.users.update_one({"id": user["id"]}, {"$set": {
                "subscription": renewed_tier,
                "subscriptionStatus": "active",
                "subscriptionExpiresAt": access_until.isoformat(),
                "updatedAt": now.isoformat(),
            }})
            return renewed_tier

    await db.users.update_one({"id": user["id"]}, {"$set": {
        "subscription": "free",
        "subscriptionStatus": "expired",
        "updatedAt": now.isoformat(),
    }})
    return "free"


async def _apply_effective_tier(user: dict) -> None:
    """Rewrite a user document for an API response: current tier, no purchase token."""
    tier = await effective_tier(user)
    user["subscription"] = tier
    user["tierLimits"] = SUBSCRIPTION_TIERS.get(tier, SUBSCRIPTION_TIERS["free"])
    user.pop("playPurchaseToken", None)


@api_router.post("/billing/verify")
async def verify_play_purchase(request: PlayVerifyRequest, current_user: dict = Depends(get_current_user)):
    """Verify a Google Play subscription purchase token and grant the matching tier.

    Only what Google reports is trusted: the tier comes from the product the
    token actually bought, the token must belong to this account, and the
    grant lasts until the subscription's expiry (see effective_tier).
    """
    if request.userId != current_user["id"]:
        raise HTTPException(status_code=403, detail="You can only verify purchases for your own account")
    if not PLAY_SERVICE_ACCOUNT_FILE:
        raise HTTPException(status_code=500, detail="Play billing not configured on this server")
    if request.productId not in PLAY_PRODUCT_TIERS:
        raise HTTPException(status_code=400, detail="Unknown product")

    # One purchase token pays for one account.
    claimed = await db.payment_transactions.find_one(
        {"sessionId": request.purchaseToken}, {"_id": 0, "userId": 1})
    if claimed and claimed.get("userId") != current_user["id"]:
        raise HTTPException(status_code=409, detail="This purchase is linked to another account")

    try:
        result = await _fetch_play_subscription(request.purchaseToken)
    except Exception as e:
        logger.error(f"Play verification error: {e}")
        raise HTTPException(status_code=400, detail="Could not verify purchase")

    # The tier comes from what Google says was bought, never from the request.
    item = _play_line_item(result, request.productId)
    if not item:
        raise HTTPException(status_code=400, detail="Purchase does not match the requested product")
    tier = PLAY_PRODUCT_TIERS[item["productId"]]

    # Purchases made by the app carry the buyer's obfuscated account id.
    owner = (result.get("externalAccountIdentifiers") or {}).get("obfuscatedExternalAccountId")
    if owner and owner != play_account_id(current_user["id"]):
        raise HTTPException(status_code=403, detail="This purchase belongs to another account")

    now = datetime.now(timezone.utc)
    access_until = _play_access_until(result, item, now)
    if not access_until:
        raise HTTPException(
            status_code=400, detail=f"Subscription not active ({result.get('subscriptionState')})")

    # Record the transaction and upgrade the user's tier
    now_iso = now.isoformat()
    transaction = PaymentTransaction(
        userId=current_user["id"],
        sessionId=request.purchaseToken,
        tier=tier,
        amount=SUBSCRIPTION_TIERS.get(tier, {}).get("price", 0.0),
        currency="usd",
        status="paid",
        paymentStatus="paid",
        metadata={
            "productId": item["productId"],
            "source": "google_play",
            "expiresAt": access_until.isoformat(),
            "testPurchase": "testPurchase" in result,
            "linkedPurchaseToken": result.get("linkedPurchaseToken"),
        },
    )
    tx_doc = transaction.model_dump()
    tx_doc["createdAt"] = tx_doc["createdAt"].isoformat()
    tx_doc["updatedAt"] = tx_doc["updatedAt"].isoformat()
    # Re-verifying the same purchase refreshes the record but keeps its identity.
    on_insert = {"id": tx_doc.pop("id"), "createdAt": tx_doc.pop("createdAt")}
    try:
        await db.payment_transactions.update_one(
            {"sessionId": request.purchaseToken, "userId": current_user["id"]},
            {"$set": tx_doc, "$setOnInsert": on_insert},
            upsert=True,
        )
    except Exception as e:  # unique index: another account claimed it first
        if type(e).__name__ == "DuplicateKeyError":
            raise HTTPException(status_code=409, detail="This purchase is linked to another account")
        raise

    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {
            "subscription": tier,
            "subscriptionStatus": "active",
            "subscriptionExpiresAt": access_until.isoformat(),
            "playPurchaseToken": request.purchaseToken,
            "updatedAt": now_iso,
        }},
    )

    return {"status": "active", "tier": tier, "expiresAt": access_until.isoformat()}


@api_router.get("/checkout/status/{session_id}")
async def get_checkout_status(session_id: str, current_user: dict = Depends(get_current_user)):
    """Return the status of a checkout session.

    The frontend's PaymentSuccessPage polls this endpoint after the user
    returns from the payment provider. Previously this route did not exist,
    so the frontend always rendered 'Payment Failed'.

    Resolution: look up the payment_transactions row that the Play verify
    endpoint writes by sessionId.
    Only the transaction owner's sessions are visible; anyone else's
    sessionId returns the same pending response as a missing one.
    """
    tx = await db.payment_transactions.find_one(
        {"sessionId": session_id, "userId": current_user["id"]}, {"_id": 0}
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
async def get_projects(userId: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get the authenticated user's own projects.

    A client-supplied userId that is not the caller's own is rejected (403);
    without one, the list is always scoped to the caller — the old behaviour
    of returning everyone's projects when no userId was given is gone.
    """
    if userId is not None and userId != current_user["id"]:
        raise HTTPException(status_code=403, detail="You can only list your own projects")
    query = {"userId": current_user["id"]}

    projects = await db.projects.find(query, {"_id": 0}).sort("createdAt", -1).to_list(100)
    for p in projects:
        if isinstance(p.get('createdAt'), str):
            p['createdAt'] = datetime.fromisoformat(p['createdAt'])
        if isinstance(p.get('updatedAt'), str):
            p['updatedAt'] = datetime.fromisoformat(p['updatedAt'])
    return projects

@api_router.get("/projects/{project_id}")
async def get_project(project_id: str, current_user: dict = Depends(get_current_user)):
    return await require_project_owner(project_id, current_user)

@api_router.post("/projects", response_model=Project)
async def create_project(project_data: ProjectCreate, current_user: dict = Depends(get_current_user)):
    # Ownership is taken from the session token, never from the request body:
    # a client-supplied userId is ignored so one user cannot create projects
    # (or spend another user's quota/limits) under someone else's id.
    user_id = current_user["id"]
    
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
async def upload_file(project_id: str, file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    # Owner only, and only ZIP files up to MAX_UPLOAD_BYTES. The previous
    # endpoint had no auth and no size limit, so anyone could overwrite any
    # project's uploadRef with an arbitrarily large file.
    await require_project_owner(project_id, current_user)
    filename = (file.filename or "").lower()
    if not filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are accepted")
    if file.content_type and file.content_type not in ALLOWED_UPLOAD_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Only .zip files are accepted")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Upload exceeds the 10 MB limit")
    if not content.startswith((b"PK\x03\x04", b"PK\x05\x06")):
        raise HTTPException(status_code=400, detail="File is not a valid ZIP archive")
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
async def analyze_project(request: Request, project_id: str, reanalyze: bool = False, current_user: dict = Depends(get_current_user)):
    project = await require_project_owner(project_id, current_user)
    
    user_id = project.get("userId")
    
    # Check re-analyze limit
    if reanalyze and user_id and not await check_reanalyze_access(user_id, project_id):
        raise HTTPException(status_code=403, detail="Re-analysis limit reached. Upgrade to Pro for unlimited re-analysis.")

    # Per-user daily Gemini quota (tier-aware).
    if user_id:
        user = await db.users.find_one({"id": user_id}, {"_id": 0, **TIER_FIELDS})
        tier = await effective_tier(user)
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
async def generate_content(http_request: Request, project_id: str, request: GenerateRequest, current_user: dict = Depends(get_current_user)):
    project = await require_project_owner(project_id, current_user)
    
    if project["status"] == "pending":
        raise HTTPException(status_code=400, detail="Project must be analyzed first")
    
    # Per-user daily Gemini quota (tier-aware) — same accounting as /analyze.
    user_id = project.get("userId")
    if user_id:
        user = await db.users.find_one({"id": user_id}, {"_id": 0, **TIER_FIELDS})
        tier = await effective_tier(user)
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
async def check_can_export(project_id: str, current_user: dict = Depends(get_current_user)):
    """Check if user can export this project"""
    project = await require_project_owner(project_id, current_user)

    user_id = project.get("userId")
    can_export = await check_export_access(user_id) if user_id else False
    
    return {"canExport": can_export}

@api_router.delete("/projects/{project_id}")
async def delete_project(project_id: str, current_user: dict = Depends(get_current_user)):
    project = await require_project_owner(project_id, current_user)

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
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shutdown is handled by the `lifespan` context manager above. The old
# @app.on_event("shutdown") hook is deprecated in FastAPI >=0.93 and was
# removed in favor of the lifespan API.
