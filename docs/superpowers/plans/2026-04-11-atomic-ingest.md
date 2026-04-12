# Atomic Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an HA add-on that ingests data from Readwise, Raindrop.io, and Evernote into an Atomic knowledge base via cron-scheduled Python scripts.

**Architecture:** Python 3.12 container with system cron as PID 1. Shared library (`lib/`) provides Atomic API client, sync state persistence, folder consumer, and logging. Each adapter is a standalone script in `adapters/` that imports what it needs from `lib/`. Config comes from HA options.json (3 fields) + `.env` file in `/config/`.

**Tech Stack:** Python 3.12, requests, lxml, markdownify, system cron, jq

**Spec:** `docs/superpowers/specs/2026-04-11-atomic-ingest-design.md`

---

## File Structure

```
atomic-ingest/
├── config.yaml              # HA add-on manifest
├── Dockerfile               # python:3.12-slim + cron + jq
├── run.sh                   # Entrypoint: env setup, crontab gen, exec crond
├── requirements.txt         # Python deps
├── CHANGELOG.md             # Auto-populated by CI
├── icon.png                 # Add-on icon (reuse from atomic/)
├── logo.png                 # Add-on logo (reuse from atomic/)
├── lib/
│   ├── __init__.py
│   ├── log.py               # Logging setup
│   ├── sync_state.py        # Per-adapter JSON state in /data/
│   ├── folder_consumer.py   # Consume/processed folder pattern
│   └── atomic_client.py     # Atomic REST API client
├── adapters/
│   ├── readwise.py          # Readwise Highlights (v2) + Reader (v3)
│   ├── raindrop.py          # Raindrop.io bookmarks via ingest_url
│   └── evernote.py          # ENEX file parser + bulk create
└── tests/
    ├── conftest.py           # Shared fixtures
    ├── test_sync_state.py
    ├── test_folder_consumer.py
    ├── test_atomic_client.py
    ├── test_readwise.py
    ├── test_raindrop.py
    └── test_evernote.py
```

CI/CD:
```
.github/workflows/deploy-atomic-ingest.yml
```

---

### Task 1: Add-on skeleton

**Files:**
- Create: `atomic-ingest/config.yaml`
- Create: `atomic-ingest/Dockerfile`
- Create: `atomic-ingest/requirements.txt`
- Create: `atomic-ingest/CHANGELOG.md`
- Create: `atomic-ingest/lib/__init__.py`

- [ ] **Step 1: Create config.yaml**

```yaml
name: Atomic Ingest
description: >-
  Automated data ingestion into Atomic knowledge base.
  Readwise, Raindrop.io, Evernote, and more.
version: "1.0.0"
slug: atomic-ingest
url: "https://github.com/maksyms/ha-addons"
arch:
  - aarch64
init: false
startup: application
boot: auto

options:
  atomic_api_url: ""
  atomic_api_token: ""
  log_level: "info"
schema:
  atomic_api_url: url
  atomic_api_token: password
  log_level: "list(debug|info|warning|error)"

map:
  - data:rw
  - share:rw
  - addon_config:ro
```

- [ ] **Step 2: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    cron jq \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY lib/ lib/
COPY adapters/ adapters/
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
```

- [ ] **Step 3: Create requirements.txt**

```
requests
lxml
markdownify
```

- [ ] **Step 4: Create CHANGELOG.md**

```markdown
```

(Empty file — CI auto-populates it.)

- [ ] **Step 5: Create lib/__init__.py**

```python
```

(Empty file — marks `lib/` as a Python package.)

- [ ] **Step 6: Create .env.example**

```bash
# Atomic connection (also configurable in HA UI)
# ATOMIC_API_URL=http://23930cf1-atomic:8081
# ATOMIC_API_TOKEN=at_...

# Source credentials
READWISE_API_TOKEN=
RAINDROP_TOKEN=

# Schedule overrides (cron expressions)
# READWISE_SCHEDULE="0 * * * *"    # default: hourly on the hour
# RAINDROP_SCHEDULE="30 * * * *"   # default: hourly at :30
# EVERNOTE_SCHEDULE="0 3 * * *"    # default: daily at 3am
```

- [ ] **Step 7: Copy icon.png and logo.png from atomic/**

```bash
cp atomic/icon.png atomic-ingest/icon.png
cp atomic/logo.png atomic-ingest/logo.png
```

- [ ] **Step 8: Commit**

```bash
git add atomic-ingest/config.yaml atomic-ingest/Dockerfile atomic-ingest/requirements.txt atomic-ingest/CHANGELOG.md atomic-ingest/lib/__init__.py atomic-ingest/.env.example atomic-ingest/icon.png atomic-ingest/logo.png
git commit -m "feat(atomic-ingest): add-on skeleton with config, Dockerfile, requirements"
```

---

### Task 2: lib/log.py

**Files:**
- Create: `atomic-ingest/lib/log.py`

- [ ] **Step 1: Create lib/log.py**

```python
import logging
import os
import sys


def setup(adapter_name: str) -> logging.Logger:
    """Configure logging for an adapter.

    Reads LOG_LEVEL from environment (default: info).
    Logs to stdout so HA captures output in add-on logs.
    """
    level_name = os.environ.get("LOG_LEVEL", "info").upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger(adapter_name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            f"%(asctime)s [{adapter_name}] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
```

- [ ] **Step 2: Commit**

```bash
git add atomic-ingest/lib/log.py
git commit -m "feat(atomic-ingest): add logging setup module"
```

---

### Task 3: lib/sync_state.py

**Files:**
- Create: `atomic-ingest/lib/sync_state.py`
- Create: `atomic-ingest/tests/conftest.py`
- Create: `atomic-ingest/tests/test_sync_state.py`

- [ ] **Step 1: Write tests for SyncState**

Create `atomic-ingest/tests/conftest.py`:
```python
import pytest
from pathlib import Path


@pytest.fixture
def tmp_state_file(tmp_path):
    """Return a path to a temporary sync state JSON file."""
    return str(tmp_path / "sync_state.json")
```

Create `atomic-ingest/tests/test_sync_state.py`:
```python
import json
from lib.sync_state import SyncState


def test_get_returns_empty_dict_for_unknown_adapter(tmp_state_file):
    state = SyncState(tmp_state_file)
    assert state.get("readwise") == {}


def test_save_and_get_roundtrip(tmp_state_file):
    state = SyncState(tmp_state_file)
    state.save("readwise", {"last_updated": "2026-04-11T03:00:00Z", "cursor": "abc"})
    result = state.get("readwise")
    assert result == {"last_updated": "2026-04-11T03:00:00Z", "cursor": "abc"}


def test_save_preserves_other_adapters(tmp_state_file):
    state = SyncState(tmp_state_file)
    state.save("readwise", {"last": "2026-04-11"})
    state.save("raindrop", {"last": "2026-04-10"})
    assert state.get("readwise") == {"last": "2026-04-11"}
    assert state.get("raindrop") == {"last": "2026-04-10"}


def test_save_overwrites_adapter_state(tmp_state_file):
    state = SyncState(tmp_state_file)
    state.save("readwise", {"cursor": "abc"})
    state.save("readwise", {"cursor": "def", "extra": True})
    assert state.get("readwise") == {"cursor": "def", "extra": True}


def test_persists_across_instances(tmp_state_file):
    state1 = SyncState(tmp_state_file)
    state1.save("readwise", {"cursor": "abc"})

    state2 = SyncState(tmp_state_file)
    assert state2.get("readwise") == {"cursor": "abc"}


def test_handles_corrupted_file(tmp_state_file):
    with open(tmp_state_file, "w") as f:
        f.write("not json{{{")
    state = SyncState(tmp_state_file)
    assert state.get("readwise") == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd atomic-ingest && python -m pytest tests/test_sync_state.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'lib.sync_state'`

- [ ] **Step 3: Implement SyncState**

Create `atomic-ingest/lib/sync_state.py`:
```python
import fcntl
import json
from pathlib import Path


class SyncState:
    """Per-adapter sync state persisted as JSON in /data/.

    Call save() after each page/batch during sync for crash-safe resume.
    File-level locking prevents concurrent corruption.
    """

    def __init__(self, path: str = "/data/sync_state.json"):
        self._path = Path(path)

    def get(self, adapter_name: str) -> dict:
        """Return adapter's state dict, or {} if no prior state."""
        data = self._read()
        return data.get(adapter_name, {})

    def save(self, adapter_name: str, state: dict):
        """Replace adapter's state and persist to disk.

        Safe to call mid-sync — writes atomically with file locking.
        """
        data = self._read()
        data[adapter_name] = state
        self._write(data)

    def _read(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            with open(self._path, "r") as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                try:
                    return json.load(f)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: dict):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                json.dump(data, f, indent=2)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd atomic-ingest && python -m pytest tests/test_sync_state.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add atomic-ingest/lib/sync_state.py atomic-ingest/tests/conftest.py atomic-ingest/tests/test_sync_state.py
git commit -m "feat(atomic-ingest): add SyncState with file locking and tests"
```

---

### Task 4: lib/folder_consumer.py

**Files:**
- Create: `atomic-ingest/lib/folder_consumer.py`
- Create: `atomic-ingest/tests/test_folder_consumer.py`

- [ ] **Step 1: Write tests for folder_consumer**

Create `atomic-ingest/tests/test_folder_consumer.py`:
```python
from pathlib import Path
from lib.folder_consumer import consume


def test_yields_matching_files(tmp_path):
    consume_dir = tmp_path / "consume"
    processed_dir = tmp_path / "processed"
    consume_dir.mkdir()
    processed_dir.mkdir()

    (consume_dir / "notes.enex").write_text("<xml>data</xml>")
    (consume_dir / "readme.txt").write_text("ignore me")

    results = list(consume(consume_dir, processed_dir, "*.enex"))
    assert len(results) == 1
    assert results[0][0].name == "notes.enex"


def test_mark_done_moves_file(tmp_path):
    consume_dir = tmp_path / "consume"
    processed_dir = tmp_path / "processed"
    consume_dir.mkdir()
    processed_dir.mkdir()

    (consume_dir / "notes.enex").write_text("<xml>data</xml>")

    for file_path, mark_done in consume(consume_dir, processed_dir, "*.enex"):
        mark_done()

    assert not (consume_dir / "notes.enex").exists()
    assert (processed_dir / "notes.enex").exists()


def test_empty_consume_dir_yields_nothing(tmp_path):
    consume_dir = tmp_path / "consume"
    processed_dir = tmp_path / "processed"
    consume_dir.mkdir()
    processed_dir.mkdir()

    results = list(consume(consume_dir, processed_dir, "*.enex"))
    assert results == []


def test_mark_done_handles_duplicate_filename(tmp_path):
    consume_dir = tmp_path / "consume"
    processed_dir = tmp_path / "processed"
    consume_dir.mkdir()
    processed_dir.mkdir()

    # Pre-existing file in processed with same name
    (processed_dir / "notes.enex").write_text("old")
    (consume_dir / "notes.enex").write_text("new")

    for file_path, mark_done in consume(consume_dir, processed_dir, "*.enex"):
        mark_done()

    # New file should overwrite old one in processed
    assert (processed_dir / "notes.enex").read_text() == "new"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd atomic-ingest && python -m pytest tests/test_folder_consumer.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'lib.folder_consumer'`

- [ ] **Step 3: Implement folder_consumer**

Create `atomic-ingest/lib/folder_consumer.py`:
```python
import shutil
from pathlib import Path
from typing import Callable, Iterator


def consume(
    consume_dir: Path,
    processed_dir: Path,
    glob_pattern: str,
) -> Iterator[tuple[Path, Callable]]:
    """Yield files matching pattern from consume_dir.

    For each file, yields (file_path, mark_done). Calling mark_done()
    moves the file to processed_dir.
    """
    for file_path in sorted(consume_dir.glob(glob_pattern)):
        if not file_path.is_file():
            continue

        def mark_done(fp=file_path):
            dest = processed_dir / fp.name
            shutil.move(str(fp), str(dest))

        yield file_path, mark_done
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd atomic-ingest && python -m pytest tests/test_folder_consumer.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add atomic-ingest/lib/folder_consumer.py atomic-ingest/tests/test_folder_consumer.py
git commit -m "feat(atomic-ingest): add folder consumer with consume/processed pattern"
```

---

### Task 5: lib/atomic_client.py

**Files:**
- Create: `atomic-ingest/lib/atomic_client.py`
- Create: `atomic-ingest/tests/test_atomic_client.py`

- [ ] **Step 1: Write tests for AtomicClient**

Create `atomic-ingest/tests/test_atomic_client.py`:
```python
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
        call_kwargs = mock_request.call_args
        body = json.loads(call_kwargs.kwargs.get("data", call_kwargs[1].get("data", "{}")))
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

        body = json.loads(mock_request.call_args.kwargs.get("data", mock_request.call_args[1].get("data", "{}")))
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

        assert mock_request.call_count == 2  # 1000 + 500


class TestIngestUrl:
    @patch("lib.atomic_client.requests.Session.request")
    def test_ingests_url(self, mock_request, client):
        mock_request.return_value = _mock_response(200, {
            "atom_id": "uuid-1", "url": "https://example.com",
            "title": "Example", "content_length": 5000,
        })

        result = client.ingest_url("https://example.com")
        assert result["atom_id"] == "uuid-1"

        body = json.loads(mock_request.call_args.kwargs.get("data", mock_request.call_args[1].get("data", "{}")))
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd atomic-ingest && python -m pytest tests/test_atomic_client.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'lib.atomic_client'`

- [ ] **Step 3: Implement AtomicClient**

Create `atomic-ingest/lib/atomic_client.py`:
```python
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
        """Bulk create atoms. Auto-chunks into batches of 1000.

        Each atom dict should have at least 'content'. Optional:
        'source_url', 'published_at', 'tag_ids'.
        Sets skip_if_source_exists=True on all atoms.
        """
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
        """Batch URL ingestion. Each dict: {url, tag_ids?, title_hint?, published_at?}."""
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd atomic-ingest && python -m pytest tests/test_atomic_client.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add atomic-ingest/lib/atomic_client.py atomic-ingest/tests/test_atomic_client.py
git commit -m "feat(atomic-ingest): add AtomicClient with ingestion methods and retry logic"
```

---

### Task 6: run.sh

**Files:**
- Create: `atomic-ingest/run.sh`

- [ ] **Step 1: Create run.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail

# --- Read HA options ---
OPTIONS="/data/options.json"

ATOMIC_API_URL=$(jq -r '.atomic_api_url // empty' "$OPTIONS")
ATOMIC_API_TOKEN=$(jq -r '.atomic_api_token // empty' "$OPTIONS")
LOG_LEVEL=$(jq -r '.log_level // "info"' "$OPTIONS")

export ATOMIC_API_URL
export ATOMIC_API_TOKEN
export LOG_LEVEL

# --- Source .env if present ---
if [[ -f /config/.env ]]; then
    echo "Loading /config/.env"
    set -a
    source /config/.env
    set +a
fi

# --- Validate required config ---
if [[ -z "${ATOMIC_API_URL:-}" ]]; then
    echo "ERROR: atomic_api_url is required (set in HA UI or /config/.env)"
    exit 1
fi
if [[ -z "${ATOMIC_API_TOKEN:-}" ]]; then
    echo "ERROR: atomic_api_token is required (set in HA UI or /config/.env)"
    exit 1
fi

# --- Create consume/processed dirs ---
mkdir -p /share/atomic-ingest/evernote/consume
mkdir -p /share/atomic-ingest/evernote/processed

# --- Dump env for cron jobs ---
# Cron doesn't inherit environment, so we dump to a file that each job sources.
ENV_FILE=/app/env.sh
{
    echo "export ATOMIC_API_URL='${ATOMIC_API_URL}'"
    echo "export ATOMIC_API_TOKEN='${ATOMIC_API_TOKEN}'"
    echo "export LOG_LEVEL='${LOG_LEVEL}'"
    echo "export READWISE_API_TOKEN='${READWISE_API_TOKEN:-}'"
    echo "export RAINDROP_TOKEN='${RAINDROP_TOKEN:-}'"
} > "$ENV_FILE"

# --- Generate crontab ---
READWISE_SCHEDULE="${READWISE_SCHEDULE:-0 * * * *}"
RAINDROP_SCHEDULE="${RAINDROP_SCHEDULE:-30 * * * *}"
EVERNOTE_SCHEDULE="${EVERNOTE_SCHEDULE:-0 3 * * *}"

CRONTAB_FILE=/etc/cron.d/atomic-ingest
cat > "$CRONTAB_FILE" <<EOF
${READWISE_SCHEDULE} root . /app/env.sh && cd /app && python -u adapters/readwise.py >> /proc/1/fd/1 2>&1
${RAINDROP_SCHEDULE} root . /app/env.sh && cd /app && python -u adapters/raindrop.py >> /proc/1/fd/1 2>&1
${EVERNOTE_SCHEDULE} root . /app/env.sh && cd /app && python -u adapters/evernote.py >> /proc/1/fd/1 2>&1
EOF

chmod 0644 "$CRONTAB_FILE"

echo "Crontab installed:"
cat "$CRONTAB_FILE"
echo ""
echo "Starting crond..."

# --- Exec crond as PID 1 ---
exec cron -f
```

- [ ] **Step 2: Commit**

```bash
git add atomic-ingest/run.sh
git commit -m "feat(atomic-ingest): add run.sh entrypoint with env setup and crontab generation"
```

---

### Task 7: adapters/readwise.py

**Files:**
- Create: `atomic-ingest/adapters/readwise.py`
- Create: `atomic-ingest/tests/test_readwise.py`

- [ ] **Step 1: Write tests for Readwise adapter**

Create `atomic-ingest/tests/test_readwise.py`:
```python
import pytest
from unittest.mock import MagicMock, patch
from adapters.readwise import (
    format_highlights_atom,
    format_highlights_section,
    sync_highlights,
    sync_reader,
)


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd atomic-ingest && python -m pytest tests/test_readwise.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'adapters.readwise'`

- [ ] **Step 3: Implement readwise adapter**

Create `atomic-ingest/adapters/readwise.py`:
```python
"""Readwise adapter — syncs Highlights (v2 export) and Reader (v3 list).

Highlights: one atom per book, blockquoted highlights with notes.
Reader: ingest_url for full content, append highlights section if present.
"""

import os
import sys
import time
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.atomic_client import AtomicClient, AtomicAPIError
from lib.sync_state import SyncState
from lib import log

READWISE_EXPORT_URL = "https://readwise.io/api/v2/export/"
READWISE_READER_URL = "https://readwise.io/api/v3/list/"
RATE_LIMIT_WAIT = 60  # seconds to wait on 429


def format_highlights_atom(book: dict) -> str:
    """Format a book's highlights as atom content."""
    title = book.get("title", "Untitled")
    author = book.get("author")
    highlights = book.get("highlights", [])

    lines = [f"# {title}"]
    if author:
        lines.append(f"\nby {author}")

    for hl in highlights:
        text = hl.get("text", "").strip()
        note = hl.get("note", "").strip()
        if text:
            lines.append(f"\n> {text}")
            if note:
                lines.append(f"\n{note}")

    return "\n".join(lines)


def format_highlights_section(highlights: list[dict]) -> str:
    """Format highlights as a section to append to an existing atom."""
    if not highlights:
        return ""

    lines = ["\n\n## My Highlights"]
    for hl in highlights:
        text = hl.get("text", "").strip()
        note = hl.get("note", "").strip()
        if text:
            lines.append(f"\n> {text}")
            if note:
                lines.append(f"\n{note}")

    return "\n".join(lines)


def _readwise_get(url: str, token: str, params: dict | None = None) -> dict:
    """Make a Readwise API GET request with rate limit handling."""
    headers = {"Authorization": f"Token {token}"}
    resp = requests.get(url, headers=headers, params=params or {})

    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", RATE_LIMIT_WAIT))
        time.sleep(retry_after)
        resp = requests.get(url, headers=headers, params=params or {})

    resp.raise_for_status()
    return resp.json()


def sync_highlights(client: AtomicClient, state: SyncState, token: str):
    """Sync Readwise Highlights (v2 export API)."""
    logger = log.setup("readwise.highlights")
    adapter_state = state.get("readwise")
    updated_after = adapter_state.get("highlights_updated_after")
    cursor = adapter_state.get("highlights_cursor")

    params = {}
    if updated_after:
        params["updatedAfter"] = updated_after
    if cursor:
        params["pageCursor"] = cursor

    created = 0
    updated = 0

    while True:
        data = _readwise_get(READWISE_EXPORT_URL, token, params)
        books = data.get("results", [])

        for book in books:
            source_url = book.get("source_url", "")
            content = format_highlights_atom(book)

            existing = client.get_atom_by_source_url(source_url) if source_url else None
            if existing:
                client.update_atom(
                    existing["id"],
                    content=content,
                    source_url=source_url,
                    published_at=book.get("last_highlight_at"),
                )
                updated += 1
            else:
                client.create_atom(
                    content=content,
                    source_url=source_url,
                    published_at=book.get("last_highlight_at"),
                )
                created += 1

        next_cursor = data.get("nextPageCursor")
        adapter_state["highlights_cursor"] = next_cursor
        state.save("readwise", adapter_state)

        if not next_cursor:
            break
        params["pageCursor"] = next_cursor

    # Sync complete — update timestamp, clear cursor
    from datetime import datetime, timezone
    adapter_state["highlights_updated_after"] = datetime.now(timezone.utc).isoformat()
    adapter_state["highlights_cursor"] = None
    state.save("readwise", adapter_state)

    logger.info("Highlights sync complete: %d created, %d updated", created, updated)


def sync_reader(client: AtomicClient, state: SyncState, token: str):
    """Sync Readwise Reader (v3 list API)."""
    logger = log.setup("readwise.reader")
    adapter_state = state.get("readwise")
    updated_after = adapter_state.get("reader_updated_after")
    cursor = adapter_state.get("reader_cursor")

    params = {}
    if updated_after:
        params["updatedAfter"] = updated_after
    if cursor:
        params["pageCursor"] = cursor

    ingested = 0
    enriched = 0

    while True:
        data = _readwise_get(READWISE_READER_URL, token, params)
        results = data.get("results", [])

        for doc in results:
            source_url = doc.get("source_url") or doc.get("url", "")
            if not source_url:
                continue

            published_at = doc.get("published_date")

            # Ingest the URL — Atomic fetches full content
            try:
                client.ingest_url(url=source_url, published_at=published_at)
                ingested += 1
            except AtomicAPIError as e:
                if e.status_code == 409 or "already exists" in e.message.lower():
                    logger.debug("URL already ingested: %s", source_url)
                else:
                    logger.warning("Failed to ingest %s: %s", source_url, e)
                    continue

            # Enrich with highlights if present
            highlights = doc.get("highlights", [])
            notes = doc.get("notes", "").strip()
            hl_items = []
            if highlights:
                hl_items = [{"text": h.get("text", ""), "note": h.get("note", "")} for h in highlights]
            if notes:
                hl_items.append({"text": notes, "note": ""})

            if hl_items:
                existing = client.get_atom_by_source_url(source_url)
                if existing:
                    section = format_highlights_section(hl_items)
                    new_content = existing["content"] + section
                    client.update_atom(existing["id"], content=new_content)
                    enriched += 1

        next_cursor = data.get("nextPageCursor")
        adapter_state["reader_cursor"] = next_cursor
        state.save("readwise", adapter_state)

        if not next_cursor:
            break
        params["pageCursor"] = next_cursor

    # Sync complete — update timestamp, clear cursor
    from datetime import datetime, timezone
    adapter_state["reader_updated_after"] = datetime.now(timezone.utc).isoformat()
    adapter_state["reader_cursor"] = None
    state.save("readwise", adapter_state)

    logger.info("Reader sync complete: %d ingested, %d enriched with highlights", ingested, enriched)


def main():
    logger = log.setup("readwise")

    token = os.environ.get("READWISE_API_TOKEN", "")
    if not token:
        logger.info("READWISE_API_TOKEN not set, skipping")
        return

    api_url = os.environ["ATOMIC_API_URL"]
    api_token = os.environ["ATOMIC_API_TOKEN"]
    client = AtomicClient(api_url, api_token)
    state = SyncState()

    logger.info("Starting Readwise sync")
    sync_highlights(client, state, token)
    sync_reader(client, state, token)
    logger.info("Readwise sync complete")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd atomic-ingest && python -m pytest tests/test_readwise.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add atomic-ingest/adapters/readwise.py atomic-ingest/tests/test_readwise.py
git commit -m "feat(atomic-ingest): add Readwise adapter for Highlights and Reader"
```

---

### Task 8: adapters/raindrop.py

**Files:**
- Create: `atomic-ingest/adapters/raindrop.py`
- Create: `atomic-ingest/tests/test_raindrop.py`

- [ ] **Step 1: Write tests for Raindrop adapter**

Create `atomic-ingest/tests/test_raindrop.py`:
```python
import pytest
from unittest.mock import MagicMock, patch
from adapters.raindrop import classify_bookmark, format_notes_section, sync_raindrop


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd atomic-ingest && python -m pytest tests/test_raindrop.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'adapters.raindrop'`

- [ ] **Step 3: Implement raindrop adapter**

Create `atomic-ingest/adapters/raindrop.py`:
```python
"""Raindrop.io adapter — syncs bookmarks via ingest_url.

URL bookmarks: ingest_url for full content, enrich with notes/highlights.
Uploaded files/videos: create_atom with title + note.
"""

import os
import sys
import requests
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.atomic_client import AtomicClient, AtomicAPIError
from lib.sync_state import SyncState
from lib import log

RAINDROP_API_URL = "https://api.raindrop.io/rest/v1/raindrops/0"
PAGE_SIZE = 50


def classify_bookmark(bm: dict) -> str:
    """Classify bookmark: 'url_clean', 'url_annotated', or 'uploaded'."""
    link = bm.get("link", "").strip()
    note = bm.get("note", "").strip()
    highlights = bm.get("highlights", [])

    if not link:
        return "uploaded"
    if note or highlights:
        return "url_annotated"
    return "url_clean"


def format_notes_section(note: str, highlights: list[dict]) -> str:
    """Format Raindrop notes and highlights as a section."""
    note = note.strip()
    if not note and not highlights:
        return ""

    lines = ["\n\n## My Notes"]
    if note:
        lines.append(f"\n{note}")
    for hl in highlights:
        text = hl.get("text", "").strip()
        if text:
            lines.append(f"\n> {text}")

    return "\n".join(lines)


def _raindrop_get(url: str, token: str, params: dict) -> dict:
    """Make a Raindrop API GET request."""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json()


def sync_raindrop(client: AtomicClient, state: SyncState, token: str):
    """Sync Raindrop.io bookmarks."""
    logger = log.setup("raindrop")
    adapter_state = state.get("raindrop")
    last_sync_date = adapter_state.get("last_sync_date")

    params: dict = {"perpage": PAGE_SIZE, "sort": "-created"}
    if last_sync_date:
        params["search"] = f"lastUpdate:>{last_sync_date}"

    page = 0
    ingested = 0
    enriched = 0
    created = 0

    while True:
        params["page"] = page
        data = _raindrop_get(RAINDROP_API_URL, token, params)
        items = data.get("items", [])

        if not items:
            break

        for bm in items:
            kind = classify_bookmark(bm)
            link = bm.get("link", "").strip()
            title = bm.get("title", "Untitled")
            note = bm.get("note", "")
            highlights = bm.get("highlights", [])
            published_at = bm.get("created")

            if kind == "uploaded":
                content = f"# {title}"
                if note.strip():
                    content += f"\n\n{note.strip()}"
                source_url = f"https://app.raindrop.io/my/0/{bm.get('_id', '')}"
                client.create_atom(
                    content=content,
                    source_url=source_url,
                    published_at=published_at,
                )
                created += 1

            elif kind == "url_clean":
                try:
                    client.ingest_url(url=link, published_at=published_at)
                    ingested += 1
                except AtomicAPIError as e:
                    if e.status_code == 409 or "already exists" in e.message.lower():
                        logger.debug("URL already ingested: %s", link)
                    else:
                        logger.warning("Failed to ingest %s: %s", link, e)

            elif kind == "url_annotated":
                try:
                    client.ingest_url(url=link, published_at=published_at)
                    ingested += 1
                except AtomicAPIError as e:
                    if e.status_code != 409 and "already exists" not in e.message.lower():
                        logger.warning("Failed to ingest %s: %s", link, e)
                        continue

                # Enrich with notes/highlights
                section = format_notes_section(note, highlights)
                if section:
                    existing = client.get_atom_by_source_url(link)
                    if existing:
                        new_content = existing["content"] + section
                        client.update_atom(existing["id"], content=new_content)
                        enriched += 1

        if len(items) < PAGE_SIZE:
            break
        page += 1

    # Update sync state
    adapter_state["last_sync_date"] = date.today().isoformat()
    state.save("raindrop", adapter_state)

    logger.info(
        "Raindrop sync complete: %d ingested, %d enriched, %d created (uploaded)",
        ingested, enriched, created,
    )


def main():
    logger = log.setup("raindrop")

    token = os.environ.get("RAINDROP_TOKEN", "")
    if not token:
        logger.info("RAINDROP_TOKEN not set, skipping")
        return

    api_url = os.environ["ATOMIC_API_URL"]
    api_token = os.environ["ATOMIC_API_TOKEN"]
    client = AtomicClient(api_url, api_token)
    state = SyncState()

    logger.info("Starting Raindrop sync")
    sync_raindrop(client, state, token)
    logger.info("Raindrop sync complete")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd atomic-ingest && python -m pytest tests/test_raindrop.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add atomic-ingest/adapters/raindrop.py atomic-ingest/tests/test_raindrop.py
git commit -m "feat(atomic-ingest): add Raindrop adapter with ingest_url and annotation enrichment"
```

---

### Task 9: adapters/evernote.py

**Files:**
- Create: `atomic-ingest/adapters/evernote.py`
- Create: `atomic-ingest/tests/test_evernote.py`

- [ ] **Step 1: Write tests for Evernote adapter**

Create `atomic-ingest/tests/test_evernote.py`:
```python
import pytest
from pathlib import Path
from adapters.evernote import parse_enex, format_note_atom


SAMPLE_ENEX = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export4.dtd">
<en-export>
  <note>
    <title>My First Note</title>
    <content><![CDATA[<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
<div>Hello world</div>
<div><br/></div>
<div>This is a <b>test</b> note.</div>
</en-note>]]></content>
    <created>20260411T120000Z</created>
    <updated>20260411T130000Z</updated>
    <note-attributes>
      <source-url>https://example.com/article</source-url>
    </note-attributes>
  </note>
  <note>
    <title>Second Note</title>
    <content><![CDATA[<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
<div>Short note</div>
</en-note>]]></content>
    <created>20260410T080000Z</created>
    <updated>20260410T090000Z</updated>
    <note-attributes/>
  </note>
</en-export>"""


class TestParseEnex:
    def test_parses_two_notes(self, tmp_path):
        enex_file = tmp_path / "test.enex"
        enex_file.write_text(SAMPLE_ENEX)
        notes = list(parse_enex(enex_file))
        assert len(notes) == 2

    def test_extracts_title(self, tmp_path):
        enex_file = tmp_path / "test.enex"
        enex_file.write_text(SAMPLE_ENEX)
        notes = list(parse_enex(enex_file))
        assert notes[0]["title"] == "My First Note"
        assert notes[1]["title"] == "Second Note"

    def test_extracts_content_as_html(self, tmp_path):
        enex_file = tmp_path / "test.enex"
        enex_file.write_text(SAMPLE_ENEX)
        notes = list(parse_enex(enex_file))
        assert "Hello world" in notes[0]["content_html"]

    def test_extracts_created_date(self, tmp_path):
        enex_file = tmp_path / "test.enex"
        enex_file.write_text(SAMPLE_ENEX)
        notes = list(parse_enex(enex_file))
        assert notes[0]["created"] == "2026-04-11T12:00:00Z"


class TestFormatNoteAtom:
    def test_formats_note_as_markdown(self):
        note = {
            "title": "My Note",
            "content_html": "<div>Hello <b>world</b></div>",
            "created": "2026-04-11T12:00:00Z",
        }
        content = format_note_atom(note)
        assert content.startswith("# My Note\n\n")
        assert "Hello" in content
        assert "**world**" in content

    def test_handles_empty_content(self):
        note = {"title": "Empty", "content_html": "", "created": "2026-04-11T12:00:00Z"}
        content = format_note_atom(note)
        assert content == "# Empty"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd atomic-ingest && python -m pytest tests/test_evernote.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'adapters.evernote'`

- [ ] **Step 3: Implement evernote adapter**

Create `atomic-ingest/adapters/evernote.py`:
```python
"""Evernote adapter — parses .enex files from consume folder, creates atoms.

Scans /share/atomic-ingest/evernote/consume/ for .enex files.
Parses ENEX XML, converts HTML to Markdown, bulk creates atoms.
Moves processed files to /share/atomic-ingest/evernote/processed/.
"""

import os
import re
import sys
import hashlib
from pathlib import Path
from datetime import datetime

from lxml import etree
from markdownify import markdownify

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.atomic_client import AtomicClient
from lib.folder_consumer import consume
from lib import log

CONSUME_DIR = Path("/share/atomic-ingest/evernote/consume")
PROCESSED_DIR = Path("/share/atomic-ingest/evernote/processed")
BULK_SIZE = 1000


def parse_enex(enex_path: Path) -> list[dict]:
    """Parse an ENEX file and yield note dicts.

    Each dict has: title, content_html, created, source_url (optional).
    """
    tree = etree.parse(str(enex_path))
    notes = []

    for note_el in tree.findall(".//note"):
        title = note_el.findtext("title", "Untitled")

        # Content is CDATA-wrapped ENML (HTML-like)
        content_raw = note_el.findtext("content", "")
        # Strip the ENML doctype and en-note wrapper
        content_html = _extract_enml_body(content_raw)

        # Parse Evernote date format: 20260411T120000Z -> ISO 8601
        created_raw = note_el.findtext("created", "")
        created = _parse_evernote_date(created_raw)

        # Source URL from note attributes
        attrs_el = note_el.find("note-attributes")
        source_url = None
        if attrs_el is not None:
            source_url = attrs_el.findtext("source-url")

        notes.append({
            "title": title,
            "content_html": content_html,
            "created": created,
            "source_url": source_url,
        })

    return notes


def _extract_enml_body(content: str) -> str:
    """Extract body content from ENML, stripping doctype and en-note tags."""
    # Remove XML declaration and doctype
    content = re.sub(r'<\?xml[^>]*\?>', '', content)
    content = re.sub(r'<!DOCTYPE[^>]*>', '', content)
    # Remove en-note wrapper
    content = re.sub(r'</?en-note[^>]*>', '', content)
    return content.strip()


def _parse_evernote_date(date_str: str) -> str | None:
    """Convert Evernote date (20260411T120000Z) to ISO 8601."""
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str.strip(), "%Y%m%dT%H%M%SZ")
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def format_note_atom(note: dict) -> str:
    """Format an Evernote note as atom content (Markdown)."""
    title = note["title"]
    html = note.get("content_html", "")

    if not html.strip():
        return f"# {title}"

    md = markdownify(html, heading_style="ATX", strip=["img"]).strip()
    return f"# {title}\n\n{md}"


def _note_source_url(note: dict, enex_filename: str) -> str:
    """Generate a stable source URL for dedup.

    Uses the Evernote source-url if available, otherwise generates
    a deterministic URI from the note title and created date.
    """
    if note.get("source_url"):
        return note["source_url"]

    # Deterministic fallback: hash of title + created + filename
    key = f"{note['title']}|{note.get('created', '')}|{enex_filename}"
    digest = hashlib.sha256(key.encode()).hexdigest()[:12]
    return f"evernote:///import/{digest}"


def main():
    logger = log.setup("evernote")

    api_url = os.environ["ATOMIC_API_URL"]
    api_token = os.environ["ATOMIC_API_TOKEN"]
    client = AtomicClient(api_url, api_token)

    files_found = False
    for enex_path, mark_done in consume(CONSUME_DIR, PROCESSED_DIR, "*.enex"):
        files_found = True
        logger.info("Processing %s", enex_path.name)

        notes = parse_enex(enex_path)
        logger.info("Parsed %d notes from %s", len(notes), enex_path.name)

        # Build atom dicts for bulk create
        atoms = []
        for note in notes:
            content = format_note_atom(note)
            source_url = _note_source_url(note, enex_path.name)
            atom = {"content": content, "source_url": source_url}
            if note.get("created"):
                atom["published_at"] = note["created"]
            atoms.append(atom)

        # Bulk create in chunks
        if atoms:
            result = client.create_atoms_bulk(atoms)
            logger.info(
                "%s: %d created, %d skipped",
                enex_path.name, result["count"], result["skipped"],
            )

        mark_done()
        logger.info("Moved %s to processed", enex_path.name)

    if not files_found:
        logger.debug("No .enex files found in consume folder")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd atomic-ingest && python -m pytest tests/test_evernote.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add atomic-ingest/adapters/evernote.py atomic-ingest/tests/test_evernote.py
git commit -m "feat(atomic-ingest): add Evernote adapter with ENEX parsing and bulk create"
```

---

### Task 10: CI/CD workflow

**Files:**
- Create: `.github/workflows/deploy-atomic-ingest.yml`

- [ ] **Step 1: Create deploy workflow**

Create `.github/workflows/deploy-atomic-ingest.yml` (based on `deploy-atomic.yml`):

```yaml
name: Deploy Atomic Ingest Add-on

on:
  push:
    branches: [master]
    paths:
      - 'atomic-ingest/**'

permissions:
  contents: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          fetch-depth: 0

      - name: Bump addon version
        run: |
          cd atomic-ingest
          current=$(grep '^version:' config.yaml | sed 's/version: *"\(.*\)"/\1/')
          IFS='.' read -r major minor patch <<< "$current"
          new_version="${major}.${minor}.$((patch + 1))"
          sed -i "s/^version: \"${current}\"/version: \"${new_version}\"/" config.yaml
          echo "VERSION=${new_version}" >> "$GITHUB_ENV"
          echo "PREV_VERSION=${current}" >> "$GITHUB_ENV"
          echo "Bumped version: ${current} → ${new_version}"

      - name: Generate changelog
        run: |
          PREV_COMMIT=$(git log --oneline --grep="Bump HAOS addon version to ${PREV_VERSION}" --format="%H" -1)
          if [ -n "$PREV_COMMIT" ]; then
            CHANGES=$(git log --oneline "${PREV_COMMIT}..HEAD" --no-decorate \
              | grep -v "\[skip ci\]" \
              | sed 's/^[a-f0-9]* /- /')
          else
            CHANGES=$(git log --oneline -10 --no-decorate \
              | grep -v "\[skip ci\]" \
              | sed 's/^[a-f0-9]* /- /')
          fi

          CHANGELOG="atomic-ingest/CHANGELOG.md"
          NEW_ENTRY="## ${VERSION}"$'\n'"${CHANGES}"
          if [ -f "$CHANGELOG" ]; then
            echo -e "${NEW_ENTRY}\n\n$(cat "$CHANGELOG")" > "$CHANGELOG"
          else
            echo "$NEW_ENTRY" > "$CHANGELOG"
          fi

      - name: Commit version bump and changelog
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add atomic-ingest/config.yaml atomic-ingest/CHANGELOG.md
          git commit -m "Bump HAOS addon version to ${VERSION} [skip ci]"
          git pull --rebase
          git push
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/deploy-atomic-ingest.yml
git commit -m "ci(atomic-ingest): add deploy workflow with version bump and changelog"
```

---

### Task 11: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add atomic-ingest section to CLAUDE.md**

Add after the `## atomic` section in `CLAUDE.md`:

```markdown
## atomic-ingest

### Architecture

Cron-based Python add-on that ingests data from multiple sources into Atomic via its REST API. Single container with `crond` as PID 1, spawning adapter scripts on schedule.

### Commands

```bash
# Run tests locally
cd atomic-ingest && pip install -r requirements.txt && pip install pytest
python -m pytest tests/ -v
```

### Configuration

Three HA UI options: `atomic_api_url`, `atomic_api_token`, `log_level`. All source-specific credentials and schedule overrides in `.env` at `/addon_configs/atomic-ingest/` (mounted as `/config/` inside container).

### Key Files

| File | Purpose |
|------|---------|
| `config.yaml` | HA add-on manifest |
| `Dockerfile` | python:3.12-slim + cron |
| `run.sh` | Entrypoint — env setup, crontab gen, exec crond |
| `lib/atomic_client.py` | Atomic REST API client |
| `lib/sync_state.py` | Per-adapter JSON state in /data/ |
| `lib/folder_consumer.py` | Consume/processed folder pattern |
| `adapters/readwise.py` | Readwise Highlights + Reader |
| `adapters/raindrop.py` | Raindrop.io bookmarks via ingest_url |
| `adapters/evernote.py` | ENEX file import via bulk create |

### Adapters

**Readwise** (hourly): Highlights v2 export (one atom per book) + Reader v3 list (ingest_url + highlight enrichment). Auth: `READWISE_API_TOKEN`.

**Raindrop** (hourly): Bookmarks via `ingest_url` for URLs, `create_atom` for uploaded files. Notes/highlights appended via update. Auth: `RAINDROP_TOKEN`.

**Evernote** (daily): Scans `/share/atomic-ingest/evernote/consume/` for `.enex` files, parses to Markdown, bulk creates, moves to `processed/`.

### Adding a new adapter

1. Create `adapters/<name>.py` with a `main()` that reads env vars, imports from `lib/`, and syncs
2. Add credential env var to `.env.example`
3. Add `<NAME>_SCHEDULE` to `run.sh` crontab generation with a default
4. Add the env var export to `run.sh`'s env dump
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add atomic-ingest section to CLAUDE.md"
```

---

### Task 12: Run all tests and verify

- [ ] **Step 1: Install test dependencies and run full suite**

```bash
cd atomic-ingest && pip install -r requirements.txt && pip install pytest
python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 2: Verify Dockerfile builds**

```bash
cd atomic-ingest && docker build -t atomic-ingest-test .
```

Expected: build succeeds.

- [ ] **Step 3: Verify run.sh generates crontab correctly**

```bash
docker run --rm \
  -v "$(pwd)/test-options.json:/data/options.json" \
  atomic-ingest-test \
  bash -c "cat /etc/cron.d/atomic-ingest"
```

Where `test-options.json` contains:
```json
{"atomic_api_url": "http://test:8081", "atomic_api_token": "at_test", "log_level": "info"}
```

Expected: three crontab entries with correct schedules.
