# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tubepocket.models import CookieConfig, CookieMode, SubtitleOutput


APP_DIR_NAME = "TubePocket"


@dataclass(slots=True)
class AppConfig:
    cookies: CookieConfig
    subtitle_output: SubtitleOutput = SubtitleOutput.ORIGINAL


def config_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_DIR_NAME
    return Path.home() / ".tubepocket"


def config_path() -> Path:
    return config_dir() / "config.json"


def default_output_dir() -> Path:
    return Path.home() / "Downloads" / APP_DIR_NAME


def load_config(path: Path | None = None) -> AppConfig:
    target = path or config_path()
    if not target.exists():
        return AppConfig(cookies=CookieConfig())
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppConfig(cookies=CookieConfig())

    cookies_data: dict[str, Any] = data.get("cookies") or {}
    try:
        mode = CookieMode(cookies_data.get("mode", CookieMode.NONE.value))
    except ValueError:
        mode = CookieMode.NONE
    try:
        subtitle_output = SubtitleOutput(data.get("subtitle_output", SubtitleOutput.ORIGINAL.value))
    except ValueError:
        subtitle_output = SubtitleOutput.ORIGINAL
    return AppConfig(
        cookies=CookieConfig(
            mode=mode,
            browser=str(cookies_data.get("browser") or "chrome"),
            cookies_path=str(cookies_data.get("cookies_path") or ""),
        ),
        subtitle_output=subtitle_output,
    )


def save_config(config: AppConfig, path: Path | None = None) -> None:
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(config)
    data["cookies"]["mode"] = config.cookies.mode.value
    data["subtitle_output"] = config.subtitle_output.value
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")

