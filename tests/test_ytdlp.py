# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from pathlib import Path

from tubepocket.models import CookieConfig, CookieMode, DownloadMode, DownloadSelection, MediaFormat, SubtitleItem, SubtitleOutput
from tubepocket.ytdlp import (
    FILENAME_TEMPLATE,
    cookie_args,
    download_args,
    finalize_plain_text_subtitle,
    metadata_args,
    subtitle_download_dir,
    subtitle_file_to_plain_text,
    yt_dlp_ejs_status,
)


def test_cookie_args() -> None:
    assert cookie_args(CookieConfig()) == []
    assert cookie_args(CookieConfig(mode=CookieMode.BROWSER, browser="edge")) == ["--cookies-from-browser", "edge"]
    assert cookie_args(CookieConfig(mode=CookieMode.FILE, cookies_path="C:/tmp/cookies.txt")) == [
        "--cookies",
        "C:/tmp/cookies.txt",
    ]


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


def test_metadata_args_does_not_precheck_cookie_file() -> None:
    args = metadata_args(
        "https://www.youtube.com/watch?v=abc123",
        CookieConfig(mode=CookieMode.FILE, cookies_path="C:/missing/cookies.txt"),
    )

    assert args[3:5] == ["--cookies", "C:/missing/cookies.txt"]


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


def test_subtitle_text_download_converts_to_srt_first(tmp_path: Path) -> None:
    selection = DownloadSelection(
        mode=DownloadMode.SUBTITLE,
        url="https://www.youtube.com/watch?v=abc123",
        subtitle=SubtitleItem(lang="en", automatic=False),
        subtitle_output=SubtitleOutput.TEXT,
        output_dir=tmp_path,
    )

    args = download_args(selection)

    assert args[args.index("--convert-subs") + 1] == "srt"
    assert Path(args[args.index("-P") + 1]) == subtitle_download_dir(selection)
    assert Path(args[args.index("-P") + 1]) != tmp_path


def test_subtitle_file_to_plain_text_removes_timing_and_markup(tmp_path: Path) -> None:
    source = tmp_path / "sample.en.srt"
    source.write_text(
        "\n".join(
            [
                "1",
                "00:00:00,000 --> 00:00:01,000",
                "<b>Hello</b>",
                "",
                "2",
                "00:00:01,000 --> 00:00:02,000",
                "Hello",
                "",
                "3",
                "00:00:02,000 --> 00:00:03,000",
                "world",
            ]
        ),
        encoding="utf-8",
    )

    assert subtitle_file_to_plain_text(source) == "Hello\nworld\n"


def test_finalize_plain_text_subtitle_writes_txt(tmp_path: Path) -> None:
    selection = DownloadSelection(
        mode=DownloadMode.SUBTITLE,
        url="https://www.youtube.com/watch?v=abc123",
        subtitle=SubtitleItem(lang="en", automatic=False),
        subtitle_output=SubtitleOutput.TEXT,
        video_id="abc123",
        output_dir=tmp_path,
    )
    source_dir = subtitle_download_dir(selection)
    source_dir.mkdir(parents=True, exist_ok=True)
    source = source_dir / "Uploader - Title [abc123].en.srt"
    source.write_text("1\n00:00:00,000 --> 00:00:01,000\nLine\n", encoding="utf-8")

    target = finalize_plain_text_subtitle(selection)

    assert target == tmp_path / "Uploader - Title [abc123].en.txt"
    assert target.read_text(encoding="utf-8") == "Line\n"
    assert not source.exists()
    assert not list(tmp_path.glob("*.srt"))


def test_yt_dlp_ejs_status_detects_uv_tool_package(tmp_path: Path) -> None:
    site_packages = tmp_path / "uv" / "tools" / "yt-dlp" / "Lib" / "site-packages"
    (site_packages / "yt_dlp_ejs").mkdir(parents=True)

    status = yt_dlp_ejs_status(
        yt_dlp_path=str(tmp_path / ".local" / "bin" / "yt-dlp.exe"),
        appdata=str(tmp_path),
        userprofile=str(tmp_path),
    )

    assert status == "✅ yt-dlp-ejs installed"


def test_yt_dlp_ejs_status_warns_for_uv_tool_without_package(tmp_path: Path) -> None:
    (tmp_path / "uv" / "tools" / "yt-dlp" / "Lib" / "site-packages").mkdir(parents=True)

    status = yt_dlp_ejs_status(
        yt_dlp_path=str(tmp_path / ".local" / "bin" / "yt-dlp.exe"),
        appdata=str(tmp_path),
        userprofile=str(tmp_path),
    )

    assert status == "⚠️ yt-dlp-ejs not found; install yt-dlp[default]"


def test_yt_dlp_ejs_status_is_unknown_for_release_exe(tmp_path: Path) -> None:
    status = yt_dlp_ejs_status(
        yt_dlp_path=str(tmp_path / "yt-dlp.exe"),
        appdata=str(tmp_path / "missing"),
        userprofile=str(tmp_path / "profile"),
    )

    assert status == "ℹ️ Unknown; official exe may bundle EJS"
