.PHONY: help install install-dev lint format type-check security test clean fix check-all ci

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	uv sync

install-dev: ## Install development dependencies
	uv sync --all-extras --dev

lint: ## Run Ruff linter
	uv run ruff check trackstudio/

format: ## Format code with Ruff
	uv run ruff format trackstudio/

format-check: ## Check code formatting
	uv run ruff format trackstudio/ --check

type-check: ## Run MyPy type checking
	uv run mypy trackstudio/ --ignore-missing-imports --show-error-codes || true

security: ## Run Bandit security linter
	uv run bandit -r trackstudio/ -f json

test: ## Run pytest
	uv run pytest tests/ -v

clean: ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

fix: ## Fix auto-fixable linting issues
	uv run ruff check trackstudio/ --fix
	uv run ruff format trackstudio/

check-all: lint format-check security ## Run all checks (MyPy disabled)

ci: install-dev check-all test ## Run CI pipeline locally

pre-commit-install: ## Install pre-commit hooks
	uv run pre-commit install

pre-commit-run: ## Run pre-commit on all files
	uv run pre-commit run --all-files

run-server: ## Run TrackStudio server
	uv run trackstudio run

# Development workflow targets
dev-setup: install-dev pre-commit-install ## Complete development setup
	@echo "✅ Development environment ready!"
	@echo "💡 Run 'make help' to see available commands"

dev-check: fix check-all ## Quick development check (fix + check all)
