import datetime
import unittest
from unittest.mock import MagicMock, patch

from imapper import main as main_module


class TestImapper(unittest.TestCase):
    def setUp(self):
        main_module.profiles = {
            "test_account": {
                "server": "imap.test.com",
                "user": "test@test.com",
                "password": "password",
            }
        }

    def test_parse_header_str(self):
        raw = "=?utf-8?B?44OG44K544OI?="
        self.assertEqual(main_module.parse_header_str(raw), "テスト")
        self.assertEqual(main_module.parse_header_str(None), "")
        self.assertEqual(main_module.parse_header_str("plain text"), "plain text")

    @patch("imapper.main.IMAPClient")
    def test_crawl_displays_id(self, mock_imap_cls):
        mock_client = MagicMock()
        mock_imap_cls.return_value = mock_client
        mock_client.search.side_effect = [[42], [42]]

        envelope_mock = MagicMock()
        envelope_mock.date = datetime.datetime(2026, 11, 4, 12, 0, 0)
        envelope_mock.subject = b"Test Subject"
        envelope_from = MagicMock()
        envelope_from.name = "Tester"
        envelope_from.mailbox = b"tester"
        envelope_from.host = b"example.com"
        envelope_mock.from_ = [envelope_from]

        mock_client.fetch.return_value = {42: {b"ENVELOPE": envelope_mock}}

        with patch.object(main_module.console, "print") as mock_print:
            main_module.crawl(days_delta=1)

            # Check that a Table was printed and has 4 columns: ID, Subject, Sender, Date
            table_calls = [
                arg
                for call in mock_print.call_args_list
                for arg in call[0]
                if hasattr(arg, "columns")
            ]
            self.assertTrue(len(table_calls) > 0)
            table = table_calls[0]
            column_headers = [col.header for col in table.columns]
            self.assertEqual(column_headers, ["ID", "Subject", "Sender", "Date"])

    @patch("imapper.main.IMAPClient")
    def test_read_mail_found(self, mock_imap_cls):
        mock_client = MagicMock()
        mock_imap_cls.return_value = mock_client

        raw_rfc822 = (
            b"From: sender@example.com\r\n"
            b"To: recipient@example.com\r\n"
            b"Subject: Test Subject\r\n"
            b"Date: Wed, 4 Nov 2026 12:00:00 +0000\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n"
            b"\r\n"
            b"Test Body Message"
        )
        mock_client.fetch.return_value = {42: {b"RFC822": raw_rfc822}}

        with patch.object(main_module.console, "print") as mock_print:
            success = main_module.read_mail("42")
            self.assertTrue(success)
            panel_renderables = [
                str(getattr(arg, "renderable", arg))
                for call in mock_print.call_args_list
                for arg in call[0]
            ]
            self.assertTrue(any("42" in text for text in panel_renderables))
            self.assertTrue(any("Test Subject" in text for text in panel_renderables))
            self.assertTrue(
                any("Test Body Message" in text for text in panel_renderables)
            )

    @patch("imapper.main.IMAPClient")
    def test_read_mail_not_found(self, mock_imap_cls):
        mock_client = MagicMock()
        mock_imap_cls.return_value = mock_client
        mock_client.fetch.return_value = {}

        with patch.object(main_module.console, "print"):
            success = main_module.read_mail("999")
            self.assertFalse(success)

    def test_read_mail_invalid_id(self):
        with patch.object(main_module.console, "print"):
            success = main_module.read_mail("invalid_id")
            self.assertFalse(success)

    def test_read_mail_unknown_account(self):
        with patch.object(main_module.console, "print"):
            success = main_module.read_mail("42", account="nonexistent")
            self.assertFalse(success)


if __name__ == "__main__":
    unittest.main()
