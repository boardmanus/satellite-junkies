import json
import sys
import unittest
from unittest import mock
from datetime import datetime

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


class TestMain(unittest.TestCase):
    def test_load_config_success(self):
        config_data = {'spreadsheet_id': 'abc', 'calendar_id': 'primary'}
        with mock.patch('main.os.path.exists', return_value=True), \
             mock.patch('builtins.open', mock.mock_open(read_data=json.dumps(config_data))):
            config = main.load_config()

        self.assertEqual(config['spreadsheet_id'], 'abc')
        self.assertEqual(config['calendar_id'], 'primary')
        self.assertEqual(config['sheet_range'], 'Sheet1!A:Z')

    def test_load_config_missing_file(self):
        with mock.patch('main.os.path.exists', return_value=False):
            with self.assertRaises(FileNotFoundError):
                main.load_config()

    def test_load_config_missing_keys(self):
        config_data = {'spreadsheet_id': 'abc'}
        with mock.patch('main.os.path.exists', return_value=True), \
             mock.patch('builtins.open', mock.mock_open(read_data=json.dumps(config_data))):
            with self.assertRaises(KeyError):
                main.load_config()

    def test_parse_row_success(self):
        headers = ['Date', 'Time', 'Court', 'Opponent']
        row = ['23/04/2026', '8:30 PM', '0', 'Moon']
        result = main.parse_row(row, headers)

        self.assertEqual(result['date'], '23/04/2026')
        self.assertEqual(result['time'], '8:30 PM')
        self.assertEqual(result['court'], '0')
        self.assertEqual(result['opponent'], 'Moon')

    def test_parse_row_missing_column(self):
        headers = ['Date', 'Time', 'Court']
        row = ['23/04/2026', '19:30', '0']
        with self.assertRaises(ValueError):
            main.parse_row(row, headers)

    def test_parse_row_incomplete_row(self):
        headers = ['Date', 'Time', 'Court', 'Opponent']
        row = ['23/04/2026', '19:30', '0']
        result = main.parse_row(row, headers)
        self.assertIsNone(result)

    def test_parse_datetime_local(self):
        parsed = main.parse_datetime_local('23/04/2026', '8:30 PM')
        self.assertEqual(parsed.year, 2026)
        self.assertEqual(parsed.month, 4)
        self.assertEqual(parsed.day, 23)
        self.assertEqual(parsed.hour, 20)
        self.assertEqual(parsed.minute, 30)

    def test_build_event_summary_and_description(self):
        game_data = {'court': '4', 'opponent': 'Beat Street'}
        self.assertEqual(main.build_event_summary(game_data['court'], game_data['opponent']), 'Court 4, Beat Street')
        self.assertEqual(main.build_event_description(game_data['court'], game_data['opponent']), 'Satellite Junkies vs Beat Street, on Court 4')

    def test_create_or_update_event_creates_new_event(self):
        calendar_service = mock.Mock()
        calendar_service.events.return_value.list.return_value.execute.return_value = {'items': []}
        calendar_service.events.return_value.insert.return_value.execute.return_value = {'id': 'new-event'}

        game_data = {'date': '23/04/2026', 'time': '8:30 PM', 'court': '0', 'opponent': 'Moon'}
        main.create_or_update_event(calendar_service, 'primary', game_data)

        calendar_service.events.return_value.insert.assert_called_once()
        calendar_service.events.return_value.update.assert_not_called()

    def test_create_or_update_event_updates_existing_event(self):
        calendar_service = mock.Mock()
        existing_event = {'id': 'existing'}
        calendar_service.events.return_value.list.return_value.execute.return_value = {'items': [existing_event]}
        calendar_service.events.return_value.update.return_value.execute.return_value = {'id': 'existing'}

        game_data = {'date': '23/04/2026', 'time': '8:30 PM', 'court': '0', 'opponent': 'Moon'}
        main.create_or_update_event(calendar_service, 'primary', game_data)

        calendar_service.events.return_value.update.assert_called_once()
        calendar_service.events.return_value.insert.assert_not_called()


if __name__ == '__main__':
    unittest.main()
