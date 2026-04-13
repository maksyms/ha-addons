import pytest
from unittest.mock import MagicMock, patch
from adapters.readwise import (
    format_highlights_atom,
    format_highlights_section,
    sync_highlights,
    sync_reader,
)
from lib.atomic_client import AtomicAPIError


class TestFormatHighlightsAtom:
    def test_formats_book_with_highlights(self):
        book = {
            "title": "Deep Work",
            "author": "Cal Newport",
            "highlights": [
                {"text": "Focus is a superpower.", "note": ""},
                {"text": "Depth over shallowness.", "note": "Great point"},
            ],
        }
        content = format_highlights_atom(book)
        assert content.startswith("# Deep Work\n\nby Cal Newport\n")
        assert "> Focus is a superpower." in content
        assert "> Depth over shallowness." in content
        assert "Great point" in content

    def test_handles_empty_author(self):
        book = {"title": "No Author", "author": None, "highlights": []}
        content = format_highlights_atom(book)
        assert content == "# No Author"

    def test_handles_highlight_with_note(self):
        book = {
            "title": "Test",
            "author": "Author",
            "highlights": [{"text": "Quote", "note": "My note"}],
        }
        content = format_highlights_atom(book)
        assert "> Quote" in content
        assert "My note" in content


class TestFormatHighlightsSection:
    def test_formats_highlights_for_reader_doc(self):
        highlights = [
            {"text": "Key insight", "note": ""},
            {"text": "Another point", "note": "Interesting"},
        ]
        section = format_highlights_section(highlights)
        assert section.startswith("\n\n## My Highlights\n")
        assert "> Key insight" in section
        assert "> Another point" in section
        assert "Interesting" in section

    def test_returns_empty_string_for_no_highlights(self):
        assert format_highlights_section([]) == ""


class TestSyncHighlights:
    @patch("adapters.readwise.requests.get")
    def test_creates_atom_for_new_book(self, mock_get, tmp_state_file):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "results": [{
                    "title": "Test Book",
                    "author": "Author",
                    "readable_title": "Test Book",
                    "source_url": "https://readwise.io/bookreview/123",
                    "last_highlight_at": "2026-04-11T00:00:00Z",
                    "highlights": [{"text": "Quote", "note": ""}],
                }],
                "nextPageCursor": None,
            },
        )

        client = MagicMock()
        client.get_atom_by_source_url.return_value = None
        client.create_atom.return_value = {"id": "uuid-1"}

        from lib.sync_state import SyncState
        state = SyncState(tmp_state_file)

        sync_highlights(client, state, "test-token")

        client.create_atom.assert_called_once()
        call_kwargs = client.create_atom.call_args[1]
        assert "# Test Book" in call_kwargs["content"]
        assert call_kwargs["source_url"] == "https://readwise.io/bookreview/123"

    @patch("adapters.readwise.requests.get")
    def test_updates_atom_for_existing_book(self, mock_get, tmp_state_file):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "results": [{
                    "title": "Test Book",
                    "author": "Author",
                    "readable_title": "Test Book",
                    "source_url": "https://readwise.io/bookreview/123",
                    "last_highlight_at": "2026-04-11T00:00:00Z",
                    "highlights": [{"text": "Quote", "note": ""}],
                }],
                "nextPageCursor": None,
            },
        )

        client = MagicMock()
        client.get_atom_by_source_url.return_value = {"id": "uuid-1", "content": "old"}
        client.update_atom.return_value = {"id": "uuid-1"}

        from lib.sync_state import SyncState
        state = SyncState(tmp_state_file)

        sync_highlights(client, state, "test-token")

        client.update_atom.assert_called_once()
        client.create_atom.assert_not_called()


class TestSyncReaderFallback:
    @patch("adapters.readwise.requests.get")
    def test_creates_fallback_atom_on_parse_error(self, mock_get, tmp_state_file):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "results": [{
                    "title": "Cool App",
                    "source_url": "https://cool.app",
                    "url": "https://cool.app",
                    "site_name": "cool.app",
                    "author": "Jane Dev",
                    "summary": "A productivity tool.",
                    "notes": "",
                    "published_date": "2026-04-11",
                    "highlights": [],
                }],
                "nextPageCursor": None,
            },
        )

        client = MagicMock()
        client.ingest_url.side_effect = AtomicAPIError(
            500, '{"error":"Ingestion error: Page is not article-shaped (failed readability check)"}',
        )
        client.create_atom.return_value = {"id": "uuid-fb"}

        from lib.sync_state import SyncState
        state = SyncState(tmp_state_file)

        sync_reader(client, state, "test-token")

        client.create_atom.assert_called_once()
        call_kwargs = client.create_atom.call_args[1]
        assert "# Cool App" in call_kwargs["content"]
        assert "**Source:** cool.app" in call_kwargs["content"]
        assert "**Author:** Jane Dev" in call_kwargs["content"]
        assert "A productivity tool." in call_kwargs["content"]
        assert call_kwargs["source_url"] == "https://cool.app"

    @patch("adapters.readwise.requests.get")
    def test_skips_on_http_fetch_error(self, mock_get, tmp_state_file):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "results": [{
                    "title": "Dead",
                    "source_url": "https://dead.com",
                    "url": "https://dead.com",
                    "site_name": "dead.com",
                    "author": "",
                    "summary": "",
                    "notes": "",
                    "published_date": "2026-04-11",
                    "highlights": [],
                }],
                "nextPageCursor": None,
            },
        )

        client = MagicMock()
        client.ingest_url.side_effect = AtomicAPIError(
            500, '{"error":"Ingestion error: HTTP 404 Not Found for https://dead.com"}',
        )

        from lib.sync_state import SyncState
        state = SyncState(tmp_state_file)

        sync_reader(client, state, "test-token")

        client.create_atom.assert_not_called()

    @patch("adapters.readwise.requests.get")
    def test_fallback_atom_gets_highlights_enriched(self, mock_get, tmp_state_file):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "results": [{
                    "title": "Annotated App",
                    "source_url": "https://annotated.app",
                    "url": "https://annotated.app",
                    "site_name": "annotated.app",
                    "author": "",
                    "summary": "Some app.",
                    "notes": "My thoughts",
                    "published_date": "2026-04-11",
                    "highlights": [{"text": "Key insight", "note": ""}],
                }],
                "nextPageCursor": None,
            },
        )

        client = MagicMock()
        client.ingest_url.side_effect = AtomicAPIError(
            500, '{"error":"Ingestion error: Page is not article-shaped (failed readability check)"}',
        )
        client.create_atom.return_value = {"id": "uuid-fb3"}
        client.get_atom_by_source_url.return_value = {
            "id": "uuid-fb3",
            "content": "# Annotated App\n\n**Source:** annotated.app\n\n## Summary\nSome app.",
        }
        client.update_atom.return_value = {"id": "uuid-fb3"}

        from lib.sync_state import SyncState
        state = SyncState(tmp_state_file)

        sync_reader(client, state, "test-token")

        client.create_atom.assert_called_once()
        client.update_atom.assert_called_once()
        update_kwargs = client.update_atom.call_args
        assert "## My Highlights" in update_kwargs[1]["content"]
