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
    api/ (shared API utilities, error handling)
    auth/ (authentication, JWT handling)
    catalog/ (products, categories)
    users/ (user profiles, addresses)
    carts/ (shopping cart management)
    common/ (shared repository base)
requirements.txt
.env.example
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

## Docker
- Duplicate `.env.example` to `.env` and adjust secrets, hostnames, and credentials as needed. The compose stack reads from `.env` by default.
- Build and start the production-oriented stack:
  ```bash
  docker compose --env-file .env -f docker-compose.prod.yml up -d --build
  ```
- Run migrations once the services are healthy:
  ```bash
  docker compose --env-file .env -f docker-compose.prod.yml exec web python backend/manage.py migrate
  ```
- Tail logs or enter the web container shell when troubleshooting:
  ```bash
  docker compose --env-file .env -f docker-compose.prod.yml logs -f web
  docker compose --env-file .env -f docker-compose.prod.yml exec web /bin/sh
  ```
- `Makefile` shortcuts wrap the same commands (for example `make prod-bootstrap` runs build → up → migrate → seed).

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
- Infrastructure & deployment automation now live in the dedicated Ops repository; consult that project for Docker, Compose, and environment provisioning guidance.
