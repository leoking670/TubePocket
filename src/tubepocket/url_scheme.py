# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse


YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}


class UrlError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LaunchUrl:
    canonical_url: str
    video_id: str


def build_scheme_url(youtube_url: str) -> str:
    launch = normalize_youtube_url(youtube_url)
    return "tubepocket://open?" + urlencode({"url": launch.canonical_url})


def parse_launch_arg(arg: str) -> LaunchUrl:
    parsed = urlparse(arg)
    if parsed.scheme != "tubepocket" or parsed.netloc != "open":
        raise UrlError("Expected tubepocket://open?url=...")
    values = parse_qs(parsed.query)
    raw_url = values.get("url", [""])[0]
    if not raw_url:
        raise UrlError("Missing url parameter")
    return normalize_youtube_url(raw_url)


def normalize_youtube_url(raw_url: str) -> LaunchUrl:
    parsed = urlparse(raw_url)
    host = parsed.netloc.lower()
    video_id = ""

    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/", 1)[0]
    elif host in YOUTUBE_HOSTS:
        qs = parse_qs(parsed.query)
        video_id = qs.get("v", [""])[0]
        if not video_id and parsed.path.startswith("/shorts/"):
            video_id = parsed.path.split("/", 3)[2]
    else:
        raise UrlError("Only YouTube URLs are supported")

    video_id = video_id.strip()
    if not video_id:
        raise UrlError("Missing YouTube video id")
    if any(ch in video_id for ch in "/?&#"):
        raise UrlError("Invalid YouTube video id")

    canonical = urlunparse(("https", "www.youtube.com", "/watch", "", urlencode({"v": video_id}), ""))
    return LaunchUrl(canonical, video_id)


def quote_for_scheme(url: str) -> str:
    return quote(url, safe="")

