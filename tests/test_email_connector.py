"""Gmail message parsing and draft encoding, with a fake Gmail service."""
import base64
import email
import email.policy
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from email_agent import email_connector as connector


def encoded(text):
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def message(**payload):
    return {"id": "m1", "threadId": "t1", "snippet": "s", "labelIds": ["INBOX"], "payload": payload}


class ParsingTests(unittest.TestCase):
    def test_clean_body_hides_links_and_squeezes_whitespace(self):
        text = "Ciao\xa0 \t Mario\r\nvedi https://example.com/x?y=1\n\n\n\nfine​"
        self.assertEqual(connector.clean_email_body(text), "Ciao Mario\nvedi [URL]\n\nfine")
        self.assertEqual(connector.clean_email_body(""), "")

    def test_decode_accepts_missing_padding_and_bad_bytes(self):
        self.assertEqual(connector._decode_part(encoded("àè")), "àè")
        self.assertEqual(connector._decode_part(""), "")
        self.assertIn("�", connector._decode_part(base64.urlsafe_b64encode(b"\xff").decode()))

    def test_body_prefers_the_first_plain_text_part_in_nested_multipart(self):
        payload = {"mimeType": "multipart/mixed", "parts": [
            {"mimeType": "text/html", "body": {"data": encoded("<b>html</b>")}},
            {"mimeType": "multipart/alternative", "parts": [
                {"mimeType": "text/plain", "body": {"data": encoded("testo")}}]},
        ]}
        self.assertEqual(connector.extract_body(payload), "testo")

    def test_normalize_uses_case_insensitive_headers_and_defaults(self):
        full = message(mimeType="text/plain", body={"data": encoded("x" * 50)},
                       headers=[{"name": "FROM", "value": "a@b.it"}, {"name": "date", "value": "Mon, 16 Nov 2026 10:00:00 +0100"}])
        with patch.object(connector, "MAX_EMAIL_BODY_CHARS", 10):
            data = connector.normalize_message(full)
        self.assertEqual((data["from"], data["to"], data["subject"]), ("a@b.it", "", "No Subject"))
        self.assertEqual(data["date"], "2026-11-16T10:00:00+01:00")
        self.assertEqual(data["body"], "x" * 10)
        self.assertEqual((data["id"], data["thread_id"], data["label_ids"]), ("m1", "t1", ["INBOX"]))

    def test_unparseable_date_is_kept_as_received(self):
        data = connector.normalize_message(message(headers=[{"name": "Date", "value": "ieri"}]))
        self.assertEqual(data["date"], "ieri")
        self.assertEqual(data["from"], "Unknown")


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = MagicMock()
        messages = self.service.users.return_value.messages.return_value
        messages.list.return_value.execute.return_value = {"messages": [{"id": "a"}, {"id": "b"}]}
        messages.get.return_value.execute.side_effect = lambda: message(headers=[])
        self.messages = messages
        target = patch.object(connector, "get_gmail_service", return_value=self.service)
        target.start()
        self.addCleanup(target.stop)

    def test_search_clamps_the_page_size_and_fetches_each_message(self):
        self.assertEqual(len(connector.search_messages("", max_results=500)), 2)
        self.assertEqual(self.messages.list.call_args.kwargs, {"userId": "me", "q": None, "maxResults": 100})
        connector.search_messages("x", max_results=0)
        self.assertEqual(self.messages.list.call_args.kwargs["maxResults"], 1)
        self.assertEqual(self.messages.get.call_args.kwargs["format"], "full")

    def test_day_query_covers_exactly_one_day(self):
        connector.messages_for_day(date(2026, 12, 31))
        self.assertEqual(self.messages.list.call_args.kwargs["q"], "after:2026/12/31 before:2027/01/01")

    def test_get_message_requires_an_id(self):
        with self.assertRaises(ValueError):
            connector.get_message("  ")
        connector.get_message(" m1 ")
        self.assertEqual(self.messages.get.call_args.kwargs["id"], "m1")

    def test_draft_is_saved_never_sent(self):
        drafts = self.service.users.return_value.drafts.return_value
        drafts.create.return_value.execute.return_value = {"id": "d1"}
        self.assertEqual(connector.save_as_draft("c@d.it", "Preventivo", "Testo città"), {"id": "d1"})
        raw = drafts.create.call_args.kwargs["body"]["message"]["raw"]
        parsed = email.message_from_bytes(base64.urlsafe_b64decode(raw), policy=email.policy.default)
        self.assertEqual((parsed["To"], parsed["Subject"]), ("c@d.it", "Preventivo"))
        self.assertIn("Testo città", parsed.get_content())
        self.service.users.return_value.messages.return_value.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
