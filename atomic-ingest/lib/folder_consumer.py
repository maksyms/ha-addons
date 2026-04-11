import shutil
from pathlib import Path
from typing import Callable, Iterator


def consume(
    consume_dir: Path,
    processed_dir: Path,
    glob_pattern: str,
) -> Iterator[tuple[Path, Callable]]:
    """Yield files matching pattern from consume_dir.

    For each file, yields (file_path, mark_done). Calling mark_done()
    moves the file to processed_dir.
    """
    for file_path in sorted(consume_dir.glob(glob_pattern)):
        if not file_path.is_file():
            continue

        def mark_done(fp=file_path):
            dest = processed_dir / fp.name
            shutil.move(str(fp), str(dest))

        yield file_path, mark_done
