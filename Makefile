.PHONY: up down web test lint

up:
	docker compose up --build -d

down:
	docker compose down

web:
	cd frontend && npm install && npm run dev

test:
	cd backend && pytest -q

lint:
	cd backend && ruff check . && ruff format --check .
	cd frontend && npm run lint
