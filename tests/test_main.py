import datetime
import unittest
from email.message import EmailMessage
from unittest.mock import MagicMock, mock_open, patch

from imapclient.exceptions import IMAPClientError

from imapper import main as main_module


class TestObtainProfiles(unittest.TestCase):
    def test_obtain_profiles_loads_yaml(self):
        yaml_content = (
            "acc1:\n  server: imap.acc1.com\n  user: user1@acc1.com\n  password: pw1\n"
        )
        with patch("builtins.open", mock_open(read_data=yaml_content)) as mocked_file:
            main_module.obtain_profiles()
            mocked_file.assert_called_once_with(
                "./imapper-profiles.yaml", "r", encoding="utf-8"
            )
            self.assertEqual(
                main_module.profiles,
                {
                    "acc1": {
                        "server": "imap.acc1.com",
                        "user": "user1@acc1.com",
                        "password": "pw1",
                    }
                },
            )


class TestParseHeaderStr(unittest.TestCase):
    def test_empty_and_none(self):
        self.assertEqual(main_module.parse_header_str(None), "")
        self.assertEqual(main_module.parse_header_str(""), "")
        self.assertEqual(main_module.parse_header_str(b""), "")

    def test_plain_str_and_bytes(self):
        self.assertEqual(main_module.parse_header_str("plain text"), "plain text")
        self.assertEqual(main_module.parse_header_str(b"plain bytes"), "plain bytes")

    def test_mime_encoded_utf8_str_and_bytes(self):
        raw_str = "=?utf-8?B?44OG44K544OI?="
        raw_bytes = b"=?utf-8?B?44OG44K544OI?="
        self.assertEqual(main_module.parse_header_str(raw_str), "テスト")
        self.assertEqual(main_module.parse_header_str(raw_bytes), "テスト")

    def test_mime_encoded_iso2022jp_str_and_bytes(self):
        raw_str = "=?iso-2022-jp?B?GyRCJUYlOSVIGyhC?="
        raw_bytes = b"=?iso-2022-jp?B?GyRCJUYlOSVIGyhC?="
        self.assertEqual(main_module.parse_header_str(raw_str), "テスト")
        self.assertEqual(main_module.parse_header_str(raw_bytes), "テスト")

    def test_raw_utf8_and_iso2022jp_bytes(self):
        utf8_bytes = "日本語件名".encode()
        iso2022jp_bytes = "日本語件名".encode("iso-2022-jp")
        self.assertEqual(main_module.parse_header_str(utf8_bytes), "日本語件名")
        self.assertEqual(main_module.parse_header_str(iso2022jp_bytes), "日本語件名")

    def test_unknown_charset_and_invalid_bytes_fallback(self):
        raw = "=?unknown-charset?B?44OG44K544OI?="
        self.assertEqual(main_module.parse_header_str(raw), "テスト")
        invalid_bytes = b"\xff\xfe"
        self.assertEqual(main_module.parse_header_str(invalid_bytes), "\ufffd\ufffd")

    def test_mixed_mime_and_plain_fragments(self):
        # Mixed encoded and unencoded parts make decode_header return (bytes, charset) and (bytes, None)
        raw = "=?utf-8?B?5bGx55Sw?= Tarou"
        self.assertEqual(main_module.parse_header_str(raw), "山田 Tarou")


class TestCrawl(unittest.TestCase):
    def setUp(self):
        main_module.profiles = {
            "test_account": {
                "server": "imap.test.com",
                "user": "test@test.com",
                "password": "password",
            }
        }

    @patch("imapper.main.IMAPClient")
    def test_crawl_displays_id_and_formats_sender(self, mock_imap_cls):
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

            table_calls = [
                arg
                for call in mock_print.call_args_list
                for arg in call[0]
                if hasattr(arg, "columns")
            ]
            self.assertEqual(len(table_calls), 1)
            table = table_calls[0]
            column_headers = [col.header for col in table.columns]
            self.assertEqual(column_headers, ["ID", "Subject", "Sender", "Date"])
            self.assertEqual(table.columns[0]._cells, ["42"])
            self.assertEqual(table.columns[1]._cells, ["Test Subject"])
            self.assertEqual(table.columns[2]._cells, ["Tester <tester@example.com>"])
            self.assertEqual(table.columns[3]._cells, ["2026-11-04 12:00:00"])

    @patch("imapper.main.IMAPClient")
    def test_crawl_sender_and_subject_variants(self, mock_imap_cls):
        mock_client = MagicMock()
        mock_imap_cls.return_value = mock_client
        mock_client.search.side_effect = [[1, 2, 3], [1, 2, 3]]

        # Msg 1: No subject, no sender name (only email)
        env1 = MagicMock()
        env1.date = datetime.datetime(2026, 11, 4, 10, 0, 0)
        env1.subject = None
        from1 = MagicMock()
        from1.name = None
        from1.mailbox = b"noname"
        from1.host = b"example.com"
        env1.from_ = [from1]

        # Msg 2: Empty from_ list, UTF-8 MIME subject
        env2 = MagicMock()
        env2.date = datetime.datetime(2026, 11, 4, 11, 0, 0)
        env2.subject = b"=?utf-8?B?44OG44K544OI5LqM?="
        env2.from_ = []

        # Msg 3: Sender without mailbox/host, ISO-2022-JP MIME subject
        env3 = MagicMock()
        env3.date = datetime.datetime(2026, 11, 4, 12, 0, 0)
        env3.subject = b"=?iso-2022-jp?B?GyRCJUYlOSVIGyhC?="
        from3 = MagicMock()
        from3.name = None
        from3.mailbox = None
        from3.host = None
        env3.from_ = [from3]

        mock_client.fetch.return_value = {
            1: {b"ENVELOPE": env1},
            2: {b"ENVELOPE": env2},
            3: {b"ENVELOPE": env3},
        }

        with patch.object(main_module.console, "print") as mock_print:
            main_module.crawl(days_delta=3)

            table = next(
                arg
                for call in mock_print.call_args_list
                for arg in call[0]
                if hasattr(arg, "columns")
            )
            self.assertEqual(
                table.columns[1]._cells, ["(No Subject)", "テスト二", "テスト"]
            )
            self.assertEqual(
                table.columns[2]._cells,
                ["noname@example.com", "(No sender)", ""],
            )

    @patch("imapper.main.IMAPClient")
    def test_crawl_no_messages(self, mock_imap_cls):
        mock_client = MagicMock()
        mock_imap_cls.return_value = mock_client
        mock_client.search.side_effect = [[], []]

        with patch.object(main_module.console, "print"):
            main_module.crawl(days_delta=1)
            mock_client.fetch.assert_not_called()

    @patch("imapper.main.IMAPClient")
    def test_crawl_explicit_standard_mode(self, mock_imap_cls):
        main_module.profiles["test_account"]["mode"] = "standard"
        mock_client = MagicMock()
        mock_imap_cls.return_value = mock_client
        mock_client.search.side_effect = [[], []]

        with patch.object(main_module.console, "print"):
            main_module.crawl(days_delta=1)
            mock_client.login.assert_called_once_with("test@test.com", "password")

    @patch("imapper.main.IMAPClient")
    def test_crawl_illegal_login_mode(self, mock_imap_cls):
        main_module.profiles["test_account"]["mode"] = "oauth"
        mock_client = MagicMock()
        mock_imap_cls.return_value = mock_client

        with patch.object(main_module.console, "print") as mock_print:
            main_module.crawl(days_delta=1)
            mock_client.login.assert_not_called()
            mock_client.select_folder.assert_not_called()
            printed = [str(call[0][0]) for call in mock_print.call_args_list]
            self.assertIn("Illegal login mode", printed)


class TestExtractBody(unittest.TestCase):
    def test_extract_body_plain(self):
        msg = EmailMessage()
        msg.set_content("Hello Plain World")
        self.assertEqual(main_module.extract_body(msg).strip(), "Hello Plain World")

    def test_extract_body_get_content_exception_fallback(self):
        mock_msg = MagicMock(spec=EmailMessage)
        mock_body_part = MagicMock()
        mock_body_part.get_content.side_effect = LookupError("unknown encoding")
        mock_body_part.get_payload.return_value = b"fallback payload"
        mock_msg.get_body.return_value = mock_body_part

        result = main_module.extract_body(mock_msg)
        self.assertEqual(result, "b'fallback payload'")

    def test_extract_body_multipart_fallback_with_text_and_attachment(self):
        mock_msg = MagicMock(spec=EmailMessage)
        mock_msg.get_body.return_value = None
        mock_msg.is_multipart.return_value = True

        part_text = MagicMock()
        part_text.get_content_type.return_value = "text/plain"
        part_text.get.return_value = "inline"
        part_text.get_payload.return_value = "テキスト本文".encode()
        part_text.get_content_charset.return_value = "utf-8"

        part_attachment = MagicMock()
        part_attachment.get_content_type.return_value = "text/plain"
        part_attachment.get.return_value = "attachment; filename=test.txt"
        part_attachment.get_payload.return_value = b"attachment text"

        mock_msg.walk.return_value = [part_text, part_attachment]

        self.assertEqual(main_module.extract_body(mock_msg), "テキスト本文")

    def test_extract_body_multipart_fallback_no_readable_body(self):
        mock_msg = MagicMock(spec=EmailMessage)
        mock_msg.get_body.return_value = None
        mock_msg.is_multipart.return_value = True
        mock_msg.walk.return_value = []

        self.assertEqual(main_module.extract_body(mock_msg), "(No readable body)")

    def test_extract_body_singlepart_fallback_with_payload(self):
        mock_msg = MagicMock(spec=EmailMessage)
        mock_msg.get_body.return_value = None
        mock_msg.is_multipart.return_value = False
        mock_msg.get_payload.return_value = b"Singlepart fallback"
        mock_msg.get_content_charset.return_value = "utf-8"

        self.assertEqual(main_module.extract_body(mock_msg), "Singlepart fallback")

    def test_extract_body_singlepart_fallback_empty_decoded_payload(self):
        mock_msg = MagicMock(spec=EmailMessage)
        mock_msg.get_body.return_value = None
        mock_msg.is_multipart.return_value = False
        mock_msg.get_payload.side_effect = [None, "raw string payload"]

        self.assertEqual(main_module.extract_body(mock_msg), "raw string payload")


class TestReadMail(unittest.TestCase):
    def setUp(self):
        main_module.profiles = {
            "test_account": {
                "server": "imap.test.com",
                "user": "test@test.com",
                "password": "password",
            }
        }

    @patch("imapper.main.IMAPClient")
    def test_read_mail_found_via_rfc822(self, mock_imap_cls):
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
    def test_read_mail_found_via_body_with_specific_account(self, mock_imap_cls):
        main_module.profiles["test_account"]["mode"] = "standard"
        mock_client = MagicMock()
        mock_imap_cls.return_value = mock_client

        # Minimal message without headers to test fallback defaults
        raw_body = b"\r\nMinimal body"
        mock_client.fetch.return_value = {10: {b"BODY[]": raw_body}}

        with patch.object(main_module.console, "print") as mock_print:
            success = main_module.read_mail("10", account="test_account")
            self.assertTrue(success)
            panel_renderables = [
                str(getattr(arg, "renderable", arg))
                for call in mock_print.call_args_list
                for arg in call[0]
            ]
            self.assertTrue(any("(No Subject)" in text for text in panel_renderables))
            self.assertTrue(any("(No sender)" in text for text in panel_renderables))
            self.assertTrue(any("(No recipient)" in text for text in panel_renderables))
            self.assertTrue(any("(No date)" in text for text in panel_renderables))

    @patch("imapper.main.IMAPClient")
    def test_read_mail_not_found(self, mock_imap_cls):
        mock_client = MagicMock()
        mock_imap_cls.return_value = mock_client
        mock_client.fetch.return_value = {}

        with patch.object(main_module.console, "print"):
            success = main_module.read_mail("999")
            self.assertFalse(success)

    @patch("imapper.main.IMAPClient")
    def test_read_mail_empty_raw_bytes(self, mock_imap_cls):
        mock_client = MagicMock()
        mock_imap_cls.return_value = mock_client
        mock_client.fetch.return_value = {42: {b"FLAGS": (b"\\Seen",)}}

        with patch.object(main_module.console, "print"):
            success = main_module.read_mail("42")
            self.assertFalse(success)

    def test_read_mail_invalid_id(self):
        with patch.object(main_module.console, "print"):
            success = main_module.read_mail("invalid_id")
            self.assertFalse(success)

    def test_read_mail_unknown_account(self):
        with patch.object(main_module.console, "print"):
            success = main_module.read_mail("42", account="nonexistent")
            self.assertFalse(success)

    @patch("imapper.main.IMAPClient")
    def test_read_mail_illegal_login_mode(self, mock_imap_cls):
        main_module.profiles["test_account"]["mode"] = "illegal"
        mock_client = MagicMock()
        mock_imap_cls.return_value = mock_client

        with patch.object(main_module.console, "print") as mock_print:
            success = main_module.read_mail("42")
            self.assertFalse(success)
            printed = [str(call[0][0]) for call in mock_print.call_args_list]
            self.assertIn("Illegal login mode", printed)

    @patch("imapper.main.IMAPClient")
    def test_read_mail_handles_imap_error_and_continues(self, mock_imap_cls):
        main_module.profiles = {
            "broken_account": {
                "server": "imap.broken.com",
                "user": "u1",
                "password": "p1",
            },
            "working_account": {
                "server": "imap.working.com",
                "user": "u2",
                "password": "p2",
            },
        }
        broken_client = MagicMock()
        broken_client.login.side_effect = IMAPClientError("Auth failed")

        working_client = MagicMock()
        working_client.fetch.return_value = {
            42: {b"BODY[]": b"Subject: Found\r\n\r\nBody"}
        }

        mock_imap_cls.side_effect = [broken_client, working_client]

        with patch.object(main_module.console, "print"):
            success = main_module.read_mail("42")
            self.assertTrue(success)


class TestMainCLI(unittest.TestCase):
    @patch("imapper.main.crawl")
    @patch("imapper.main.obtain_profiles")
    @patch("imapper.main.load_dotenv")
    def test_main_crawl_default_and_custom_days(
        self, mock_dotenv, mock_obtain, mock_crawl
    ):
        with patch("sys.argv", ["imapper", "crawl"]):
            main_module.main()
            mock_dotenv.assert_called_once()
            mock_obtain.assert_called_once()
            mock_crawl.assert_called_once_with(1)

        mock_crawl.reset_mock()
        with patch("sys.argv", ["imapper", "crawl", "--days-delta", "7"]):
            main_module.main()
            mock_crawl.assert_called_once_with(7)

    @patch("imapper.main.read_mail")
    @patch("imapper.main.obtain_profiles")
    @patch("imapper.main.load_dotenv")
    def test_main_read_command(self, mock_dotenv, mock_obtain, mock_read):
        with patch("sys.argv", ["imapper", "read", "42"]):
            main_module.main()
            mock_read.assert_called_once_with("42", None)

        mock_read.reset_mock()
        with patch("sys.argv", ["imapper", "read", "42", "--account", "acc1"]):
            main_module.main()
            mock_read.assert_called_once_with("42", "acc1")

    @patch("imapper.main.obtain_profiles")
    @patch("imapper.main.load_dotenv")
    def test_main_missing_subcommand_exits(self, mock_dotenv, mock_obtain):
        with (
            patch("sys.argv", ["imapper"]),
            patch("sys.stderr"),
            self.assertRaises(SystemExit),
        ):
            main_module.main()


if __name__ == "__main__":
    unittest.main()
