.PHONY: backend-test backend-build backend-dev daemon-dev vscode-package frontend-dev frontend-build frontend-bundle wordbird dev

backend-test:
	cd backend && uv run pytest tests/ -v

backend-build:
	cd backend && uv build

backend-dev:
	cd backend && uv run uvicorn wordbird.server.server:app --factory --reload --host 127.0.0.1 --port 7870

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
	rm -rf backend/src/wordbird/server/static
	cp -r frontend/dist backend/src/wordbird/server/static

# Run everything for production
wordbird: frontend-bundle
	cd backend && uv run wordbird

# Run all three dev servers: backend (with reload), frontend (with HMR), daemon
# Uses a wrapper script so Ctrl+C cleanly kills all children
dev:
	@bash -c '\
	cleanup() { kill -INT 0 2>/dev/null; sleep 1; kill -9 0 2>/dev/null; exit 0; }; \
	trap cleanup INT TERM; \
	echo "Starting backend on http://127.0.0.1:7870"; \
	echo "Starting frontend on http://localhost:5173"; \
	echo "Starting daemon..."; \
	(cd backend && uv run uvicorn wordbird.server.server:app --factory --reload --host 127.0.0.1 --port 7870) & \
	(cd frontend && npm run dev) & \
	sleep 3 && (cd backend && uv run wordbird-daemon) & \
	wait'
