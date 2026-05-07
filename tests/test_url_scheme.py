# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import pytest

from tubepocket.url_scheme import UrlError, build_scheme_url, normalize_youtube_url, parse_launch_arg


def test_normalizes_watch_url_and_strips_playlist() -> None:
    launch = normalize_youtube_url("https://www.youtube.com/watch?v=abc123&list=PL123&index=4")

    assert launch.video_id == "abc123"
    assert launch.canonical_url == "https://www.youtube.com/watch?v=abc123"


def test_normalizes_youtu_be_url() -> None:
    launch = normalize_youtube_url("https://youtu.be/abc123?si=ignored")

    assert launch.video_id == "abc123"
    assert launch.canonical_url == "https://www.youtube.com/watch?v=abc123"


def test_parse_launch_arg() -> None:
    scheme = build_scheme_url("https://www.youtube.com/watch?v=abc123&list=PL123")

    launch = parse_launch_arg(scheme)

    assert launch.canonical_url == "https://www.youtube.com/watch?v=abc123"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/watch?v=abc123",
        "https://www.youtube.com/watch?list=PL123",
        "tubepocket://open?url=https%3A%2F%2Fexample.com",
    ],
)
def test_rejects_invalid_urls(url: str) -> None:
    with pytest.raises(UrlError):
        if url.startswith("tubepocket:"):
            parse_launch_arg(url)
        else:
            normalize_youtube_url(url)

