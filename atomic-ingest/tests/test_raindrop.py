import pytest
from unittest.mock import MagicMock, patch
from adapters.raindrop import classify_bookmark, format_notes_section, sync_raindrop
from lib.sync_state import SyncState
from lib.atomic_client import AtomicAPIError


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


class TestSyncRaindropFallback:
    @patch("adapters.raindrop.requests.get")
    def test_creates_fallback_atom_on_parse_error(self, mock_get, tmp_state_file):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "items": [{
                    "_id": 789,
                    "title": "Cool Homepage",
                    "link": "https://cool.io",
                    "excerpt": "A cool tool for developers.",
                    "domain": "cool.io",
                    "type": "link",
                    "tags": ["tools", "dev"],
                    "note": "",
                    "highlights": [],
                    "created": "2026-04-11T00:00:00Z",
                }],
            },
        )

        client = MagicMock()
        client.ingest_url.side_effect = AtomicAPIError(
            500, '{"error":"Ingestion error: Page is not article-shaped (failed readability check)"}',
        )
        client.create_atom.return_value = {"id": "uuid-fb"}

        state = SyncState(tmp_state_file)
        sync_raindrop(client, state, "test-token")

        client.create_atom.assert_called_once()
        call_kwargs = client.create_atom.call_args[1]
        assert "# Cool Homepage" in call_kwargs["content"]
        assert "**Source:** cool.io" in call_kwargs["content"]
        assert "**Tags:** tools, dev" in call_kwargs["content"]
        assert "## Summary" in call_kwargs["content"]
        assert "A cool tool for developers." in call_kwargs["content"]
        assert call_kwargs["source_url"] == "https://cool.io"
        assert call_kwargs["published_at"] == "2026-04-11T00:00:00Z"

    @patch("adapters.raindrop.requests.get")
    def test_skips_on_http_fetch_error(self, mock_get, tmp_state_file):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "items": [{
                    "_id": 790,
                    "title": "Dead Link",
                    "link": "https://dead.com",
                    "excerpt": "",
                    "domain": "dead.com",
                    "type": "link",
                    "tags": [],
                    "note": "",
                    "highlights": [],
                    "created": "2026-04-11T00:00:00Z",
                }],
            },
        )

        client = MagicMock()
        client.ingest_url.side_effect = AtomicAPIError(
            500, '{"error":"Ingestion error: HTTP 403 Forbidden for https://dead.com"}',
        )

        state = SyncState(tmp_state_file)
        sync_raindrop(client, state, "test-token")

        client.create_atom.assert_not_called()

    @patch("adapters.raindrop.requests.get")
    def test_fallback_for_annotated_url_still_enriches(self, mock_get, tmp_state_file):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "items": [{
                    "_id": 791,
                    "title": "Annotated Homepage",
                    "link": "https://annotated.io",
                    "excerpt": "Some description.",
                    "domain": "annotated.io",
                    "type": "link",
                    "tags": [],
                    "note": "My thoughts on this",
                    "highlights": [{"text": "Key quote"}],
                    "created": "2026-04-11T00:00:00Z",
                }],
            },
        )

        client = MagicMock()
        client.ingest_url.side_effect = AtomicAPIError(
            500, '{"error":"Ingestion error: Page is not article-shaped (failed readability check)"}',
        )
        client.create_atom.return_value = {"id": "uuid-fb2"}
        client.get_atom_by_source_url.return_value = {"id": "uuid-fb2", "content": "# Annotated Homepage\n\n**Source:** annotated.io\n\n## Summary\nSome description."}
        client.update_atom.return_value = {"id": "uuid-fb2"}

        state = SyncState(tmp_state_file)
        sync_raindrop(client, state, "test-token")

        # Fallback atom created
        client.create_atom.assert_called_once()
        # Then enriched with notes
        client.update_atom.assert_called_once()
        update_kwargs = client.update_atom.call_args[1]
        assert "## My Notes" in update_kwargs["content"]
        assert "My thoughts on this" in update_kwargs["content"]
