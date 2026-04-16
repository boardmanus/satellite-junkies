# Satellite Junkies Calendar Sync

This project automates the synchronization of game times from a Google Sheet to Google Calendar. It reads game data from the specified spreadsheet and creates or updates calendar events accordingly.

## Setup

1. **Enable Google APIs**:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/).
   - Create a new project or select an existing one.
   - Enable the Google Sheets API and Google Calendar API.
   - Create credentials (OAuth 2.0 Client ID) and download the `credentials.json` file.
   - Place `credentials.json` in the project root.

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Script**:
   ```bash
   python main.py
   ```
   - On the first run, it will prompt for Google authentication.
   - Follow the instructions to grant permissions.

## Spreadsheet Format

The Google Sheet should have the following columns (case-insensitive):
- **Date**: In YYYY-MM-DD format
- **Time**: In HH:MM format (24-hour)
- **Game**: The name of the game/event

Example:
| Date       | Time  | Game          |
|------------|-------|---------------|
| 2023-10-01 | 14:00 | Game A        |
| 2023-10-02 | 16:30 | Game B        |

## How It Works

- The script reads data from the specified Google Sheet.
- For each game, it checks if a calendar event already exists for that day (marked with a custom property).
- If an event exists, it updates the event with the current information.
- If not, it creates a new event.
- All events created/updated by this script are marked with `source=satellite-junkies` in extended properties.

## Configuration

- **SPREADSHEET_ID**: Set in `main.py` (extracted from the sheet URL).
- **CALENDAR_ID**: Set to 'primary' for the default calendar; change if needed.
- **Time Zone**: Currently set to UTC; modify if your events are in a different time zone.

## Notes

- Ensure the Google account has access to the spreadsheet and calendar.
- The script assumes one game per day; if multiple games occur on the same day, only the first event will be updated.
- Game duration is assumed to be 1 hour; adjust in the code if necessary.