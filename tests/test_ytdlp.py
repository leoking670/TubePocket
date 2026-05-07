# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from pathlib import Path

from tubepocket.models import CookieConfig, CookieMode, DownloadMode, DownloadSelection, MediaFormat, SubtitleItem, SubtitleOutput
from tubepocket.ytdlp import (
    FILENAME_TEMPLATE,
    ProcessResult,
    cookie_args,
    download_args,
    metadata_args,
    summarize_ytdlp_error,
    validate_cookie_config,
)


def test_cookie_args() -> None:
    assert cookie_args(CookieConfig()) == []
    assert cookie_args(CookieConfig(mode=CookieMode.BROWSER, browser="edge")) == ["--cookies-from-browser", "edge"]
    assert cookie_args(CookieConfig(mode=CookieMode.FILE, cookies_path="C:/tmp/cookies.txt")) == [
        "--cookies",
        "C:/tmp/cookies.txt",
    ]


def test_validate_cookie_config() -> None:
    assert validate_cookie_config(CookieConfig()) == []
    assert validate_cookie_config(CookieConfig(mode=CookieMode.BROWSER, browser="edge")) == []
    assert validate_cookie_config(CookieConfig(mode=CookieMode.BROWSER, browser="unknown"))
    assert validate_cookie_config(CookieConfig(mode=CookieMode.FILE, cookies_path=""))
    assert validate_cookie_config(CookieConfig(mode=CookieMode.FILE, cookies_path="C:/missing/cookies.txt"))


def test_validate_cookie_file_exists(tmp_path: Path) -> None:
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")

    assert validate_cookie_config(CookieConfig(mode=CookieMode.FILE, cookies_path=str(cookies))) == []


def test_metadata_args_uses_argument_list() -> None:
    args = metadata_args("https://www.youtube.com/watch?v=abc123", CookieConfig(mode=CookieMode.BROWSER, browser="chrome"))

    assert args == [
        "yt-dlp",
        "--dump-single-json",
        "--no-playlist",
        "--cookies-from-browser",
        "chrome",
        "https://www.youtube.com/watch?v=abc123",
    ]


def test_video_download_combines_video_only_with_audio(tmp_path: Path) -> None:
    selection = DownloadSelection(
        mode=DownloadMode.VIDEO,
        url="https://www.youtube.com/watch?v=abc123",
        video_format=MediaFormat(format_id="137", ext="mp4", vcodec="avc1", acodec="none"),
        audio_format=MediaFormat(format_id="140", ext="m4a", vcodec="none", acodec="mp4a.40.2"),
        output_dir=tmp_path,
    )

    args = download_args(selection)

    assert "-f" in args
    assert args[args.index("-f") + 1] == "137+140"
    assert args[args.index("-o") + 1] == FILENAME_TEMPLATE
    assert args[-1] == selection.url


def test_video_download_uses_combined_format_directly(tmp_path: Path) -> None:
    selection = DownloadSelection(
        mode=DownloadMode.VIDEO,
        url="https://www.youtube.com/watch?v=abc123",
        video_format=MediaFormat(format_id="18", ext="mp4", vcodec="avc1", acodec="mp4a.40.2"),
        output_dir=tmp_path,
    )

    args = download_args(selection)

    assert args[args.index("-f") + 1] == "18"


def test_audio_download_uses_selected_audio(tmp_path: Path) -> None:
    selection = DownloadSelection(
        mode=DownloadMode.AUDIO,
        url="https://www.youtube.com/watch?v=abc123",
        audio_format=MediaFormat(format_id="140", ext="m4a", vcodec="none", acodec="mp4a.40.2"),
        output_dir=tmp_path,
    )

    args = download_args(selection)

    assert args[args.index("-f") + 1] == "140"


def test_subtitle_download_uploaded_and_convert(tmp_path: Path) -> None:
    selection = DownloadSelection(
        mode=DownloadMode.SUBTITLE,
        url="https://www.youtube.com/watch?v=abc123",
        subtitle=SubtitleItem(lang="ja", automatic=False),
        subtitle_output=SubtitleOutput.SRT,
        output_dir=tmp_path,
    )

    args = download_args(selection)

    assert "--skip-download" in args
    assert "--write-subs" in args
    assert "--write-auto-subs" not in args
    assert args[args.index("--sub-langs") + 1] == "ja"
    assert args[args.index("--convert-subs") + 1] == "srt"


def test_subtitle_download_auto_original(tmp_path: Path) -> None:
    selection = DownloadSelection(
        mode=DownloadMode.SUBTITLE,
        url="https://www.youtube.com/watch?v=abc123",
        subtitle=SubtitleItem(lang="en", automatic=True),
        subtitle_output=SubtitleOutput.ORIGINAL,
        output_dir=tmp_path,
    )

    args = download_args(selection)

    assert "--write-auto-subs" in args
    assert "--convert-subs" not in args


def test_summarize_ytdlp_error_keeps_dialog_short() -> None:
    stderr = "\n".join(
        [
            "WARNING: [youtube] Download failed: [SSL: UNEXPECTED_EOF_WHILE_READING]",
            "WARNING: [youtube] Remote components challenge solver script was skipped",
            "ERROR: [youtube] abc123: Requested format is not available. Only images are available for download",
        ]
    )

    summary = summarize_ytdlp_error(ProcessResult(1, "", stderr))

    assert "Network/TLS failed" in summary
    assert "YouTube JS challenge solving failed" in summary
    assert "requested media format" in summary
    assert "image/storyboard formats" in summary
    assert len(summary.splitlines()) == 4
