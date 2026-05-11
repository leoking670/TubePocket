# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import socket
import threading

from tubepocket.scheme_ipc import HOST, SchemeIpcServer, send_open_to_existing_instance
from tubepocket.url_scheme import normalize_youtube_url


def test_sends_launch_url_to_existing_scheme_instance() -> None:
    received = []
    event = threading.Event()

    def on_open(launch) -> None:
        received.append(launch)
        event.set()

    server = SchemeIpcServer(on_open, port=0)
    server.start()
    try:
        launch = normalize_youtube_url("https://www.youtube.com/watch?v=abc123&list=ignored")

        assert send_open_to_existing_instance(launch, port=server.port)
        assert event.wait(1.0)
        assert received[0].canonical_url == "https://www.youtube.com/watch?v=abc123"
    finally:
        server.close()


def test_send_returns_false_when_no_scheme_instance_is_available() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        port = sock.getsockname()[1]

    launch = normalize_youtube_url("https://www.youtube.com/watch?v=abc123")

    assert not send_open_to_existing_instance(launch, port=port, timeout=0.05)
