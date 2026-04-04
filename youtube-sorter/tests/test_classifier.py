"""Tests for video classification."""

import json
from unittest.mock import patch, MagicMock
from sorter.classifier import classify_videos, VideoMetadata


def make_video(vid: str, title: str, desc: str = "", tags: list[str] | None = None):
    return VideoMetadata(video_id=vid, title=title, description=desc, tags=tags or [])


CATEGORIES = ["Claude & AI", "Science", "Other"]


def fake_anthropic_response(content_text: str):
    """Build a mock Anthropic API response."""
    msg = MagicMock()
    block = MagicMock()
    block.text = content_text
    msg.content = [block]
    msg.stop_reason = "end_turn"
    return msg


@patch("sorter.classifier.anthropic.Anthropic")
def test_classify_single_video(mock_anthropic_class):
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    mock_client.messages.create.return_value = fake_anthropic_response(
        json.dumps([{"video_id": "v1", "category": "Science", "confidence": 0.92}])
    )

    videos = [make_video("v1", "Quantum Computing Explained")]
    results = classify_videos(videos, CATEGORIES, api_key="test-key")

    assert len(results) == 1
    assert results["v1"].category == "Science"
    assert results["v1"].confidence == 0.92


@patch("sorter.classifier.anthropic.Anthropic")
def test_classify_batch(mock_anthropic_class):
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    mock_client.messages.create.return_value = fake_anthropic_response(
        json.dumps([
            {"video_id": "v1", "category": "Claude & AI", "confidence": 0.95},
            {"video_id": "v2", "category": "Science", "confidence": 0.88},
        ])
    )

    videos = [
        make_video("v1", "Claude 4 Release Notes"),
        make_video("v2", "CRISPR Gene Editing"),
    ]
    results = classify_videos(videos, CATEGORIES, api_key="test-key")

    assert len(results) == 2
    assert results["v1"].category == "Claude & AI"
    assert results["v2"].category == "Science"


@patch("sorter.classifier.anthropic.Anthropic")
def test_low_confidence_falls_back_to_other(mock_anthropic_class):
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    mock_client.messages.create.return_value = fake_anthropic_response(
        json.dumps([{"video_id": "v1", "category": "Science", "confidence": 0.3}])
    )

    videos = [make_video("v1", "Random vlog about nothing")]
    results = classify_videos(videos, CATEGORIES, api_key="test-key")

    assert results["v1"].category == "Other"


@patch("sorter.classifier.anthropic.Anthropic")
def test_invalid_category_falls_back_to_other(mock_anthropic_class):
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    mock_client.messages.create.return_value = fake_anthropic_response(
        json.dumps([{"video_id": "v1", "category": "Cooking", "confidence": 0.9}])
    )

    videos = [make_video("v1", "Gordon Ramsay recipe")]
    results = classify_videos(videos, CATEGORIES, api_key="test-key")

    assert results["v1"].category == "Other"
