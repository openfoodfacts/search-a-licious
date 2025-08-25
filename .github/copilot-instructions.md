# Search-a-licious Development Instructions

Search-a-licious is a comprehensive search platform built with Python FastAPI backend, TypeScript/Lit frontend, Elasticsearch, Redis, and Docker Compose orchestration. Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match these instructions.

## Working Effectively

### Prerequisites and Environment Setup
- Ensure `vm.max_map_count=262144` for Elasticsearch: `sudo sysctl -w vm.max_map_count=262144`
- Install Docker and Docker Compose
- Install Python 3.11+, Node.js LTS, and Poetry
- Create `.envrc` file with required environment variables:
```bash
export USER_GID=$(id -g)
export USER_UID=$(id -u)
export CONFIG_PATH=data/config/openfoodfacts.yml
export OFF_API_URL=https://world.openfoodfacts.org
export ALLOWED_ORIGINS='http://localhost,http://127.0.0.1'
```

### Frontend Development (TypeScript/Lit Web Components)
- **Install dependencies**: `cd frontend && npm install` -- takes ~33 seconds. NEVER CANCEL.
- **Build**: `npm run build` -- takes ~6 seconds, includes TypeScript compilation and translations
- **Development build with watch**: `npm run build:watch` -- runs continuously  
- **Lint and format**: `npm run lint` -- takes ~5 seconds, includes ESLint and lit-analyzer
- **Format code**: `npm run format` -- applies Prettier formatting
- **Tests**: `npm run test` -- requires Playwright browsers: `npx playwright install` first
- **Serve locally**: `npm run serve` -- development server with hot reload

### Backend Development (Python FastAPI)
- **Install dependencies**: `poetry install` -- takes ~4 seconds for dev dependencies
- **Run API server locally**: `poetry run uvicorn app.api:app --reload --host 0.0.0.0 --port 8000`
- **Unit tests**: `poetry run pytest tests/unit/` -- takes ~6 seconds, 42 tests run in ~2.3 seconds. NEVER CANCEL. Set timeout to 30+ seconds.
- **Integration tests**: Requires Elasticsearch running: `poetry run pytest tests/int/`
- **Lint with black**: `poetry run black --check app/` or use pre-commit (see below)
- **Type checking**: `poetry run mypy app/`
- **CLI tools**: `poetry run python -m app --help` -- shows available commands

### Docker Development (Full Stack)
- **Build containers**: `make build` -- **NETWORK DEPENDENT**: fails without internet access to install Poetry. Set timeout to 60+ minutes. NEVER CANCEL.
- **Start services**: `make up` -- starts Elasticsearch, Redis, API, and frontend services
- **Stop services**: `make down`
- **View logs**: `docker compose logs -f [service-name]`

**CRITICAL NETWORK ISSUE**: Docker build currently fails due to Poetry installation requiring `https://install.python-poetry.org` access. If network access is limited, use local Poetry development instead.

### Testing and Quality Assurance
- **Run all tests**: `make test` -- takes 10-15 minutes total. NEVER CANCEL. Set timeout to 30+ minutes.
  - Backend unit tests: ~6 seconds
  - Backend integration tests: requires Elasticsearch, ~5-10 minutes  
  - Frontend tests: requires Playwright browsers, ~2-5 minutes
- **Pre-commit hooks**: `pre-commit install && pre-commit run --all-files` -- initial setup ~10 seconds per hook. NEVER CANCEL.
- **Lint all code**: `make lint` -- runs both backend (black) and frontend (ESLint) linting

### Code Quality and Formatting  
- **Backend**: Use `black`, `flake8`, `isort`, `mypy` via pre-commit or Poetry
- **Frontend**: Use `prettier`, `eslint`, `lit-analyzer` via npm scripts
- **Pre-commit**: Run `make check` before committing -- takes 5-15 minutes depending on cache. NEVER CANCEL. Set timeout to 30+ minutes.

## Validation Scenarios

Always test these scenarios after making changes:

### Frontend Component Validation
1. **Build verification**: `cd frontend && npm run build` -- should complete without TypeScript errors
2. **Component rendering**: Verify web components render in browser at `http://localhost:3000` (if using dev server)
3. **Search functionality**: Test search bar, filters, and results display
4. **Responsive design**: Check mobile and desktop layouts

### Backend API Validation  
1. **API startup**: `poetry run uvicorn app.api:app --host 0.0.0.0 --port 8000` -- should start without errors
2. **API health**: GET `http://localhost:8000/health` -- returns 500 without Redis/Elasticsearch (expected), but endpoint accessible
3. **CLI functionality**: `poetry run python -m app --help` -- shows available commands
4. **Import functionality**: Test data import with `poetry run python -m app import --help`
5. **Configuration loading**: Verify config file at `data/config/openfoodfacts.yml` loads correctly

### Integration Validation
1. **Full stack**: Start all services with `make up` and test complete search workflow
2. **Data flow**: Import sample data, verify indexing, test search results
3. **Performance**: Check search response times < 1 second for typical queries

## Network Dependencies and Timing

### Commands That Require Network Access
- **Docker build** (`make build`): Fails without access to Poetry installation server
- **Playwright browser installation** (`npx playwright install`): Downloads ~100MB of browser binaries
- **Pre-commit hook setup**: Some hooks require package downloads
- **Poetry dependency resolution**: Initial poetry install needs PyPI access

### Recommended Timeouts
- **`npm install`**: 60 seconds (typically 33 seconds)
- **Frontend build**: 30 seconds (typically 6 seconds)  
- **Backend unit tests**: 30 seconds (typically 6 seconds)
- **Docker build**: 3600 seconds (60 minutes) -- can take 30-60 minutes. NEVER CANCEL.
- **Full test suite**: 1800 seconds (30 minutes) -- integration tests can be slow. NEVER CANCEL.
- **Pre-commit all files**: 1800 seconds (30 minutes) -- initial hook setup is slow. NEVER CANCEL.

## Project Structure and Navigation

### Key Directories
- `/app/`: Python FastAPI backend code
- `/frontend/`: TypeScript/Lit frontend code  
- `/docs/`: MkDocs documentation
- `/data/config/`: YAML configuration files
- `/tests/`: Python test suite (unit and integration)
- `/docker/`: Docker Compose configuration files
- `/.github/workflows/`: CI/CD pipeline definitions

### Important Files
- `pyproject.toml`: Python dependencies and tool configuration
- `frontend/package.json`: Node.js dependencies and scripts
- `Makefile`: Common development tasks and shortcuts
- `docker-compose.yml`: Main service definitions
- `.pre-commit-config.yaml`: Code quality hook definitions

### Configuration Files
- `data/config/openfoodfacts.yml`: Main search configuration
- `.env`: Environment variables for Docker Compose
- `.envrc`: Development environment variables (create manually)

## Common Development Tasks

### Adding New Search Fields
1. Update configuration in `data/config/openfoodfacts.yml`
2. Modify indexing logic in `app/indexing.py`
3. Update query building in `app/es_query_builder.py`  
4. Add frontend components if needed
5. Run full test suite to validate

### Modifying Web Components
1. Edit TypeScript files in `frontend/src/`
2. Build: `npm run build` 
3. Test: `npm run test` (after installing Playwright browsers)
4. Format: `npm run format`
5. Validate in browser at `http://localhost:3000`

### Database Schema Changes
1. Update Elasticsearch mappings in configuration
2. Modify data import logic in `app/_import.py`
3. Test with sample data import
4. Run integration tests to verify

### Debugging and Troubleshooting
- **Frontend**: Use browser dev tools, check TypeScript compilation errors
- **Backend**: Use `poetry run python -m app --help` for CLI debugging
- **Docker**: Use `docker compose logs -f [service]` for service logs
- **Elasticsearch**: Access ElasticVue at `http://localhost:8080` when running

## Limitations and Known Issues

### Network Connectivity Issues
- Docker build fails without internet access due to Poetry installation requirements
- Playwright tests require browser download (~100MB)
- Some pre-commit hooks fail during initial setup without network access

### Workarounds  
- **Local development**: Use Poetry locally instead of Docker for backend development
- **Testing**: Run unit tests locally, skip integration tests if Elasticsearch unavailable
- **Linting**: Use Poetry-based linting instead of pre-commit if network issues persist

### Browser Requirements
- **Frontend tests**: Require Chromium installation via Playwright
- **Development**: Modern browser with ES2020+ support for web components
- **Mobile testing**: Use browser dev tools responsive design mode

Always run validation steps and measure timing for any new commands you add to these instructions to ensure accuracy and reliability.