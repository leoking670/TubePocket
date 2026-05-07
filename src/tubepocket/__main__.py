# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import sys

from tubepocket.app import run_app


def main() -> None:
    run_app(sys.argv[1:])


if __name__ == "__main__":
    main()

