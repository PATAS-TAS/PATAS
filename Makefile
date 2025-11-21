.PHONY: install dev-install test lint format run docker-build docker-run clean

install:
	poetry install

dev-install:
	poetry install --with dev

test:
	poetry run pytest tests/ -v --cov=app --cov-report=term-missing

lint:
	poetry run ruff check app
	poetry run mypy app

format:
	poetry run ruff format app tests
	poetry run black app tests

run:
	poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker-build:
	docker build -t patas-spamapi:latest .

docker-run:
	docker-compose up

clean:
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .coverage htmlcov

import-db:
	@echo "Usage: make import-db FILE=path/to/file.csv NAMESPACE=telegram_mod FORMAT=csv"
	poetry run python scripts/import_telegram_db.py $(FILE) $(NAMESPACE) $(FORMAT)

export-db:
	@echo "Usage: make export-db NAMESPACE=telegram_mod OUTPUT=output.json FORMAT=json"
	poetry run python scripts/export_training_data.py export $(NAMESPACE) $(OUTPUT) $(FORMAT)

list-namespaces:
	poetry run python scripts/export_training_data.py list

test-production:
	@echo "Testing production API..."
	@poetry run python scripts/test_production_api.py

test-production-shell:
	@echo "Testing production API (shell script)..."
	@./scripts/test_production_api.sh

export-openapi:
	@echo "Exporting OpenAPI schema to docs/openapi.json..."
	@poetry run python scripts/export_openapi.py

migrate-db:
	@echo "Running database migration..."
	@poetry run python scripts/migrate_add_evaluation_metrics.py

check-db-schema:
	@echo "Checking database schema..."
	@poetry run python scripts/check_db_schema.py

