import os
import pickle
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly',
          'https://www.googleapis.com/auth/calendar']

# Google Sheet ID from the URL
SPREADSHEET_ID = '15TqYxGo8TSb49CBrRoZALoMPi6WqpuMSSFBbbs65E80'
RANGE_NAME = 'Sheet1!A:Z'  # Adjust if sheet name differs

# Calendar ID (use 'primary' for default calendar)
CALENDAR_ID = 'primary'

def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('.private/token.pickle'):
        with open('.private/token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                '.private/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('.private/token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds

def main():
    """Main function to read from Google Sheet and update Google Calendar."""
    creds = get_credentials()
    sheets_service = build('sheets', 'v4', credentials=creds)
    calendar_service = build('calendar', 'v3', credentials=creds)

    # Call the Sheets API
    sheet = sheets_service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
                                range=RANGE_NAME).execute()
    values = result.get('values', [])

    if not values:
        logging.warning('No data found in the spreadsheet.')
        return

    # Assume first row is headers
    headers = values[0]
    logging.info(f'Headers: {headers}')

    # Find column indices (case-insensitive)
    date_col = next((i for i, h in enumerate(headers) if h.lower() == 'date'), None)
    time_col = next((i for i, h in enumerate(headers) if h.lower() == 'time'), None)
    game_col = next((i for i, h in enumerate(headers) if h.lower() == 'game'), None)

    if date_col is None or time_col is None or game_col is None:
        logging.error('Required columns (Date, Time, Game) not found in the sheet.')
        return

    for row in values[1:]:
        if len(row) <= max(date_col, time_col, game_col):
            logging.warning(f'Skipping incomplete row: {row}')
            continue

        date_str = row[date_col].strip()
        time_str = row[time_col].strip()
        game_name = row[game_col].strip()

        try:
            # Parse date and time
            start_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            # Assume game duration is 1 hour; adjust as needed
            end_datetime = start_datetime + timedelta(hours=1)
        except ValueError as e:
            logging.error(f'Error parsing date/time for {game_name}: {e}')
            continue

        # Check for existing event on the same day
        day_start = start_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        events_result = calendar_service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=day_start.isoformat() + 'Z',
            timeMax=day_end.isoformat() + 'Z',
            privateExtendedProperty='source=satellite-junkies',
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])

        if events:
            # Update the existing event (assume one per day)
            event = events[0]
            event['summary'] = game_name
            event['start']['dateTime'] = start_datetime.isoformat() + 'Z'
            event['end']['dateTime'] = end_datetime.isoformat() + 'Z'
            calendar_service.events().update(calendarId=CALENDAR_ID, eventId=event['id'], body=event).execute()
            logging.info(f'Updated calendar event for {game_name} on {date_str}')
        else:
            # Create new event
            event = {
                'summary': game_name,
                'start': {
                    'dateTime': start_datetime.isoformat() + 'Z',
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_datetime.isoformat() + 'Z',
                    'timeZone': 'UTC',
                },
                'extendedProperties': {
                    'private': {
                        'source': 'satellite-junkies'
                    }
                }
            }
            calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
            logging.info(f'Created new calendar event for {game_name} on {date_str}')

if __name__ == '__main__':
    main()