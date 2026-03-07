# Contributing to Diamond Options Engine

## Setup

```bash
git clone https://github.com/pvc1997/diamond_options_engine.git
cd diamond_options_engine
uv sync --dev
pre-commit install
```

## Development Workflow

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes
3. Run tests: `uv run pytest tests/ -x -q`
4. Run linter: `uv run ruff check src/ tests/`
5. Commit (pre-commit hooks will run automatically)
6. Push and open a PR

## Code Style

- **Formatter:** ruff format (line length 100)
- **Linter:** ruff check (E, F, I, UP, B, SIM rules)
- **Type checker:** pyright (standard mode)
- **Tests:** pytest with pytest-mock, all external calls mocked

## Architecture Guidelines

- Config via `get_config()` singleton (Pydantic Settings)
- Pure functions preferred (especially in `costs.py`, `pricing/`)
- All market data access through `data/market.py` with caching
- SQLite for persistence (ledgers, no ORM beyond peewee)
- MCP tools in `mcp_server/server.py`, one function per tool
- Tests mirror `src/` structure: `test_costs.py` tests `costs.py`

## Adding a New MCP Tool

1. Add the function in the relevant `src/diamond_options/` module
2. Add a `@mcp.tool()` wrapper in `mcp_server/server.py`
3. Add tests in `tests/`
4. Update tool count in `CLAUDE.md` and `README.md`

## Adding a New Strategy

1. Add the `StrategySpec` in `strategy/definitions.py`
2. Add scoring logic in `strategy/scanner.py`
3. Add leg builder in `strategy/definitions.py`
4. Add tests

## Running Tests

```bash
# All tests (~550, ~2.5s)
uv run pytest tests/ -x --tb=short -q

# Specific module
uv run pytest tests/test_costs.py -v

# With coverage
uv run pytest tests/ --cov=diamond_options --cov-report=term-missing
```

## Commit Messages

Use conventional-style messages:
- `feat: add iron butterfly strategy`
- `fix: correct STT calculation for index options`
- `refactor: simplify IV solver convergence logic`
- `test: add Monte Carlo edge case tests`
- `docs: update README with Phase 8 tools`
