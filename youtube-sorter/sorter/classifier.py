"""Video classification using Anthropic API."""

import json
import logging
from dataclasses import dataclass

import anthropic

logger = logging.getLogger(__name__)

BATCH_SIZE = 15
CONFIDENCE_THRESHOLD = 0.5
MODEL = "claude-sonnet-4-6-20250514"


@dataclass
class VideoMetadata:
    video_id: str
    title: str
    description: str = ""
    tags: list[str] | None = None


@dataclass
class Classification:
    category: str
    confidence: float


def _build_system_prompt(categories: list[str]) -> str:
    cat_list = "\n".join(f"- {c}" for c in categories)
    return f"""You are a video classifier. Classify each video into exactly one of these categories:

{cat_list}

Respond with a JSON array. Each element must have:
- "video_id": the video ID provided
- "category": one of the exact category names above
- "confidence": a float from 0.0 to 1.0

If you are unsure, use a low confidence score. Only output valid JSON, no other text."""


def _build_user_prompt(videos: list[VideoMetadata]) -> str:
    items = []
    for v in videos:
        entry = f"Video ID: {v.video_id}\nTitle: {v.title}"
        if v.description:
            desc = v.description[:500]
            entry += f"\nDescription: {desc}"
        if v.tags:
            entry += f"\nTags: {', '.join(v.tags[:20])}"
        items.append(entry)
    return "\n\n---\n\n".join(items)


def _parse_response(text: str, categories: list[str],
                    videos: list[VideoMetadata]) -> dict[str, Classification]:
    """Parse the AI response, falling back to 'Other' for invalid entries."""
    valid_categories = set(categories)
    if "Other" not in valid_categories:
        valid_categories.add("Other")

    results = {}
    try:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error("Failed to parse classifier response as JSON: %s", text[:200])
        for v in videos:
            results[v.video_id] = Classification(category="Other", confidence=0.0)
        return results

    parsed = {item["video_id"]: item for item in data if "video_id" in item}
    for v in videos:
        item = parsed.get(v.video_id)
        if not item:
            results[v.video_id] = Classification(category="Other", confidence=0.0)
            continue

        category = item.get("category", "Other")
        confidence = float(item.get("confidence", 0.0))

        if category not in valid_categories or confidence < CONFIDENCE_THRESHOLD:
            category = "Other"

        results[v.video_id] = Classification(category=category, confidence=confidence)

    return results


def classify_videos(videos: list[VideoMetadata], categories: list[str],
                    api_key: str, model: str = MODEL) -> dict[str, Classification]:
    """Classify videos into categories. Batches automatically."""
    if not videos:
        return {}

    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = _build_system_prompt(categories)
    all_results: dict[str, Classification] = {}

    for i in range(0, len(videos), BATCH_SIZE):
        batch = videos[i:i + BATCH_SIZE]
        user_prompt = _build_user_prompt(batch)

        try:
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = response.content[0].text
            batch_results = _parse_response(text, categories, batch)
            all_results.update(batch_results)
        except Exception as e:
            logger.error("Classification API call failed: %s", e)
            for v in batch:
                try:
                    single_prompt = _build_user_prompt([v])
                    resp = client.messages.create(
                        model=model,
                        max_tokens=256,
                        system=system_prompt,
                        messages=[{"role": "user", "content": single_prompt}],
                    )
                    single_results = _parse_response(resp.content[0].text, categories, [v])
                    all_results.update(single_results)
                except Exception as e2:
                    logger.error("Single classification failed for %s: %s", v.video_id, e2)
                    all_results[v.video_id] = Classification(category="Other", confidence=0.0)

    return all_results
