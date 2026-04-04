"""Configuration loading from HA options.json and environment variables."""

import json
import os
from dataclasses import dataclass, field


@dataclass
class Config:
    youtube_cookies: str = "/share/youtube-sorter/cookies.txt"
    playlist_ids: list[str] = field(default_factory=list)
    anthropic_api_key: str = ""
    categories: list[str] = field(default_factory=list)
    schedule_cron: str = "0 */6 * * *"
    date_sort_field: str = "date_added"
    date_sort_order: str = "desc"
    watch_threshold: int = 90
    create_sublists: bool = False
    db_path: str = "/data/youtube_sorter.db"


def load_config(options_path: str, db_path: str) -> Config:
    """Load config from options.json, with env var overrides for scalars."""
    config = Config(db_path=db_path)

    if os.path.exists(options_path):
        with open(options_path) as f:
            opts = json.load(f)
        config.playlist_ids = [p for p in opts.get("playlist_ids", []) if p]
        config.categories = [c for c in opts.get("categories", []) if c]
        config.anthropic_api_key = opts.get("anthropic_api_key", "")
        config.youtube_cookies = opts.get("youtube_cookies", config.youtube_cookies)
        config.schedule_cron = opts.get("schedule_cron", config.schedule_cron)
        config.date_sort_field = opts.get("date_sort_field", config.date_sort_field)
        config.date_sort_order = opts.get("date_sort_order", config.date_sort_order)
        config.watch_threshold = opts.get("watch_threshold", config.watch_threshold)
        config.create_sublists = opts.get("create_sublists", config.create_sublists)

    # Env var overrides for scalars
    for env_key in ["youtube_cookies", "anthropic_api_key", "schedule_cron",
                    "date_sort_field", "date_sort_order"]:
        val = os.environ.get(env_key.upper()) or os.environ.get(env_key)
        if val:
            setattr(config, env_key, val)

    wt = os.environ.get("WATCH_THRESHOLD") or os.environ.get("watch_threshold")
    if wt:
        config.watch_threshold = int(wt)

    return config
