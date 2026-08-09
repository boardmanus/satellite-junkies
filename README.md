# Satellite Junkies Calendar Sync

This project automates the synchronization of game times from a Google Sheet to Google Calendar. It reads game data from the specified spreadsheet and creates or updates calendar events accordingly.

## Setup

1. **Create a Consistent Python Environment**:
   - Install dependencies and create `.venv` with uv:

     ```bash
     uv sync
     ```

2. **Enable Google APIs**:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/).
   - Create a new project or select an existing one.
   - Enable the Google Sheets API and Google Calendar API.
   - Create credentials (OAuth 2.0 Client ID) and download the `credentials.json` file.
   - Place `credentials.json` in the project root.

3. **Run the Script**:

   ```bash
   uv run python main.py
   ```

    - On the first run, it will prompt for Google authentication.
    - Follow the instructions to grant permissions.

## Spreadsheet Format

The Google Sheet should have the following columns (case-insensitive):

- **Date**: In DD/MM/YYYY format
- **Time**: In HH:MM AM/PM format (12-hour), e.g. `8:30 PM`
- **Court**: The court being played on
- **Opponent**: The team being played

Example:

| Date       | Time     | Court | Opponent    |
|------------|----------|-------|-------------|
| 23/04/2026 | 8:30 PM  | 0     | Moon        |
| 30/04/2026 | 8:30 PM  | 4     | Beat Street |

## How It Works

- The script reads data from the specified Google Sheet.
- For each game, it checks if a calendar event already exists for that day (marked with a custom property).
- If an event exists, it updates the event with the current information.
- If not, it creates a new event.
- All events created/updated by this script are marked with `source=satellite-junkies` in extended properties.

## Configuration

Configuration is stored in a `config.json` file that provides the following details:

- **spreadsheet_id**: The id of the Satellite Junkies spreadsheet to use (extracted from the sheet URL).
- **calendar_id**: The id of the calendar to update. Set to 'primary' for the default calendar; change if needed.

## Testing

Run the unit tests with:

```bash
uv run python -m unittest discover tests
```

## Notes

- Ensure the Google account has access to the spreadsheet and calendar.
- The script assumes one game per day; if multiple games occur on the same day, only the first event will be updated.
- Game duration is assumed to be 1 hour; adjust in the code if necessary.
- Time-zone is always the script runners local time
