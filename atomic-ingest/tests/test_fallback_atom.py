import pytest
from lib.atomic_client import AtomicAPIError
from lib.fallback_atom import is_content_parse_error, format_fallback_atom


class TestIsContentParseError:
    def test_readability_failure_is_parse_error(self):
        err = AtomicAPIError(500, '{"error":"Ingestion error: Page is not article-shaped (failed readability check)"}')
        assert is_content_parse_error(err) is True

    def test_non_html_content_is_parse_error(self):
        err = AtomicAPIError(500, '{"error":"Ingestion error: Non-HTML content type: application/pdf"}')
        assert is_content_parse_error(err) is True

    def test_http_403_is_not_parse_error(self):
        err = AtomicAPIError(500, '{"error":"Ingestion error: HTTP 403 Forbidden for https://example.com"}')
        assert is_content_parse_error(err) is False

    def test_http_404_is_not_parse_error(self):
        err = AtomicAPIError(500, '{"error":"Ingestion error: HTTP 404 Not Found for https://example.com"}')
        assert is_content_parse_error(err) is False

    def test_http_530_is_not_parse_error(self):
        err = AtomicAPIError(500, '{"error":"Ingestion error: HTTP 530 <unknown status code> for https://example.com"}')
        assert is_content_parse_error(err) is False

    def test_non_500_error_is_not_parse_error(self):
        err = AtomicAPIError(409, '{"error":"Already exists"}')
        assert is_content_parse_error(err) is False

    def test_non_ingestion_500_is_not_parse_error(self):
        err = AtomicAPIError(500, '{"error":"Internal server error"}')
        assert is_content_parse_error(err) is False


class TestFormatFallbackAtom:
    def test_full_raindrop_metadata(self):
        content = format_fallback_atom(
            title="Example Site",
            source="example.com",
            type="link",
            tags=["rust", "programming"],
            summary="An example website about Rust programming.",
            notes="Check this out later",
        )
        assert content == (
            "# Example Site\n"
            "\n"
            "**Source:** example.com\n"
            "**Type:** link\n"
            "**Tags:** rust, programming\n"
            "\n"
            "## Summary\n"
            "An example website about Rust programming.\n"
            "\n"
            "## Notes\n"
            "Check this out later"
        )

    def test_readwise_metadata_with_author(self):
        content = format_fallback_atom(
            title="Deep Work",
            source="calnewport.com",
            author="Cal Newport",
            summary="A guide to focused work.",
        )
        assert content == (
            "# Deep Work\n"
            "\n"
            "**Source:** calnewport.com\n"
            "**Author:** Cal Newport\n"
            "\n"
            "## Summary\n"
            "A guide to focused work."
        )

    def test_title_only(self):
        content = format_fallback_atom(title="Bare Bookmark")
        assert content == "# Bare Bookmark"

    def test_omits_empty_sections(self):
        content = format_fallback_atom(
            title="Minimal",
            source="minimal.com",
        )
        assert content == (
            "# Minimal\n"
            "\n"
            "**Source:** minimal.com"
        )
        assert "## Summary" not in content
        assert "## Notes" not in content
        assert "**Tags:**" not in content

    def test_empty_tags_list_omitted(self):
        content = format_fallback_atom(title="No Tags", tags=[])
        assert "**Tags:**" not in content

    def test_empty_string_fields_omitted(self):
        content = format_fallback_atom(
            title="Test",
            source="",
            author="",
            summary="",
            notes="",
        )
        assert content == "# Test"
