# Sync-Notion-Todoist Development Guidelines

## Setup & Commands
- **Install Dependencies**: `pip install -r requirements.txt`
- **Run Application**: `python main.py`
- **Run GUI**: `python Run-GUI.py`
- **Run with Docker**: `docker-compose up`
- **Linting**: `flake8 *.py` (requires installing flake8)
- **Run Single Component**: Use `python Notion_to_Local.py` or `python Todoist_to_Local.py`

## Code Style Guidelines
- **Imports**: Standard library first, then third-party, then local modules
- **Formatting**: 4-space indentation, 120 character line length
- **Docstrings**: Use triple quotes for function/class documentation
- **Error Handling**: Use try/except with specific exceptions, proper error messages
- **Naming**: snake_case for functions/variables, CamelCase for classes
- **JSON Handling**: Use `ensure_ascii=False, indent=2, default=str` when dumping
- **Date Handling**: Use timezone-aware datetime objects when possible
- **API Calls**: Always use `raise_for_status()` to check for HTTP errors
- **Environment Variables**: Load from .env file using python-dotenv

## Project Structure
- API interactions in helper.py
- Sync operations in Sync.py
- Main execution flow in main.py
- One-way syncs in Notion_to_Local.py and Todoist_to_Local.py