.PHONY: help install test build clean deploy

help:
	@echo "Available targets:"
	@echo "  install    - Install Python dependencies"
	@echo "  test       - Run tests"
	@echo "  build      - Build Lambda deployment package"
	@echo "  clean      - Clean build artifacts"
	@echo "  lint       - Run linters"

install:
	pip install -r requirements.txt
	pip install pytest pytest-cov

test:
	pytest tests/ -v --cov=src --cov-report=term --cov-report=html

build:
	@echo "Building Lambda deployment package..."
	@rm -rf package lambda-deployment.zip
	@mkdir -p package
	@cp -r src/* package/
	@pip install -r requirements.txt -t package/
	@cd package && zip -r ../lambda-deployment.zip .
	@rm -rf package
	@echo "Package created: lambda-deployment.zip"

clean:
	rm -rf package lambda-deployment.zip
	rm -rf .pytest_cache .coverage htmlcov
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete

lint:
	@echo "Running code formatters..."
	black --check --diff src/ tests/ || true
	isort --check-only --diff src/ tests/ || true
	@echo "Running linters..."
	flake8 src/ tests/ || true
	pylint src/ tests/ --exit-zero --max-line-length=127 --disable=C0114,C0115,C0116 || true
	mypy src/ --ignore-missing-imports --no-strict-optional || true

