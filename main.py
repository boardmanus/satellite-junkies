import json
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

CONFIG_PATH = 'config.json'
CREDENTIALS_PATH = '.private/credentials.json'
TOKEN_PATH = '.private/token.pickle'
DEFAULT_RANGE_NAME = 'Sheet1!A:Z'  # Adjust if sheet name differs


def load_config():
    if not os.path.exists(CONFIG_PATH):
        logging.error('Missing config.json in the project root.')
        raise FileNotFoundError('config.json not found')

    with open(CONFIG_PATH, 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)

    if 'spreadsheet_id' not in config or 'calendar_id' not in config:
        logging.error('config.json must include spreadsheet_id and calendar_id.')
        raise KeyError('Missing required config values')

    config.setdefault('sheet_range', DEFAULT_RANGE_NAME)
    return config


def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.
    """
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token_file:
            creds = pickle.load(token_file)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                logging.error('Missing credentials.json in the project root.')
                raise FileNotFoundError('credentials.json not found')
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'wb') as token_file:
            pickle.dump(creds, token_file)
    return creds


def parse_row(row, headers):
    date_col = next((i for i, h in enumerate(headers) if h.lower() == 'date'), None)
    time_col = next((i for i, h in enumerate(headers) if h.lower() == 'time'), None)
    court_col = next((i for i, h in enumerate(headers) if h.lower() == 'court'), None)
    opponent_col = next((i for i, h in enumerate(headers) if h.lower() == 'opponent'), None)

    if None in (date_col, time_col, court_col, opponent_col):
        missing = [name for name, col in [
            ('Date', date_col),
            ('Time', time_col),
            ('Court', court_col),
            ('Opponent', opponent_col),
        ] if col is None]
        logging.error('Required columns missing from sheet: %s', ', '.join(missing))
        raise ValueError('Missing required sheet columns')

    if len(row) <= max(date_col, time_col, court_col, opponent_col):
        logging.warning('Skipping incomplete row: %s', row)
        return None

    return {
        'date': row[date_col].strip(),
        'time': row[time_col].strip(),
        'court': row[court_col].strip(),
        'opponent': row[opponent_col].strip(),
    }


def build_event_summary(game_data):
    return f"Court {game_data['court']} vs {game_data['opponent']}"


def build_event_description(game_data):
    return f"Court: {game_data['court']}\nOpponent: {game_data['opponent']}"


def parse_datetime_local(date_str, time_str):
    try:
        naive_dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
        local_tz = datetime.now().astimezone().tzinfo
        return naive_dt.replace(tzinfo=local_tz)
    except ValueError as first_error:
        logging.error('Error parsing date/time: %s %s', date_str, time_str)
        raise first_error


def create_or_update_event(calendar_service, calendar_id, game_data):
    start = parse_datetime_local(game_data['date'], game_data['time'])
    end = start + timedelta(hours=1)
    local_tz = start.tzinfo

    day_start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    events_result = calendar_service.events().list(
        calendarId=calendar_id,
        timeMin=day_start.isoformat(),
        timeMax=day_end.isoformat(),
        privateExtendedProperty='source=satellite-junkies',
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    summary = build_event_summary(game_data)
    description = build_event_description(game_data)
    event_body = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start.isoformat(),
            'timeZone': str(local_tz),
        },
        'end': {
            'dateTime': end.isoformat(),
            'timeZone': str(local_tz),
        },
        'extendedProperties': {
            'private': {
                'source': 'satellite-junkies'
            }
        }
    }

    if events:
        event = events[0]
        event.update(event_body)
        calendar_service.events().update(calendarId=calendar_id, eventId=event['id'], body=event).execute()
        logging.info('Updated calendar event for %s on %s', summary, game_data['date'])
    else:
        calendar_service.events().insert(calendarId=calendar_id, body=event_body).execute()
        logging.info('Created new calendar event for %s on %s', summary, game_data['date'])


def main():
    config = load_config()
    creds = get_credentials()
    sheets_service = build('sheets', 'v4', credentials=creds)
    calendar_service = build('calendar', 'v3', credentials=creds)

    sheet = sheets_service.spreadsheets()
    result = sheet.values().get(spreadsheetId=config['spreadsheet_id'],
                                range=config['sheet_range']).execute()
    values = result.get('values', [])

    if not values:
        logging.warning('No data found in the spreadsheet.')
        return

    headers = values[0]
    logging.info('Headers: %s', headers)

    for row in values[1:]:
        game_data = parse_row(row, headers)
        if not game_data:
            continue

        try:
            create_or_update_event(calendar_service, config['calendar_id'], game_data)
        except ValueError:
            continue


if __name__ == '__main__':
    main()
