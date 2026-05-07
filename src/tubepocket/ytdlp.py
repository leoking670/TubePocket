# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from tubepocket.formats import parse_video_info
from tubepocket.models import CookieConfig, CookieMode, DownloadMode, DownloadSelection, SubtitleOutput, VideoInfo


FILENAME_TEMPLATE = "%(uploader)s - %(title)s [%(id)s].%(ext)s"
SUPPORTED_COOKIE_BROWSERS = ["chrome", "edge", "firefox", "brave", "chromium", "opera", "vivaldi"]


@dataclass(slots=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class YtdlpError(RuntimeError):
    def __init__(self, message: str, result: ProcessResult | None = None) -> None:
        super().__init__(message)
        self.result = result


def tool_available(name: str) -> bool:
    return shutil.which(name) is not None


def metadata_args(url: str, cookies: CookieConfig) -> list[str]:
    issues = validate_cookie_config(cookies)
    if issues:
        raise ValueError("; ".join(issues))
    return ["yt-dlp", "--dump-single-json", "--no-playlist", *cookie_args(cookies), url]


def load_metadata(url: str, cookies: CookieConfig) -> tuple[VideoInfo, ProcessResult]:
    args = metadata_args(url, cookies)
    result = run_capture(args)
    if not result.ok:
        raise YtdlpError("yt-dlp metadata failed", result)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise YtdlpError(f"yt-dlp returned invalid JSON: {exc}", result) from exc
    return parse_video_info(payload), result


def download_args(selection: DownloadSelection) -> list[str]:
    issues = validate_cookie_config(selection.cookies)
    if issues:
        raise ValueError("; ".join(issues))
    selection.output_dir.mkdir(parents=True, exist_ok=True)
    base = [
        "yt-dlp",
        "--no-playlist",
        "--newline",
        "-P",
        str(selection.output_dir),
        "-o",
        FILENAME_TEMPLATE,
        *cookie_args(selection.cookies),
    ]

    if selection.mode == DownloadMode.VIDEO:
        if not selection.video_format:
            raise ValueError("video selection requires a video format")
        format_spec = selection.video_format.format_id
        if not selection.video_format.has_audio and selection.audio_format:
            format_spec = f"{selection.video_format.format_id}+{selection.audio_format.format_id}"
        return [*base, "-f", format_spec, selection.url]

    if selection.mode == DownloadMode.AUDIO:
        if not selection.audio_format:
            raise ValueError("audio selection requires an audio format")
        return [*base, "-f", selection.audio_format.format_id, selection.url]

    if selection.mode == DownloadMode.SUBTITLE:
        if not selection.subtitle:
            raise ValueError("subtitle selection requires a subtitle")
        args = [*base, "--skip-download"]
        args.append("--write-auto-subs" if selection.subtitle.automatic else "--write-subs")
        args.extend(["--sub-langs", selection.subtitle.lang])
        if selection.subtitle_output != SubtitleOutput.ORIGINAL:
            args.extend(["--convert-subs", selection.subtitle_output.value])
        args.append(selection.url)
        return args

    raise ValueError(f"unsupported mode: {selection.mode}")


def run_capture(args: list[str]) -> ProcessResult:
    completed = subprocess.run(args, capture_output=True, text=True, shell=False, encoding="utf-8", errors="replace")
    return ProcessResult(completed.returncode, completed.stdout, completed.stderr)


def stream_process(args: list[str]) -> Iterator[str]:
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        shell=False,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    for line in process.stdout:
        yield line.rstrip("\n")
    returncode = process.wait()
    if returncode != 0:
        raise YtdlpError(f"yt-dlp exited with code {returncode}", ProcessResult(returncode, "", ""))


def cookie_args(cookies: CookieConfig) -> list[str]:
    if cookies.mode == CookieMode.BROWSER:
        browser = cookies.browser.strip()
        return ["--cookies-from-browser", browser] if browser else []
    if cookies.mode == CookieMode.FILE:
        path = cookies.cookies_path.strip()
        return ["--cookies", path] if path else []
    return []


def validate_cookie_config(cookies: CookieConfig) -> list[str]:
    if cookies.mode == CookieMode.BROWSER:
        browser = cookies.browser.strip().lower()
        if not browser:
            return ["Choose a browser for cookies-from-browser."]
        if browser not in SUPPORTED_COOKIE_BROWSERS:
            supported = ", ".join(SUPPORTED_COOKIE_BROWSERS)
            return [f"Unsupported browser '{cookies.browser}'. Choose one of: {supported}."]
    if cookies.mode == CookieMode.FILE:
        path = cookies.cookies_path.strip()
        if not path:
            return ["Choose a cookies.txt file."]
        if not Path(path).is_file():
            return [f"Cookies file does not exist: {path}"]
    return []
