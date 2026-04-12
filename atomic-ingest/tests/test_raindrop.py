import pytest
from unittest.mock import MagicMock, patch
from adapters.raindrop import classify_bookmark, format_notes_section, sync_raindrop
from lib.sync_state import SyncState


class TestClassifyBookmark:
    def test_url_without_annotations(self):
        bm = {"link": "https://example.com", "note": "", "highlights": [], "type": "link"}
        assert classify_bookmark(bm) == "url_clean"

    def test_url_with_note(self):
        bm = {"link": "https://example.com", "note": "Good read", "highlights": [], "type": "link"}
        assert classify_bookmark(bm) == "url_annotated"

    def test_url_with_highlights(self):
        bm = {"link": "https://example.com", "note": "", "highlights": [{"text": "key"}], "type": "link"}
        assert classify_bookmark(bm) == "url_annotated"

    def test_uploaded_file(self):
        bm = {"link": "", "note": "My file", "highlights": [], "type": "document"}
        assert classify_bookmark(bm) == "uploaded"

    def test_empty_link_is_uploaded(self):
        bm = {"link": "", "note": "", "highlights": [], "type": "link"}
        assert classify_bookmark(bm) == "uploaded"


class TestFormatNotesSection:
    def test_formats_note_and_highlights(self):
        section = format_notes_section("My note", [{"text": "Key point"}])
        assert "## My Notes" in section
        assert "My note" in section
        assert "> Key point" in section

    def test_note_only(self):
        section = format_notes_section("Just a note", [])
        assert "## My Notes" in section
        assert "Just a note" in section

    def test_highlights_only(self):
        section = format_notes_section("", [{"text": "Quote"}])
        assert "## My Notes" in section
        assert "> Quote" in section

    def test_empty_returns_empty(self):
        assert format_notes_section("", []) == ""


class TestSyncRaindrop:
    @patch("adapters.raindrop.requests.get")
    def test_ingests_url_bookmark(self, mock_get, tmp_state_file):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "items": [{
                    "_id": 123,
                    "title": "Example",
                    "link": "https://example.com",
                    "excerpt": "An example",
                    "note": "",
                    "highlights": [],
                    "type": "link",
                    "created": "2026-04-11T00:00:00Z",
                }],
            },
        )

        client = MagicMock()
        client.ingest_url.return_value = {"atom_id": "uuid-1"}

        from lib.sync_state import SyncState
        state = SyncState(tmp_state_file)

        sync_raindrop(client, state, "test-token")

        client.ingest_url.assert_called_once_with(
            url="https://example.com",
            published_at="2026-04-11T00:00:00Z",
        )

    @patch("adapters.raindrop.requests.get")
    def test_creates_atom_for_uploaded_file(self, mock_get, tmp_state_file):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "items": [{
                    "_id": 456,
                    "title": "My Document",
                    "link": "",
                    "excerpt": "",
                    "note": "Important file",
                    "highlights": [],
                    "type": "document",
                    "created": "2026-04-11T00:00:00Z",
                }],
            },
        )

        client = MagicMock()
        client.create_atom.return_value = {"id": "uuid-2"}

        from lib.sync_state import SyncState
        state = SyncState(tmp_state_file)

        sync_raindrop(client, state, "test-token")

        client.create_atom.assert_called_once()
        call_kwargs = client.create_atom.call_args[1]
        assert "# My Document" in call_kwargs["content"]
        client.ingest_url.assert_not_called()

    @patch("adapters.raindrop.time.sleep")
    @patch("adapters.raindrop.requests.get")
    def test_handles_rate_limit(self, mock_get, mock_sleep, tmp_state_file):
        rate_limit_resp = MagicMock(
            status_code=429, headers={"Retry-After": "5"},
        )
        ok_resp = MagicMock(
            status_code=200,
            json=lambda: {
                "items": [{
                    "_id": 123,
                    "title": "Example",
                    "link": "https://example.com",
                    "note": "",
                    "highlights": [],
                    "created": "2026-04-11T00:00:00Z",
                }],
            },
        )
        mock_get.side_effect = [rate_limit_resp, ok_resp]

        client = MagicMock()
        client.ingest_url.return_value = {"atom_id": "uuid-1"}

        state = SyncState(tmp_state_file)
        sync_raindrop(client, state, "test-token")

        mock_sleep.assert_called_once_with(5)
        client.ingest_url.assert_called_once()

    @patch("adapters.raindrop.get_limit", return_value=1)
    @patch("adapters.raindrop.requests.get")
    def test_respects_ingest_limit(self, mock_get, mock_limit, tmp_state_file):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "items": [
                    {"_id": 1, "title": "First", "link": "https://first.com",
                     "note": "", "highlights": [], "created": "2026-04-11T00:00:00Z"},
                    {"_id": 2, "title": "Second", "link": "https://second.com",
                     "note": "", "highlights": [], "created": "2026-04-11T00:00:00Z"},
                ],
            },
        )

        client = MagicMock()
        client.ingest_url.return_value = {"atom_id": "uuid-1"}

        state = SyncState(tmp_state_file)
        sync_raindrop(client, state, "test-token")

        # Only first item should be processed
        assert client.ingest_url.call_count == 1
        # Sync state should not be updated (limit active)
        assert state.get("raindrop") == {}

    @patch("adapters.raindrop.get_limit", return_value=None)
    @patch("adapters.raindrop.requests.get")
    def test_updates_sync_state_without_limit(self, mock_get, mock_limit, tmp_state_file):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "items": [{
                    "_id": 1, "title": "Example", "link": "https://example.com",
                    "note": "", "highlights": [], "created": "2026-04-11T00:00:00Z",
                }],
            },
        )

        client = MagicMock()
        client.ingest_url.return_value = {"atom_id": "uuid-1"}

        state = SyncState(tmp_state_file)
        sync_raindrop(client, state, "test-token")

        # Sync state should be updated
        assert state.get("raindrop").get("last_sync_date") is not None
