.PHONY: install backend frontend test lint demo experiment up down
install:
	python -m pip install -e "backend[dev]"
	cd frontend && npm install
	cd frontend && npx playwright install chromium
backend:
	cd backend && python -m uvicorn app.main:app --reload
frontend:
	cd frontend && npm run dev
test:
	cd backend && python -m pytest
	cd frontend && npm test -- --run
	cd frontend && npm run test:e2e
lint:
	cd backend && python -m ruff check app tests experiments
	cd frontend && npm run lint
	python scripts/check_design.py
demo:
	python scripts/demo.py
experiment:
	cd backend && python -m experiments.run_experiment $(ARGS)
up:
	docker compose up --build
down:
	docker compose down
