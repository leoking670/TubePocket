# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from pathlib import Path

from tubepocket.registry import COMMAND_SUBKEY, SCHEME_KEY, ProtocolRegistry, RegistryState, build_open_command, parse_command_target


class FakeRegistry:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_value(self, key: str, name: str = "") -> str | None:
        return self.values.get((key, name))

    def set_value(self, key: str, name: str, value: str) -> None:
        self.values[(key, name)] = value

    def delete_tree(self, key: str) -> None:
        for item in list(self.values):
            if item[0] == key or item[0].startswith(key + "\\"):
                del self.values[item]


def test_build_and_parse_command_with_spaces() -> None:
    command = build_open_command(Path("C:/Program Files/TubePocket/TubePocket.exe"))

    assert command == '"C:\\Program Files\\TubePocket\\TubePocket.exe" "%1"'
    assert parse_command_target(command) == "C:\\Program Files\\TubePocket\\TubePocket.exe"


def test_status_unregistered() -> None:
    registry = ProtocolRegistry(FakeRegistry())

    status = registry.status(Path("C:/Apps/TubePocket.exe"))

    assert status.state == RegistryState.UNREGISTERED


def test_register_and_status_current(tmp_path: Path) -> None:
    exe = tmp_path / "TubePocket.exe"
    exe.write_text("", encoding="utf-8")
    fake = FakeRegistry()
    registry = ProtocolRegistry(fake)

    registry.register(exe)
    status = registry.status(exe)

    assert fake.values[(SCHEME_KEY, "")] == "URL:TubePocket Protocol"
    assert fake.values[(SCHEME_KEY, "URL Protocol")] == ""
    assert fake.values[(COMMAND_SUBKEY, "")] == build_open_command(exe)
    assert status.state == RegistryState.REGISTERED_CURRENT
    assert status.target_exists is True


def test_status_other_missing_path(tmp_path: Path) -> None:
    fake = FakeRegistry()
    fake.set_value(COMMAND_SUBKEY, "", build_open_command(tmp_path / "Old.exe"))
    registry = ProtocolRegistry(fake)

    status = registry.status(tmp_path / "TubePocket.exe")

    assert status.state == RegistryState.REGISTERED_OTHER
    assert status.target_exists is False


def test_unregister_is_idempotent(tmp_path: Path) -> None:
    fake = FakeRegistry()
    registry = ProtocolRegistry(fake)
    exe = tmp_path / "TubePocket.exe"

    registry.register(exe)
    registry.unregister()
    registry.unregister()

    assert registry.status(exe).state == RegistryState.UNREGISTERED

