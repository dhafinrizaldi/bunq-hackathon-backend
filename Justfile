bunq-api:
    cd bunq-api && uv run uvicorn src.bunq_api.app:app --reload

mcp-client:
    cd mcp-client && uv run app.py ../mcp-server/server.py

mcp-client-terminal:
    cd mcp-client && uv run client.py ../mcp-server/server.py

all:
    #!/usr/bin/env bash
    cd bunq-api && uv run uvicorn src.bunq_api.app:app --reload &
    cd mcp-client && uv run app.py ../mcp-server/server.py &
    wait

lint:
    cd bunq-api && uv run ruff check .
    cd mcp-client && uv run ruff check .
    cd mcp-server && uv run ruff check .

format:
    cd bunq-api && uv run ruff format .
    cd mcp-client && uv run ruff format .
    cd mcp-server && uv run ruff format .

sync:
    cd bunq-api && uv sync
    cd mcp-client && uv sync
    cd mcp-server && uv sync
