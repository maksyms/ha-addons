from pathlib import Path
from lib.folder_consumer import consume


def test_yields_matching_files(tmp_path):
    consume_dir = tmp_path / "consume"
    processed_dir = tmp_path / "processed"
    consume_dir.mkdir()
    processed_dir.mkdir()

    (consume_dir / "notes.enex").write_text("<xml>data</xml>")
    (consume_dir / "readme.txt").write_text("ignore me")

    results = list(consume(consume_dir, processed_dir, "*.enex"))
    assert len(results) == 1
    assert results[0][0].name == "notes.enex"


def test_mark_done_moves_file(tmp_path):
    consume_dir = tmp_path / "consume"
    processed_dir = tmp_path / "processed"
    consume_dir.mkdir()
    processed_dir.mkdir()

    (consume_dir / "notes.enex").write_text("<xml>data</xml>")

    for file_path, mark_done in consume(consume_dir, processed_dir, "*.enex"):
        mark_done()

    assert not (consume_dir / "notes.enex").exists()
    assert (processed_dir / "notes.enex").exists()


def test_empty_consume_dir_yields_nothing(tmp_path):
    consume_dir = tmp_path / "consume"
    processed_dir = tmp_path / "processed"
    consume_dir.mkdir()
    processed_dir.mkdir()

    results = list(consume(consume_dir, processed_dir, "*.enex"))
    assert results == []


def test_mark_done_handles_duplicate_filename(tmp_path):
    consume_dir = tmp_path / "consume"
    processed_dir = tmp_path / "processed"
    consume_dir.mkdir()
    processed_dir.mkdir()

    (processed_dir / "notes.enex").write_text("old")
    (consume_dir / "notes.enex").write_text("new")

    for file_path, mark_done in consume(consume_dir, processed_dir, "*.enex"):
        mark_done()

    assert (processed_dir / "notes.enex").read_text() == "new"
