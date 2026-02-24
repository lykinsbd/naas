# Testing

NAAS uses pytest for testing with comprehensive coverage.

## Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=naas --cov-report=term-missing

# Run specific test file
uv run pytest tests/unit/test_app.py

# Run with verbose output
uv run pytest -v
```

## Test Structure

- `tests/unit/` - Unit tests for individual components
- `tests/integration/` - Integration tests for API endpoints
- `tests/contract/` - Contract tests for API behavior

## Code Quality

```bash
# Run all checks (linting, formatting, type checking, tests)
invoke check

# Individual checks
invoke lint      # Ruff linting
invoke format    # Ruff formatting
invoke typecheck # mypy type checking
invoke test      # pytest
```

## Coverage

Current test coverage: 94 tests, 80%+ coverage

Target: 80%+ coverage on all new code
