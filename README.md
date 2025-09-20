# FakeStore Django Backend

A layered Django + DRF backend implementing the FakeStore dataset with a Controller → Service → Repository architecture, explicit DTO/mapping layer, and Dockerized Postgres.

## Architecture

Layers:
- Controllers (DRF APIViews) in each app `views.py` convert HTTP to service calls.
- Services (`services.py`) orchestrate business logic & return DTOs.
- Repositories (`repositories.py`) abstract ORM CRUD + custom queries.
- DTOs & Mappers (`dtos.py`) ensure separation between domain models and API layer.
- Models mirror provided SQL schema (keeping given integer primary keys).

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

### Products
- `GET /api/products/` (optional `?category=electronics`)
- `GET /api/products/by-categories/?categoryIds=1,2,3` (filter by one or more category IDs)
- `POST /api/products/`
- `GET /api/products/<id>/`
- `PUT /api/products/<id>/`
- `PATCH /api/products/<id>/`
- `DELETE /api/products/<id>/`

Body (create/update example):
```json
{
  "title": "Test Product",
  "description": "Desc",
  "price": "12.99",
  "image": "http://example.com/img.png",
  "categories": [1,2]
}
```

### Categories
- `GET /api/categories/`
- `POST /api/categories/`
- `GET /api/categories/<id>/`
- `PUT /api/categories/<id>/`
- `PATCH /api/categories/<id>/`
- `DELETE /api/categories/<id>/`

### Users
- `GET /api/users/`
- `POST /api/users/`
- `GET /api/users/<id>/`
- `PUT /api/users/<id>/`
- `PATCH /api/users/<id>/`
- `DELETE /api/users/<id>/`

### Carts
- `GET /api/carts/` (optional `?user_id=1`)
- `POST /api/carts/`
- `GET /api/carts/<id>/`
- `PUT /api/carts/<id>/`
- `PATCH /api/carts/<id>/` (advanced item operations)
- `DELETE /api/carts/<id>/`

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

Run tests (reliable options):
- Using dotted test modules (most robust; avoids ambiguous `tests` import):
```bash
python backend/manage.py test apps.auth.tests apps.catalog.tests apps.carts.tests apps.users.tests -v 2
```
- Using app labels (note the custom auth app label to avoid clashing with `django.contrib.auth`):
```bash
python backend/manage.py test fakestore_auth catalog carts users -v 2
```
- From inside the backend folder:
```bash
cd backend
python manage.py test fakestore_auth catalog carts users -v 2
```

Notes on bare discovery and ImportError:
- Running `python backend/manage.py test -v 2` may sometimes raise `ImportError: 'tests' module incorrectly imported...` when the environment has a top-level `tests` module installed. This is a unittest discovery quirk when a package named `tests` is imported without its full package path.
- Use one of the commands above (dotted modules or explicit app labels) to ensure Python imports `apps.<app>.tests` and not a global `tests` package.

Notes:
- DRF test client is used with `format='json'` for all JSON requests.
- Tests authenticate via JWT where needed (using the login endpoint and attaching the `Authorization: Bearer <token>` header).

## Notes
- Unified seeding command: `python manage.py seed_fakestore [--flush]` loads the full dataset (products, users, addresses, carts, cart items).
- Repositories intentionally thin; add caching, soft delete, or query specifications as complexity grows.
- Error codes are centralized in `apps/api/utils.py` (`error_response`). Add new codes there.
- Future enhancements: pagination, authentication, rate limiting, category/product validation details, global exception handler for SERVER_ERROR wrapping.

## License
