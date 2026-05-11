# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Callable

from tubepocket.url_scheme import LaunchUrl, UrlError, normalize_youtube_url


HOST = "127.0.0.1"
PORT = 45973
MAX_MESSAGE_BYTES = 8192


class SchemeIpcServer:
    def __init__(self, on_open: Callable[[LaunchUrl], None], host: str = HOST, port: int = PORT) -> None:
        self.on_open = on_open
        self.host = host
        self.port = port
        self._socket: socket.socket | None = None
        self._stopped = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.host, self.port))
        listener.listen()
        listener.settimeout(0.2)
        self.port = listener.getsockname()[1]
        self._socket = listener
        self._thread = threading.Thread(target=self._serve, name="TubePocketSchemeIpc", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stopped.set()
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def _serve(self) -> None:
        while not self._stopped.is_set():
            try:
                assert self._socket is not None
                conn, _addr = self._socket.accept()
            except (TimeoutError, socket.timeout):
                continue
            except OSError:
                break
            with conn:
                self._handle(conn)

    def _handle(self, conn: socket.socket) -> None:
        conn.settimeout(1.0)
        try:
            data = _read_line(conn)
            launch = _decode_open_message(data)
        except (OSError, UrlError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
            conn.sendall(b"error\n")
            return
        self.on_open(launch)
        conn.sendall(b"ok\n")


def send_open_to_existing_instance(launch: LaunchUrl, host: str = HOST, port: int = PORT, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout) as conn:
            conn.settimeout(timeout)
            conn.sendall(_encode_open_message(launch))
            return _read_line(conn) == b"ok"
    except OSError:
        return False


def _encode_open_message(launch: LaunchUrl) -> bytes:
    payload = {"app": "tubepocket", "action": "open", "url": launch.canonical_url}
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")


def _decode_open_message(data: bytes) -> LaunchUrl:
    payload = json.loads(data.decode("utf-8"))
    if payload.get("app") != "tubepocket" or payload.get("action") != "open":
        raise ValueError("Unexpected IPC message")
    return normalize_youtube_url(str(payload.get("url", "")))


def _read_line(conn: socket.socket) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while size < MAX_MESSAGE_BYTES:
        chunk = conn.recv(1)
        if not chunk:
            break
        if chunk == b"\n":
            break
        chunks.append(chunk)
        size += len(chunk)
    return b"".join(chunks)
