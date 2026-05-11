# TubePocket

[繁體中文](README.zh-TW.md)

TubePocket is a GPL-3.0-only Windows desktop tool for visually selecting YouTube video, audio, or subtitles through `yt-dlp`.

The normal user entry point is the packaged `TubePocket.exe`. Source execution is for review, development, and building only. URL scheme registration is intentionally disabled when running from source.

## Requirements

- Windows
- `yt-dlp` available on `PATH`
- `ffmpeg` available on `PATH` for video merging and subtitle conversion
- `deno` on `PATH` is recommended for YouTube JavaScript challenge solving
- Chrome or Edge with Tampermonkey for the userscript
- Python 3.13 and `uv` for development/building

TubePocket does not bundle `yt-dlp` or `ffmpeg`.

If you install `yt-dlp` with `uv tool`, prefer:

```powershell
uv tool install --force "yt-dlp[default]"
```

The plain `uv tool install yt-dlp` installs the base PyPI package. For YouTube challenge solving, yt-dlp's EJS documentation recommends installing the `default` dependency group because it includes the companion `yt-dlp-ejs` package. TubePocket only detects local tools; it does not install JS runtimes, download EJS components, or change proxy settings for you.

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

Parts of this project may be generated or edited with AI assistance and reviewed before release.

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

Manual starts and browser URL Scheme starts are kept separate. A browser-launched TubePocket window is reused for later `tubepocket://` opens, so clicking the userscript repeatedly does not create a new app window each time.

## Download Behavior

Each task downloads exactly one content type:

- Video: select one video format. If it is video-only, TubePocket chooses the most compatible audio-only format and asks `yt-dlp` to merge them.
- Audio: select one audio-only format.
- Subtitle: select one subtitle. Uploaded subtitles are all shown; automatic subtitles are limited to English (`en` and `en-*`). Output can be original format, `srt`, `vtt`, or plain `text`. The plain text option removes timestamps and subtitle markup after download.

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
- `yt-dlp --cookies-from-browser <browser>`, selected from a browser list in the GUI
- `yt-dlp --cookies <cookies.txt>`

Cookie settings are stored in a small JSON config under the user's local application data directory.

When TubePocket is launched from the browser and the saved cookie settings are incomplete, the app stops before calling `yt-dlp`, opens the status page, and shows a clear warning. For example, a missing `cookies.txt` path is reported as a setup issue instead of surfacing only as a download failure.

## Proxy and YouTube JS Challenges

Some videos or cookie-backed requests may require YouTube JavaScript challenge solving. If downloads fail with warnings about EJS, remote components, JavaScript challenges, or "Only images are available", check your `yt-dlp` installation first:

```powershell
uv tool install --force "yt-dlp[default]"
deno --version
yt-dlp -v --cookies-from-browser firefox --dump-single-json --no-playlist "URL"
```

If your network requires a proxy, configure it in your shell or yt-dlp configuration. TubePocket will not change proxy settings automatically.

PowerShell example:

```powershell
$env:HTTP_PROXY='http://127.0.0.1:7890'
$env:HTTPS_PROXY='http://127.0.0.1:7890'
```

yt-dlp config example:

```text
--proxy http://127.0.0.1:7890
```

TubePocket's status page only detects local conditions. It checks whether `yt-dlp`, `ffmpeg`, and `deno` are visible on `PATH`. For EJS support, it can confirm whether `yt-dlp-ejs` is installed in a `uv tool` managed `yt-dlp` environment. If you use a standalone `yt-dlp.exe` from GitHub releases or another installation method, TubePocket may show the EJS status as unknown because official executables may bundle the required components internally.

TubePocket starts `yt-dlp` and `ffmpeg` without opening a separate console window. During metadata loading and downloads, the GUI shows an in-progress status indicator.

## Legal

TubePocket is licensed under `GPL-3.0-only`. It is a local interface for invoking user-installed tools. Users are responsible for ensuring they have the right to download content and for complying with YouTube terms, third-party tool licenses, and local law.

`yt-dlp` and `ffmpeg` are not distributed with this project.
