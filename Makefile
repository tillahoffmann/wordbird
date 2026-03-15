.PHONY: backend-test backend-build backend-dev daemon-dev vscode-package frontend-dev frontend-build frontend-bundle dev

backend-test:
	cd backend && uv run pytest tests/ -v

backend-build:
	cd backend && uv build

backend-dev:
	cd backend && uv run uvicorn wordbird.server.server:app --reload --host 127.0.0.1 --port 7870

# Run just the daemon (expects server running separately)
daemon-dev:
	cd backend && uv run wordbird-daemon

vscode-package:
	cd vscode-extension && $(MAKE) package

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

# Build frontend and copy into backend for serving as static files
frontend-bundle:
	cd frontend && npm run build
	rm -rf backend/src/wordbird/static
	cp -r frontend/dist backend/src/wordbird/static

# Run both backend and frontend dev servers
dev:
	@echo "Starting backend on http://127.0.0.1:7870"
	@echo "Starting frontend on http://localhost:5173 (proxies /api to backend)"
	@$(MAKE) backend-dev & $(MAKE) frontend-dev & wait
