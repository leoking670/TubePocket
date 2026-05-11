# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import queue
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from tubepocket.config import AppConfig, default_output_dir, load_config, save_config
from tubepocket.formats import (
    choose_default_audio,
    choose_default_subtitle,
    choose_default_video,
    choose_matching_audio,
    split_formats,
)
from tubepocket.models import CookieMode, DownloadMode, DownloadSelection, MediaFormat, SubtitleItem, SubtitleOutput, VideoInfo
from tubepocket.registry import ProtocolRegistry, RegistryState, current_executable, is_packaged
from tubepocket.url_scheme import LaunchUrl, UrlError, parse_launch_arg
from tubepocket.ytdlp import (
    SUPPORTED_COOKIE_BROWSERS,
    YtdlpError,
    download_args,
    finalize_plain_text_subtitle,
    load_metadata,
    stream_process,
    tool_available,
    yt_dlp_ejs_status,
)


def run_app(argv: list[str]) -> None:
    launch: LaunchUrl | None = None
    error: str | None = None
    if argv:
        try:
            launch = parse_launch_arg(argv[0])
        except UrlError as exc:
            error = str(exc)
    root = tk.Tk()
    root.title("TubePocket")
    root.geometry("1100x720")
    TubePocketApp(root, launch, error)
    root.mainloop()


class TubePocketApp:
    def __init__(self, root: tk.Tk, launch: LaunchUrl | None, launch_error: str | None) -> None:
        self.root = root
        self.config = load_config()
        self.registry = ProtocolRegistry()
        self.launch = launch
        self.video_info: VideoInfo | None = None
        self.videos: list[MediaFormat] = []
        self.audios: list[MediaFormat] = []
        self.subtitles: list[SubtitleItem] = []
        self.mode = tk.StringVar(value=DownloadMode.VIDEO.value)
        self.subtitle_output = tk.StringVar(value=self.config.subtitle_output.value)
        self.cookies_mode = tk.StringVar(value=self.config.cookies.mode.value)
        self.cookies_browser = tk.StringVar(value=self.config.cookies.browser)
        self.cookies_path = tk.StringVar(value=self.config.cookies.cookies_path)
        self.log_visible = tk.BooleanVar(value=False)
        self.worker_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.downloading = False

        self._build_ui()
        self.refresh_status()
        if launch_error:
            self.set_status(f"Invalid launch URL: {launch_error}")
        if launch:
            self.load_video_async(launch.canonical_url)
        self.root.after(100, self.poll_worker_queue)

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top = ttk.Frame(self.root, padding=10)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(2, weight=1)

        ttk.Label(top, text="TubePocket").grid(row=0, column=0, sticky="w", padx=(0, 16))
        status_area = ttk.Frame(top)
        status_area.grid(row=0, column=1, sticky="ew")
        status_area.columnconfigure(0, weight=1)
        self.status_label = ttk.Label(status_area, text="")
        self.status_label.grid(row=0, column=0, sticky="w")
        self.busy_bar = ttk.Progressbar(status_area, mode="indeterminate", length=160)
        self.busy_bar.grid(row=0, column=1, sticky="e", padx=(12, 0))
        self.busy_bar.grid_remove()

        actions = ttk.Frame(top)
        actions.grid(row=0, column=2, sticky="e")
        self.register_button = ttk.Button(actions, text="Register protocol", command=self.register_protocol)
        self.register_button.grid(row=0, column=0, padx=4)
        ttk.Button(actions, text="Unregister protocol", command=self.unregister_protocol).grid(row=0, column=1, padx=4)
        ttk.Button(actions, text="Refresh", command=self.refresh_status).grid(row=0, column=2, padx=4)

        self.main = ttk.Notebook(self.root)
        self.main.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self.status_tab = ttk.Frame(self.main, padding=10)
        self.download_tab = ttk.Frame(self.main, padding=10)
        self.main.add(self.status_tab, text="Status")
        self.main.add(self.download_tab, text="Download")
        self._build_status_tab()
        self._build_download_tab()

    def _build_status_tab(self) -> None:
        self.status_tab.columnconfigure(1, weight=1)
        labels = [
            ("yt-dlp", "ytdlp_status"),
            ("yt-dlp EJS", "ytdlp_ejs_status"),
            ("ffmpeg", "ffmpeg_status"),
            ("Deno", "deno_status"),
            ("Protocol", "protocol_status"),
            ("Cookies", "cookies_status"),
            ("Output", "output_status"),
            ("App", "runtime_status"),
        ]
        self.status_values: dict[str, ttk.Label] = {}
        for row, (label, key) in enumerate(labels):
            ttk.Label(self.status_tab, text=label).grid(row=row, column=0, sticky="w", pady=4)
            value = ttk.Label(self.status_tab, text="")
            value.grid(row=row, column=1, sticky="ew", pady=4)
            self.status_values[key] = value

        cookies = ttk.LabelFrame(self.status_tab, text="Cookies", padding=8)
        cookies.grid(row=len(labels), column=0, columnspan=2, sticky="ew", pady=(12, 0))
        cookies.columnconfigure(1, weight=1)

        cookie_modes = ttk.Frame(cookies)
        cookie_modes.grid(row=0, column=0, columnspan=3, sticky="w")
        for idx, (text, value) in enumerate(
            [("None", CookieMode.NONE.value), ("From browser", CookieMode.BROWSER.value), ("cookies.txt", CookieMode.FILE.value)]
        ):
            ttk.Radiobutton(cookie_modes, text=text, variable=self.cookies_mode, value=value, command=self.on_cookie_mode_changed).grid(
                row=0, column=idx, sticky="w", padx=(0, 16)
            )

        self.cookie_none_hint = ttk.Label(cookies, text="✅ No browser cookies will be used.")
        self.cookie_browser_label = ttk.Label(cookies, text="Browser")
        self.cookie_browser_combo = ttk.Combobox(
            cookies,
            textvariable=self.cookies_browser,
            values=SUPPORTED_COOKIE_BROWSERS,
            width=18,
            state="readonly",
        )
        self.cookie_browser_combo.bind("<<ComboboxSelected>>", lambda _event: self.save_cookie_config())

        self.cookie_file_label = ttk.Label(cookies, text="File")
        self.cookie_file_entry = ttk.Entry(cookies, textvariable=self.cookies_path)
        self.cookie_file_entry.bind("<FocusOut>", lambda _event: self.save_cookie_config())
        self.cookie_file_button = ttk.Button(cookies, text="Browse", command=self.choose_cookies_file)
        self.update_cookie_fields()

    def _build_download_tab(self) -> None:
        self.download_tab.columnconfigure(0, weight=1)
        self.download_tab.rowconfigure(3, weight=1)

        url_row = ttk.Frame(self.download_tab)
        url_row.grid(row=0, column=0, sticky="ew")
        url_row.columnconfigure(1, weight=1)
        ttk.Label(url_row, text="URL").grid(row=0, column=0, sticky="w")
        self.url_var = tk.StringVar(value=self.launch.canonical_url if self.launch else "")
        ttk.Entry(url_row, textvariable=self.url_var).grid(row=0, column=1, sticky="ew", padx=8)
        self.load_button = ttk.Button(url_row, text="Load", command=lambda: self.load_video_async(self.url_var.get()))
        self.load_button.grid(row=0, column=2)

        mode_row = ttk.Frame(self.download_tab)
        mode_row.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        for col, (text, value) in enumerate(
            [("Video", DownloadMode.VIDEO.value), ("Audio", DownloadMode.AUDIO.value), ("Subtitle", DownloadMode.SUBTITLE.value)]
        ):
            ttk.Radiobutton(mode_row, text=text, variable=self.mode, value=value, command=self.update_mode_view).grid(
                row=0, column=col, sticky="w", padx=(0, 16)
            )
        ttk.Label(mode_row, text="Subtitle output").grid(row=0, column=3, sticky="e", padx=(16, 4))
        self.subtitle_output_combo = ttk.Combobox(
            mode_row,
            textvariable=self.subtitle_output,
            values=[item.value for item in SubtitleOutput],
            width=10,
            state="readonly",
        )
        self.subtitle_output_combo.grid(row=0, column=4)
        self.subtitle_output_combo.bind("<<ComboboxSelected>>", lambda _event: self.save_cookie_config())

        self.title_label = ttk.Label(self.download_tab, text="No video loaded")
        self.title_label.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        self.table_frame = ttk.Frame(self.download_tab)
        self.table_frame.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        self.table_frame.columnconfigure(0, weight=1)
        self.table_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(self.table_frame, show="headings", selectmode="browse")
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=yscroll.set)

        buttons = ttk.Frame(self.download_tab)
        buttons.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self.download_button = ttk.Button(buttons, text="Download", command=self.start_download)
        self.download_button.grid(row=0, column=0, padx=(0, 8))
        ttk.Checkbutton(buttons, text="Show log", variable=self.log_visible, command=self.update_log_visibility).grid(row=0, column=1)
        self.progress_label = ttk.Label(buttons, text="")
        self.progress_label.grid(row=0, column=2, sticky="w", padx=(12, 0))

        self.log_text = tk.Text(self.download_tab, height=8, wrap="word")
        self.update_log_visibility()

    def refresh_status(self) -> None:
        self.status_values["ytdlp_status"].configure(text=tool_status("yt-dlp", required=True))
        self.status_values["ytdlp_ejs_status"].configure(text=yt_dlp_ejs_status())
        self.status_values["ffmpeg_status"].configure(text=tool_status("ffmpeg", required=True))
        self.status_values["deno_status"].configure(text=tool_status("deno", required=False))
        self.status_values["output_status"].configure(text=f"📁 {default_output_dir()}")
        self.status_values["runtime_status"].configure(text="✅ Packaged exe" if is_packaged() else "ℹ️ Source/development")
        cookies = self.current_cookie_config()
        cookie_issues: list[str] = []
        cookie_text = "✅ Ready" if not cookie_issues else "⚠️ " + "; ".join(cookie_issues)
        self.status_values["cookies_status"].configure(text=cookie_status_text(cookies))

        exe = current_executable()
        try:
            status = self.registry.status(exe)
            if status.state == RegistryState.REGISTERED_CURRENT:
                text = "✅ Registered to current exe"
            elif status.state == RegistryState.REGISTERED_OTHER:
                exists = "exists" if status.target_exists else "missing"
                text = f"⚠️ Registered elsewhere: {status.target_path} ({exists})"
            else:
                text = "⚠️ Not registered"
            self.status_values["protocol_status"].configure(text=text)
        except Exception as exc:
            self.status_values["protocol_status"].configure(text=f"❌ Error: {exc}")

        if not is_packaged():
            self.register_button.configure(state="disabled", text="Register requires packaged exe")
        else:
            self.register_button.configure(state="normal", text="Register / re-register protocol")

    def register_protocol(self) -> None:
        if not is_packaged():
            messagebox.showinfo("TubePocket", "Protocol registration is only supported from the packaged TubePocket.exe.")
            return
        try:
            self.registry.register(current_executable())
            self.refresh_status()
            messagebox.showinfo("TubePocket", "Protocol registered.")
        except Exception as exc:
            messagebox.showerror("TubePocket", f"Registration failed: {exc}")

    def unregister_protocol(self) -> None:
        try:
            self.registry.unregister()
            self.refresh_status()
            messagebox.showinfo("TubePocket", "Protocol unregistered.")
        except Exception as exc:
            messagebox.showerror("TubePocket", f"Unregister failed: {exc}")

    def choose_cookies_file(self) -> None:
        path = filedialog.askopenfilename(title="Select cookies.txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self.cookies_path.set(path)
            self.cookies_mode.set(CookieMode.FILE.value)
            self.save_cookie_config()
            self.update_cookie_fields()

    def on_cookie_mode_changed(self) -> None:
        self.update_cookie_fields()
        self.save_cookie_config()
        self.refresh_status()

    def update_cookie_fields(self) -> None:
        self.cookie_none_hint.grid_remove()
        self.cookie_browser_label.grid_remove()
        self.cookie_browser_combo.grid_remove()
        self.cookie_file_label.grid_remove()
        self.cookie_file_entry.grid_remove()
        self.cookie_file_button.grid_remove()

        mode = self.cookies_mode.get()
        if mode == CookieMode.BROWSER.value:
            self.cookie_browser_label.grid(row=1, column=0, sticky="w", pady=(8, 0))
            self.cookie_browser_combo.grid(row=1, column=1, sticky="w", pady=(8, 0))
        elif mode == CookieMode.FILE.value:
            self.cookie_file_label.grid(row=1, column=0, sticky="w", pady=(8, 0))
            self.cookie_file_entry.grid(row=1, column=1, sticky="ew", pady=(8, 0))
            self.cookie_file_button.grid(row=1, column=2, padx=(8, 0), pady=(8, 0))
        else:
            self.cookie_none_hint.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def current_cookie_config(self):
        try:
            self.config.cookies.mode = CookieMode(self.cookies_mode.get())
        except ValueError:
            self.config.cookies.mode = CookieMode.NONE
        browser = self.cookies_browser.get().strip().lower()
        self.config.cookies.browser = browser if browser in SUPPORTED_COOKIE_BROWSERS else "chrome"
        if self.cookies_browser.get() != self.config.cookies.browser:
            self.cookies_browser.set(self.config.cookies.browser)
        self.config.cookies.cookies_path = self.cookies_path.get().strip()
        return self.config.cookies

    def save_cookie_config(self) -> None:
        self.current_cookie_config()
        try:
            self.config.subtitle_output = SubtitleOutput(self.subtitle_output.get())
        except ValueError:
            self.config.subtitle_output = SubtitleOutput.ORIGINAL
        save_config(self.config)

    def load_video_async(self, url: str) -> None:
        if not url.strip():
            return
        cookies = self.current_cookie_config()
        self.load_button.configure(state="disabled")
        self.start_busy("Loading metadata...")
        self.append_log(f"Loading metadata: {url}")

        def worker() -> None:
            try:
                info, result = load_metadata(url.strip(), cookies)
                self.worker_queue.put(("metadata", info))
                if result.stderr:
                    self.worker_queue.put(("log", result.stderr))
            except YtdlpError as exc:
                detail = exc.result.stderr if exc.result else str(exc)
                self.worker_queue.put(("error", f"{exc}\n{detail}"))
            except Exception as exc:
                self.worker_queue.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def receive_metadata(self, info: VideoInfo) -> None:
        self.video_info = info
        self.videos, self.audios = split_formats(info)
        self.subtitles = info.subtitles
        self.title_label.configure(text=f"{info.title} - {info.uploader}")
        self.update_mode_view()
        self.stop_busy("Metadata loaded")
        self.load_button.configure(state="normal")
        self.main.select(self.download_tab)

    def update_mode_view(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        mode = DownloadMode(self.mode.get())
        if mode == DownloadMode.VIDEO:
            self.configure_tree(["format_id", "ext", "resolution", "fps", "vcodec", "acodec", "tbr", "size", "note"])
            for fmt in self.videos:
                self.tree.insert("", "end", iid=fmt.format_id, values=row_for_video(fmt))
            default = choose_default_video(self.videos)
            if default:
                self.tree.selection_set(default.format_id)
        elif mode == DownloadMode.AUDIO:
            self.configure_tree(["format_id", "ext", "acodec", "abr", "tbr", "asr", "size", "note"])
            for fmt in self.audios:
                self.tree.insert("", "end", iid=fmt.format_id, values=row_for_audio(fmt))
            default = choose_default_audio(self.audios)
            if default:
                self.tree.selection_set(default.format_id)
        else:
            self.configure_tree(["lang", "source", "ext", "name"])
            for idx, sub in enumerate(self.subtitles):
                self.tree.insert("", "end", iid=str(idx), values=[sub.lang, sub.source, sub.ext, sub.name])
            if self.video_info:
                default = choose_default_subtitle(self.video_info)
                if default:
                    self.tree.selection_set(str(self.subtitles.index(default)))
        self.update_subtitle_controls()

    def configure_tree(self, columns: list[str]) -> None:
        self.tree.configure(columns=columns)
        for col in columns:
            self.tree.heading(col, text=col)
            width = 150 if col in {"format_id", "vcodec", "acodec", "name", "note"} else 90
            self.tree.column(col, width=width, minwidth=60, stretch=True)

    def update_subtitle_controls(self) -> None:
        is_subtitle = self.mode.get() == DownloadMode.SUBTITLE.value
        state = "readonly" if is_subtitle else "disabled"
        if is_subtitle and self.subtitle_output.get() != SubtitleOutput.ORIGINAL.value and not tool_available("ffmpeg"):
            state = "disabled"
        self.subtitle_output_combo.configure(state=state)

    def start_download(self) -> None:
        if self.downloading or not self.video_info:
            return
        try:
            selection = self.build_selection()
            if selection.mode == DownloadMode.SUBTITLE and selection.subtitle_output != SubtitleOutput.ORIGINAL and not tool_available("ffmpeg"):
                messagebox.showerror("TubePocket", "ffmpeg is required for subtitle conversion.")
                return
            args = download_args(selection)
        except Exception as exc:
            messagebox.showerror("TubePocket", str(exc))
            return
        self.downloading = True
        self.download_button.configure(state="disabled")
        self.load_button.configure(state="disabled")
        self.start_busy("Downloading...")
        self.progress_label.configure(text="Starting...")
        self.append_log("Command: " + " ".join(args))

        def worker() -> None:
            try:
                for line in stream_process(args):
                    self.worker_queue.put(("download-log", line))
                if selection.mode == DownloadMode.SUBTITLE and selection.subtitle_output == SubtitleOutput.TEXT:
                    target = finalize_plain_text_subtitle(selection)
                    self.worker_queue.put(("log", f"Saved plain text subtitle: {target}"))
                self.worker_queue.put(("done", "Download complete"))
            except Exception as exc:
                self.worker_queue.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def build_selection(self) -> DownloadSelection:
        mode = DownloadMode(self.mode.get())
        selected = self.tree.selection()
        if not selected:
            raise ValueError("Select one row first.")
        cookies = self.current_cookie_config()
        output = default_output_dir()
        if mode == DownloadMode.VIDEO:
            video = find_format(self.videos, selected[0])
            audio = None if video.has_audio else choose_matching_audio(video, self.audios)
            return DownloadSelection(
                mode=mode,
                url=self.video_info.webpage_url or self.url_var.get(),
                video_format=video,
                audio_format=audio,
                cookies=cookies,
                output_dir=output,
            )
        if mode == DownloadMode.AUDIO:
            audio = find_format(self.audios, selected[0])
            return DownloadSelection(
                mode=mode,
                url=self.video_info.webpage_url or self.url_var.get(),
                audio_format=audio,
                cookies=cookies,
                output_dir=output,
            )
        idx = int(selected[0])
        return DownloadSelection(
            mode=mode,
            url=self.video_info.webpage_url or self.url_var.get(),
            subtitle=self.subtitles[idx],
            subtitle_output=SubtitleOutput(self.subtitle_output.get()),
            video_id=self.video_info.video_id,
            cookies=cookies,
            output_dir=output,
        )

    def poll_worker_queue(self) -> None:
        try:
            while True:
                kind, payload = self.worker_queue.get_nowait()
                if kind == "metadata":
                    self.receive_metadata(payload)  # type: ignore[arg-type]
                elif kind in {"log", "download-log"}:
                    text = str(payload)
                    self.append_log(text)
                    if kind == "download-log":
                        self.progress_label.configure(text=progress_summary(text))
                elif kind == "error":
                    self.append_log(str(payload))
                    self.stop_busy("Error")
                    self.downloading = False
                    self.download_button.configure(state="normal")
                    self.load_button.configure(state="normal")
                    messagebox.showerror("TubePocket", str(payload))
                elif kind == "done":
                    self.append_log(str(payload))
                    self.progress_label.configure(text=str(payload))
                    self.stop_busy(str(payload))
                    self.downloading = False
                    self.download_button.configure(state="normal")
                    self.load_button.configure(state="normal")
        except queue.Empty:
            pass
        self.root.after(100, self.poll_worker_queue)

    def update_log_visibility(self) -> None:
        if self.log_visible.get():
            self.log_text.grid(row=5, column=0, sticky="nsew", pady=(8, 0))
            self.download_tab.rowconfigure(5, weight=0)
        else:
            self.log_text.grid_remove()

    def append_log(self, text: str) -> None:
        self.log_text.insert("end", text.rstrip() + "\n")
        self.log_text.see("end")

    def set_status(self, text: str) -> None:
        self.status_label.configure(text=text)

    def start_busy(self, text: str) -> None:
        self.set_status(text)
        self.busy_bar.grid()
        self.busy_bar.start(12)

    def stop_busy(self, text: str) -> None:
        self.busy_bar.stop()
        self.busy_bar.grid_remove()
        self.set_status(text)


def find_format(formats: list[MediaFormat], format_id: str) -> MediaFormat:
    for fmt in formats:
        if fmt.format_id == format_id:
            return fmt
    raise ValueError(f"Unknown format id: {format_id}")


def row_for_video(fmt: MediaFormat) -> list[str]:
    return [
        fmt.format_id,
        fmt.ext,
        fmt.resolution,
        "" if fmt.fps is None else f"{fmt.fps:g}",
        fmt.vcodec,
        fmt.acodec,
        "" if fmt.tbr is None else f"{fmt.tbr:g}",
        fmt.display_size,
        fmt.format_note or fmt.format,
    ]


def row_for_audio(fmt: MediaFormat) -> list[str]:
    return [
        fmt.format_id,
        fmt.ext,
        fmt.acodec,
        "" if fmt.abr is None else f"{fmt.abr:g}",
        "" if fmt.tbr is None else f"{fmt.tbr:g}",
        "" if fmt.asr is None else str(fmt.asr),
        fmt.display_size,
        fmt.format_note or fmt.format,
    ]


def progress_summary(line: str) -> str:
    match = re.search(r"\[download\]\s+(.+)", line)
    return match.group(1).strip() if match else line[:120]


def tool_status(name: str, required: bool) -> str:
    if tool_available(name):
        return "✅ Available"
    return "❌ Missing from PATH" if required else "⚠️ Missing from PATH"

def cookie_status_text(cookies) -> str:
    if cookies.mode == CookieMode.NONE:
        return "ℹ️ Not used"
    if cookies.mode == CookieMode.BROWSER:
        return f"ℹ️ Browser: {cookies.browser}"
    if cookies.mode == CookieMode.FILE:
        return "ℹ️ cookies.txt selected" if cookies.cookies_path else "ℹ️ cookies.txt mode"
    return "ℹ️ Unknown"
