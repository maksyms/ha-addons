import os
import pytest
from lib.limit import get_limit


class TestGetLimit:
    def setup_method(self):
        os.environ.pop("INGEST_LIMIT", None)
        os.environ.pop("RAINDROP_LIMIT", None)
        os.environ.pop("READWISE_LIMIT", None)

    def teardown_method(self):
        os.environ.pop("INGEST_LIMIT", None)
        os.environ.pop("RAINDROP_LIMIT", None)
        os.environ.pop("READWISE_LIMIT", None)

    def test_returns_none_by_default(self):
        assert get_limit("raindrop") is None

    def test_global_limit(self):
        os.environ["INGEST_LIMIT"] = "5"
        assert get_limit("raindrop") == 5

    def test_adapter_limit_overrides_global(self):
        os.environ["INGEST_LIMIT"] = "5"
        os.environ["RAINDROP_LIMIT"] = "10"
        assert get_limit("raindrop") == 10

    def test_adapter_limit_without_global(self):
        os.environ["RAINDROP_LIMIT"] = "3"
        assert get_limit("raindrop") == 3

    def test_empty_string_treated_as_unset(self):
        os.environ["INGEST_LIMIT"] = ""
        assert get_limit("raindrop") is None

    def test_whitespace_treated_as_unset(self):
        os.environ["INGEST_LIMIT"] = "  "
        assert get_limit("raindrop") is None

    def test_different_adapter_names(self):
        os.environ["READWISE_LIMIT"] = "7"
        assert get_limit("readwise") == 7
        assert get_limit("raindrop") is None
