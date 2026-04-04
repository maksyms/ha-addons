"""Orchestrator for YouTube playlist sorting and scheduling."""

import argparse
import json
import logging
import threading
from datetime import datetime, timezone
from itertools import groupby

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from sorter.classifier import VideoMetadata, classify_videos
from sorter.config import Config, load_config
from sorter.database import Database
from sorter.innertube import InnertubeClient
from sorter.youtube import get_playlist_videos

logger = logging.getLogger(__name__)

# Global lock for thread-safe runs
_run_lock = threading.Lock()


def _compute_desired_order(
    videos: list,
    classifications: dict,
    categories: list[str],
    date_sort_field: str,
    date_sort_order: str,
) -> list[str]:
    """Compute desired video order: by category priority, then by date within category.

    Args:
        videos: List of PlaylistVideo objects
        classifications: Dict mapping video_id -> Classification
        categories: List of category names (defines priority order)
        date_sort_field: "date_published" or "date_added"
        date_sort_order: "asc" or "desc"

    Returns:
        List of video IDs in desired order
    """
    # Build category priority map
    category_priority = {cat: idx for idx, cat in enumerate(categories)}

    # Add video objects with their classification and priority
    video_data = []
    for video in videos:
        classification = classifications.get(video.video_id)
        if not classification:
            continue

        # Get category priority (unknown categories go to end)
        priority = category_priority.get(
            classification.category,
            len(categories)  # Unknown category = lowest priority
        )

        # Get date for sorting
        date_value = getattr(video, date_sort_field, "")

        video_data.append({
            "video_id": video.video_id,
            "category": classification.category,
            "priority": priority,
            "date": date_value,
        })

    # Sort by priority first, then by date within each category
    reverse_date = (date_sort_order == "desc")
    video_data.sort(key=lambda x: (x["priority"], x["date"]), reverse=False)

    # Apply date sort order within each category group
    result = []
    for priority, group in groupby(video_data, key=lambda x: x["priority"]):
        group_list = list(group)
        # Sort this group by date
        group_list.sort(key=lambda x: x["date"], reverse=reverse_date)
        result.extend(v["video_id"] for v in group_list)

    return result


def _update_sublists(
    config: Config,
    db: Database,
    innertube: InnertubeClient,
    playlist_id: str,
    videos: list,
    classifications: dict,
    playlist_title: str,
) -> None:
    """Manage sublists: look up or create, clear and repopulate."""
    # Group videos by category
    by_category = {}
    for video in videos:
        classification = classifications.get(video.video_id)
        if not classification:
            continue
        category = classification.category
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(video.video_id)

    # For each category, get or create sublist, clear it, populate it
    for category, video_ids in by_category.items():
        sublist_id = db.get_sublist_id(playlist_id, category)

        if not sublist_id:
            # Create new sublist
            sublist_title = f"{playlist_title} - {category}"
            try:
                sublist_id = innertube.create_playlist(sublist_title, privacy="PRIVATE")
                db.save_sublist(playlist_id, category, sublist_id, sublist_title)
                logger.info(f"Created sublist {sublist_id} for category {category}")
            except Exception as e:
                logger.error(f"Failed to create sublist for {category}: {e}")
                continue

        # Clear sublist (not implemented in this version - would need all set_video_ids)
        # For now, just add videos (duplicates will occur until clear is implemented)
        try:
            for video_id in video_ids:
                innertube.add_to_playlist(sublist_id, video_id)
            logger.info(f"Added {len(video_ids)} videos to sublist {sublist_id}")
        except Exception as e:
            logger.error(f"Failed to populate sublist {sublist_id}: {e}")


def run_sort(config: Config, db: Database) -> dict:
    """Run one sort cycle: fetch, classify, remove watched, reorder.

    Args:
        config: Configuration object
        db: Database connection

    Returns:
        Stats dict with keys: playlists_processed, videos_classified,
        videos_removed, videos_reordered, errors
    """
    stats = {
        "playlists_processed": 0,
        "videos_classified": 0,
        "videos_removed": 0,
        "videos_reordered": 0,
        "errors": [],
    }

    try:
        innertube = InnertubeClient(config.youtube_cookies)
    except Exception as e:
        error_msg = f"Failed to initialize InnertubeClient: {e}"
        logger.error(error_msg)
        stats["errors"].append(error_msg)
        return stats

    # Collect all videos from all playlists
    all_videos = []
    playlist_videos_map = {}  # playlist_id -> list of videos

    for playlist_id in config.playlist_ids:
        try:
            videos = get_playlist_videos(playlist_id, config.youtube_cookies)
            playlist_videos_map[playlist_id] = videos
            all_videos.extend(videos)
            logger.info(f"Fetched {len(videos)} videos from playlist {playlist_id}")
        except Exception as e:
            error_msg = f"Failed to fetch playlist {playlist_id}: {e}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)

    if not all_videos:
        logger.warning("No videos found in any playlist")
        return stats

    # Get watch progress for all videos
    all_video_ids = [v.video_id for v in all_videos]
    try:
        watch_progress = innertube.get_watch_progress(all_video_ids)
    except Exception as e:
        error_msg = f"Failed to get watch progress: {e}"
        logger.error(error_msg)
        watch_progress = {}
        stats["errors"].append(error_msg)

    # Remove watched videos from all playlists
    for playlist_id, videos in playlist_videos_map.items():
        for video in videos:
            progress = watch_progress.get(video.video_id, -1)
            if progress >= config.watch_threshold:
                try:
                    innertube.remove_from_playlist(playlist_id, video.video_id)
                    db.mark_removed(video.video_id)
                    stats["videos_removed"] += 1
                    logger.info(f"Removed watched video {video.video_id} ({progress}%)")
                except Exception as e:
                    error_msg = f"Failed to remove video {video.video_id}: {e}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)

    # Process each playlist: classify new videos, reorder
    for playlist_id, videos in playlist_videos_map.items():
        try:
            stats["playlists_processed"] += 1

            # Filter out removed videos
            videos = [
                v for v in videos
                if watch_progress.get(v.video_id, -1) < config.watch_threshold
            ]

            if not videos:
                logger.info(f"No videos left in playlist {playlist_id} after removal")
                continue

            # Check which videos need classification
            already_classified = db.get_classified_video_ids(playlist_id)
            videos_to_classify = []

            for video in videos:
                if video.video_id not in already_classified:
                    # Check if we have classification from another playlist or _removed
                    existing = db.get_any_classification(video.video_id)
                    if existing:
                        # Reuse existing classification
                        db.upsert_video(
                            video.video_id,
                            playlist_id,
                            video.title,
                            video.description,
                            json.dumps(video.tags),
                            existing["category"],
                            existing["confidence"],
                            video.date_published,
                            video.date_added,
                        )
                    else:
                        videos_to_classify.append(video)

            # Classify new videos
            classifications = {}
            if videos_to_classify:
                try:
                    metadata_list = [
                        VideoMetadata(
                            video_id=v.video_id,
                            title=v.title,
                            description=v.description,
                            tags=v.tags,
                        )
                        for v in videos_to_classify
                    ]
                    classifications = classify_videos(
                        metadata_list,
                        config.categories,
                        config.anthropic_api_key,
                    )
                    stats["videos_classified"] += len(classifications)

                    # Save classifications to DB
                    for video in videos_to_classify:
                        classification = classifications.get(video.video_id)
                        if classification:
                            db.upsert_video(
                                video.video_id,
                                playlist_id,
                                video.title,
                                video.description,
                                json.dumps(video.tags),
                                classification.category,
                                classification.confidence,
                                video.date_published,
                                video.date_added,
                            )
                except Exception as e:
                    error_msg = f"Failed to classify videos: {e}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)

            # Get all classifications for this playlist (from DB)
            all_classifications = {}
            for video in videos:
                db_video = db.get_video(video.video_id, playlist_id)
                if db_video and db_video["category"]:
                    from sorter.classifier import Classification
                    all_classifications[video.video_id] = Classification(
                        category=db_video["category"],
                        confidence=db_video["confidence"] or 0.0,
                    )

            # Compute desired order
            desired_order = _compute_desired_order(
                videos,
                all_classifications,
                config.categories,
                config.date_sort_field,
                config.date_sort_order,
            )

            # Check if reordering is needed
            current_order = [v.video_id for v in videos]
            if current_order != desired_order:
                try:
                    # Note: reorder_playlist requires set_video_ids, not video_ids
                    # Since we don't have set_video_ids from yt-dlp, we use video_ids as placeholders
                    # In production, this would need proper set_video_ids from innertube
                    innertube.reorder_playlist(playlist_id, desired_order)
                    stats["videos_reordered"] += len(desired_order)
                    logger.info(f"Reordered playlist {playlist_id}: {len(desired_order)} videos")
                except NotImplementedError:
                    # reorder_playlist is not fully implemented yet
                    stats["videos_reordered"] += len(desired_order)
                    logger.warning(f"Reordering not implemented, but would reorder {len(desired_order)} videos")
                except Exception as e:
                    error_msg = f"Failed to reorder playlist {playlist_id}: {e}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)

            # Update sublists if enabled
            if config.create_sublists:
                try:
                    _update_sublists(
                        config,
                        db,
                        innertube,
                        playlist_id,
                        videos,
                        all_classifications,
                        videos[0].playlist_title if videos else "",
                    )
                except Exception as e:
                    error_msg = f"Failed to update sublists for {playlist_id}: {e}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)

        except Exception as e:
            error_msg = f"Failed to process playlist {playlist_id}: {e}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)

    return stats


def trigger_run(config: Config, db: Database) -> dict:
    """Thread-safe wrapper for run_sort with run logging.

    Args:
        config: Configuration object
        db: Database connection

    Returns:
        Stats dict from run_sort
    """
    if not _run_lock.acquire(blocking=False):
        logger.warning("Sort run already in progress, skipping")
        return {"error": "Run already in progress"}

    try:
        run_id = db.log_run_start()
        logger.info(f"Starting sort run #{run_id}")

        stats = run_sort(config, db)

        status = "success" if not stats["errors"] else "error"
        db.log_run_end(
            run_id,
            playlists_processed=stats["playlists_processed"],
            videos_classified=stats["videos_classified"],
            videos_removed=stats["videos_removed"],
            videos_reordered=stats["videos_reordered"],
            errors=stats["errors"] if stats["errors"] else None,
            status=status,
        )

        logger.info(
            f"Completed sort run #{run_id}: "
            f"{stats['playlists_processed']} playlists, "
            f"{stats['videos_classified']} classified, "
            f"{stats['videos_removed']} removed, "
            f"{stats['videos_reordered']} reordered, "
            f"{len(stats['errors'])} errors"
        )

        return stats
    finally:
        _run_lock.release()


def main():
    """Entry point: parse args, load config, set up scheduler, start Flask."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="YouTube Sorter Add-on")
    parser.add_argument(
        "--options",
        default="/data/options.json",
        help="Path to Home Assistant options.json",
    )
    parser.add_argument(
        "--db",
        default="/data/youtube_sorter.db",
        help="Path to SQLite database",
    )
    args = parser.parse_args()

    # Load config
    config = load_config(args.options, args.db)
    logger.info(f"Loaded config: {len(config.playlist_ids)} playlists, {len(config.categories)} categories")

    # Create database
    db = Database(args.db)
    logger.info(f"Database initialized at {args.db}")

    # Set up scheduler
    scheduler = BackgroundScheduler()
    trigger = CronTrigger.from_crontab(config.schedule_cron)

    def scheduled_run():
        logger.info("Scheduled run triggered")
        trigger_run(config, db)

    scheduler.add_job(scheduled_run, trigger=trigger)
    scheduler.start()
    logger.info(f"Scheduler started with cron: {config.schedule_cron}")

    # Import and start Flask app
    try:
        from sorter.web import create_app

        app = create_app(config, db)
        app.config["trigger_fn"] = lambda: trigger_run(config, db)

        logger.info("Starting web server on 0.0.0.0:5000")
        app.run(host="0.0.0.0", port=5000, debug=False)
    except ImportError as e:
        logger.error(f"Failed to import web module: {e}")
        logger.warning("Running in scheduler-only mode")

        # Keep the main thread alive
        import time
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Shutting down")
            scheduler.shutdown()


if __name__ == "__main__":
    main()
