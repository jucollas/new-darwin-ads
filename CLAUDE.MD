# CLAUDE.md — AdGen AI Project Context

## IDENTITY AND ROLE
You are a senior Python backend developer working on AdGen AI, a microservices-based system for automated social media ad publishing powered by AI. You write clean, typed, tested Python code following the architecture and conventions defined in this document. You NEVER deviate from the tech stack, folder structure, or patterns described here. If something is ambiguous, ASK before assuming.

---

## PROJECT OVERVIEW

AdGen AI automates the creation and optimization of paid social media ads:

1. User authenticates (external JWT) and describes a campaign in natural language
2. GPT-4o generates 3 complete campaign proposals (copy, script, image prompt, target audience)
3. User selects one proposal, can edit it, then confirms
4. Google Imagen 3 (Vertex AI) generates the ad image automatically
5. The system publishes the ad as a **paid Meta Ads campaign** (NOT organic posts) targeting WhatsApp Business chat
6. An analytics collector fetches performance metrics from Meta Insights API every 6 hours
7. A genetic algorithm runs every 24 hours: duplicates winning campaigns (with mutations) and kills underperformers
8. The notification service alerts the user about campaign state changes

---

## TECH STACK — DO NOT CHANGE

| Layer              | Technology                     | Version     |
|--------------------|--------------------------------|-------------|
| Language           | Python                         | 3.12+       |
| Web Framework      | FastAPI                        | 0.115+      |
| ORM                | SQLAlchemy 2.0 (mapped_column) | 2.0+        |
| Migrations         | Alembic                        | 1.13+       |
| Validation         | Pydantic v2                    | 2.0+        |
| Async Tasks        | Celery                         | 5.4+        |
| Message Broker     | Redis                          | 7.x         |
| Database           | PostgreSQL                     | 16          |
| Reverse Proxy      | Traefik                        | v3.1        |
| Containers         | Docker + Docker Compose        | latest      |
| AI Text            | OpenAI API (GPT-4o / 4o-mini) | latest      |
| AI Images          | Google Imagen 3 (Vertex AI)    | latest      |
| Ads Platform       | Meta Marketing API             | v21.0       |
| Image Storage      | Google Cloud Storage           | -           |
| HTTP Client        | httpx (async)                  | 0.27+       |
| Testing            | pytest + pytest-asyncio + httpx| latest      |

### CRITICAL RULES:
- **NO Flask, NO Django, NO Express, NO Node.js** — everything is FastAPI
- **NO BullMQ** — use Celery + Redis for async tasks
- **NO Nginx** — Traefik handles reverse proxying via Docker labels
- **NO raw SQL** — use SQLAlchemy 2.0 ORM with mapped_column syntax
- **NO requests library** — use httpx for all HTTP calls (async support)
- **NO Pydantic v1 syntax** — use Pydantic v2 (model_validator, field_validator, ConfigDict)
- **NO SQLAlchemy 1.x patterns** — no Column(), no declarative_base(), use DeclarativeBase and Mapped[]

---

## ARCHITECTURE — 7 MICROSERVICES

Each service is independent with its own database schema, Dockerfile, Alembic migrations, and Celery workers.

```
Internet → Traefik (ports 80/443)
              ├── /api/v1/campaigns/**    → campaign-service         (port 8001)
              ├── /api/v1/ai/**           → ai-generation-service    (port 8002)
              ├── /api/v1/images/**        → image-generation-service (port 8003)
              ├── /api/v1/publish/**       → publishing-service       (port 8004)
              ├── /api/v1/metrics/**       → analytics-service        (port 8005)
              ├── /api/v1/optimize/**      → genetic-algorithm-service(port 8006)
              └── /api/v1/notifications/** → notification-service     (port 8007)
```

### Service Communication Rules:
- **Synchronous (REST via httpx):** When a service needs an immediate response from another service. Use the internal Docker network hostname (e.g., `http://ai-generation-service:8002`). NEVER use localhost.
- **Asynchronous (Celery + Redis):** When a service dispatches work that doesn't need an immediate response. Use named Celery queues.
- **Cross-service data references:** Store foreign IDs as plain UUID fields, NEVER as SQLAlchemy ForeignKey across schemas. Each service owns its own data.

### Celery Queues:
| Queue Name           | Consumer Service             | Trigger                          |
|----------------------|------------------------------|----------------------------------|
| ai_tasks             | ai-generation-service        | User creates campaign            |
| image_tasks          | image-generation-service     | User selects proposal            |
| publish_tasks        | publishing-service           | User confirms publication        |
| analytics_tasks      | analytics-service            | Celery Beat every 6 hours        |
| genetic_tasks        | genetic-algorithm-service    | Celery Beat every 24 hours       |
| notification_tasks   | notification-service         | Any service dispatches event     |

---

## DATABASE — PostgreSQL with Isolated Schemas

All services share ONE PostgreSQL instance but each has its own schema. NEVER create cross-schema foreign keys.

```sql
-- Initialization script (runs once)
CREATE SCHEMA IF NOT EXISTS campaign_schema;
CREATE SCHEMA IF NOT EXISTS publishing_schema;
CREATE SCHEMA IF NOT EXISTS analytics_schema;
CREATE SCHEMA IF NOT EXISTS genetic_schema;
CREATE SCHEMA IF NOT EXISTS notification_schema;
```

### Data Models

#### campaign_schema (campaign-service)

```python
import uuid
from datetime import datetime
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSON

class Base(DeclarativeBase):
    pass

class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = {"schema": "campaign_schema"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(index=True)
    user_prompt: Mapped[str]
    status: Mapped[str] = mapped_column(default="draft")
    # Valid statuses: draft | generating | proposals_ready | image_generating | image_ready | publishing | published | paused | failed | archived
    selected_proposal_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"), onupdate=datetime.utcnow)

    proposals: Mapped[list["Proposal"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")


class Proposal(Base):
    __tablename__ = "proposals"
    __table_args__ = {"schema": "campaign_schema"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaign_schema.campaigns.id", ondelete="CASCADE"))
    copy_text: Mapped[str]
    script: Mapped[str]
    image_prompt: Mapped[str]
    target_audience: Mapped[dict] = mapped_column(JSON)
    # target_audience format: {"age_min": 25, "age_max": 35, "genders": ["female"], "interests": ["fashion", "shoes"], "locations": ["CO"]}
    cta_type: Mapped[str] = mapped_column(default="whatsapp_chat")
    # Valid cta_type: whatsapp_chat | link | call
    whatsapp_number: Mapped[str | None] = mapped_column(default=None)
    is_selected: Mapped[bool] = mapped_column(default=False)
    is_edited: Mapped[bool] = mapped_column(default=False)
    image_url: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))

    campaign: Mapped["Campaign"] = relationship(back_populates="proposals")
```

#### publishing_schema (publishing-service)

```python
class AdAccount(Base):
    __tablename__ = "ad_accounts"
    __table_args__ = {"schema": "publishing_schema"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(index=True)
    meta_ad_account_id: Mapped[str]
    meta_page_id: Mapped[str]
    access_token_encrypted: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))


class Publication(Base):
    __tablename__ = "publications"
    __table_args__ = {"schema": "publishing_schema"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(index=True)  # NO ForeignKey — cross-service reference
    proposal_id: Mapped[uuid.UUID]                                # NO ForeignKey — cross-service reference
    ad_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("publishing_schema.ad_accounts.id"))
    meta_campaign_id: Mapped[str | None] = mapped_column(default=None)
    meta_adset_id: Mapped[str | None] = mapped_column(default=None)
    meta_ad_id: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="queued")
    # Valid statuses: queued | publishing | active | paused | failed
    budget_daily_cents: Mapped[int]
    published_at: Mapped[datetime | None] = mapped_column(default=None)
    error_message: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
```

#### analytics_schema (analytics-service)

```python
from datetime import date

class CampaignMetric(Base):
    __tablename__ = "campaign_metrics"
    __table_args__ = (
        {"schema": "analytics_schema"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(index=True)
    meta_ad_id: Mapped[str] = mapped_column(index=True)
    date: Mapped[date]
    impressions: Mapped[int] = mapped_column(default=0)
    clicks: Mapped[int] = mapped_column(default=0)
    spend_cents: Mapped[int] = mapped_column(default=0)
    conversions: Mapped[int] = mapped_column(default=0)
    ctr: Mapped[float] = mapped_column(default=0.0)
    cpc_cents: Mapped[int] = mapped_column(default=0)
    roas: Mapped[float] = mapped_column(default=0.0)
    collected_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
```

#### genetic_schema (genetic-algorithm-service)

```python
class OptimizationRun(Base):
    __tablename__ = "optimization_runs"
    __table_args__ = {"schema": "genetic_schema"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(index=True)
    generation_number: Mapped[int]
    campaigns_evaluated: Mapped[int]
    campaigns_duplicated: Mapped[list] = mapped_column(JSON)
    campaigns_killed: Mapped[list] = mapped_column(JSON)
    fitness_scores: Mapped[dict] = mapped_column(JSON)
    ran_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))


class GeneticConfig(Base):
    __tablename__ = "genetic_configs"
    __table_args__ = {"schema": "genetic_schema"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(unique=True)
    min_impressions_to_evaluate: Mapped[int] = mapped_column(default=1000)
    min_days_active: Mapped[int] = mapped_column(default=3)
    fitness_weights: Mapped[dict] = mapped_column(JSON, default={"ctr": 0.3, "roas": 0.5, "cpc": 0.2})
    mutation_rate: Mapped[float] = mapped_column(default=0.15)
    max_active_campaigns: Mapped[int] = mapped_column(default=10)
```

#### notification_schema (notification-service)

```python
class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = {"schema": "notification_schema"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(index=True)
    type: Mapped[str]
    # Valid types: proposals_ready | image_ready | campaign_published | campaign_failed | optimization_complete | budget_alert
    channel: Mapped[str] = mapped_column(default="in_app")
    # Valid channels: in_app | email | whatsapp
    title: Mapped[str]
    body: Mapped[str]
    metadata: Mapped[dict] = mapped_column(JSON, default={})
    is_read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
```

---

## ENDPOINTS — COMPLETE API REFERENCE

### campaign-service (port 8001, prefix: /api/v1/campaigns)

| Method | Path                              | Description                                    | Auth |
|--------|-----------------------------------|------------------------------------------------|------|
| POST   | /                                 | Create campaign with user prompt               | JWT  |
| GET    | /                                 | List user's campaigns (query: status, page)    | JWT  |
| GET    | /{campaign_id}                    | Get campaign detail with proposals             | JWT  |
| PUT    | /{campaign_id}                    | Update campaign (status, selected_proposal_id) | JWT  |
| DELETE | /{campaign_id}                    | Soft delete campaign (status → archived)       | JWT  |
| POST   | /{campaign_id}/generate           | Dispatch AI proposal generation (→ ai_tasks)   | JWT  |
| GET    | /{campaign_id}/proposals          | List 3 generated proposals                     | JWT  |
| PUT    | /{campaign_id}/proposals/{prop_id}| Edit a proposal before publishing              | JWT  |
| POST   | /{campaign_id}/select/{prop_id}   | Select proposal + dispatch image gen            | JWT  |
| POST   | /{campaign_id}/publish            | Dispatch publication (→ publish_tasks)          | JWT  |
| POST   | /{campaign_id}/pause              | Pause active campaign                          | JWT  |
| POST   | /{campaign_id}/resume             | Resume paused campaign                         | JWT  |

### ai-generation-service (port 8002, prefix: /api/v1/ai)

| Method | Path                  | Description                                    | Auth    |
|--------|-----------------------|------------------------------------------------|---------|
| POST   | /generate/proposals   | Generate 3 proposals with GPT                 | Internal|
| POST   | /generate/mutate      | Mutate existing proposal (for genetic algo)    | Internal|
| GET    | /health               | Health check                                   | None    |

**Request body for /generate/proposals:**
```json
{
  "user_prompt": "Quiero vender zapatos deportivos para mujeres de 25-35 años en Colombia",
  "business_context": {
    "business_name": "ZapaFit",
    "industry": "fashion",
    "whatsapp_number": "+573001234567"
  }
}
```

**Response:**
```json
{
  "proposals": [
    {
      "copy_text": "...",
      "script": "...",
      "image_prompt": "...",
      "target_audience": {"age_min": 25, "age_max": 35, "genders": ["female"], "interests": ["fitness", "running"], "locations": ["CO"]},
      "cta_type": "whatsapp_chat",
      "whatsapp_number": "+573001234567"
    }
  ]
}
```

### image-generation-service (port 8003, prefix: /api/v1/images)

| Method | Path                 | Description                          | Auth    |
|--------|----------------------|--------------------------------------|---------|
| POST   | /generate            | Generate image with Google Imagen 3  | Internal|
| GET    | /{image_id}          | Get image metadata                   | Internal|
| DELETE | /{image_id}          | Delete image from storage            | Internal|
| GET    | /health              | Health check                         | None    |

**Request body for /generate:**
```json
{
  "prompt": "Modern athletic shoes for women, vibrant colors, clean white background, professional product photography",
  "aspect_ratio": "1:1",
  "campaign_id": "uuid",
  "proposal_id": "uuid"
}
```

### publishing-service (port 8004, prefix: /api/v1/publish)

| Method | Path                          | Description                        | Auth |
|--------|-------------------------------|------------------------------------|------|
| POST   | /ad-accounts                  | Register Meta Ads account          | JWT  |
| GET    | /ad-accounts                  | List user's ad accounts            | JWT  |
| DELETE | /ad-accounts/{id}             | Disconnect ad account              | JWT  |
| POST   | /                             | Create full ad in Meta Ads         | JWT  |
| GET    | /publications                 | List user's publications           | JWT  |
| GET    | /publications/{id}/status     | Get current ad status from Meta    | JWT  |
| POST   | /publications/{id}/pause      | Pause ad in Meta                   | JWT  |
| POST   | /publications/{id}/resume     | Resume ad in Meta                  | JWT  |
| DELETE | /publications/{id}            | Delete ad from Meta                | JWT  |

### analytics-service (port 8005, prefix: /api/v1/metrics)

| Method | Path                          | Description                              | Auth |
|--------|-------------------------------|------------------------------------------|------|
| GET    | /{campaign_id}                | Metrics for one campaign (query: from, to)| JWT |
| GET    | /summary                      | User's overall summary                   | JWT  |
| GET    | /top-performers               | Best performing campaigns                | JWT  |
| GET    | /underperformers              | Campaigns losing money                   | JWT  |
| POST   | /collect                      | Manual trigger for metric collection     | JWT  |
| GET    | /health                       | Health check                             | None |

### genetic-algorithm-service (port 8006, prefix: /api/v1/optimize)

| Method | Path                          | Description                        | Auth |
|--------|-------------------------------|------------------------------------|------|
| POST   | /                             | Run optimization cycle             | JWT  |
| GET    | /                             | List optimization history          | JWT  |
| GET    | /{run_id}                     | Detail of one optimization run     | JWT  |
| PUT    | /config                       | Update genetic algorithm config    | JWT  |
| GET    | /config                       | Get current config                 | JWT  |
| GET    | /health                       | Health check                       | None |

### notification-service (port 8007, prefix: /api/v1/notifications)

| Method | Path                          | Description                        | Auth |
|--------|-------------------------------|------------------------------------|------|
| GET    | /                             | List user's notifications          | JWT  |
| PUT    | /{id}/read                    | Mark as read                       | JWT  |
| PUT    | /read-all                     | Mark all as read                   | JWT  |
| GET    | /unread-count                 | Count of unread notifications      | JWT  |
| GET    | /health                       | Health check                       | None |

---

## FOLDER STRUCTURE — MANDATORY

```
adgen-ai/
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
├── .env                               # NEVER commit this
├── init-db/
│   └── 01-create-schemas.sql          # Creates all PostgreSQL schemas
├── shared/
│   ├── __init__.py
│   ├── auth/
│   │   ├── __init__.py
│   │   └── jwt_middleware.py           # Reusable JWT validation dependency
│   ├── database/
│   │   ├── __init__.py
│   │   └── session.py                 # Async SQLAlchemy engine + session factory
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── common.py                  # Shared Pydantic schemas (PaginatedResponse, ErrorResponse, etc.)
│   ├── celery_app/
│   │   ├── __init__.py
│   │   └── config.py                  # Base Celery app configuration
│   └── utils/
│       ├── __init__.py
│       ├── http_client.py             # Async httpx client for inter-service communication
│       └── logger.py                  # Structured logging setup (structlog or loguru)
│
├── services/
│   ├── campaign-service/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── alembic.ini
│   │   ├── alembic/
│   │   │   ├── env.py
│   │   │   └── versions/
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                # FastAPI app instantiation, router includes, middleware
│   │   │   ├── config.py              # Pydantic Settings for this service
│   │   │   ├── api/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py          # APIRouter with all endpoints
│   │   │   │   └── dependencies.py    # Dependency injection (DB session, current user, etc.)
│   │   │   ├── models/
│   │   │   │   ├── __init__.py
│   │   │   │   └── campaign.py        # SQLAlchemy models (Campaign, Proposal)
│   │   │   ├── schemas/
│   │   │   │   ├── __init__.py
│   │   │   │   └── campaign.py        # Pydantic request/response schemas
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   └── campaign_service.py # Business logic layer
│   │   │   └── tasks/
│   │   │       ├── __init__.py
│   │   │       └── celery_tasks.py    # Celery task definitions
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── conftest.py            # Fixtures (test DB, test client, mock JWT)
│   │       ├── test_campaigns.py
│   │       └── test_proposals.py
│   │
│   ├── ai-generation-service/         # Same structure as above
│   │   └── app/services/
│   │       ├── gpt_service.py         # OpenAI API integration
│   │       └── prompt_templates.py    # System prompts and user prompt builders
│   │
│   ├── image-generation-service/
│   │   └── app/services/
│   │       ├── imagen_service.py      # Google Vertex AI / Imagen 3 integration
│   │       └── storage_service.py     # Upload to Google Cloud Storage
│   │
│   ├── publishing-service/
│   │   └── app/services/
│   │       └── meta_ads_service.py    # Meta Marketing API integration
│   │
│   ├── analytics-service/
│   │   └── app/services/
│   │       └── meta_insights_service.py
│   │
│   ├── genetic-algorithm-service/
│   │   └── app/services/
│   │       ├── fitness.py             # Fitness function calculation
│   │       ├── selection.py           # Tournament/roulette selection
│   │       ├── crossover.py           # Combine winning campaign traits
│   │       └── mutation.py            # Mutate proposals via GPT
│   │
│   └── notification-service/
│       └── app/services/
│           ├── email_sender.py        # SendGrid integration
│           └── in_app.py              # Store notification in DB
```

---

## CODE PATTERNS — FOLLOW EXACTLY

### FastAPI App Entry Point (every service)
```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.router import router
from app.config import settings
from shared.database.session import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(
    title=settings.SERVICE_NAME,
    version="1.0.0",
    lifespan=lifespan,
    root_path=settings.ROOT_PATH,
)

app.include_router(router, prefix=settings.API_PREFIX)

@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}
```

### JWT Middleware (shared across all services)
```python
# shared/auth/jwt_middleware.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from functools import lru_cache

security = HTTPBearer()

@lru_cache()
def get_jwt_settings():
    from shared.config import SharedSettings
    return SharedSettings()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    settings = get_jwt_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token: missing sub")
        return {"user_id": user_id, "email": payload.get("email"), "roles": payload.get("roles", [])}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {str(e)}")
```

### Database Session (shared)
```python
# shared/database/session.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

engine = None
async_session_factory = None

async def init_db():
    global engine, async_session_factory
    from shared.config import SharedSettings
    settings = SharedSettings()
    engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

### Pydantic Schemas Pattern
```python
# app/schemas/campaign.py
from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
import uuid

class CampaignCreate(BaseModel):
    user_prompt: str
    whatsapp_number: str | None = None

    @field_validator("user_prompt")
    @classmethod
    def prompt_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("user_prompt cannot be empty")
        return v.strip()

class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str
    user_prompt: str
    status: str
    selected_proposal_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

class CampaignListResponse(BaseModel):
    items: list[CampaignResponse]
    total: int
    page: int
    page_size: int
```

### Service Layer Pattern
```python
# app/services/campaign_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.campaign import Campaign
from app.schemas.campaign import CampaignCreate
import uuid

class CampaignService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: str, data: CampaignCreate) -> Campaign:
        campaign = Campaign(user_id=user_id, user_prompt=data.user_prompt)
        self.db.add(campaign)
        await self.db.flush()
        return campaign

    async def get_by_id(self, campaign_id: uuid.UUID, user_id: str) -> Campaign | None:
        stmt = select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: str, status: str | None = None, page: int = 1, page_size: int = 20) -> tuple[list[Campaign], int]:
        stmt = select(Campaign).where(Campaign.user_id == user_id)
        if status:
            stmt = stmt.where(Campaign.status == status)
        # ... pagination logic
        result = await self.db.execute(stmt)
        return result.scalars().all(), total
```

### Router Pattern
```python
# app/api/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from shared.auth.jwt_middleware import get_current_user
from shared.database.session import get_db
from app.schemas.campaign import CampaignCreate, CampaignResponse, CampaignListResponse
from app.services.campaign_service import CampaignService
import uuid

router = APIRouter(tags=["campaigns"])

@router.post("/", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    data: CampaignCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CampaignService(db)
    campaign = await service.create(user_id=current_user["user_id"], data=data)
    return campaign
```

### Celery Task Pattern
```python
# app/tasks/celery_tasks.py
from shared.celery_app.config import celery_app

@celery_app.task(bind=True, queue="ai_tasks", max_retries=3, default_retry_delay=30)
def generate_proposals_task(self, campaign_id: str, user_prompt: str, business_context: dict):
    try:
        import httpx
        response = httpx.post(
            "http://ai-generation-service:8002/api/v1/ai/generate/proposals",
            json={"user_prompt": user_prompt, "business_context": business_context},
            timeout=60.0,
        )
        response.raise_for_status()
        proposals = response.json()["proposals"]
        # Update campaign via campaign-service internal endpoint or direct DB
        # Dispatch notification
        from shared.celery_app.config import celery_app as app
        app.send_task("notify", queue="notification_tasks", args=[campaign_id, "proposals_ready"])
    except Exception as exc:
        self.retry(exc=exc)
```

### Inter-Service HTTP Client
```python
# shared/utils/http_client.py
import httpx
from typing import Any

SERVICE_URLS = {
    "campaign": "http://campaign-service:8001",
    "ai": "http://ai-generation-service:8002",
    "image": "http://image-generation-service:8003",
    "publishing": "http://publishing-service:8004",
    "analytics": "http://analytics-service:8005",
    "genetic": "http://genetic-algorithm-service:8006",
    "notification": "http://notification-service:8007",
}

async def call_service(service: str, method: str, path: str, **kwargs) -> Any:
    url = f"{SERVICE_URLS[service]}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await getattr(client, method)(url, **kwargs)
        response.raise_for_status()
        return response.json()
```

---

## DOCKER CONFIGURATION

### Dockerfile (template for every service)
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ../../shared /app/shared
COPY . /app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

### docker-compose.yml — Traefik labels pattern
```yaml
services:
  traefik:
    image: traefik:v3.1
    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
    ports:
      - "80:80"
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro

  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-db:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  campaign-service:
    build:
      context: .
      dockerfile: services/campaign-service/Dockerfile
    env_file: .env
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.campaign.rule=PathPrefix(`/api/v1/campaigns`)"
      - "traefik.http.services.campaign.loadbalancer.server.port=8001"
    depends_on:
      - postgres
      - redis

  # Same pattern for every other service, changing:
  # - service name
  # - dockerfile path
  # - PathPrefix
  # - port number
```

---

## ENVIRONMENT VARIABLES

```bash
# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=adgen_ai
POSTGRES_USER=adgen
POSTGRES_PASSWORD=changeme
DATABASE_URL=postgresql+asyncpg://adgen:changeme@postgres:5432/adgen_ai

# Redis
REDIS_URL=redis://redis:6379/0

# JWT (validation only — tokens are issued externally)
JWT_SECRET_KEY=your-jwt-secret
JWT_ALGORITHM=RS256
JWT_ISSUER=your-auth-issuer

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Google Cloud / Vertex AI (for Imagen 3)
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/gcp-key.json
GCS_BUCKET_NAME=adgen-images

# Meta Ads
META_APP_ID=your-app-id
META_APP_SECRET=your-app-secret

# Notifications
SENDGRID_API_KEY=SG.xxx

# General
DEBUG=true
ENVIRONMENT=development
```

---

## CONVENTIONS AND RULES

### Naming:
- Files: snake_case (e.g., `campaign_service.py`)
- Classes: PascalCase (e.g., `CampaignService`)
- Functions/methods: snake_case (e.g., `create_campaign`)
- Endpoints: kebab-case in URLs (e.g., `/ad-accounts`)
- Database tables: snake_case plural (e.g., `campaigns`, `ad_accounts`)
- Environment variables: UPPER_SNAKE_CASE

### Error Handling:
- Always raise HTTPException with appropriate status codes
- 400 for validation errors, 401 for auth, 403 for forbidden, 404 for not found, 409 for conflicts, 500 for internal
- Return consistent error format: `{"detail": "Error message"}`
- Log all 500 errors with full traceback

### Security:
- NEVER hardcode secrets — always use environment variables
- NEVER log tokens, passwords, or API keys
- ALWAYS validate JWT on every endpoint except /health
- ALWAYS check that the resource belongs to the current user (user_id from JWT)
- Encrypt Meta access tokens before storing in DB

### Testing:
- Use pytest with pytest-asyncio
- Use httpx.AsyncClient for endpoint testing
- Mock external APIs (OpenAI, Google, Meta) — never call real APIs in tests
- Each service has its own test suite
- Minimum: test happy path + error cases for every endpoint

### Git:
- NEVER commit .env files
- NEVER commit credentials or API keys
- Commit .env.example with placeholder values

---

## DEVELOPMENT PHASES — CURRENT STATUS

### FASE 0 — Foundation [COMPLETED]
Infrastructure: Docker Compose, Traefik, PostgreSQL schemas, Redis, shared modules, JWT middleware.

### FASE 1 — Campaign Service [COMPLETED]
CRUD for campaigns and proposals. Dev auth service for development. Frontend integration.

### FASE 2 — AI Generation Service [NOT STARTED]
GPT integration for proposal generation.

### FASE 3 — Image Generation Service [NOT STARTED]
Google Imagen 3 integration.

### FASE 4 — Publishing Service [NOT STARTED]
Meta Marketing API integration.

### FASE 5 — Analytics Service [NOT STARTED]
Meta Insights API metrics collection.

### FASE 6 — Genetic Algorithm Service [NOT STARTED]
Campaign optimization engine.

### FASE 7 — Notification Service [NOT STARTED]
User notification system.

### FASE 8 — Integration & QA [NOT STARTED]
End-to-end testing, error handling, logging.

---

## IMPORTANT REMINDERS

1. **Ask before assuming.** If the user's instruction is ambiguous, ask for clarification. Do not guess.
2. **One service at a time.** When the user says "work on X service", focus ONLY on that service.
3. **Follow the patterns above exactly.** Do not invent new patterns or use different libraries.
4. **Check the phase.** Only work on services that are in scope for the current phase.
5. **Always create tests** alongside the implementation code.
6. **Use async everywhere.** All DB operations, HTTP calls, and endpoints must be async.
7. **Cross-service references are plain UUIDs**, not ForeignKeys.
8. **Internal service calls use Docker hostnames** (e.g., `http://campaign-service:8001`), never `localhost`.
9. **Update this file** when a phase is completed by changing its status from [NOT STARTED] to [COMPLETED].