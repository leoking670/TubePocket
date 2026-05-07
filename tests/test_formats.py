# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from tubepocket.formats import (
    choose_default_audio,
    choose_default_subtitle,
    choose_default_video,
    choose_matching_audio,
    parse_video_info,
    split_formats,
)


FIXTURE = {
    "id": "abc123",
    "title": "Example",
    "uploader": "Uploader",
    "webpage_url": "https://www.youtube.com/watch?v=abc123",
    "language": "ja",
    "formats": [
        {
            "format_id": "v-webm",
            "ext": "webm",
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "vcodec": "vp9",
            "acodec": "none",
            "tbr": 2400,
        },
        {
            "format_id": "v-mp4",
            "ext": "mp4",
            "width": 1280,
            "height": 720,
            "fps": 30,
            "vcodec": "avc1",
            "acodec": "none",
            "tbr": 1200,
        },
        {
            "format_id": "combined",
            "ext": "mp4",
            "width": 640,
            "height": 360,
            "vcodec": "avc1",
            "acodec": "mp4a.40.2",
            "tbr": 700,
        },
        {
            "format_id": "a-m4a",
            "ext": "m4a",
            "vcodec": "none",
            "acodec": "mp4a.40.2",
            "abr": 128,
            "asr": 44100,
        },
        {
            "format_id": "a-webm",
            "ext": "webm",
            "vcodec": "none",
            "acodec": "opus",
            "abr": 160,
            "asr": 48000,
        },
    ],
    "subtitles": {
        "en": [{"ext": "vtt", "name": "English"}],
        "ja": [{"ext": "vtt", "name": "Japanese"}],
        "zh-Hans": [{"ext": "vtt", "name": "Chinese"}],
    },
    "automatic_captions": {
        "en": [{"ext": "vtt", "name": "English auto"}],
        "en-US": [{"ext": "vtt", "name": "English US auto"}],
        "ja": [{"ext": "vtt", "name": "Japanese auto"}],
    },
}


def test_parse_and_split_formats() -> None:
    info = parse_video_info(FIXTURE)

    videos, audios = split_formats(info)

    assert [item.format_id for item in videos] == ["v-webm", "v-mp4", "combined"]
    assert [item.format_id for item in audios] == ["a-m4a", "a-webm"]
    assert [(item.lang, item.automatic) for item in info.subtitles] == [
        ("en", False),
        ("ja", False),
        ("zh-Hans", False),
        ("en", True),
        ("en-US", True),
    ]


def test_default_media_choices() -> None:
    info = parse_video_info(FIXTURE)

    assert choose_default_video(info.formats).format_id == "v-webm"
    assert choose_default_audio(info.formats).format_id == "a-webm"
    assert choose_default_subtitle(info).lang == "ja"


def test_matching_audio_prefers_container_compatibility() -> None:
    info = parse_video_info(FIXTURE)
    videos, audios = split_formats(info)

    assert choose_matching_audio(next(item for item in videos if item.format_id == "v-mp4"), audios).format_id == "a-m4a"
    assert choose_matching_audio(next(item for item in videos if item.format_id == "v-webm"), audios).format_id == "a-webm"


def test_matching_audio_falls_back_to_best_quality() -> None:
    info = parse_video_info(FIXTURE)
    videos, audios = split_formats(info)
    unknown_container = next(item for item in videos if item.format_id == "v-mp4")
    unknown_container.ext = "mov"

    assert choose_matching_audio(unknown_container, audios).format_id == "a-webm"


def test_subtitle_default_falls_back_to_uploaded_english_then_auto_english() -> None:
    no_original = dict(FIXTURE, language="fr")
    info = parse_video_info(no_original)
    assert choose_default_subtitle(info).lang == "en"
    assert choose_default_subtitle(info).automatic is False

    no_uploaded_en = dict(FIXTURE, language="fr", subtitles={"zh": [{"ext": "vtt"}]})
    info = parse_video_info(no_uploaded_en)
    assert choose_default_subtitle(info).lang == "en"
    assert choose_default_subtitle(info).automatic is True

