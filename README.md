# AVENOR — Backend Engine & Real-Time ASGI Platform

> *"Learning, without limits."*  
> High-performance multi-tenant white-label Learning Management and Institutional Education SaaS Platform.

---

## 1. Architecture Overview

The AVENOR backend is an enterprise-grade, asynchronous-first platform architected on **Django 5.1**, **Django REST Framework 3.15**, and **Daphne 4.1 (ASGI)** with **Django Channels 4.2**. It handles multi-tenant database isolation, dynamic institutional theming, real-time WebSockets, background job orchestration with **Celery 5.4**, and high-speed in-memory state caching with **Redis 7**.

### Core Technology Stack
- **Web & ASGI Server:** Daphne 4.1.2 (HTTP/1.1 & persistent WebSockets)
- **Framework:** Django 5.1.4 + Django REST Framework 3.15.2
- **Relational Storage:** PostgreSQL 17 (multi-tenant schema isolation, UUID primary keys, JSONB audit logging)
- **Real-Time Layer:** Django Channels 4.2.2 + Channels-Redis 4.3.0 (`/ws/` protocol)
- **Task & Schedule Queue:** Celery 5.4.0 + Redis 7 message broker + Celery Beat scheduler
- **Authentication:** SimpleJWT (Stateless Bearer Tokens, dual-mode HTTP header & WebSocket query param extraction)
- **API Documentation & Schema:** OpenAPI 3.0 via `drf-spectacular`

---

## 2. Directory Structure & App Domain Layout

```
backend/
├── manage.py
├── Dockerfile
├── docker-entrypoint.sh
├── .dockerignore
├── config/
│   ├── asgi.py                    # Dual HTTP & WebSocket ProtocolTypeRouter
│   ├── wsgi.py                    # WSGI fallback entrypoint
│   ├── urls.py                    # Root URL router, OpenAPI specs, and cloud healthchecks
│   └── settings/
│       ├── base.py                # Core configuration, JWT lifetime, installed apps
│       ├── development.py         # Local developer environment & in-memory channel layers
│       └── production.py          # Enterprise security, SSL, HSTS, Redis cluster
├── common/                        # Shared utility layers, pagination, standard envelopes
│   ├── health.py                  # Livez, readyz, and healthz diagnostic probes
│   └── tests/                     # Cloud readiness and liveness test suite
└── apps/
    ├── tenants/                   # Multi-tenant organization provisioning, domain resolution & theming
    ├── users/                     # Custom User model, JWT authentication, RBAC, profiles
    ├── courses/                   # Degree programmes, courses, modules, lessons, video streaming & syllabus studio
    ├── admissions/                # Institutional admissions pipeline, application reviews & decision workflow
    ├── assessments/               # Quizzes, assignments, auto-grading, and tamper-proof certificate verification
    ├── finance/                   # Subscriptions (Starter, Professional, Enterprise), invoice ledgers, Stripe hooks
    ├── analytics/                 # Immutable security audit logs, platform metrics, and student performance tracking
    └── communications/            # Daphne ASGI WebSockets, threads, live typing indicators, and user notification streams
```

---

## 3. Real-Time WebSocket Protocols (`apps/communications`)

All WebSocket connections authenticate via SimpleJWT tokens passed either through the `Authorization` header or query string `?token=<jwt_access_token>`.

| Route | Consumer Class | Description & Key Event Handlers |
| :--- | :--- | :--- |
| `/ws/communications/threads/<thread_id>/` | `DiscussionConsumer` | Live thread replies, real-time typing indicators (`typing_start`, `typing_stop`), atomic upvotes (`toggle_upvote`), and faculty endorsements. |
| `/ws/communications/notifications/` | `NotificationConsumer` | Private user-authenticated alert stream with `mark_read` acknowledgment. |
| `/ws/communications/announcements/<tenant_slug>/` | `AnnouncementConsumer` | Broadcast institutional bulletins to all active learners in a tenant organization. |

---

## 4. Cloud Diagnostic & Health Probes

Available directly on the root API gateway:
- **`GET /livez/`**: Liveness probe returning `{ "status": "alive" }`.
- **`GET /readyz/`**: Readiness probe executing dynamic query checks on PostgreSQL and roundtrips on Redis. Returns HTTP 503 if dependencies are degraded.
- **`GET /healthz/`**: Consolidated uptime and service latency diagnostics.

---

## 5. Local Setup & Quickstart

### Prerequisites
- Python 3.12 or 3.13
- PostgreSQL 17
- Redis 7

### Installation
```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start Daphne ASGI server
python manage.py runserver 127.0.0.1:8000
```

### Background Workers
```bash
# Start Celery worker
celery -A config worker -l info

# Start Celery beat scheduler
celery -A config beat -l info
```

---

## 6. Testing

The backend includes a comprehensive automated test suite spanning unit tests, API integration tests, and async WebSocket consumer tests:

```bash
# Run full suite (83 tests)
python manage.py test apps common
```

---

## 7. Production Containerization

The backend includes a production-grade multi-stage Docker build:
```bash
# Build image
docker build -t avenor-backend:latest .

# Run container with Daphne ASGI
docker run -p 8000:8000 \
  -e DJANGO_SETTINGS_MODULE=config.settings.production \
  -e DATABASE_URL=postgres://avenor:password@db:5432/avenor \
  -e REDIS_URL=redis://redis:6379/0 \
  avenor-backend:latest
```
