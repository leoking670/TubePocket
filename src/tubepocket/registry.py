# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol


SCHEME = "tubepocket"
SCHEME_KEY = r"Software\Classes\tubepocket"
COMMAND_SUBKEY = r"Software\Classes\tubepocket\shell\open\command"


class RegistryState(str, Enum):
    UNREGISTERED = "unregistered"
    REGISTERED_CURRENT = "registered_current"
    REGISTERED_OTHER = "registered_other"


@dataclass(slots=True)
class ProtocolStatus:
    state: RegistryState
    command: str = ""
    target_path: str = ""
    target_exists: bool = False


class RegistryBackend(Protocol):
    def get_value(self, key: str, name: str = "") -> str | None: ...

    def set_value(self, key: str, name: str, value: str) -> None: ...

    def delete_tree(self, key: str) -> None: ...


class WinregBackend:
    def __init__(self) -> None:
        import winreg

        self.winreg = winreg

    def get_value(self, key: str, name: str = "") -> str | None:
        try:
            with self.winreg.OpenKey(self.winreg.HKEY_CURRENT_USER, key) as handle:
                value, _ = self.winreg.QueryValueEx(handle, name)
                return str(value)
        except FileNotFoundError:
            return None
        except OSError:
            return None

    def set_value(self, key: str, name: str, value: str) -> None:
        with self.winreg.CreateKeyEx(self.winreg.HKEY_CURRENT_USER, key, 0, self.winreg.KEY_SET_VALUE) as handle:
            self.winreg.SetValueEx(handle, name, 0, self.winreg.REG_SZ, value)

    def delete_tree(self, key: str) -> None:
        self._delete_tree(key)

    def _delete_tree(self, key: str) -> None:
        try:
            with self.winreg.OpenKey(
                self.winreg.HKEY_CURRENT_USER,
                key,
                0,
                self.winreg.KEY_READ | self.winreg.KEY_WRITE,
            ) as handle:
                while True:
                    try:
                        child = self.winreg.EnumKey(handle, 0)
                    except OSError:
                        break
                    self._delete_tree(key + "\\" + child)
        except FileNotFoundError:
            return
        try:
            self.winreg.DeleteKey(self.winreg.HKEY_CURRENT_USER, key)
        except FileNotFoundError:
            return


def is_packaged() -> bool:
    return bool(getattr(sys, "frozen", False))


def current_executable() -> Path:
    return Path(sys.executable).resolve()


def build_open_command(exe_path: Path | str) -> str:
    return f'"{Path(exe_path)}" "%1"'


def parse_command_target(command: str) -> str:
    command = command.strip()
    if not command:
        return ""
    if command.startswith('"'):
        match = re.match(r'^"([^"]+)"', command)
        return match.group(1) if match else ""
    return command.split(maxsplit=1)[0]


class ProtocolRegistry:
    def __init__(self, backend: RegistryBackend | None = None) -> None:
        self.backend = backend or WinregBackend()

    def status(self, current_exe: Path | str) -> ProtocolStatus:
        command = self.backend.get_value(COMMAND_SUBKEY, "") or ""
        if not command:
            return ProtocolStatus(RegistryState.UNREGISTERED)
        target = parse_command_target(command)
        current = str(Path(current_exe).resolve()).casefold()
        resolved_target = str(Path(target).resolve()).casefold() if target else ""
        exists = bool(target and Path(target).exists())
        state = RegistryState.REGISTERED_CURRENT if resolved_target == current else RegistryState.REGISTERED_OTHER
        return ProtocolStatus(state=state, command=command, target_path=target, target_exists=exists)

    def register(self, exe_path: Path | str) -> None:
        command = build_open_command(exe_path)
        self.backend.set_value(SCHEME_KEY, "", "URL:TubePocket Protocol")
        self.backend.set_value(SCHEME_KEY, "URL Protocol", "")
        self.backend.set_value(COMMAND_SUBKEY, "", command)

    def unregister(self) -> None:
        self.backend.delete_tree(SCHEME_KEY)

