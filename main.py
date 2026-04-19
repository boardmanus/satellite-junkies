import json
import os
import pickle
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
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


def parse_row(row: list, headers: list):
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

    court_value = row[court_col].strip()
    try:
        court_value = int(court_value)
    except ValueError:
        logging.warning('Court value is not numeric: %s', court_value)

    return {
        'date': row[date_col].strip(),
        'time': row[time_col].strip(),
        'court': court_value,
        'opponent': row[opponent_col].strip(),
    }

def build_event_summary(court: int, opponent: str):
    match court:
        case 0:
            return "Volleyball Practice @ Moon"
        case _:
            return f"Volleyball, Court {court} vs {opponent}"


def build_event_description(court: int, opponent: str):
    match court:
        case 0:
            return "Volleyball Practice, rule of 10."
        case _:
            return f"Satellite Junkies vs {opponent}, on Court {court}"

def build_event_address(court: int):
    match court:
        case 0:
            return "Moon Under Water, 152 Somerfield Street, Somerfield, Christchurch 8024"
        case 1 | 2 | 3 | 4 | 5 | 6:
            return "Pioneer Stadium, 75 Lyttelton St, Somerfield, Christchurch 8024"
        case _:
            return "Parakiore, 50 Saint Asaph Street, Christchurch Central City, Christchurch 8011"

def build_guests(config: dict):
    return config.get('players', [])

def parse_datetime_local(date_str: str, time_str: str):
    ntime_str = time_str.strip().upper().replace(' ', '')
    dt = datetime.strptime(f"{date_str} {ntime_str}", "%d/%m/%Y %I:%M%p")
    return dt.replace(tzinfo=ZoneInfo('Pacific/Auckland'))

def normalize_attendees(attendees):
    if not attendees:
        return []
    return sorted([attendee.get('email') for attendee in attendees if 'email' in attendee])

def needs_update(existing_event, new_body):
    keys_to_check = ['summary', 'description', 'location', 'start', 'end']
    for key in keys_to_check:
        if existing_event.get(key) != new_body.get(key):
            return True

    existing_attendees = normalize_attendees(existing_event.get('attendees', []))
    new_attendees = normalize_attendees(new_body.get('attendees', []))
    if existing_attendees != new_attendees:
        return True

    return False

def create_or_update_event(config: dict, calendar_service, game_data: dict):
    date: str = game_data['date']
    time: str = game_data['time']
    court: int = game_data['court']
    opponent: str = game_data['opponent']

    start = parse_datetime_local(date, time)
    end = start + timedelta(hours=1)
    day_start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    calendar_id = config['calendar_id']

    events_result = calendar_service.events().list(
        calendarId=calendar_id,
        timeMin=day_start.isoformat(),
        timeMax=day_end.isoformat(),
        privateExtendedProperty='source=satellite-junkies',
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    summary = build_event_summary(court, opponent)
    event_body = {
        'summary': summary,
        'description': build_event_description(court, opponent),
        'location': build_event_address(court),
        'start': {
            'dateTime': start.isoformat(),
            'timeZone': start.tzinfo.key
        },
        'end': {
            'dateTime': end.isoformat(),
            'timeZone': start.tzinfo.key
        },
        'extendedProperties': {
            'private': {
                'source': 'satellite-junkies'
            }
        },
        'attendees': [{'email': email} for email in build_guests(config)]
    }

    if events:
        if len(events) > 1:
            logging.warning('Multiple events found for %s on %s, keeping the first and deleting the rest.', summary, date)
        existing_event = events[0]
        if needs_update(existing_event, event_body):
            calendar_service.events().update(
                calendarId=calendar_id,
                eventId=existing_event['id'],
                body=event_body,
                sendUpdates='none'
            ).execute()
            logging.info('Updated calendar event for %s on %s', summary, date)
        else:
            logging.info('Calendar event for %s on %s is already up to date', summary, date)
        # Delete any additional events
        for extra_event in events[1:]:
            calendar_service.events().delete(calendarId=calendar_id, eventId=extra_event['id']).execute()
            logging.info('Deleted duplicate calendar event for %s on %s', summary, date)
    else:
        calendar_service.events().insert(
            calendarId=calendar_id,
            body=event_body,
            sendUpdates='none'
        ).execute()
        logging.info('Created new calendar event for %s on %s', summary, date)


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
    for row in values[1:]:
        game_data = parse_row(row, headers)
        if not game_data:
            continue

        try:
            create_or_update_event(config, calendar_service, game_data)
        except ValueError:
            continue


if __name__ == '__main__':
    main()
