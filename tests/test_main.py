"""Unit tests for calendar sync helpers and event behavior."""

import json
import sys
import unittest
from unittest import mock
from datetime import datetime
from zoneinfo import ZoneInfo

# Stub Google API modules for environments where googleapiclient is not installed.
mock_googleapiclient_discovery = mock.Mock()
mock_googleapiclient_discovery.build = mock.Mock()
sys.modules['googleapiclient'] = mock.Mock(discovery=mock_googleapiclient_discovery)
sys.modules['googleapiclient.discovery'] = mock_googleapiclient_discovery
sys.modules['google.oauth2'] = mock.Mock()
sys.modules['google.oauth2.credentials'] = mock.Mock(Credentials=mock.Mock())
sys.modules['google_auth_oauthlib'] = mock.Mock()
sys.modules['google_auth_oauthlib.flow'] = mock.Mock(InstalledAppFlow=mock.Mock())
sys.modules['google.auth'] = mock.Mock()
sys.modules['google.auth.transport'] = mock.Mock()
sys.modules['google.auth.transport.requests'] = mock.Mock(Request=mock.Mock())

import main

TEST_CONFIG = {
    'spreadsheet_id': 'test-spreadsheet-id',
    'calendar_id': 'primary',
    'sheet_range': 'Sheet1!A:Z',
    'players': ['player1@example.com', 'player2@example.com']
}

class TestLoadConfig(unittest.TestCase):
    """Tests for config loading and validation."""

    def test_load_config_success(self):
        """Loads a valid config file."""
        with mock.patch('main.os.path.exists', return_value=True), \
             mock.patch('builtins.open', mock.mock_open(read_data=json.dumps(TEST_CONFIG))):
            config = main.load_config()

        self.assertEqual(config['spreadsheet_id'], 'test-spreadsheet-id')
        self.assertEqual(config['calendar_id'], 'primary')
        self.assertEqual(config['players'], ['player1@example.com', 'player2@example.com'])

    def test_load_config_missing_file(self):
        """Raises when config.json is missing."""
        with mock.patch('main.os.path.exists', return_value=False):
            with self.assertRaises(FileNotFoundError):
                main.load_config()

    def test_load_config_missing_keys(self):
        """Raises when required config keys are absent."""
        config_data = {'spreadsheet_id': 'abc'}
        with mock.patch('main.os.path.exists', return_value=True), \
             mock.patch('builtins.open', mock.mock_open(read_data=json.dumps(config_data))):
            with self.assertRaises(KeyError):
                main.load_config()


class TestGameData(unittest.TestCase):
    """Tests for GameData formatting and event payload generation."""

    def setUp(self):
        """Create a shared timezone-aware start time."""
        self.start_time = datetime(2026, 4, 23, 20, 30, tzinfo=ZoneInfo('Pacific/Auckland'))

    def test_game_data_practice_summary(self):
        """Uses the practice summary for court zero."""
        game = main.GameData(self.start_time, 0, 'Moon')
        self.assertEqual(game.summary(), 'Volleyball Practice @ Moon')

    def test_game_data_match_summary(self):
        """Uses the match summary for normal courts."""
        game = main.GameData(self.start_time, 4, 'Beat Street')
        self.assertEqual(game.summary(), 'Volleyball, Court 4 vs Beat Street')

    def test_game_data_practice_description(self):
        """Uses the practice description for court zero."""
        game = main.GameData(self.start_time, 0, 'Moon')
        self.assertEqual(game.description(), 'Volleyball Practice, rule of 10.')

    def test_game_data_match_description(self):
        """Uses the match description for normal courts."""
        game = main.GameData(self.start_time, 4, 'Beat Street')
        self.assertEqual(game.description(), 'Satellite Junkies vs Beat Street, on Court 4')

    def test_game_data_practice_address(self):
        """Maps court zero to the practice venue."""
        game = main.GameData(self.start_time, 0, 'Moon')
        self.assertEqual(game.address(), 'Moon Under Water, 152 Somerfield Street, Somerfield, Christchurch 8024')

    def test_game_data_pioneer_stadium_address(self):
        """Maps courts 1-6 to Pioneer Stadium."""
        game = main.GameData(self.start_time, 3, 'Team A')
        self.assertEqual(game.address(), 'Pioneer Stadium, 75 Lyttelton St, Somerfield, Christchurch 8024')

    def test_game_data_parakiore_address(self):
        """Maps other courts to Parakiore."""
        game = main.GameData(self.start_time, 10, 'Team B')
        self.assertEqual(game.address(), 'Parakiore, 50 Saint Asaph Street, Christchurch Central City, Christchurch 8011')

    def test_game_data_event_creation(self):
        """Builds a complete event payload with attendees."""
        game = main.GameData(self.start_time, 4, 'Beat Street')
        event = game.event(['player1@example.com'])

        self.assertEqual(event['summary'], 'Volleyball, Court 4 vs Beat Street')
        self.assertEqual(event['description'], 'Satellite Junkies vs Beat Street, on Court 4')
        self.assertEqual(event['location'], 'Pioneer Stadium, 75 Lyttelton St, Somerfield, Christchurch 8024')
        self.assertEqual(len(event['attendees']), 1)
        self.assertEqual(event['attendees'][0]['email'], 'player1@example.com')


class TestParsingFunctions(unittest.TestCase):
    """Tests for date/time and row parsing helpers."""

    def test_parse_datetime_local(self):
        """Parses PM date/time values correctly."""
        parsed = main.parse_datetime_local('23/04/2026', '8:30 PM')
        self.assertEqual(parsed.year, 2026)
        self.assertEqual(parsed.month, 4)
        self.assertEqual(parsed.day, 23)
        self.assertEqual(parsed.hour, 20)
        self.assertEqual(parsed.minute, 30)
        self.assertEqual(str(parsed.tzinfo), 'Pacific/Auckland')

    def test_parse_datetime_local_morning(self):
        """Parses AM date/time values correctly."""
        parsed = main.parse_datetime_local('23/04/2026', '9:15 AM')
        self.assertEqual(parsed.hour, 9)
        self.assertEqual(parsed.minute, 15)

    def test_parse_row_success(self):
        """Parses a valid row into GameData."""
        headers = ['Date', 'Time', 'Court', 'Opponent']
        row = ['23/04/2026', '8:30 PM', '0', 'Moon']
        result = main.parse_row(row, headers)

        self.assertIsInstance(result, main.GameData)
        self.assertEqual(result.start_time.day, 23)
        self.assertEqual(result.start_time.month, 4)
        self.assertEqual(result.start_time.year, 2026)
        self.assertEqual(result.court, 0)
        self.assertEqual(result.opponent, 'Moon')

    def test_parse_row_missing_column(self):
        """Raises when a required header is missing."""
        headers = ['Date', 'Time', 'Court']
        row = ['23/04/2026', '19:30', '0']
        with self.assertRaises(ValueError):
            main.parse_row(row, headers)

    def test_parse_row_incomplete_row(self):
        """Raises when row values are incomplete."""
        headers = ['Date', 'Time', 'Court', 'Opponent']
        row = ['23/04/2026', '19:30', '0']
        with self.assertRaises(ValueError):
            main.parse_row(row, headers)

    def test_parse_row_case_insensitive_headers(self):
        """Accepts lowercase header names."""
        headers = ['date', 'time', 'court', 'opponent']
        row = ['23/04/2026', '8:30 PM', '4', 'Beat Street']
        result = main.parse_row(row, headers)

        self.assertEqual(result.court, 4)
        self.assertEqual(result.opponent, 'Beat Street')


class TestAttendeeNormalization(unittest.TestCase):
    """Tests for attendee email normalization."""

    def test_normalize_empty_attendees(self):
        """Returns empty list for empty attendees."""
        result = main.normalize_attendees([])
        self.assertEqual(result, [])

    def test_normalize_none_attendees(self):
        """Returns empty list for None attendees."""
        result = main.normalize_attendees(None)
        self.assertEqual(result, [])

    def test_normalize_attendees_with_email(self):
        """Sorts attendee emails alphabetically."""
        attendees = [
            {'email': 'player2@example.com'},
            {'email': 'player1@example.com'},
        ]
        result = main.normalize_attendees(attendees)
        self.assertEqual(result, ['player1@example.com', 'player2@example.com'])

    def test_normalize_attendees_skip_missing_email(self):
        """Skips attendee entries missing email key."""
        attendees = [
            {'name': 'Player 1'},
            {'email': 'player2@example.com'},
        ]
        result = main.normalize_attendees(attendees)
        self.assertEqual(result, ['player2@example.com'])


class TestEventComparison(unittest.TestCase):
    """Tests for event comparison/update checks."""

    def setUp(self):
        """Create a shared timezone-aware start time."""
        self.start_time = datetime(2026, 4, 23, 20, 30, tzinfo=ZoneInfo('Pacific/Auckland'))

    def test_needs_update_no_changes(self):
        """Does not require update when payloads match."""
        existing = {
            'summary': 'Test Event',
            'description': 'Test Description',
            'location': 'Test Location',
            'start': {'dateTime': '2026-04-23T20:30:00'},
            'end': {'dateTime': '2026-04-23T21:30:00'},
            'attendees': [{'email': 'test@example.com'}]
        }
        new_body = existing.copy()
        self.assertFalse(main.needs_update(existing, new_body))

    def test_needs_update_summary_changed(self):
        """Requires update when summary changes."""
        existing = {'summary': 'Old Summary', 'description': 'Desc', 'location': 'Loc', 'start': {}, 'end': {}}
        new_body = {'summary': 'New Summary', 'description': 'Desc', 'location': 'Loc', 'start': {}, 'end': {}}
        self.assertTrue(main.needs_update(existing, new_body))

    def test_needs_update_attendees_changed(self):
        """Requires update when attendees differ."""
        existing = {
            'summary': 'Event',
            'description': 'Desc',
            'location': 'Loc',
            'start': {},
            'end': {},
            'attendees': [{'email': 'old@example.com'}]
        }
        new_body = {
            'summary': 'Event',
            'description': 'Desc',
            'location': 'Loc',
            'start': {},
            'end': {},
            'attendees': [{'email': 'new@example.com'}]
        }
        self.assertTrue(main.needs_update(existing, new_body))


if __name__ == '__main__':
    unittest.main()
