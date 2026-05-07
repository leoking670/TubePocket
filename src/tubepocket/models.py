# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class DownloadMode(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLE = "subtitle"


class SubtitleOutput(str, Enum):
    ORIGINAL = "original"
    SRT = "srt"
    VTT = "vtt"


class CookieMode(str, Enum):
    NONE = "none"
    BROWSER = "browser"
    FILE = "file"


@dataclass(slots=True)
class CookieConfig:
    mode: CookieMode = CookieMode.NONE
    browser: str = "chrome"
    cookies_path: str = ""


@dataclass(slots=True)
class MediaFormat:
    format_id: str
    ext: str = ""
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    vcodec: str = "none"
    acodec: str = "none"
    tbr: float | None = None
    abr: float | None = None
    asr: int | None = None
    filesize: int | None = None
    filesize_approx: int | None = None
    format_note: str = ""
    format: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_audio_only(self) -> bool:
        return self.has_audio and not self.has_video

    @property
    def has_audio(self) -> bool:
        return bool(self.acodec and self.acodec != "none")

    @property
    def has_video(self) -> bool:
        return bool(self.vcodec and self.vcodec != "none")

    @property
    def display_size(self) -> str:
        size = self.filesize or self.filesize_approx
        if not size:
            return ""
        units = ["B", "KB", "MB", "GB"]
        value = float(size)
        unit = 0
        while value >= 1024 and unit < len(units) - 1:
            value /= 1024
            unit += 1
        return f"{value:.1f} {units[unit]}"

    @property
    def resolution(self) -> str:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        if self.height:
            return f"{self.height}p"
        return ""

    def video_score(self) -> tuple[int, float, float]:
        return (self.height or 0, self.fps or 0.0, self.tbr or 0.0)

    def audio_score(self) -> tuple[float, float]:
        return (self.abr or self.tbr or 0.0, float(self.asr or 0))


@dataclass(slots=True)
class SubtitleItem:
    lang: str
    name: str = ""
    ext: str = ""
    automatic: bool = False
    raw: list[dict[str, Any]] = field(default_factory=list)

    @property
    def source(self) -> str:
        return "auto" if self.automatic else "uploaded"


@dataclass(slots=True)
class VideoInfo:
    video_id: str
    title: str
    uploader: str
    webpage_url: str
    language: str = ""
    formats: list[MediaFormat] = field(default_factory=list)
    subtitles: list[SubtitleItem] = field(default_factory=list)


@dataclass(slots=True)
class DownloadSelection:
    mode: DownloadMode
    url: str
    video_format: MediaFormat | None = None
    audio_format: MediaFormat | None = None
    subtitle: SubtitleItem | None = None
    subtitle_output: SubtitleOutput = SubtitleOutput.ORIGINAL
    cookies: CookieConfig = field(default_factory=CookieConfig)
    output_dir: Path = Path.home() / "Downloads" / "TubePocket"

