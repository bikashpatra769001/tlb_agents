# Project Structure

## Root Directory Layout
```
agents-with-strands/
├── .kiro/                  # Kiro IDE configuration and steering rules
├── .venv/                  # Alternative virtual environment (unused)
├── strands/                # Active virtual environment directory
├── hello.py                # Main entry point and example code
├── pyproject.toml          # Project configuration and dependencies
├── uv.lock                 # Dependency lock file
├── .python-version         # Python version specification
└── README.md               # Project documentation (empty)
```

## Key Conventions
- **Entry Point**: `hello.py` serves as the main application entry point
- **Virtual Environment**: Use `strands/` directory (not `.venv/`)
- **Dependencies**: Manage via `pyproject.toml` and `uv` commands
- **Python Version**: Strictly Python 3.12 as specified in `.python-version`

## File Organization Guidelines
- Keep main application logic in root-level Python files for now
- Use descriptive module names as the project grows
- Follow standard Python package structure when adding modules
- Maintain the minimal structure until complexity requires reorganization

## Development Workflow
- All Python code should be compatible with Python 3.12+
- Use `uv` for all dependency management operations
- Virtual environment activation via `strands/bin/activate`