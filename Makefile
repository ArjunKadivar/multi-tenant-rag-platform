.PHONY: install dev test lint up down logs worker

install:
	pip install -r requirements.txt -r requirements-dev.txt

dev:
	uvicorn app.main:app --reload --port 8000

test:
	pytest --cov=app --cov-report=term-missing

lint:
	ruff check app tests

up:
	docker compose -f docker/docker-compose.yml up --build -d

down:
	docker compose -f docker/docker-compose.yml down

logs:
	docker compose -f docker/docker-compose.yml logs -f api worker

worker:
	celery -A app.workers.celery_app worker --loglevel=info
