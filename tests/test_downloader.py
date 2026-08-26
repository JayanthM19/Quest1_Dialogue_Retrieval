import sys
from pathlib import Path
from types import ModuleType

import pytest

from framefinder.downloader import AcquisitionError, acquire_video


def test_url_downloads_use_video_id_in_filename(monkeypatch, tmp_path: Path) -> None:
    captured_options: dict = {}
    previous = tmp_path / "source-old-video.mp4"
    legacy_previous = tmp_path / "source.mkv"
    unrelated = tmp_path / "keep-me.txt"
    previous.write_bytes(b"old video")
    legacy_previous.write_bytes(b"legacy video")
    unrelated.write_text("not managed by the downloader", encoding="utf-8")

    class FakeYoutubeDL:
        def __init__(self, options: dict) -> None:
            captured_options.update(options)
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def extract_info(self, source: str, download: bool) -> dict:
            assert source == "https://example.com/watch?v=new-video"
            assert download is True
            downloaded = tmp_path / "source-new-video.mp4"
            downloaded.write_bytes(b"video")
            return {
                "id": "new-video",
                "ext": "mp4",
                "requested_downloads": [{"filepath": str(downloaded)}],
            }

        def prepare_filename(self, info: dict) -> str:
            return str(tmp_path / f"source-{info['id']}.{info['ext']}")

    yt_dlp = ModuleType("yt_dlp")
    yt_dlp.YoutubeDL = FakeYoutubeDL
    yt_dlp_utils = ModuleType("yt_dlp.utils")
    yt_dlp_utils.DownloadError = RuntimeError
    monkeypatch.setitem(sys.modules, "yt_dlp", yt_dlp)
    monkeypatch.setitem(sys.modules, "yt_dlp.utils", yt_dlp_utils)
    monkeypatch.setattr("framefinder.downloader.shutil.which", lambda _: None)

    result = acquire_video(
        "https://example.com/watch?v=new-video",
        tmp_path,
    )

    assert result == (tmp_path / "source-new-video.mp4").resolve()
    assert captured_options["outtmpl"] == str(tmp_path / "source-%(id)s.%(ext)s")
    assert result.is_file()
    assert not previous.exists()
    assert not legacy_previous.exists()
    assert unrelated.is_file()


def test_failed_download_preserves_previous_video(monkeypatch, tmp_path: Path) -> None:
    previous = tmp_path / "source-old-video.mp4"
    previous.write_bytes(b"old video")

    class FailingYoutubeDL:
        def __init__(self, options: dict) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def extract_info(self, source: str, download: bool) -> dict:
            raise RuntimeError("network unavailable")

    yt_dlp = ModuleType("yt_dlp")
    yt_dlp.YoutubeDL = FailingYoutubeDL
    yt_dlp_utils = ModuleType("yt_dlp.utils")
    yt_dlp_utils.DownloadError = RuntimeError
    monkeypatch.setitem(sys.modules, "yt_dlp", yt_dlp)
    monkeypatch.setitem(sys.modules, "yt_dlp.utils", yt_dlp_utils)
    monkeypatch.setattr("framefinder.downloader.shutil.which", lambda _: None)
    monkeypatch.setattr("framefinder.downloader.time.sleep", lambda _: None)

    with pytest.raises(AcquisitionError, match="Could not download the video"):
        acquire_video("https://example.com/watch?v=new-video", tmp_path)

    assert previous.is_file()


def test_existing_local_file_is_returned_without_downloader(tmp_path: Path) -> None:
    source = tmp_path / "local.mp4"
    source.write_bytes(b"video")

    assert acquire_video(str(source), tmp_path / "downloads") == source.resolve()
