# FakeStore Django Backend

A layered Django + DRF backend implementing the FakeStore dataset with a Controller → Service → Repository architecture, explicit DTO/mapping layer, and Dockerized Postgres.

## Architecture

Layers:
- Controllers (DRF APIViews) in each app `views.py` convert HTTP to service calls.
- Services (`services.py`) orchestrate business logic & return DTOs.
- Repositories (`repositories.py`) abstract ORM CRUD + custom queries.
- DTOs & Mappers (`dtos.py`) ensure separation between domain models and API layer.
- Models now use auto-increment primary keys (IDs are server-assigned). Clients must not send `id` fields on create.

Apps:
- `catalog`: products, categories, product-category relation (through model).
- `users`: users & addresses.
- `carts`: carts & cart products (with quantity).

## Project Layout
```
backend/
  fakestore/ (settings, urls)
  apps/
    catalog/
    users/
    carts/
    common/ (shared repository base)
 devops/
  Dockerfile
  docker-compose.yml
requirements.txt
.env.example
```

## Running with Docker

Copy env file:
```bash
cp .env.example .env
```

Start services:
```bash
cd devops
docker compose up --build
```

Run migrations & seed (single command):
```bash
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_fakestore
# Re-seed from scratch (flush existing data):
docker compose exec web python manage.py seed_fakestore --flush
```

## API Endpoints

Base path: `/api/`

Authentication & Permissions
- JWT is required for write operations on most resources. Public GETs are allowed unless noted.
- Auth endpoints:
  - Public: `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/refresh`
  - Auth required: `GET /api/auth/me`, `POST /api/auth/logout`, `POST /api/auth/logout-all`
- Products & Categories: Public GETs; POST/PUT/PATCH/DELETE require auth
- Users: Public GETs; POST/PUT/PATCH/DELETE require auth
- Carts: Public GETs; POST/PUT/PATCH/DELETE require auth
- Special cases:
  - `GET /api/products/by-categories/`: Public
  - Product ratings `GET`: Public summary; `POST`/`DELETE`: Auth required

Attach a JWT access token for protected routes using the `Authorization: Bearer <token>` header.

### Products
- Public: `GET /api/products/` (optional `?category=electronics`)
- Public: `GET /api/products/by-categories/?categoryIds=1,2,3` (filter by one or more category IDs)
- Auth required: `POST /api/products/`
- Public: `GET /api/products/<id>/`
- Auth required: `PUT /api/products/<id>/`
- Auth required: `PATCH /api/products/<id>/`
- Auth required: `DELETE /api/products/<id>/`
- Ratings:
  - Public: `GET /api/products/<id>/rating/`
  - Auth required: `POST /api/products/<id>/rating/` (set/update user rating)
  - Auth required: `DELETE /api/products/<id>/rating/` (remove user rating)

Body (create/update example) (omit `id`; it will be generated):
```json
{
  "title": "Test Product",
  "description": "Desc",
  "price": "12.99",
  "image": "http://example.com/img.png",
  "categories": [1,2]
}
```

Pagination (Products list):
- Query params: `page` (default 1), `limit` (default 10, max 100)
- Response shape:
```jsonc
{
  "count": 57,
  "next": "http://localhost:8000/api/products/?page=2&limit=10",
  "previous": null,
  "results": [
    { "id": 1, "title": "...", "price": 12.99, ... }
  ]
}
```

### Categories
- Public: `GET /api/categories/`
- Auth required: `POST /api/categories/`
- Public: `GET /api/categories/<id>/`
- Auth required: `PUT /api/categories/<id>/`
- Auth required: `PATCH /api/categories/<id>/`
- Auth required: `DELETE /api/categories/<id>/`

### Users
- Public: `GET /api/users/`
- Auth required: `POST /api/users/`
- Public: `GET /api/users/<id>/`
- Auth required: `PUT /api/users/<id>/`
- Auth required: `PATCH /api/users/<id>/`
- Auth required: `DELETE /api/users/<id>/`

### Carts
- Public: `GET /api/carts/` (optional `?userId=1`)
- Public: `GET /api/carts/users/<user_id>/` (list carts for a specific user)
- Auth required: `POST /api/carts/`
- Public: `GET /api/carts/<id>/`
- Auth required: `PUT /api/carts/<id>/`
- Auth required: `PATCH /api/carts/<id>/` (advanced item operations)
- Auth required: `DELETE /api/carts/<id>/`

Cart PATCH payload supports combined operations (executed in order add → update → remove):
```json
{
  "add": [{"productId": 10, "quantity": 2}],
  "update": [{"productId": 5, "quantity": 7}],
  "remove": [3],
  "date": "2025-09-12T10:00:00Z",
  "userId": 4
}
```
Rules:
- add: increments quantity (creates line if absent)
- update: sets quantity exactly (creates if absent)
- remove: deletes line items by productId
- date: ISO date/datetime string (date part stored)
- userId: reassign cart to another user (no auth rules yet)

Compatibility: older `user_id` query param is still accepted, but `userId` is preferred and documented.

### Error Envelope
All error responses use a consistent structure:
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Product not found",
    "details": {"id": "999"}
  }
}
```
Codes:
| Code | HTTP | Meaning |
|------|------|---------|
| NOT_FOUND | 404 | Requested resource missing |
| VALIDATION_ERROR | 400 | Input validation failed |
| SERVER_ERROR | 500 | Unexpected server exception |

Examples:
```jsonc
// Missing product
{"error":{"code":"NOT_FOUND","message":"Product not found","details":{"id":"99999"}}}

// Bad category IDs
{"error":{"code":"VALIDATION_ERROR","message":"Some category IDs do not exist","details":{"missing":[999]}}}

// Invalid quantity in cart patch
{"error":{"code":"VALIDATION_ERROR","message":"Invalid quantity","details":{"productId":1,"quantity":-5}}}
```

## Extending
- Add write operations by expanding repositories & services (e.g., `create_product`).
- Add pagination by integrating DRF pagination in settings and adjusting views.
- Replace manual DTO serializers with DRF ModelSerializers if you later loosen layering constraints.

## Development outside Docker
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Ensure local Postgres is running & env vars point to it
python backend/manage.py migrate
python backend/manage.py runserver
```

## Testing

Unit tests are provided for all main API areas and run against SQLite automatically (tests switch DB in settings when `test` is in `sys.argv`). Tests now live under per-app `tests/` packages for consistent discovery.

Covered areas and endpoints:
- Auth
  - `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/refresh`, `GET /api/auth/me`, `POST /api/auth/logout`, `POST /api/auth/logout-all`
- Catalog
  - Products: `GET/POST /api/products/`, `GET/PUT/PATCH/DELETE /api/products/:id/`
  - Filters: `GET /api/products/?category=...`, `GET /api/products/by-categories/?categoryIds=1,2` (valid/empty/invalid)
  - Categories: `GET/POST /api/categories/`, `GET/PUT/PATCH/DELETE /api/categories/:id/`
  - Ratings: `GET/POST/DELETE /api/products/:id/rating/`
  - Error envelope: 404 and validation error cases
- Carts
  - `GET/POST /api/carts/`, `GET/PUT/PATCH/DELETE /api/carts/:id/`
  - PATCH operations: `add`, `update`, `remove`, `date`, `userId`
- Users
  - `GET/POST /api/users/`, `GET/PUT/PATCH/DELETE /api/users/:id/`

Test file locations:
- `backend/apps/auth/tests/test_auth.py`
- `backend/apps/catalog/tests/test_catalog.py`
- `backend/apps/carts/tests/test_carts.py`
- `backend/apps/users/tests/test_users.py`

### Pytest (Preferred)

Pytest is configured via `pytest.ini` and a root `conftest.py`.

Run entire suite:
```bash
pytest
```

Or with coverage (if desired):
```bash
pytest --cov=backend/apps --cov-report=term-missing
```

Makefile target:
```bash
make pytest
```

Useful flags:
```bash
pytest -k "rating and not delete" -vv
pytest --maxfail=1 -q
```

### Django test runner (legacy / fallback)
You can still invoke the built-in runner:
```bash
python backend/manage.py test apps.auth.tests apps.catalog.tests apps.carts.tests apps.users.tests -v 2
```

Note: Prefer pytest for faster iteration, richer assertions, and better failure introspection.

Notes:
- DRF test client is used with `format='json'` for all JSON requests.
- Tests authenticate via JWT where needed (using the login endpoint and attaching the `Authorization: Bearer <token>` header).

## Notes
- Unified seeding command: `python manage.py seed_fakestore [--flush]` loads the full dataset (products, users, addresses, carts, cart items).
- Repositories intentionally thin; add caching, soft delete, or query specifications as complexity grows.
- Error codes are centralized in `apps/api/utils.py` (`error_response`). Add new codes there.
- Future enhancements: pagination, authentication, rate limiting, category/product validation details, global exception handler for SERVER_ERROR wrapping.

## Production Deployment

This repository includes a production compose file and a multi-stage production Dockerfile. Core principles:

| Aspect | Approach |
|--------|----------|
| Image Build | Multi-stage (`infra/Dockerfile.prod`) installing dependencies once |
| App Server | Gunicorn (WSGI) with configurable workers/threads |
| Secrets | Inject via environment variables / `env_file` (not baked into image) |
| Migrations | Run automatically before Gunicorn starts |
| Health Probes | `/health/live` (liveness) & `/health/ready` (readiness) |
| Caching | Redis (optional – readiness reports skipped if not set) |

### 1. Prepare Environment File

Create `.env.prod` (referenced by `infra/docker-compose.prod.yml` via `env_file`):

```bash
cat > .env.prod <<'EOF'
DJANGO_SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key as g; print(g())')
POSTGRES_PASSWORD=change-me-strong
ALLOWED_HOSTS=*
EOF
```

Keep this file out of version control (add to `.gitignore` if not already).

### 2. Build & Start

Using the Makefile (recommended):

```bash
make prod-build
make prod-up       # or: make prod-bootstrap (build+up+migrate+seed if seed command exists)
```

Direct compose commands:
```bash
docker compose -f infra/docker-compose.prod.yml build
docker compose -f infra/docker-compose.prod.yml up -d
```

### 3. Verify

```bash
curl -s http://localhost:8000/health/live | jq .
curl -s -i http://localhost:8000/health/ready | jq .
```
Expect `status: ok` for readiness when DB (and Redis if configured) are reachable.

### 4. Logs & Management

```bash
make prod-logs
make prod-migrate
make prod-restart
make prod-shell
make check-secret    # prints SECRET_KEY length and whether dev key used
```

### 5. Stopping / Destroying

```bash
make prod-down      # keeps volumes
make prod-destroy   # removes volumes (data loss!)
```

### 6. Gunicorn Tuning (Optional)

Default: 3 workers, 2 threads, 30s timeout. Adjust based on CPU cores (rule of thumb: workers = cores * 2 + 1 for CPU-bound; fewer if IO-bound + threads enabled). Example override (edit compose `command` or future entrypoint):

```
--workers 4 --threads 2 --timeout 30
```

### 7. Health Endpoints

| Endpoint | Purpose | Status Codes |
|----------|---------|--------------|
| `/health/live` | Process liveness | 200 always (if Python process responding) |
| `/health/ready` | Dependency readiness (DB, Redis) | 200 (ok) / 503 (degraded) |

Example readiness success:
```json
{
  "status": "ok",
  "checks": {
    "database": {"status": "ok", "latency_ms": 2.31},
    "redis": {"status": "ok"}
  }
}
```

Example degraded (DB down):
```json
{
  "status": "degraded",
  "checks": {
    "database": {"status": "fail", "error": "could not connect"},
    "redis": {"status": "ok"}
  }
}
```

Kubernetes probe suggestions:
```yaml
livenessProbe:
  httpGet: { path: /health/live, port: 8000 }
  periodSeconds: 10
readinessProbe:
  httpGet: { path: /health/ready, port: 8000 }
  initialDelaySeconds: 5
  periodSeconds: 15
  failureThreshold: 3
```

### 8. Makefile Quick Reference

| Target | Description |
|--------|-------------|
| `prod-build` | Build production images |
| `prod-up` | Start prod stack (detached) |
| `prod-bootstrap` | build + up + migrate + seed (if seed command) |
| `prod-migrate` | Run migrations |
| `prod-seed` | Run seed command if present |
| `prod-logs` | Tail web logs |
| `prod-shell` | Shell into web container |
| `prod-restart` | Restart web service |
| `prod-down` | Stop (preserve volumes) |
| `prod-destroy` | Stop & remove volumes |
| `check-secret` | Inspect runtime SECRET_KEY |

## Troubleshooting (Production)

### SECRET_KEY is missing or using insecure default
Cause: `DJANGO_SECRET_KEY` not exported or overridden with empty mapping in compose. Ensure `.env.prod` has a real value and no direct empty `DJANGO_SECRET_KEY:` line in `environment:`.

Check inside container:
```bash
docker compose -f infra/docker-compose.prod.yml exec web env | grep DJANGO_SECRET_KEY
```

### `sh: 3: --workers: not found`
Usually a side-effect after migration failure causing shell to mis-read the continued command. Fix the underlying error (often missing secret) and prefer a simplified `command` or entrypoint script.

### Readiness returns 503
Check DB connectivity and Redis URL. Run:
```bash
docker compose -f infra/docker-compose.prod.yml exec web python -c "import psycopg2,os;print('DB HOST',os.environ.get('POSTGRES_HOST'))"
```

### Need to rotate secret key
Generate a new key, update `.env.prod`, recreate containers. Active JWTs signed with the old key become invalid (expected).

### Migrations didn’t run
Check logs for migration errors; re-run:
```bash
make prod-migrate
```

### How to add an entrypoint script (optional)
Create `infra/entrypoint.sh`:
```sh
#!/bin/sh
set -e
python backend/manage.py migrate
exec gunicorn fakestore.wsgi:application --chdir backend --bind 0.0.0.0:8000 --workers 3 --threads 2 --timeout 30
```
Dockerfile.prod snippet:
```dockerfile
COPY infra/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
CMD ["/app/entrypoint.sh"]
```
Remove the `command:` override in compose.


## License
