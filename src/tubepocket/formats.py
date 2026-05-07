# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

from tubepocket.models import MediaFormat, SubtitleItem, VideoInfo


def parse_video_info(data: dict[str, Any]) -> VideoInfo:
    formats = [parse_format(item) for item in data.get("formats", []) if item.get("format_id")]
    subtitles = parse_subtitles(data.get("subtitles") or {}, automatic=False)
    subtitles.extend(parse_subtitles(data.get("automatic_captions") or {}, automatic=True))
    return VideoInfo(
        video_id=str(data.get("id") or ""),
        title=str(data.get("title") or ""),
        uploader=str(data.get("uploader") or data.get("channel") or ""),
        webpage_url=str(data.get("webpage_url") or ""),
        language=str(data.get("language") or data.get("original_language") or ""),
        formats=formats,
        subtitles=subtitles,
    )


def parse_format(item: dict[str, Any]) -> MediaFormat:
    return MediaFormat(
        format_id=str(item.get("format_id") or ""),
        ext=str(item.get("ext") or ""),
        width=_int_or_none(item.get("width")),
        height=_int_or_none(item.get("height")),
        fps=_float_or_none(item.get("fps")),
        vcodec=str(item.get("vcodec") or "none"),
        acodec=str(item.get("acodec") or "none"),
        tbr=_float_or_none(item.get("tbr")),
        abr=_float_or_none(item.get("abr")),
        asr=_int_or_none(item.get("asr")),
        filesize=_int_or_none(item.get("filesize")),
        filesize_approx=_int_or_none(item.get("filesize_approx")),
        format_note=str(item.get("format_note") or ""),
        format=str(item.get("format") or ""),
        raw=item,
    )


def parse_subtitles(items: dict[str, list[dict[str, Any]]], automatic: bool) -> list[SubtitleItem]:
    result: list[SubtitleItem] = []
    for lang, entries in sorted(items.items()):
        if automatic and not is_english_lang(lang):
            continue
        if not entries:
            continue
        first = entries[0]
        result.append(
            SubtitleItem(
                lang=lang,
                name=str(first.get("name") or ""),
                ext=str(first.get("ext") or ""),
                automatic=automatic,
                raw=entries,
            )
        )
    return result


def is_english_lang(lang: str) -> bool:
    lowered = lang.lower()
    return lowered == "en" or lowered.startswith("en-")


def split_formats(info: VideoInfo) -> tuple[list[MediaFormat], list[MediaFormat]]:
    videos = [fmt for fmt in info.formats if fmt.has_video]
    audio = [fmt for fmt in info.formats if fmt.is_audio_only]
    return videos, audio


def choose_default_video(formats: list[MediaFormat]) -> MediaFormat | None:
    videos = [fmt for fmt in formats if fmt.has_video]
    return max(videos, key=lambda item: item.video_score(), default=None)


def choose_default_audio(formats: list[MediaFormat]) -> MediaFormat | None:
    audio = [fmt for fmt in formats if fmt.is_audio_only]
    return max(audio, key=lambda item: item.audio_score(), default=None)


def choose_matching_audio(video: MediaFormat, audio_formats: list[MediaFormat]) -> MediaFormat | None:
    if not audio_formats:
        return None
    compatible = [fmt for fmt in audio_formats if _compatible_with_video(video, fmt)]
    candidates = compatible or audio_formats
    return max(candidates, key=lambda item: item.audio_score(), default=None)


def choose_default_subtitle(info: VideoInfo) -> SubtitleItem | None:
    uploaded = [item for item in info.subtitles if not item.automatic]
    automatic = [item for item in info.subtitles if item.automatic]
    language = info.language.lower()
    if language:
        for item in uploaded:
            if item.lang.lower() == language or item.lang.lower().startswith(language + "-"):
                return item
    for item in uploaded:
        if is_english_lang(item.lang):
            return item
    for item in automatic:
        if is_english_lang(item.lang):
            return item
    return None


def _compatible_with_video(video: MediaFormat, audio: MediaFormat) -> bool:
    video_ext = video.ext.lower()
    audio_ext = audio.ext.lower()
    acodec = audio.acodec.lower()
    if video_ext in {"mp4", "m4v"}:
        return audio_ext in {"m4a", "mp4"} or "aac" in acodec
    if video_ext == "webm":
        return audio_ext == "webm" or "opus" in acodec
    return False


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None

