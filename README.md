# AdGen AI

Automated social media ad publishing system powered by AI.

## Quick Start

1. Copy environment file:
   ```bash
   cp .env.example .env
   ```

2. Start all services:
   ```bash
   docker-compose up --build
   ```

3. Verify:
   - Traefik Dashboard: http://localhost:8080
   - Frontend: http://localhost
   - Campaign Service Health: http://localhost/api/v1/campaigns/health
   - AI Service Health: http://localhost/api/v1/ai/health
   - Image Service Health: http://localhost/api/v1/images/health
   - Publishing Service Health: http://localhost/api/v1/publish/health
   - Analytics Service Health: http://localhost/api/v1/metrics/health
   - Genetic Service Health: http://localhost/api/v1/optimize/health
   - Notification Service Health: http://localhost/api/v1/notifications/health

## Architecture

See `CLAUDE.md` for complete architecture documentation.
# new-darwin-ads
