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

        Safe to call mid-sync — holds exclusive lock across read-modify-write.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0)
                try:
                    data = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    data = {}
                data[adapter_name] = state
                f.seek(0)
                f.truncate()
                json.dump(data, f, indent=2)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

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
