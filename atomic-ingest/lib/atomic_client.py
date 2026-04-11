import json
import time
import logging
import requests
from typing import Any

logger = logging.getLogger(__name__)

BULK_CHUNK_SIZE = 1000
MAX_RETRIES = 3
RETRY_BACKOFF = [1, 3, 10]


class AtomicAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Atomic API error {status_code}: {message}")


class AtomicClient:
    """Atomic knowledge base REST API client.

    Ingestion-related methods are fully implemented.
    Other methods raise NotImplementedError (stubs for future use).
    """

    def __init__(self, base_url: str, api_token: str):
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        })

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Make an HTTP request with retry logic.

        Retries on 5xx and network errors. Raises AtomicAPIError on 4xx.
        """
        url = f"{self._base_url}{path}"
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                resp = self._session.request(method, url, **kwargs)

                if resp.status_code < 400:
                    return resp

                if resp.status_code >= 500 and attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF[attempt]
                    logger.warning(
                        "Atomic API %s %s returned %d, retrying in %ds",
                        method, path, resp.status_code, wait,
                    )
                    time.sleep(wait)
                    last_error = AtomicAPIError(resp.status_code, resp.text)
                    continue

                raise AtomicAPIError(resp.status_code, resp.text)

            except requests.exceptions.RequestException as e:
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF[attempt]
                    logger.warning(
                        "Atomic API %s %s network error: %s, retrying in %ds",
                        method, path, e, wait,
                    )
                    time.sleep(wait)
                    last_error = e
                    continue
                raise

        raise last_error

    # --- Ingestion (implemented) ---

    def create_atom(
        self,
        content: str,
        source_url: str | None = None,
        published_at: str | None = None,
        tag_ids: list[str] | None = None,
    ) -> dict:
        """Create a single atom. Returns atom dict or {"skipped": True}."""
        body: dict[str, Any] = {
            "content": content,
            "skip_if_source_exists": True,
        }
        if source_url is not None:
            body["source_url"] = source_url
        if published_at is not None:
            body["published_at"] = published_at
        if tag_ids is not None:
            body["tag_ids"] = tag_ids

        resp = self._request("POST", "/api/atoms", data=json.dumps(body))
        return resp.json()

    def create_atoms_bulk(self, atoms: list[dict]) -> dict:
        """Bulk create atoms. Auto-chunks into batches of 1000."""
        for atom in atoms:
            atom.setdefault("skip_if_source_exists", True)

        total_atoms = []
        total_skipped = 0

        for i in range(0, len(atoms), BULK_CHUNK_SIZE):
            chunk = atoms[i : i + BULK_CHUNK_SIZE]
            resp = self._request("POST", "/api/atoms/bulk", data=json.dumps(chunk))
            result = resp.json()
            total_atoms.extend(result.get("atoms", []))
            total_skipped += result.get("skipped", 0)

        return {
            "atoms": total_atoms,
            "count": len(total_atoms),
            "skipped": total_skipped,
        }

    def get_atom(self, atom_id: str) -> dict:
        """Get a single atom by ID."""
        resp = self._request("GET", f"/api/atoms/{atom_id}")
        return resp.json()

    def update_atom(
        self,
        atom_id: str,
        content: str,
        source_url: str | None = None,
        published_at: str | None = None,
        tag_ids: list[str] | None = None,
    ) -> dict:
        """Update an existing atom. Triggers re-embedding."""
        body: dict[str, Any] = {"content": content}
        if source_url is not None:
            body["source_url"] = source_url
        if published_at is not None:
            body["published_at"] = published_at
        if tag_ids is not None:
            body["tag_ids"] = tag_ids

        resp = self._request("PUT", f"/api/atoms/{atom_id}", data=json.dumps(body))
        return resp.json()

    def get_atom_by_source_url(self, url: str) -> dict | None:
        """Find atom by source URL. Returns None if not found."""
        try:
            resp = self._request("GET", "/api/atoms/by-source-url", params={"url": url})
            return resp.json()
        except AtomicAPIError as e:
            if e.status_code == 404:
                return None
            raise

    def list_atoms(
        self,
        limit: int = 50,
        offset: int = 0,
        tag_id: str | None = None,
        source: str | None = None,
        source_value: str | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> dict:
        """List atoms with pagination and filtering."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if tag_id is not None:
            params["tag_id"] = tag_id
        if source is not None:
            params["source"] = source
        if source_value is not None:
            params["source_value"] = source_value
        if sort_by is not None:
            params["sort_by"] = sort_by
        if sort_order is not None:
            params["sort_order"] = sort_order

        resp = self._request("GET", "/api/atoms", params=params)
        return resp.json()

    def ingest_url(
        self,
        url: str,
        tag_ids: list[str] | None = None,
        title_hint: str | None = None,
        published_at: str | None = None,
    ) -> dict:
        """Ingest a URL — Atomic fetches and extracts content server-side."""
        body: dict[str, Any] = {"url": url}
        if tag_ids is not None:
            body["tag_ids"] = tag_ids
        if title_hint is not None:
            body["title_hint"] = title_hint
        if published_at is not None:
            body["published_at"] = published_at

        resp = self._request("POST", "/api/ingest/url", data=json.dumps(body))
        return resp.json()

    def ingest_urls(self, urls: list[dict]) -> dict:
        """Batch URL ingestion."""
        resp = self._request(
            "POST", "/api/ingest/urls", data=json.dumps({"urls": urls}),
        )
        return resp.json()

    def health(self) -> dict:
        """Check server health. Auth header is sent but ignored by server."""
        resp = self._request("GET", "/health")
        return resp.json()

    def delete_atom(self, atom_id: str):
        """Delete an atom by ID."""
        self._request("DELETE", f"/api/atoms/{atom_id}")

    # --- Search (stub) ---

    def search(self, query: str, mode: str = "hybrid", limit: int = 20, threshold: float | None = None) -> list:
        raise NotImplementedError

    # --- Tags (stub) ---

    def list_tags(self, min_count: int | None = None) -> list:
        raise NotImplementedError

    def create_tag(self, name: str, parent_id: str | None = None) -> dict:
        raise NotImplementedError

    # --- Feeds (stub) ---

    def list_feeds(self) -> list:
        raise NotImplementedError

    def create_feed(self, **kwargs) -> dict:
        raise NotImplementedError

    # --- Embeddings (stub) ---

    def get_embedding_status(self) -> dict:
        raise NotImplementedError

    def process_pending(self):
        raise NotImplementedError

    def retry_embedding(self, atom_id: str):
        raise NotImplementedError

    # --- Databases (stub) ---

    def list_databases(self) -> list:
        raise NotImplementedError

    def get_database_stats(self, db_id: str) -> dict:
        raise NotImplementedError
