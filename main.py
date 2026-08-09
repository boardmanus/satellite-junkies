"""Sync volleyball game rows from Google Sheets into Google Calendar events."""

import json
import logging
import os
import pickle
from datetime import datetime, timedelta
from collections.abc import Mapping, Sequence
from typing import Any, TypedDict
from zoneinfo import ZoneInfo
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly',
          'https://www.googleapis.com/auth/calendar']

CONFIG_PATH = 'config.json'
CREDENTIALS_PATH = '.private/credentials.json'
TOKEN_PATH = '.private/token.pickle'
DEFAULT_RANGE_NAME = 'Sheet1!A:Z'  # Adjust if sheet name differs


class EventDateTime(TypedDict):
    """Calendar API datetime payload."""
    dateTime: str
    timeZone: str


class ExtendedPropertiesPrivate(TypedDict):
    """Private extended properties metadata."""
    source: str


class ExtendedProperties(TypedDict):
    """Extended properties container."""
    private: ExtendedPropertiesPrivate


class Attendee(TypedDict):
    """Calendar attendee payload."""
    email: str


class CalendarEvent(TypedDict):
    """Calendar event payload used for create/update calls."""
    summary: str
    description: str
    location: str
    start: EventDateTime
    end: EventDateTime
    extendedProperties: ExtendedProperties
    attendees: list[Attendee]


Row = Sequence[str]
Headers = Sequence[str]
Players = Sequence[str]


def load_config() -> dict[str, Any]:
    """Load and validate app configuration from config.json."""
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


def get_credentials() -> Any:
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.
    """
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token_file:
            creds = pickle.load(token_file)
            if not creds or creds.expired or not creds.valid:
                creds = None
                logging.info('Stored credentials are invalid or expired, re-authenticating...')

    if not creds:
        if not os.path.exists(CREDENTIALS_PATH):
            logging.error('Missing credentials.json in the project root.')
            raise FileNotFoundError('credentials.json not found')
        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_PATH, SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)

    with open(TOKEN_PATH, 'wb') as token_file:
        pickle.dump(creds, token_file)

    return creds

class GameData:
    """Represents a single game entry parsed from a sheet row."""
    start_time: datetime
    court: int
    opponent: str

    def __init__(self, start_time: datetime, court: int, opponent: str):
        """Initialize game details used to build a calendar event."""
        self.start_time = start_time
        self.court = court
        self.opponent = opponent

    def summary(self) -> str:
        """Return the calendar event summary for this game."""
        match self.court:
            case 0:
                return "Volleyball Practice @ Moon"
            case _:
                return f"Volleyball, Court {self.court} vs {self.opponent}"

    def description(self) -> str:
        """Return the calendar event description for this game."""
        match self.court:
            case 0:
                return "Volleyball Practice, rule of 10."
            case _:
                return f"Satellite Junkies vs {self.opponent}, on Court {self.court}"

    def address(self) -> str:
        """Return the venue address derived from court number."""
        match self.court:
            case 0:
                return "Moon Under Water, 152 Somerfield Street, Somerfield, Christchurch 8024"
            case 1 | 2 | 3 | 4 | 5 | 6:
                return "Pioneer Stadium, 75 Lyttelton St, Somerfield, Christchurch 8024"
            case _:
                return "Parakiore, 50 Saint Asaph Street, Christchurch Central City, Christchurch 8011"

    def event(self, guests: Players | None = None) -> CalendarEvent:
        """Build the Google Calendar event payload for this game."""

        if guests is None:
            guests = []

        start_time = self.start_time
        end_time = start_time + timedelta(hours=1)

        return {
            'summary': self.summary(),
            'description': self.description(),
            'location': self.address(),
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'Pacific/Auckland'
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'Pacific/Auckland'
            },
            'extendedProperties': {
                'private': {
                    'source': 'satellite-junkies'
                }
            },
            'attendees': [{'email': email} for email in guests]
        }

def parse_datetime_local(date_str: str, time_str: str) -> datetime:
    """Parse date/time strings into Pacific/Auckland local datetime."""
    ntime_str = time_str.strip().upper().replace(' ', '')
    dt = datetime.strptime(f"{date_str} {ntime_str}", "%d/%m/%Y %I:%M%p")
    return dt.replace(tzinfo=ZoneInfo('Pacific/Auckland'))

def parse_row(row: Row, headers: Headers) -> GameData:
    """Convert a raw sheet row into validated GameData."""
    date_col = next((i for i, h in enumerate(headers) if h.lower() == 'date'), None)
    time_col = next((i for i, h in enumerate(headers) if h.lower() == 'time'), None)
    court_col = next((i for i, h in enumerate(headers) if h.lower() == 'court'), None)
    opponent_col = next((i for i, h in enumerate(headers) if h.lower() == 'opponent'), None)

    if date_col is None or time_col is None or court_col is None or opponent_col is None:
        missing = [name for name, col in [
            ('Date', date_col),
            ('Time', time_col),
            ('Court', court_col),
            ('Opponent', opponent_col),
        ] if col is None]
        raise ValueError(f'Missing required sheet columns: {",".join(missing)}')

    if len(row) <= max(date_col, time_col, court_col, opponent_col):
        raise ValueError(f'Incomplete row data: {row}')

    start_time = parse_datetime_local(row[date_col].strip(), row[time_col].strip())
    court_value = int(row[court_col].strip())
    opponent = row[opponent_col].strip()

    return GameData(start_time, court_value, opponent)


def normalize_attendees(attendees: Sequence[Mapping[str, str]] | None) -> list[str]:
    """Return sorted attendee email list from a calendar attendee payload."""
    if not attendees:
        return []
    return sorted([attendee['email'] for attendee in attendees if 'email' in attendee])

def needs_update(existing_event: Mapping[str, Any], new_body: Mapping[str, Any]) -> bool:
    """Determine whether an existing calendar event differs from desired state."""
    keys_to_check = ['summary', 'description', 'location', 'start', 'end']
    for key in keys_to_check:
        if existing_event.get(key) != new_body.get(key):
            return True

    existing_attendees = normalize_attendees(existing_event.get('attendees', []))
    new_attendees = normalize_attendees(new_body.get('attendees', []))
    if existing_attendees != new_attendees:
        return True

    return False

def find_events(calendar_service: Any, calendar_id: str, start_time: datetime) -> list[dict[str, Any]]:
    """Find source-tagged events on the same day as start_time."""
    day_start = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    events_result = calendar_service.events().list(
        calendarId=calendar_id,
        timeMin=day_start.isoformat(),
        timeMax=day_end.isoformat(),
        privateExtendedProperty='source=satellite-junkies',
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    return events_result.get('items', [])

def update_events(
    calendar_service: Any,
    calendar_id: str,
    event: CalendarEvent,
    events: Sequence[Mapping[str, Any]],
) -> None:
    """Update first matching event and remove duplicates."""

    existing_event = events[0]
    start_time = event['start']['dateTime']
    if needs_update(existing_event, event):
        calendar_service.events().update(
            calendarId=calendar_id,
            eventId=existing_event['id'],
            body=event,
            sendUpdates='none'
        ).execute()
        logging.info('Updated calendar event: %s @ %s', event.get('summary'), start_time)
    else:
        logging.info('Calendar event already exists: %s @ %s', event.get('summary'), start_time)

    # Delete any additional events
    for extra_event in events[1:]:
        start_time = event['start']['dateTime']
        calendar_service.events().delete(calendarId=calendar_id, eventId=extra_event['id']).execute()
        logging.info('Deleted duplicate calendar event: %s @ %s', extra_event.get('summary'), start_time)

def create_event(calendar_service: Any, calendar_id: str, event: CalendarEvent) -> None:
    """Insert a new calendar event for a game."""
    start_time = event['start']['dateTime']
    calendar_service.events().insert(
        calendarId=calendar_id,
        body=event,
        sendUpdates='none'
    ).execute()
    logging.info('Created new calendar event: %s @ %s', event.get('summary'), start_time)


def handle_row(
    calendar_service: Any,
    calendar_id: str,
    row: Row,
    headers: Headers,
    guests: Players,
) -> None:
    """Process one sheet row and create or update the related event."""
    try:
        game_data = parse_row(row, headers)
        if game_data.start_time < datetime.now(game_data.start_time.tzinfo):
            logging.info('Skipping past event: %s @ %s', game_data.summary(), game_data.start_time)
            return

        event = game_data.event(guests)
        existing_events = find_events(calendar_service, calendar_id, game_data.start_time)
        if len(existing_events) > 0:
            update_events(calendar_service, calendar_id, event, existing_events)
        else:
            create_event(calendar_service, calendar_id, event)

    except ValueError as err:
        logging.error('Skipping row due to error: %s', err)


def main() -> None:
    """Read sheet data and sync all rows to calendar events."""
    config = load_config()
    creds = get_credentials()
    sheets_service = build('sheets', 'v4', credentials=creds)
    calendar_service = build('calendar', 'v3', credentials=creds)

    # pylint: disable=no-member
    sheet = sheets_service.spreadsheets()
    # pylint: enable=no-member
    result = sheet.values().get(spreadsheetId=config['spreadsheet_id'],
                                range=config['sheet_range']).execute()
    values = result.get('values', [])

    if not values:
        logging.warning('No data found in the spreadsheet.')
        return

    headers = values[0]
    calendar_id = config['calendar_id']
    guests = config.get('players', [])

    for row in values[1:]:
        handle_row(calendar_service, calendar_id, row, headers, guests)


if __name__ == '__main__':
    main()
