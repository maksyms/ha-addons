import json
import pytest
from unittest.mock import patch, MagicMock
from lib.atomic_client import AtomicClient, AtomicAPIError


@pytest.fixture
def client():
    return AtomicClient("http://atomic:8081", "at_test_token")


def _mock_response(status_code=200, json_data=None, headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.headers = headers or {}
    resp.text = json.dumps(json_data or {})
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from requests.exceptions import HTTPError
        resp.raise_for_status.side_effect = HTTPError(response=resp)
    return resp


class TestCreateAtom:
    @patch("lib.atomic_client.requests.Session.request")
    def test_creates_atom_with_content(self, mock_request, client):
        mock_request.return_value = _mock_response(201, {
            "id": "uuid-1", "content": "# Test", "title": "Test",
            "embedding_status": "pending",
        })

        result = client.create_atom("# Test\n\nBody text")

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        body = json.loads(call_args.kwargs.get("data", "{}"))
        assert body["content"] == "# Test\n\nBody text"
        assert body["skip_if_source_exists"] is True
        assert result["id"] == "uuid-1"

    @patch("lib.atomic_client.requests.Session.request")
    def test_creates_atom_with_all_fields(self, mock_request, client):
        mock_request.return_value = _mock_response(201, {"id": "uuid-2"})

        client.create_atom(
            "# Title",
            source_url="https://example.com",
            published_at="2026-04-11T00:00:00Z",
            tag_ids=["tag-1"],
        )

        body = json.loads(mock_request.call_args.kwargs.get("data", "{}"))
        assert body["source_url"] == "https://example.com"
        assert body["published_at"] == "2026-04-11T00:00:00Z"
        assert body["tag_ids"] == ["tag-1"]

    @patch("lib.atomic_client.requests.Session.request")
    def test_skipped_atom_returns_skipped(self, mock_request, client):
        mock_request.return_value = _mock_response(200, {"skipped": True})
        result = client.create_atom("# Dupe", source_url="https://dupe.com")
        assert result.get("skipped") is True


class TestBulkCreate:
    @patch("lib.atomic_client.requests.Session.request")
    def test_bulk_creates_atoms(self, mock_request, client):
        mock_request.return_value = _mock_response(201, {
            "atoms": [{"id": "1"}, {"id": "2"}], "count": 2, "skipped": 0,
        })

        atoms = [
            {"content": "# One", "source_url": "https://one.com"},
            {"content": "# Two", "source_url": "https://two.com"},
        ]
        result = client.create_atoms_bulk(atoms)
        assert result["count"] == 2

    @patch("lib.atomic_client.requests.Session.request")
    def test_bulk_chunks_at_1000(self, mock_request, client):
        mock_request.return_value = _mock_response(201, {
            "atoms": [], "count": 0, "skipped": 0,
        })

        atoms = [{"content": f"# Note {i}"} for i in range(1500)]
        client.create_atoms_bulk(atoms)

        assert mock_request.call_count == 2


class TestIngestUrl:
    @patch("lib.atomic_client.requests.Session.request")
    def test_ingests_url(self, mock_request, client):
        mock_request.return_value = _mock_response(200, {
            "atom_id": "uuid-1", "url": "https://example.com",
            "title": "Example", "content_length": 5000,
        })

        result = client.ingest_url("https://example.com")
        assert result["atom_id"] == "uuid-1"

        body = json.loads(mock_request.call_args.kwargs.get("data", "{}"))
        assert body["url"] == "https://example.com"


class TestGetAtomBySourceUrl:
    @patch("lib.atomic_client.requests.Session.request")
    def test_returns_atom_when_found(self, mock_request, client):
        mock_request.return_value = _mock_response(200, {
            "id": "uuid-1", "content": "# Found",
        })
        result = client.get_atom_by_source_url("https://example.com")
        assert result["id"] == "uuid-1"

    @patch("lib.atomic_client.requests.Session.request")
    def test_returns_none_when_not_found(self, mock_request, client):
        mock_request.return_value = _mock_response(404)
        result = client.get_atom_by_source_url("https://missing.com")
        assert result is None


class TestRetryBehavior:
    @patch("lib.atomic_client.time.sleep")
    @patch("lib.atomic_client.requests.Session.request")
    def test_retries_on_500(self, mock_request, mock_sleep, client):
        mock_request.side_effect = [
            _mock_response(500),
            _mock_response(200, {"status": "ok"}),
        ]
        result = client.health()
        assert result["status"] == "ok"
        assert mock_request.call_count == 2

    @patch("lib.atomic_client.requests.Session.request")
    def test_raises_on_401(self, mock_request, client):
        mock_request.return_value = _mock_response(401)
        with pytest.raises(AtomicAPIError):
            client.health()
