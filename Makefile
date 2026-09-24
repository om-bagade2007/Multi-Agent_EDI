.PHONY: install backend frontend test lint demo experiment up down pune-data doctor compare-pune
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
pune-data:
	python scripts/build_pune_network.py
	python scripts/build_pune_regions.py
doctor:
	python scripts/doctor.py
compare-pune:
	cd backend && python -m experiments.run_experiment --compare --mode pune --scenarios 1 --duration 1800 --rate-per-minute 0.67 --speed 10 --out ../results/pune_compare.csv
