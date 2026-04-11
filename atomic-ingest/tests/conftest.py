import pytest
from pathlib import Path


@pytest.fixture
def tmp_state_file(tmp_path):
    """Return a path to a temporary sync state JSON file."""
    return str(tmp_path / "sync_state.json")
