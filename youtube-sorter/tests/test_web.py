# youtube-sorter/tests/test_web.py
import json
from sorter.web import create_app
from sorter.config import Config
from sorter.database import Database


def make_test_app():
    config = Config(db_path=":memory:")
    db = Database(":memory:")
    app = create_app(config, db)
    app.config["trigger_fn"] = lambda: None
    app.config["TESTING"] = True
    return app, db


def test_index_serves_html():
    app, _ = make_test_app()
    with app.test_client() as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"YouTube Sorter" in resp.data


def test_api_videos_returns_json():
    app, db = make_test_app()
    db.upsert_video("v1", "PL1", "Test", "", "[]", "Science", 0.9, "", "")
    with app.test_client() as client:
        resp = client.get("/api/videos")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["videos"]) == 1
        assert data["videos"][0]["video_id"] == "v1"


def test_api_runs_returns_json():
    app, db = make_test_app()
    run_id = db.log_run_start()
    db.log_run_end(run_id, status="success")
    with app.test_client() as client:
        resp = client.get("/api/runs")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["runs"]) == 1


def test_api_trigger_returns_accepted():
    app, _ = make_test_app()
    with app.test_client() as client:
        resp = client.post("/api/trigger")
        assert resp.status_code == 202
