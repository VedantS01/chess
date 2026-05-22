.PHONY: dev test lint backend-build runner-build frontend-build clean

PYTHON ?= python3
VENV   ?= .venv

dev:
	docker compose up --build

test:
	$(VENV)/bin/ruff check .
	$(VENV)/bin/pytest -q
	cd frontend && pnpm test

lint:
	$(VENV)/bin/ruff check .
	cd frontend && pnpm lint

backend-build:
	docker build -f Dockerfile.backend -t chesslab-backend:dev .

runner-build:
	docker build -f Dockerfile.runner -t chesslab-runner:dev .

frontend-build:
	cd frontend && pnpm build

clean:
	rm -rf bot_artifacts/ chesslab.db __pycache__/ */__pycache__/
	cd frontend && rm -rf .next/ node_modules/.cache/
