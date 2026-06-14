from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
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
from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest

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

class CheckoutRequest(BaseModel):
    userId: str
    tier: str  # pro or team
    originUrl: str

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

class GooglePlayVerifyRequest(BaseModel):
    userId: str
    tier: str          # pro or team
    purchaseToken: str
    orderId: str
    productId: str
    packageName: str = "com.stackpilot.app"

# --- Helper Functions ---
def get_ai_model(provider: str):
    models = {
        "gpt_5_2": ("openai", "gpt-5.2"),
        "claude": ("anthropic", "claude-sonnet-4-5-20250929"),
        "gemini": ("gemini", "gemini-3-flash-preview"),
        "emergent_default": ("openai", "gpt-5.2")
    }
    return models.get(provider, ("gemini", "gemini-3-flash-preview"))

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
    api_key = os.environ.get('EMERGENT_LLM_KEY')
    provider_name, model_name = get_ai_model(provider)
    
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
        chat = LlmChat(
            api_key=api_key,
            session_id=f"analyze-{uuid.uuid4()}",
            system_message="You are a code analysis expert. Always return valid JSON only."
        ).with_model(provider_name, model_name)
        
        response = await chat.send_message(UserMessage(text=prompt))
        json_str = response.strip()
        if json_str.startswith("```"):
            json_str = json_str.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]
        
        return json.loads(json_str.strip())
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
    api_key = os.environ.get('EMERGENT_LLM_KEY')
    provider_name, model_name = get_ai_model(provider)
    
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
            chat = LlmChat(api_key=api_key, session_id=f"plans-{uuid.uuid4()}", system_message="DevOps expert. Return JSON only.").with_model(provider_name, model_name)
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
            chat = LlmChat(api_key=api_key, session_id=f"docs-{uuid.uuid4()}", system_message="Technical writer. Return JSON only.").with_model(provider_name, model_name)
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

# --- Stripe Payment Routes ---
@api_router.post("/checkout/create")
async def create_checkout_session(request: CheckoutRequest, http_request: Request):
    """Create Stripe checkout session for subscription"""
    if request.tier not in ["pro", "team"]:
        raise HTTPException(status_code=400, detail="Invalid tier")
    
    user = await db.users.find_one({"id": request.userId}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get amount from server-side definition
    amount = SUBSCRIPTION_TIERS[request.tier]["price"]
    
    # Build URLs from provided origin
    success_url = f"{request.originUrl}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{request.originUrl}/pricing"
    
    # Initialize Stripe
    api_key = os.environ.get('STRIPE_API_KEY')
    host_url = str(http_request.base_url).rstrip('/')
    webhook_url = f"{host_url}api/webhook/stripe"
    
    stripe_checkout = StripeCheckout(api_key=api_key, webhook_url=webhook_url)
    
    # Create checkout session
    checkout_request = CheckoutSessionRequest(
        amount=amount,
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "user_id": request.userId,
            "tier": request.tier,
            "user_email": user.get("email", "")
        }
    )
    
    session = await stripe_checkout.create_checkout_session(checkout_request)
    
    # Create payment transaction record
    transaction = PaymentTransaction(
        userId=request.userId,
        sessionId=session.session_id,
        tier=request.tier,
        amount=amount,
        currency="usd",
        status="pending",
        paymentStatus="initiated",
        metadata={"user_email": user.get("email", "")}
    )
    
    tx_doc = transaction.model_dump()
    tx_doc['createdAt'] = tx_doc['createdAt'].isoformat()
    tx_doc['updatedAt'] = tx_doc['updatedAt'].isoformat()
    await db.payment_transactions.insert_one(tx_doc)
    
    return {"url": session.url, "sessionId": session.session_id}

@api_router.get("/checkout/status/{session_id}")
async def get_checkout_status(session_id: str, http_request: Request):
    """Get checkout session status and update subscription"""
    api_key = os.environ.get('STRIPE_API_KEY')
    host_url = str(http_request.base_url).rstrip('/')
    webhook_url = f"{host_url}api/webhook/stripe"
    
    stripe_checkout = StripeCheckout(api_key=api_key, webhook_url=webhook_url)
    
    try:
        status = await stripe_checkout.get_checkout_status(session_id)
        
        # Find the transaction
        transaction = await db.payment_transactions.find_one({"sessionId": session_id}, {"_id": 0})
        
        if transaction and status.payment_status == "paid" and transaction.get("status") != "paid":
            # Update transaction
            await db.payment_transactions.update_one(
                {"sessionId": session_id},
                {"$set": {
                    "status": "paid",
                    "paymentStatus": status.payment_status,
                    "updatedAt": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            # Upgrade user subscription
            tier = transaction.get("tier", "pro")
            await db.users.update_one(
                {"id": transaction["userId"]},
                {"$set": {
                    "subscription": tier,
                    "subscriptionStatus": "active",
                    "updatedAt": datetime.now(timezone.utc).isoformat()
                }}
            )
        elif transaction and status.status == "expired":
            await db.payment_transactions.update_one(
                {"sessionId": session_id},
                {"$set": {"status": "expired", "updatedAt": datetime.now(timezone.utc).isoformat()}}
            )
        
        return {
            "status": status.status,
            "paymentStatus": status.payment_status,
            "amount": status.amount_total,
            "currency": status.currency
        }
    except Exception as e:
        logger.error(f"Checkout status error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get checkout status")

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    body = await request.body()
    signature = request.headers.get("Stripe-Signature")
    
    api_key = os.environ.get('STRIPE_API_KEY')
    host_url = str(request.base_url).rstrip('/')
    webhook_url = f"{host_url}api/webhook/stripe"
    
    stripe_checkout = StripeCheckout(api_key=api_key, webhook_url=webhook_url)
    
    try:
        event = await stripe_checkout.handle_webhook(body, signature)
        
        if event.payment_status == "paid":
            transaction = await db.payment_transactions.find_one({"sessionId": event.session_id}, {"_id": 0})
            if transaction and transaction.get("status") != "paid":
                await db.payment_transactions.update_one(
                    {"sessionId": event.session_id},
                    {"$set": {"status": "paid", "paymentStatus": "paid", "updatedAt": datetime.now(timezone.utc).isoformat()}}
                )
                
                tier = event.metadata.get("tier", "pro")
                user_id = event.metadata.get("user_id")
                if user_id:
                    await db.users.update_one(
                        {"id": user_id},
                        {"$set": {"subscription": tier, "subscriptionStatus": "active", "updatedAt": datetime.now(timezone.utc).isoformat()}}
                    )
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}

# --- Google Play Billing ---

async def _verify_with_play_api(package_name: str, product_id: str, purchase_token: str) -> bool:
    """
    Verify a subscription purchase token with the Google Play Developer API.
    Requires GOOGLE_PLAY_CREDENTIALS_JSON env var (service account JSON as a string).
    Returns True if the subscription is active/valid, False otherwise.
    Falls back to True (trust client) if credentials are not configured.
    """
    creds_json = os.environ.get("GOOGLE_PLAY_CREDENTIALS_JSON")
    if not creds_json:
        logger.warning("GOOGLE_PLAY_CREDENTIALS_JSON not set — skipping server-side Play Store verification (set this in production)")
        return True

    try:
        import json as _json
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds_info = _json.loads(creds_json)
        credentials = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=["https://www.googleapis.com/auth/androidpublisher"]
        )
        service = build("androidpublisher", "v3", credentials=credentials, cache_discovery=False)
        result = service.purchases().subscriptionsv2().get(
            packageName=package_name,
            token=purchase_token
        ).execute()

        subscription_state = result.get("subscriptionState", "")
        # SUBSCRIPTION_STATE_ACTIVE or SUBSCRIPTION_STATE_IN_GRACE_PERIOD are valid
        return subscription_state in ("SUBSCRIPTION_STATE_ACTIVE", "SUBSCRIPTION_STATE_IN_GRACE_PERIOD")
    except Exception as e:
        logger.error(f"Google Play API verification error: {e}")
        return False


@api_router.post("/google-play/verify-purchase")
async def verify_google_play_purchase(request: GooglePlayVerifyRequest):
    """
    Verify a Google Play subscription purchase token and activate the subscription.
    Called by the Android app immediately after a successful billing flow.
    """
    if request.tier not in ["pro", "team"]:
        raise HTTPException(status_code=400, detail="Invalid subscription tier")

    user = await db.users.find_one({"id": request.userId}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Reject duplicate tokens that are already recorded as paid
    existing = await db.google_play_purchases.find_one({"purchaseToken": request.purchaseToken, "status": "active"})
    if existing:
        if existing["userId"] != request.userId:
            raise HTTPException(status_code=409, detail="Purchase token already used by another account")
        # Idempotent: same user, same token — return success
        return {"status": "ok", "subscription": request.tier}

    # Verify with Google Play Developer API
    is_valid = await _verify_with_play_api(request.packageName, request.productId, request.purchaseToken)
    if not is_valid:
        raise HTTPException(status_code=402, detail="Purchase could not be verified with Google Play")

    now = datetime.now(timezone.utc).isoformat()

    # Persist the purchase record
    await db.google_play_purchases.insert_one({
        "id": str(uuid.uuid4()),
        "userId": request.userId,
        "tier": request.tier,
        "purchaseToken": request.purchaseToken,
        "orderId": request.orderId,
        "productId": request.productId,
        "packageName": request.packageName,
        "status": "active",
        "createdAt": now,
        "updatedAt": now,
    })

    # Activate the subscription on the user record
    await db.users.update_one(
        {"id": request.userId},
        {"$set": {
            "subscription": request.tier,
            "subscriptionStatus": "active",
            "updatedAt": now,
        }}
    )

    logger.info(f"Google Play subscription activated: userId={request.userId} tier={request.tier} orderId={request.orderId}")
    return {"status": "ok", "subscription": request.tier}


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
async def analyze_project(project_id: str, reanalyze: bool = False):
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    user_id = project.get("userId")
    
    # Check re-analyze limit
    if reanalyze and user_id and not await check_reanalyze_access(user_id, project_id):
        raise HTTPException(status_code=403, detail="Re-analysis limit reached. Upgrade to Pro for unlimited re-analysis.")
    
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
async def generate_content(project_id: str, request: GenerateRequest):
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project["status"] == "pending":
        raise HTTPException(status_code=400, detail="Project must be analyzed first")
    
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

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
