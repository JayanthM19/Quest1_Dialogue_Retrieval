from __future__ import annotations

import shutil
import time
from pathlib import Path
from urllib.parse import urlparse


class AcquisitionError(RuntimeError):
    """Raised when a video cannot be acquired."""


def is_web_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _remove_previous_downloads(download_dir: Path, *, keep: Path) -> None:
    """Keep only the latest successfully acquired URL video in this directory."""
    keep = keep.resolve()
    for candidate in download_dir.iterdir():
        if not candidate.is_file() or candidate.resolve() == keep:
            continue
        if not (candidate.name.startswith("source-") or candidate.name.startswith("source.")):
            continue
        try:
            candidate.unlink()
        except OSError as exc:
            raise AcquisitionError(
                f"Downloaded the new video but could not remove the previous "
                f"download '{candidate}': {exc}"
            ) from exc


def acquire_video(
    source: str,
    download_dir: Path,
    *,
    format_selector: str = (
        "best[ext=mp4][acodec!=none][vcodec!=none]/"
        "best[acodec!=none][vcodec!=none]/"
        "bestvideo[height<=720]+bestaudio/bestvideo+bestaudio/best"
    ),
    no_check_certificates: bool = False,
) -> Path:
    """Return a local video path, downloading a URL when necessary."""
    local = Path(source).expanduser()
    if local.is_file():
        return local.resolve()

    if not is_web_url(source):
        raise AcquisitionError(
            f"Source is neither an existing file nor an HTTP(S) URL: {source}"
        )

    download_dir.mkdir(parents=True, exist_ok=True)

    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError
    except ImportError as exc:  # pragma: no cover - dependency/setup failure
        raise AcquisitionError(
            "yt-dlp is not installed. Run: python -m pip install -e ."
        ) from exc

    options = {
        # Prefer a progressive stream containing both audio and video. This keeps
        # speech mode functional without requiring an external ffmpeg merger.
        "format": format_selector,
        # Include the extractor's stable video ID in the filename. A fixed
        # ``source.ext`` name makes yt-dlp treat an older, unrelated download as
        # the requested video when the same output directory is reused.
        "outtmpl": str(download_dir / "source-%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "overwrites": False,
        "continuedl": True,
        "nocheckcertificate": no_check_certificates,
        "extractor_retries": 5,
        "retries": 5,
        "fragment_retries": 5,
        "file_access_retries": 3,
        "merge_output_format": "mkv",
    }
    # Modern YouTube extraction needs an external JavaScript runtime. Prefer a
    # compatible Node installation automatically when one is on PATH.
    if node_path := shutil.which("node"):
        options["js_runtimes"] = {"node": {"path": node_path}}
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        options["ffmpeg_location"] = get_ffmpeg_exe()
    except ImportError:
        # Progressive formats still work. Split audio/video formats will produce
        # a clear yt-dlp setup error instead of failing package import entirely.
        pass

    last_error: DownloadError | None = None
    path: Path | None = None
    video_id: str | None = None
    for attempt in range(1, 4):
        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(source, download=True)
                video_id = str(info.get("id") or "").strip() or None
                requested = info.get("requested_downloads") or []
                candidate = requested[0].get("filepath") if requested else None
                path = Path(candidate or ydl.prepare_filename(info))
            break
        except DownloadError as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(attempt)

    if path is None:
        raise AcquisitionError(f"Could not download the video: {last_error}") from last_error

    if not path.is_file():
        expected_stem = f"source-{video_id}" if video_id else None
        matches = sorted(
            candidate
            for candidate in download_dir.iterdir()
            if candidate.is_file()
            and expected_stem is not None
            and candidate.stem == expected_stem
        )
        if not matches:
            raise AcquisitionError("The downloader finished but no video file was found.")
        path = matches[0]

    path = path.resolve()
    # Delete older managed downloads only after the new video is available. A
    # failed URL request therefore never destroys the last working download.
    _remove_previous_downloads(download_dir, keep=path)
    return path
