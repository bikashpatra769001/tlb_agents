# Technology Stack

## Build System & Package Management
- **uv**: Modern Python package manager and dependency resolver
- **Python 3.12**: Required minimum version
- **pyproject.toml**: Standard Python project configuration

## Development Environment
- Virtual environment managed via `strands/` directory
- Python version pinned to 3.12 via `.python-version`

## Common Commands
```bash
# Install dependencies
uv sync

# Run the main application
python hello.py

# Create/activate virtual environment
uv venv strands
source strands/bin/activate

# Add new dependencies
uv add <package-name>

# Run Python scripts
uv run python <script.py>
```

## Project Configuration
- No external dependencies currently defined
- Minimal project setup suitable for rapid prototyping
- Standard Python project structure with pyproject.toml