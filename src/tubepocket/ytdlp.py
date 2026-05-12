# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
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
    selection.output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = subtitle_download_dir(selection)
    output_dir.mkdir(parents=True, exist_ok=True)
    base = [
        "yt-dlp",
        "--no-playlist",
        "--newline",
        "-P",
        str(output_dir),
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
        if selection.subtitle_output == SubtitleOutput.TEXT:
            args.extend(["--convert-subs", SubtitleOutput.SRT.value])
        elif selection.subtitle_output != SubtitleOutput.ORIGINAL:
            args.extend(["--convert-subs", selection.subtitle_output.value])
        args.append(selection.url)
        return args

    raise ValueError(f"unsupported mode: {selection.mode}")


def run_capture(args: list[str]) -> ProcessResult:
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        shell=False,
        encoding="utf-8",
        errors="replace",
        creationflags=_creation_flags(),
    )
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
        creationflags=_creation_flags(),
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


def finalize_plain_text_subtitle(selection: DownloadSelection) -> Path:
    if selection.mode != DownloadMode.SUBTITLE or selection.subtitle_output != SubtitleOutput.TEXT:
        raise ValueError("plain text finalization requires a text subtitle selection")
    if not selection.subtitle:
        raise ValueError("plain text finalization requires a subtitle")
    source = find_downloaded_subtitle(subtitle_download_dir(selection), selection.video_id, selection.subtitle.lang)
    text = subtitle_file_to_plain_text(source)
    target = selection.output_dir / source.with_suffix(".txt").name
    selection.output_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    source.unlink(missing_ok=True)
    _remove_empty_parent(source)
    return target


def subtitle_download_dir(selection: DownloadSelection) -> Path:
    if selection.mode == DownloadMode.SUBTITLE and selection.subtitle_output == SubtitleOutput.TEXT:
        return _plain_text_subtitle_work_dir(selection)
    return selection.output_dir


def find_downloaded_subtitle(output_dir: Path, video_id: str, lang: str) -> Path:
    candidates: list[Path] = []
    if not output_dir.exists():
        raise FileNotFoundError("Downloaded subtitle file was not found for plain text conversion.")
    for path in output_dir.iterdir():
        if path.suffix.lower() not in {".srt", ".vtt"}:
            continue
        name = path.name
        if video_id and f"[{video_id}]" not in name:
            continue
        if f".{lang}." not in name:
            continue
        candidates.append(path)
    if not candidates:
        raise FileNotFoundError("Downloaded subtitle file was not found for plain text conversion.")
    return max(candidates, key=lambda item: item.stat().st_mtime)


def subtitle_file_to_plain_text(path: Path) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    output: list[str] = []
    previous = ""
    skip_note = False
    for raw in lines:
        line = raw.strip().lstrip("\ufeff")
        if not line:
            skip_note = False
            continue
        if line.upper() in {"WEBVTT", "STYLE", "REGION"}:
            continue
        if line.upper().startswith("NOTE"):
            skip_note = True
            continue
        if skip_note:
            continue
        if line.isdigit():
            continue
        if "-->" in line:
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\{\\[^}]+\}", "", line)
        line = line.strip()
        if not line or line == previous:
            continue
        output.append(line)
        previous = line
    return "\n".join(output).strip() + "\n"


def _plain_text_subtitle_work_dir(selection: DownloadSelection) -> Path:
    lang = selection.subtitle.lang if selection.subtitle else ""
    key = "\0".join([str(selection.output_dir.resolve()), selection.video_id, lang])
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    safe_video_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", selection.video_id).strip("._") or "video"
    safe_lang = re.sub(r"[^A-Za-z0-9_.-]+", "_", lang).strip("._") or "subtitle"
    return Path(tempfile.gettempdir()) / "TubePocket" / "plain-text-subtitles" / f"{safe_video_id}-{safe_lang}-{digest}"


def _remove_empty_parent(path: Path) -> None:
    try:
        path.parent.rmdir()
    except OSError:
        pass


def yt_dlp_ejs_status(yt_dlp_path: str | None = None, appdata: str | None = None, userprofile: str | None = None) -> str:
    executable = yt_dlp_path or shutil.which("yt-dlp")
    if not executable:
        return "ℹ️ Not checked"

    uv_site_packages = _uv_tool_site_packages(appdata)
    if _looks_like_uv_tool_launcher(executable, appdata, userprofile) and uv_site_packages:
        if _has_yt_dlp_ejs(uv_site_packages):
            return "✅ yt-dlp-ejs installed"
        return "⚠️ yt-dlp-ejs not found; install yt-dlp[default]"

    return "ℹ️ Unknown; official exe may bundle EJS"


def _uv_tool_site_packages(appdata: str | None = None) -> Path | None:
    root = appdata or os.environ.get("APPDATA")
    if not root:
        return None
    site_packages = Path(root) / "uv" / "tools" / "yt-dlp" / "Lib" / "site-packages"
    return site_packages if site_packages.exists() else None


def _has_yt_dlp_ejs(site_packages: Path) -> bool:
    return (site_packages / "yt_dlp_ejs").exists() or any(site_packages.glob("yt_dlp_ejs-*.dist-info"))


def _looks_like_uv_tool_launcher(executable: str, appdata: str | None = None, userprofile: str | None = None) -> bool:
    path = Path(executable)
    text = str(path).casefold()
    root = appdata or os.environ.get("APPDATA")
    if root and str(Path(root) / "uv" / "tools" / "yt-dlp").casefold() in text:
        return True
    profile = userprofile or os.environ.get("USERPROFILE")
    if profile and path.name.lower() == "yt-dlp.exe":
        return str(Path(profile) / ".local" / "bin").casefold() in text
    return False


def _creation_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)
