# Development Guide

This guide covers setting up the development environment and using the code quality tools.

## 🚀 Quick Setup

```bash
# Clone the repository
git clone <repository-url>
cd trackstudio

# Set up development environment
make dev-setup

# Run a quick check
make dev-check
```

## 🛠️ Development Environment

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Installation

```bash
# Install with uv (recommended)
make install-dev

# Or manually with uv
uv sync --all-extras --dev
```

## 🧹 Code Quality Tools

### Ruff (Linting & Formatting)

We use [Ruff](https://docs.astral.sh/ruff/) for both linting and code formatting, replacing Black, isort, flake8, and more.

```bash
# Run linter
make lint

# Format code
make format

# Check formatting without making changes
make format-check

# Fix auto-fixable issues
make fix
```

### MyPy (Type Checking)

```bash
# Run type checking
make type-check
```

### Bandit (Security)

```bash
# Run security linter
make security
```

### All Checks

```bash
# Run all code quality checks
make check-all

# Run the full CI pipeline locally
make ci
```

## 🔧 Configuration

### Ruff Configuration

Ruff is configured in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 120
target-version = "py310"

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "N",      # pep8-naming
    "UP",     # pyupgrade
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "SIM",    # flake8-simplify
    "RET",    # flake8-return
    "ARG",    # flake8-unused-arguments
    "PTH",    # flake8-use-pathlib
    "ERA",    # eradicate (commented code)
    "PL",     # pylint
    "PERF",   # perflint
]
```

### Pre-commit Hooks

Pre-commit hooks automatically run code quality checks on commit:

```bash
# Install pre-commit hooks
make pre-commit-install

# Run pre-commit on all files manually
make pre-commit-run
```

## 🔄 GitHub Actions

Code quality checks run automatically on:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches

The CI pipeline includes:
- **Linting** with Ruff
- **Formatting** checks with Ruff
- **Type checking** with MyPy
- **Security scanning** with Bandit
- **Testing** multiple Python versions (3.10, 3.11, 3.12)

## 📋 Common Commands

| Command | Description |
|---------|-------------|
| `make help` | Show all available commands |
| `make dev-setup` | Complete development setup |
| `make dev-check` | Quick development check (fix + check all) |
| `make fix` | Auto-fix linting and formatting issues |
| `make check-all` | Run all quality checks |
| `make ci` | Run full CI pipeline locally |
| `make run-server` | Start TrackStudio server |

## 🐛 Troubleshooting

### Ruff Issues

If Ruff finds issues:

1. **Auto-fixable issues**: Run `make fix`
2. **Manual fixes needed**: Check the error messages and fix manually
3. **Configuration**: Adjust rules in `pyproject.toml` if needed

### MyPy Issues

Common MyPy issues:
- **Missing imports**: Add `# type: ignore` for third-party libraries
- **Type annotations**: Add proper type hints to functions
- **Optional types**: Use `X | None` instead of `Optional[X]` (Python 3.10+)

### Pre-commit Issues

If pre-commit hooks fail:
1. Fix the issues reported
2. Stage the fixes: `git add .`
3. Commit again

## 🎯 Code Style Guidelines

### Import Order
```python
# Standard library
import os
import sys

# Third-party
import numpy as np
import torch

# Local imports
from trackstudio.core import VisionAPI
from .base import BaseTracker
```

### Type Annotations
```python
# Use modern union syntax (Python 3.10+)
def process_frame(frame: np.ndarray | None) -> list[Detection]:
    ...

# Avoid old-style typing
# from typing import Optional, List  # ❌
# def process_frame(frame: Optional[np.ndarray]) -> List[Detection]:  # ❌
```

### Function Documentation
```python
def track_objects(frame: np.ndarray, detections: list[Detection]) -> list[Track]:
    """
    Track objects across frames.

    Args:
        frame: Input image frame
        detections: List of detected objects

    Returns:
        List of tracked objects with IDs

    Raises:
        ValueError: If frame is empty
    """
```

## 🚦 CI Status

The GitHub Actions workflow will show status badges for:
- ✅ Linting passed
- ✅ Formatting passed
- ✅ Type checking passed
- ✅ Security scan passed
- ✅ Tests passed

## 🤝 Contributing

Before submitting a PR:

1. Run `make dev-check` to ensure code quality
2. Add tests for new functionality
3. Update documentation as needed
4. Ensure all CI checks pass
