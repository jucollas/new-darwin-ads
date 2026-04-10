# CLAUDE.md — AdGen AI Project Context

## IDENTITY AND ROLE
You are a senior Python backend developer working on AdGen AI, a microservices-based system for automated social media ad publishing powered by AI. You write clean, typed, tested Python code following the architecture and conventions defined in this document. You NEVER deviate from the tech stack, folder structure, or patterns described here. If something is ambiguous, ASK before assuming.

---

## MVP SCOPE — SINGLE-USER MODE

> **This project is currently an MVP targeting a single user (the developer/owner).**
> All external service connections (Meta Ads, Google Vertex AI, Google Cloud Storage) are configured with the owner's personal credentials via environment variables. There is NO multi-user OAuth flow, NO per-user token storage for external services, and NO multi-tenant isolation for external APIs in the MVP phase.

### What this means in practice:

- **JWT authentication is kept** — the API still validates JWTs and extracts `user_id`. This preserves the multi-user-ready architecture without adding complexity. In MVP, there is only one user issuing requests.
- **Meta access token** is a single long-lived token stored in `META_ACCESS_TOKEN` env var — NOT in the `ad_accounts` database table. No OAuth callback flow is needed.
- **Meta Ad Account ID** is a single value in `META_AD_ACCOUNT_ID` env var. No account selection UI needed.
- **Meta Page ID** is a single value in `META_PAGE_ID` env var.
- **WhatsApp number** is a single value in `META_WHATSAPP_NUMBER` env var.
- **Google Cloud credentials** use `GOOGLE_APPLICATION_CREDENTIALS` (service account JSON) — already configured in previous phases.
- **All services that need Meta credentials** read them from env vars directly instead of querying the `ad_accounts` table.
- **The `ad_accounts` table and OAuth endpoints still exist** from Phase 4 but are NOT used in the MVP flow. They remain in the codebase for future multi-user expansion.

### MVP-to-Multi-User migration path (future):
When ready to support multiple users, the changes are isolated:
1. Re-enable OAuth flow in publishing-service (already built in Phase 4)
2. Switch services from reading `META_ACCESS_TOKEN` env var to querying `ad_accounts` table by `user_id`
3. Add per-user `FacebookAdsApi` instance creation (pattern already exists in `meta_ads_service.py`)
4. Add account selection UI in frontend

**Convention:** Code that reads MVP env vars should be wrapped in a helper function (e.g., `get_meta_credentials()`) so the migration to multi-user is a single function change per service, not a scattered refactor.

```python
# shared/utils/meta_credentials.py
# MVP: reads from env vars. Future: query ad_accounts table by user_id.
from app.config import settings

def get_meta_credentials(user_id: str | None = None) -> dict:
    """
    MVP: Returns owner's Meta credentials from environment variables.
    Future multi-user: Will query ad_accounts table by user_id.
    
    The user_id parameter is accepted but ignored in MVP mode,
    ensuring all call sites are already multi-user-ready.
    """
    return {
        "access_token": settings.META_ACCESS_TOKEN,
        "ad_account_id": settings.META_AD_ACCOUNT_ID,
        "page_id": settings.META_PAGE_ID,
        "whatsapp_number": settings.META_WHATSAPP_NUMBER,
    }
```

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
| Ads Platform       | Meta Marketing API             | v25.0       |
| Ads SDK            | facebook-business (Python SDK) | 25.0.0      |
| Image Storage      | Google Cloud Storage           | -           |
| HTTP Client        | httpx (async)                  | 0.27+       |
| Token Encryption   | cryptography (Fernet)          | latest      |
| Testing            | pytest + pytest-asyncio + httpx| latest      |

### CRITICAL RULES:
- **NO Flask, NO Django, NO Express, NO Node.js** — everything is FastAPI
- **NO BullMQ** — use Celery + Redis for async tasks
- **NO Nginx** — Traefik handles reverse proxying via Docker labels
- **NO raw SQL** — use SQLAlchemy 2.0 ORM with mapped_column syntax
- **NO requests library** — use httpx for all HTTP calls (async support)
- **NO Pydantic v1 syntax** — use Pydantic v2 (model_validator, field_validator, ConfigDict)
- **NO SQLAlchemy 1.x patterns** — no Column(), no declarative_base(), use DeclarativeBase and Mapped[]
- **NO raw Meta Graph API calls via httpx** — use the official `facebook-business` Python SDK for all Meta Marketing API operations. httpx is only for inter-service communication.

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

> **MVP simplification:** The `token_refresh_tasks` queue is **not needed** in MVP. The single Meta token is managed manually via env var. This queue will be re-added when multi-user support is implemented.

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

> **MVP note:** The `ad_accounts` table exists but is NOT used in the MVP flow. Meta credentials come from env vars via `get_meta_credentials()`. The table remains for future multi-user support.

```python
class AdAccount(Base):
    """MVP: NOT USED — credentials come from env vars. Kept for multi-user migration."""
    __tablename__ = "ad_accounts"
    __table_args__ = {"schema": "publishing_schema"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(index=True)
    meta_ad_account_id: Mapped[str]
    meta_page_id: Mapped[str]
    meta_business_id: Mapped[str | None] = mapped_column(default=None)
    whatsapp_phone_number: Mapped[str | None] = mapped_column(default=None)
    access_token_encrypted: Mapped[str]
    token_expires_at: Mapped[datetime | None] = mapped_column(default=None)
    token_scopes: Mapped[list] = mapped_column(JSON, default=["ads_management", "ads_read"])
    token_last_verified_at: Mapped[datetime | None] = mapped_column(default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))


class Publication(Base):
    __tablename__ = "publications"
    __table_args__ = {"schema": "publishing_schema"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(index=True)
    proposal_id: Mapped[uuid.UUID]
    # MVP: ad_account_id is nullable since we don't use the ad_accounts table
    ad_account_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    meta_campaign_id: Mapped[str | None] = mapped_column(default=None)
    meta_adset_id: Mapped[str | None] = mapped_column(default=None)
    meta_adcreative_id: Mapped[str | None] = mapped_column(default=None)
    meta_ad_id: Mapped[str | None] = mapped_column(default=None)
    meta_image_hash: Mapped[str | None] = mapped_column(default=None)
    special_ad_categories: Mapped[list] = mapped_column(JSON, default=[])
    destination_type: Mapped[str] = mapped_column(default="WHATSAPP")
    campaign_objective: Mapped[str] = mapped_column(default="OUTCOME_ENGAGEMENT")
    status: Mapped[str] = mapped_column(default="queued")
    # Valid statuses: queued | publishing | active | paused | failed
    budget_daily_cents: Mapped[int]
    published_at: Mapped[datetime | None] = mapped_column(default=None)
    error_message: Mapped[str | None] = mapped_column(default=None)
    error_code: Mapped[int | None] = mapped_column(default=None)
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

    # --- Evaluation gates ---
    min_impressions_to_evaluate: Mapped[int] = mapped_column(default=1000)
    min_days_active: Mapped[int] = mapped_column(default=3)
    min_spend_cpa_multiplier: Mapped[float] = mapped_column(default=2.0)
    # Campaign must spend at least (target_cpa × multiplier) before full evaluation
    target_cpa_cents: Mapped[int] = mapped_column(default=140)
    # Target cost per conversation in smallest currency unit (140 centavos COP ≈ $0.35 USD)

    # --- Fitness function weights (full evaluation: campaigns with 7+ days and conversion data) ---
    fitness_weights: Mapped[dict] = mapped_column(JSON, default={
        "roas": 0.30,
        "conversion_rate": 0.25,
        "cost_per_conversion": 0.20,  # inverse-normalized: lower is better
        "ctr": 0.15,
        "cpc": 0.10,                  # inverse-normalized: lower is better
    })

    # --- Early-stage weights (campaigns with 3-7 days, no reliable conversion data yet) ---
    early_stage_weights: Mapped[dict] = mapped_column(JSON, default={
        "ctr": 0.35,
        "cpc": 0.25,                  # inverse-normalized
        "cost_per_conversion": 0.20,  # inverse-normalized
        "impressions": 0.20,          # proxy for delivery health
    })

    # --- Kill thresholds ---
    emergency_kill_cpa_multiplier: Mapped[float] = mapped_column(default=3.0)
    # Kill immediately if CPA > target_cpa × this multiplier
    kill_percentile_bottom: Mapped[float] = mapped_column(default=0.20)
    # Kill bottom N% of campaigns by CTR after early stage
    ctr_absolute_floor: Mapped[float] = mapped_column(default=0.005)
    # Kill if CTR < 0.5% after 1000+ impressions (creative-audience mismatch)
    max_frequency_prospecting: Mapped[float] = mapped_column(default=3.0)
    # Kill/refresh if frequency exceeds this with declining CTR (ad fatigue)
    graduated_cpa_threshold: Mapped[float] = mapped_column(default=1.2)
    # Start budget reduction when CPA > target × this (1.2 = 20% above target)

    # --- Duplicate/scale thresholds ---
    duplicate_min_days_stable: Mapped[int] = mapped_column(default=7)
    duplicate_min_weekly_conversions: Mapped[int] = mapped_column(default=30)
    duplicate_max_cpa_ratio: Mapped[float] = mapped_column(default=1.2)
    # CPA must be within 120% of target to qualify for duplication
    duplicate_min_roas: Mapped[float] = mapped_column(default=3.0)
    # Minimum ROAS to qualify for duplication (Colombia WhatsApp benchmark)
    max_budget_increase_pct: Mapped[float] = mapped_column(default=0.20)
    # Vertical scaling: max 20% budget increase per interval
    budget_increase_interval_days: Mapped[int] = mapped_column(default=3)
    duplicates_per_winner: Mapped[int] = mapped_column(default=3)

    # --- GA parameters ---
    mutation_rate: Mapped[float] = mapped_column(default=0.15)
    crossover_rate: Mapped[float] = mapped_column(default=0.80)
    elitism_count: Mapped[int] = mapped_column(default=2)
    # Top N campaigns preserved unchanged across generations
    max_active_campaigns: Mapped[int] = mapped_column(default=10)

    # --- Mutation priorities (ordered by impact, used by GPT mutate endpoint) ---
    mutation_priorities: Mapped[list] = mapped_column(JSON, default=[
        "target_audience",    # highest impact: demographics, interests, locations
        "image_prompt",       # creative visual changes
        "copy_text",          # ad copy and CTA text
        "welcome_message",    # WhatsApp-specific: initial bot message
    ])
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
    # MVP: removed token_expiring (no multi-user token management)
    channel: Mapped[str] = mapped_column(default="in_app")
    # MVP: only in_app channel. Future: email | whatsapp
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

### image-generation-service (port 8003, prefix: /api/v1/images)

| Method | Path                 | Description                          | Auth    |
|--------|----------------------|--------------------------------------|---------|
| POST   | /generate            | Generate image with Google Imagen 3  | Internal|
| GET    | /{image_id}          | Get image metadata                   | Internal|
| DELETE | /{image_id}          | Delete image from storage            | Internal|
| GET    | /health              | Health check                         | None    |

### publishing-service (port 8004, prefix: /api/v1/publish)

> **MVP simplification:** OAuth endpoints (`/auth/meta/login`, `/auth/meta/callback`) and ad account CRUD (`/ad-accounts/*`) exist from Phase 4 but are **not used** in the MVP flow. The publish endpoint reads Meta credentials from env vars.

| Method | Path                          | Description                                          | Auth |
|--------|-------------------------------|------------------------------------------------------|------|
| ~~GET~~    | ~~/auth/meta/login~~              | ~~OAuth redirect~~ **(MVP: unused, kept for future)**    | -    |
| ~~GET~~    | ~~/auth/meta/callback~~           | ~~OAuth callback~~ **(MVP: unused, kept for future)**    | -    |
| ~~POST~~   | ~~/ad-accounts~~                  | ~~Register ad account~~ **(MVP: unused)**                | -    |
| ~~GET~~    | ~~/ad-accounts~~                  | ~~List ad accounts~~ **(MVP: unused)**                   | -    |
| ~~GET~~    | ~~/ad-accounts/{id}/verify~~      | ~~Verify token~~ **(MVP: unused)**                       | -    |
| ~~DELETE~~ | ~~/ad-accounts/{id}~~             | ~~Disconnect account~~ **(MVP: unused)**                 | -    |
| POST   | /                             | Create full ad in Meta Ads (uses env var credentials)| JWT  |
| GET    | /publications                 | List user's publications                             | JWT  |
| GET    | /publications/{id}/status     | Get current ad status from Meta                      | JWT  |
| POST   | /publications/{id}/pause      | Pause ad in Meta                                     | JWT  |
| POST   | /publications/{id}/resume     | Resume ad in Meta                                    | JWT  |
| DELETE | /publications/{id}            | Delete ad from Meta (archive, irreversible)          | JWT  |
| GET    | /health                       | Health check                                         | None |

### analytics-service (port 8005, prefix: /api/v1/metrics)

| Method | Path                          | Description                              | Auth |
|--------|-------------------------------|------------------------------------------|------|
| GET    | /{campaign_id}                | Metrics for one campaign (query: from, to)| JWT |
| GET    | /summary                      | User's overall summary                   | JWT  |
| GET    | /top-performers               | Best performing campaigns                | JWT  |
| GET    | /underperformers              | Campaigns losing money                   | JWT  |
| POST   | /collect                      | Manual trigger for metric collection     | JWT  |
| GET    | /health                       | Health check                             | None |

> **MVP note:** The analytics service uses `get_meta_credentials()` to get the single Meta access token for Insights API calls. No need to look up per-user tokens.

### genetic-algorithm-service (port 8006, prefix: /api/v1/optimize)

| Method | Path                          | Description                        | Auth |
|--------|-------------------------------|------------------------------------|------|
| POST   | /                             | Run optimization cycle             | JWT  |
| GET    | /                             | List optimization history          | JWT  |
| GET    | /{run_id}                     | Detail of one optimization run     | JWT  |
| PUT    | /config                       | Update genetic algorithm config    | JWT  |
| GET    | /config                       | Get current config                 | JWT  |
| GET    | /health                       | Health check                       | None |

> **MVP note:** The genetic algorithm evaluates ALL published campaigns (single user = all campaigns belong to one user). No per-user filtering complexity needed, but `user_id` is still stored in `OptimizationRun` and `GeneticConfig` for future multi-user compatibility.

### notification-service (port 8007, prefix: /api/v1/notifications)

| Method | Path                          | Description                        | Auth |
|--------|-------------------------------|------------------------------------|------|
| GET    | /                             | List user's notifications          | JWT  |
| PUT    | /{id}/read                    | Mark as read                       | JWT  |
| PUT    | /read-all                     | Mark all as read                   | JWT  |
| GET    | /unread-count                 | Count of unread notifications      | JWT  |
| GET    | /health                       | Health check                       | None |

> **MVP note:** Only `in_app` channel is implemented. No email (SendGrid) or WhatsApp notification delivery. The `channel` field defaults to `in_app` and no other channels are processed.

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
│       ├── meta_credentials.py        # MVP: Meta credentials from env vars (future: per-user from DB)
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
│   │   └── app/
│   │       ├── api/
│   │       │   ├── router.py          # Publish endpoints (MVP: OAuth routes exist but unused)
│   │       │   └── dependencies.py
│   │       ├── services/
│   │       │   ├── meta_ads_service.py    # facebook-business SDK wrapper — MVP: uses env var token
│   │       │   ├── meta_oauth_service.py  # OAuth flow (MVP: unused, kept for future)
│   │       │   ├── token_manager.py       # Token health checks (MVP: unused, kept for future)
│   │       │   └── token_encryption.py    # Fernet encrypt/decrypt (MVP: unused, kept for future)
│   │       └── tasks/
│   │           └── celery_tasks.py        # publish_tasks only (MVP: no token_refresh_tasks)
│   │
│   ├── analytics-service/
│   │   └── app/services/
│   │       └── meta_insights_service.py   # MVP: uses get_meta_credentials() for single token
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
│           └── in_app.py              # Store notification in DB (MVP: only channel)
│           # MVP: no email_sender.py — SendGrid integration deferred to multi-user phase
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

### Meta Credentials Helper (MVP pattern)
```python
# shared/utils/meta_credentials.py
from dataclasses import dataclass

@dataclass
class MetaCredentials:
    access_token: str
    ad_account_id: str
    page_id: str
    whatsapp_number: str

def get_meta_credentials(user_id: str | None = None) -> MetaCredentials:
    """
    MVP: Returns owner's Meta credentials from environment variables.
    Future multi-user: Will query ad_accounts table by user_id and decrypt token.
    
    The user_id parameter is accepted but ignored in MVP mode,
    ensuring all call sites are already multi-user-ready.
    """
    import os
    return MetaCredentials(
        access_token=os.environ["META_ACCESS_TOKEN"],
        ad_account_id=os.environ["META_AD_ACCOUNT_ID"],
        page_id=os.environ["META_PAGE_ID"],
        whatsapp_number=os.environ["META_WHATSAPP_NUMBER"],
    )
```

### Meta Ads SDK Pattern — MVP (publishing-service)
```python
# app/services/meta_ads_service.py
from facebook_business.api import FacebookAdsApi
from facebook_business.session import FacebookSession
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.adcreative import AdCreative
from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.adimage import AdImage
from app.config import settings
from shared.utils.meta_credentials import get_meta_credentials

class MetaAdsService:
    """
    MVP: Creates a single FacebookAdsApi instance using env var credentials.
    Future multi-user: Will accept access_token parameter for per-user instances.
    """

    def __init__(self, user_id: str | None = None):
        creds = get_meta_credentials(user_id)
        session = FacebookSession(
            app_id=settings.META_APP_ID,
            app_secret=settings.META_APP_SECRET,
            access_token=creds.access_token,
        )
        self.api = FacebookAdsApi(session)
        self.ad_account_id = creds.ad_account_id
        self.page_id = creds.page_id
        self.whatsapp_number = creds.whatsapp_number

    def create_whatsapp_campaign(
        self,
        name: str,
        copy_text: str,
        image_path: str,
        target_audience: dict,
        daily_budget_cents: int,
        welcome_message: str = "Welcome! How can we help you today?",
    ) -> dict:
        """
        Creates complete Meta Ads hierarchy for WhatsApp Click-to-Chat.
        MVP: Uses self.ad_account_id, self.page_id, self.whatsapp_number from env vars.
        """
        # 1. Upload image → image_hash
        # 2. Create Campaign (objective=OUTCOME_ENGAGEMENT, special_ad_categories=[])
        # 3. Create AdSet (destination_type=WHATSAPP, promoted_object with page_id + whatsapp_number)
        # 4. Create AdCreative (CTA=WHATSAPP_MESSAGE, page_welcome_message)
        # 5. Create Ad (link creative to adset)
        # Returns dict with all Meta IDs
        ...
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

# Meta Ads — MVP Single-User (direct credentials, no OAuth flow)
META_APP_ID=your-app-id
META_APP_SECRET=your-app-secret
META_API_VERSION=v25.0
META_ACCESS_TOKEN=your-long-lived-access-token
META_AD_ACCOUNT_ID=act_123456789
META_PAGE_ID=your-page-id
META_WHATSAPP_NUMBER=+573001234567
META_DEFAULT_CURRENCY=COP
META_DEFAULT_BID_STRATEGY=LOWEST_COST_WITHOUT_CAP
META_DEFAULT_BILLING_EVENT=IMPRESSIONS
META_DEFAULT_OPTIMIZATION_GOAL=CONVERSATIONS
META_DEFAULT_CAMPAIGN_OBJECTIVE=OUTCOME_ENGAGEMENT

# Meta Ads — Multi-User (UNUSED IN MVP, kept for future)
# META_REDIRECT_URI=https://your-domain.com/api/v1/publish/auth/meta/callback
# META_TOKEN_ENCRYPTION_KEY=your-fernet-key-here
# META_SANDBOX_AD_ACCOUNT_ID=act_sandbox_123456789
# WHATSAPP_BUSINESS_ACCOUNT_ID=your-waba-id

# Notifications — MVP: only in_app
# SENDGRID_API_KEY=SG.xxx  # UNUSED IN MVP

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
- MVP: Meta access token is in env vars (acceptable for single-user). Future: encrypt before DB storage.

### Testing:
- Use pytest with pytest-asyncio
- Use httpx.AsyncClient for endpoint testing
- Mock external APIs (OpenAI, Google, Meta) — never call real APIs in tests
- Mock the `facebook-business` SDK in tests — use `unittest.mock.patch` on SDK classes
- Mock `get_meta_credentials()` in tests — return fake credentials
- Each service has its own test suite
- Minimum: test happy path + error cases for every endpoint

### Git:
- NEVER commit .env files
- NEVER commit credentials or API keys
- Commit .env.example with placeholder values

### Meta Marketing API:
- **ALWAYS use the `facebook-business` Python SDK** — never raw httpx calls to Graph API
- **MVP: Use single `FacebookAdsApi` instance** from env var token via `get_meta_credentials()`. Future: per-user instances via `FacebookSession`.
- **ALWAYS set `special_ad_categories`** on campaign creation, even if empty (`[]`)
- **ALL budget values are in the smallest currency unit** (cents for USD, centavos for COP)
- **ALWAYS pin API version** (`api_version="v25.0"`)
- **Handle error code 190 (OAuthException)** — in MVP, log and alert (token must be manually refreshed in .env)
- **Handle error codes 17/613 (rate limit)** with exponential backoff
- **WhatsApp ads require**: `destination_type="WHATSAPP"`, `promoted_object` with `page_id` + `whatsapp_phone_number`, CTA type `WHATSAPP_MESSAGE`, link `https://api.whatsapp.com/send`
- **ODAX objectives only**: `OUTCOME_ENGAGEMENT` (default for WhatsApp), `OUTCOME_LEADS`, `OUTCOME_SALES`, `OUTCOME_TRAFFIC`
- **Interest targeting IDs** must be resolved via the Targeting Search API (`TargetingSearch.search`) — never hardcode interest IDs

---

## DEVELOPMENT PHASES — CURRENT STATUS

### FASE 0 — Foundation [COMPLETED]
Infrastructure: Docker Compose, Traefik, PostgreSQL schemas, Redis, shared modules, JWT middleware.

### FASE 1 — Campaign Service [COMPLETED]
CRUD for campaigns and proposals. Dev auth service for development. Frontend integration.

### FASE 2 — AI Generation Service [COMPLETED]
GPT integration for proposal generation. Real OpenAI GPT-4o-mini calls with retry logic, prompt templates for LATAM market, Celery async tasks, sync dev mode via USE_SYNC_AI.

### FASE 3 — Image Generation Service [COMPLETED]
Google Imagen 3 (Vertex AI) integration for ad image generation. Images uploaded to GCS public bucket. Full async flow: user selects proposal → Celery dispatches image_generate task → Imagen 3 generates image → uploaded to GCS → proposal.image_url updated → campaign status set to image_ready → frontend polls and displays image.

### FASE 4 — Publishing Service [COMPLETED]
Meta Marketing API v25.0 integration using the official `facebook-business` Python SDK (v25.0.0). Full Meta Ads hierarchy creation, OAuth flow (built but unused in MVP), token management infrastructure (built but unused in MVP). See Phase 4 details in architecture sections above.

### FASE 5 — Analytics Service [COMPLETED]
**MVP scope:** Meta Insights API metrics collection for the single owner account.

**MVP simplifications:**
- Uses `get_meta_credentials()` to obtain the single Meta access token — no per-user token lookup.
- Celery Beat task every 6 hours fetches insights for ALL active publications (single user = no user filtering needed at Meta API level).
- The `meta_insights_service.py` calls Meta Insights API via `facebook-business` SDK using the env var token.
- No token refresh logic — if token expires, it's manually updated in `.env` and containers restarted.
- Stores metrics in `analytics_schema.campaign_metrics` with `campaign_id` and `meta_ad_id` as cross-service references.

**Endpoints:** Standard CRUD as defined in API reference above. All endpoints still require JWT and filter by `user_id` (future-proof).

**Future multi-user changes:** Replace `get_meta_credentials()` call with per-user token lookup from `ad_accounts` table. Add user-scoped Celery Beat scheduling.

### FASE 6 — Genetic Algorithm Service [COMPLETED]
**MVP scope:** Campaign optimization engine for the single owner's WhatsApp Click-to-Chat campaigns in Colombia.

**Optimization strategy — WhatsApp CTWA specifics:**
- Target cost per conversation (CPA): ~$0.35 USD / ~140 COP centavos (configurable via `target_cpa_cents`)
- Colombia benchmarks: CTR 0.4%–1.0%, CPC $0.30–$0.50, ROAS 3×–7×
- Meta's 72-hour free messaging window makes WhatsApp conversations more valuable than pixel events

**Fitness function — two-phase evaluation:**
- **Early-stage (3–7 days, <50 conversions):** Weighted sum using leading indicators: CTR (0.35), CPC inverse (0.25), cost-per-conversation inverse (0.20), delivery health (0.20). Applied with confidence discount: `F × min(1, impressions/1000) × min(1, days_active/7) × min(1, spend/(2×target_CPA))`
- **Full evaluation (7+ days, learning phase exited):** Weighted sum: ROAS (0.30), conversion_rate (0.25), cost-per-conversation inverse (0.20), CTR (0.15), CPC inverse (0.10)
- **Normalization:** Min-max normalization across the active campaign portfolio (self-calibrating). Metrics where lower is better (CPC, cost_per_conversion) use inverse normalization: `1 - (x - min)/(max - min)`

**Four-tier kill framework:**
- **Tier 1 — Emergency kill (any time):** CPA > 3× target, or zero clicks after 2,000+ impressions
- **Tier 2 — Early creative kill (after 1,000+ impressions):** Bottom 20% by CTR percentile, or CTR < 0.5% absolute floor
- **Tier 3 — Performance kill (after 50+ clicks and 2× CPA spend):** Cost per conversation > 150% of target for 7+ consecutive days, or frequency > 3.0 with declining CTR (ad fatigue)
- **Tier 4 — Graduated response (after learning phase, 7+ days):** CPA 20% above target → reduce budget 20%. Still elevated after 2 days → reduce 30% more. Still elevated after 5 total days → pause campaign

**Duplicate/scale criteria (all must be met):**
- CPA within 120% of target sustained for 7+ days
- 30+ weekly conversions (exited Meta learning phase)
- ROAS above 3× (Colombia WhatsApp break-even threshold)
- Vertical scaling: budget increase max 20% every 3 days (avoids learning phase re-entry)
- Horizontal scaling: clone 3 copies per winner into non-overlapping audiences at reset budgets

**Mutation strategy (priority order, sent to ai-generation-service `/generate/mutate`):**
1. Target audience (highest impact): demographics, interests, city tiers, age brackets
2. Image prompt / creative (second): visual style, product vs lifestyle imagery
3. Ad copy and CTA text: headlines, primary text, CTA button wording
4. Welcome message (WhatsApp-specific): initial automated message, quick-reply buttons

**GA parameters:** mutation_rate=0.15, crossover_rate=0.80, elitism=top 2 campaigns preserved unchanged

**Implementation flow (runs every 24 hours via Celery Beat):**
1. Fetch all published campaigns from campaign-service + their metrics from analytics-service (internal HTTP)
2. Classify each campaign: immature (skip), early-stage (early weights), mature (full weights)
3. Calculate fitness score for all evaluable campaigns
4. Apply kill tiers: emergency kills first, then early creative kills, then performance kills, then graduated responses
5. Pause killed campaigns via publishing-service `/publications/{id}/pause`
6. Identify duplication candidates from top performers meeting all scale criteria
7. For each winner: send mutation request to ai-generation-service `/generate/mutate` with mutation priorities
8. Create new campaigns via campaign-service + publish via publishing-service (at reset budgets)
9. Store run results in `OptimizationRun` with all fitness scores, kills, and duplications
10. Dispatch notification to `notification_tasks` queue with type `optimization_complete`

**MVP simplifications:**
- Evaluates ALL published campaigns — no multi-user partitioning needed
- Uses `get_meta_credentials()` if any direct Meta API calls are needed (e.g., pausing underperformers)
- `GeneticConfig` is seeded with a single row for the owner's `user_id` on first run (auto-create with defaults if not found)
- No Pareto analysis in MVP — weighted sum only. Pareto analysis deferred to post-MVP
- No adaptive mutation rate in MVP — fixed rate. Adaptive mutation deferred to post-MVP

**Endpoints:** Standard CRUD as defined in API reference above. All endpoints still require JWT and store `user_id`.

**Future multi-user changes:** Add per-user optimization scheduling. Partition campaign evaluation by `user_id`. Each user gets their own `GeneticConfig`. Add Pareto analysis endpoint. Add adaptive mutation based on population diversity.

### FASE 7 — Notification Service [NOT STARTED]
**MVP scope:** In-app notifications only (stored in database, queried via API).

**MVP simplifications:**
- **Only `in_app` channel** — no email (SendGrid), no WhatsApp delivery.
- No `email_sender.py` — deferred to multi-user phase.
- Notifications are created by other services dispatching Celery tasks to `notification_tasks` queue.
- The notification worker simply inserts a row into `notification_schema.notifications`.
- Frontend polls `GET /api/v1/notifications/unread-count` and `GET /api/v1/notifications/` to display notifications.
- Notification types supported: `proposals_ready`, `image_ready`, `campaign_published`, `campaign_failed`, `optimization_complete`, `budget_alert`.
- **Removed from MVP:** `token_expiring` notification type (no multi-user token management).

**Endpoints:** Standard CRUD as defined in API reference above.

**Future multi-user changes:** Add `email_sender.py` with SendGrid. Add WhatsApp notification channel. Add user notification preferences (which channels to receive). Re-add `token_expiring` type.

### FASE 8 — Integration & QA [NOT STARTED]
**MVP scope:** End-to-end testing of the complete single-user flow.

**MVP simplifications:**
- E2E test covers one user journey: create campaign → generate proposals → select proposal → generate image → publish to Meta → collect metrics → run optimization → receive notifications.
- No multi-user concurrency testing.
- No OAuth flow testing (unused in MVP).
- No token refresh/expiration testing (manual process in MVP).
- Focus areas: inter-service communication reliability, Celery task chain completion, Meta API error handling (190, 17/613, 100), data consistency across schemas.
- Load testing is NOT in MVP scope.

**Future multi-user changes:** Add concurrent user tests, OAuth flow tests, token lifecycle tests, load/stress testing.

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
9. **Meta SDK calls are synchronous** — the `facebook-business` SDK does not support async. Wrap SDK calls in `asyncio.to_thread()` or execute within Celery tasks (which are already synchronous).
10. **Update this file** when a phase is completed by changing its status from [NOT STARTED] to [COMPLETED].
11. **MVP single-user:** Always use `get_meta_credentials(user_id)` for Meta credentials — never read env vars directly in service code. This ensures a clean migration path to multi-user.
12. **Keep `user_id` everywhere.** Even though there's one user in MVP, always store and filter by `user_id` from JWT. This is the #1 thing that makes multi-user migration trivial.