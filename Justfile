# ── one-time setup ──────────────────────────────────────────────────────────

# Install all deps, create bunq context, set up Django DB
setup:
    just sync
    just bunq-init
    just django-setup
    @echo ""
    @echo "✓ Setup complete. Next:"
    @echo "  1. Start services: just all"
    @echo "  2. Seed data:      just seed <email> <password>"

# Sync all uv projects + django pip deps
sync:
    cd bunq-api && uv sync
    cd mcp-client && uv sync
    cd mcp-server && uv sync
    cd tests && uv sync
    cd django-backend && python3.12 -m venv .venv --upgrade-deps -q && .venv/bin/pip install -r requirements.txt -q

# Initialise Bunq API context from BUNQ_API_KEY in .env
bunq-init:
    cd bunq-api && uv run python -m bunq_api.main

# Run Django migrations (idempotent)
django-setup:
    cd django-backend && .venv/bin/python manage.py migrate --run-syncdb

# Seed contacts, savings pocket, and salary setup
seed email password:
    cd django-backend && .venv/bin/python seed_all.py {{email}} {{password}}

# ── run services ─────────────────────────────────────────────────────────────

bunq-api:
    cd bunq-api && uv run uvicorn src.bunq_api.app:app --reload

bunq-seed:
    cd bunq-api && uv run python seed_deposits.py

django:
    cd django-backend && .venv/bin/python manage.py runserver 8080

mcp-client:
    cd mcp-client && uv run app.py ../mcp-server/server.py

mcp-client-terminal:
    cd mcp-client && uv run client.py ../mcp-server/server.py

# Start all services (bunq-api + django + mcp-client)
all:
    #!/usr/bin/env bash
    cd bunq-api && uv run uvicorn src.bunq_api.app:app --reload &
    cd django-backend && .venv/bin/python manage.py runserver 8080 &
    cd mcp-client && uv run app.py ../mcp-server/server.py &
    wait

# ── dev tools ────────────────────────────────────────────────────────────────

lint:
    cd bunq-api && uv run ruff check .
    cd mcp-client && uv run ruff check .
    cd mcp-server && uv run ruff check .

fix:
    cd bunq-api && uv run ruff check --fix . && uv run ruff format .
    cd mcp-client && uv run ruff check --fix . && uv run ruff format .
    cd mcp-server && uv run ruff check --fix . && uv run ruff format .

format:
    cd bunq-api && uv run ruff format .
    cd mcp-client && uv run ruff format .
    cd mcp-server && uv run ruff format .

test:
    cd tests && uv run pytest -v
