# Project Guidelines
The project provides a mechanism to keep calendar entries up to date with Game times entered in a spread sheet.

## Architecture
This project integrates Google Sheets and Google Calendar APIs to automate calendar event creation from spreadsheet data. The core components include:

- **Data Reading**: Fetch data from specified Google Sheets using the Sheets API
- **Event Creation**: Parse sheet data and create corresponding calendar events via the Calendar API
- **Authentication**: Handle Google API authentication (OAuth 2.0 or service account)
- **Error Handling**: Robust error handling for API failures and data validation

Key design decisions:
- Use Python with google-api-python-client for API interactions
- Store configuration (sheet ID, calendar ID, credentials) in environment variables or config files
- Implement logging for debugging and monitoring
- Data source: https://docs.google.com/spreadsheets/d/15TqYxGo8TSb49CBrRoZALoMPi6WqpuMSSFBbbs65E80/edit?gid=0#gid=0

## Build and Test
```bash
# Install dependencies
pip install -r requirements.txt

# Run the main script
python main.py

# For development/testing
python -m pytest tests/  # When tests are added
```

## Conventions
- Use descriptive variable names for sheet columns and calendar fields
- Validate data before API calls to prevent malformed events
- Log API responses and errors for troubleshooting
- Follow Google API best practices for rate limiting and quota management

## Code Style
- Follow PEP 8 Python style guidelines
- Use type hints for function parameters and return values
- Keep functions focused on single responsibilities
- Add docstrings to public functions and classes
