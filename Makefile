.PHONY: help venv install lint format typecheck test test-all api docker-build clean

PYTHON ?= python3.12
VENV := .venv-govbr-complaint-classifier
BIN := $(VENV)/bin

help:  ## List the available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

venv:  ## Create the virtual environment
	$(PYTHON) -m venv $(VENV) --prompt govbr-complaint-classifier
	$(BIN)/pip install --upgrade pip

install: venv  ## Install the package with every extra, plus git hooks
	$(BIN)/pip install -e ".[data,labeling,analysis,dev]"
	$(BIN)/pre-commit install
	$(BIN)/nbstripout --install
	$(BIN)/python -m ipykernel install --user --name govbr-complaint-classifier --display-name "govbr-complaint-classifier"

lint:  ## Check style and common bugs
	$(BIN)/ruff check src tests scripts
	$(BIN)/ruff format --check src tests scripts

format:  ## Fix style automatically
	$(BIN)/ruff check --fix src tests scripts
	$(BIN)/ruff format src tests scripts

typecheck:  ## Static type check
	$(BIN)/mypy

test:  ## Fast suite (no network, no database, no trained model)
	$(BIN)/pytest -m "not integration"

test-all:  ## Everything, including integration tests
	$(BIN)/pytest

api:  ## Run the API locally with auto-reload
	$(BIN)/uvicorn govbr_classifier.api.main:app --reload --port 8000

docker-build:  ## Build the serving image
	docker build -t govbr-classifier:local .

clean:  ## Remove caches (keeps the venv and data)
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
