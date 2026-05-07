# TubePocket

TubePocket is a GPL-3.0-only Windows desktop tool for visually selecting YouTube video, audio, or subtitles through `yt-dlp`.

The normal user entry point is the packaged `TubePocket.exe`. Source execution is for review, development, and building only. URL scheme registration is intentionally disabled when running from source.

## Requirements

- Windows
- `yt-dlp` available on `PATH`
- `ffmpeg` available on `PATH` for video merging and subtitle conversion
- Chrome or Edge with Tampermonkey for the userscript
- Python 3.13 and `uv` for development/building

TubePocket does not bundle `yt-dlp` or `ffmpeg`.

## Development

```powershell
uv sync --extra dev
uv run pytest
```

Run the development GUI for inspection only:

```powershell
uv run tubepocket-dev
```

The development GUI can inspect logic and load URLs, but it will not register the `tubepocket://` protocol. Registration is only available in the PyInstaller-built executable.

## Build

```powershell
uv sync --extra dev
uv run pyinstaller tubepocket.spec
```

The packaged app is written to:

```text
dist\TubePocket\TubePocket.exe
```

Run that executable, then use the status page to register or unregister the protocol.

## Browser Script

Install `scripts/tubepocket.user.js` in Tampermonkey. On a YouTube watch page, it injects a TubePocket button into the action area. The button opens:

```text
tubepocket://open?url=<encoded-canonical-youtube-url>
```

Playlist parameters are ignored. Only the current video is sent to the desktop app.

## Protocol Registration

TubePocket writes only to the current user registry hive:

```text
HKCU\Software\Classes\tubepocket
```

The app provides:

- Register: points `tubepocket://` at the current packaged `TubePocket.exe`.
- Re-register: overwrites stale registrations after the exe is moved.
- Unregister: removes the `tubepocket` protocol key for uninstall or repair.

No administrator privileges are required.

## Download Behavior

Each task downloads exactly one content type:

- Video: select one video format. If it is video-only, TubePocket chooses the most compatible audio-only format and asks `yt-dlp` to merge them.
- Audio: select one audio-only format.
- Subtitle: select one subtitle. Uploaded subtitles are all shown; automatic subtitles are limited to English (`en` and `en-*`). Output can be original format, `srt`, or `vtt`.

Files are saved to:

```text
%USERPROFILE%\Downloads\TubePocket
```

The fixed filename template is:

```text
%(uploader)s - %(title)s [%(id)s].%(ext)s
```

## Cookies

The app supports three modes:

- No cookies
- `yt-dlp --cookies-from-browser <browser>`
- `yt-dlp --cookies <cookies.txt>`

Cookie settings are stored in a small JSON config under the user's local application data directory.

## Legal

TubePocket is licensed under `GPL-3.0-only`. It is a local interface for invoking user-installed tools. Users are responsible for ensuring they have the right to download content and for complying with YouTube terms, third-party tool licenses, and local law.

`yt-dlp` and `ffmpeg` are not distributed with this project.

