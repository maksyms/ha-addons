# youtube-sorter/sorter/web.py
"""Flask web UI — read-only database view and trigger endpoint."""

import os
import threading

from flask import Flask, jsonify, send_from_directory

from sorter.config import Config
from sorter.database import Database


def create_app(config: Config, db: Database) -> Flask:
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    app = Flask(__name__, static_folder=static_dir)

    @app.route("/")
    def index():
        return send_from_directory(static_dir, "index.html")

    @app.route("/api/videos")
    def api_videos():
        videos = db.get_all_videos()
        return jsonify({"videos": videos})

    @app.route("/api/runs")
    def api_runs():
        runs = db.get_recent_runs()
        return jsonify({"runs": runs})

    @app.route("/api/trigger", methods=["POST"])
    def api_trigger():
        trigger_fn = app.config.get("trigger_fn")
        if trigger_fn:
            threading.Thread(target=trigger_fn, daemon=True).start()
        return jsonify({"status": "accepted"}), 202

    return app
