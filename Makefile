# Makefile for FakeStore infra (production oriented)
# Usage examples:
#   make prod-build            # Build prod images
#   make prod-up               # Start stack in background
#   make prod-config           # Render merged compose config
#   make prod-migrate          # Run Django migrations in prod stack
#   make prod-seed             # Seed initial data (idempotent)
#   make prod-bootstrap        # Build, up, migrate, seed
#   make prod-logs             # Tail web logs
#   make prod-down             # Stop stack
#   make prod-restart          # Restart web service

SHELL := /bin/bash

ENV_FILE ?= .env.prod
COMPOSE_FILE ?= docker-compose.prod.yml
DJANGO_APP_DIR ?= backend
DJANGO_MANAGE := $(DJANGO_APP_DIR)/manage.py

COMPOSE_ENV_FLAG := $(if $(ENV_FILE),--env-file $(ENV_FILE),)
COMPOSE_PROD := docker compose $(COMPOSE_ENV_FLAG) -f $(COMPOSE_FILE)

.PHONY: help
help:
	@echo "Available targets:" && \
	egrep -h '^[a-zA-Z0-9_.-]+:.*?##' Makefile | awk 'BEGIN {FS=":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' | sort

.PHONY: prod-build
prod-build: ## Build production images
	$(COMPOSE_PROD) build

.PHONY: prod-up
prod-up: ## Start production stack (detached)
	$(COMPOSE_PROD) up -d

.PHONY: prod-config
prod-config: ## Render final docker compose configuration
	$(COMPOSE_PROD) config

.PHONY: prod-ps
prod-ps: ## Show running containers for production stack
	$(COMPOSE_PROD) ps

.PHONY: prod-migrate
prod-migrate: ## Run Django migrations inside prod web container
	$(COMPOSE_PROD) exec web sh -c '\
		sentinel="$${ENTRYPOINT_MIGRATIONS_SENTINEL:-}"; \
		if [ -n "$$sentinel" ] && [ ! -f "$$sentinel" ]; then \
			echo "Waiting for entrypoint migrations to finish (sentinel: $$sentinel)"; \
			max_wait="$${ENTRYPOINT_MIGRATIONS_WAIT_SECONDS:-180}"; \
			i=0; \
			while [ ! -f "$$sentinel" ]; do \
				if [ "$$max_wait" -gt 0 ] && [ "$$i" -ge "$$max_wait" ]; then \
					echo "Timed out after $$max_wait seconds waiting for $$sentinel"; \
					exit 1; \
				fi; \
				sleep 1; \
				i=$$((i+1)); \
			done; \
		fi; \
		python $(DJANGO_MANAGE) migrate'

.PHONY: prod-seed
prod-seed: ## Seed initial data (management command 'seed_fakestore')
	@if $(COMPOSE_PROD) exec web python $(DJANGO_MANAGE) help seed_fakestore >/dev/null 2>&1; then \
		echo "Seeding initial data..."; \
		$(COMPOSE_PROD) exec web python $(DJANGO_MANAGE) seed_fakestore; \
	else \
		echo "[WARN] seed_fakestore command not found. Skipping."; \
	fi

.PHONY: prod-bootstrap
prod-bootstrap: prod-build prod-up prod-migrate prod-seed schema-export ## Build, start, migrate, seed, export schema
	@echo "Production bootstrap complete."

.PHONY: prod-logs
prod-logs: ## Tail web logs
	$(COMPOSE_PROD) logs -f web

.PHONY: prod-down
prod-down: ## Stop production stack (preserve volumes)
	$(COMPOSE_PROD) down

.PHONY: prod-destroy
prod-destroy: ## Stop stack and remove volumes (DANGEROUS)
	$(COMPOSE_PROD) down -v

.PHONY: prod-restart
prod-restart: ## Restart web service
	$(COMPOSE_PROD) restart web

.PHONY: prod-shell
prod-shell: ## Open shell in web container
	$(COMPOSE_PROD) exec web /bin/sh

.PHONY: prod-collectstatic
prod-collectstatic: ## Run collectstatic (if STATIC_ROOT configured)
	$(COMPOSE_PROD) exec web python $(DJANGO_MANAGE) collectstatic --noinput

.PHONY: check-secret
check-secret: ## Print secret key length inside running web container
	$(COMPOSE_PROD) exec web python -c "import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','fakestore.settings');django.setup();from django.conf import settings;print('SECRET_KEY length:',len(settings.SECRET_KEY));print('Starts with dev-secret-key?',settings.SECRET_KEY.startswith('dev-secret-key'))"

.PHONY: prod-migrate-once
prod-migrate-once: ## Run migrations (one-off container) before starting web (alternative workflow)
	$(COMPOSE_PROD) run --rm web python $(DJANGO_MANAGE) migrate

# Convenience alias
.PHONY: logs
logs: prod-logs ## Alias for prod-logs

# ---------------------------------------------------------------------------
# OpenAPI schema export (static artifacts)
# ---------------------------------------------------------------------------
SCHEMA_DIR=$(DJANGO_APP_DIR)/static/schema
SCHEMA_JSON=$(SCHEMA_DIR)/openapi.json
SCHEMA_YAML=$(SCHEMA_DIR)/openapi.yaml

.PHONY: schema-export
schema-export: ## Export OpenAPI schema to JSON & YAML (requires running web container)
	@echo "Exporting OpenAPI schema (JSON & YAML) to $(SCHEMA_DIR)";
	$(COMPOSE_PROD) exec web mkdir -p $(SCHEMA_DIR)
	$(COMPOSE_PROD) exec web python $(DJANGO_MANAGE) spectacular --file /tmp/schema.json --format openapi-json
	$(COMPOSE_PROD) exec web python -c "import json,sys; p='/tmp/schema.json'; raw=open(p).read().strip() or sys.exit('Empty schema'); obj=json.loads(raw); open(p,'w').write(json.dumps(obj, indent=2))"
	$(COMPOSE_PROD) exec web python -c "import json,yaml,os; obj=json.load(open('/tmp/schema.json')); open('/tmp/schema.yaml','w').write(yaml.safe_dump(obj, sort_keys=False))"
	$(COMPOSE_PROD) exec web sh -c "cp /tmp/schema.json $(SCHEMA_JSON) && cp /tmp/schema.yaml $(SCHEMA_YAML)"
	@echo "Schema written to $(SCHEMA_JSON) and $(SCHEMA_YAML)"

.PHONY: schema-export-local
schema-export-local: ## Run schema export using local python (no docker) (ensure venv active)
	python $(DJANGO_MANAGE) spectacular --file $(SCHEMA_JSON) --format openapi-json
	python -c "import json,yaml; obj=json.load(open('$(SCHEMA_JSON)')); open('$(SCHEMA_YAML)','w').write(yaml.safe_dump(obj, sort_keys=False)); print('Wrote YAML schema to $(SCHEMA_YAML)')"
	@echo "Schema written to $(SCHEMA_JSON) and $(SCHEMA_YAML)"

.PHONY: prod-build-with-schema
prod-build-with-schema: prod-build prod-up schema-export ## Build, start, export schema
	@echo "Build + schema export complete."

# ---------------------------------------------------------------------------
# Testing (pytest)
# ---------------------------------------------------------------------------
.PHONY: pytest
pytest: ## Run test suite with pytest
	pytest -q
