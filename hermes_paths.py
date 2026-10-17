"""Platform-aware Hermes home / auth path helpers.

Mirrors Hermes core (`hermes_constants.get_hermes_home`): on native Windows the
default home is ``%LOCALAPPDATA%\\hermes``, not ``~/.hermes``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def get_hermes_home() -> Path:
    """Return the active Hermes home (HERMES_HOME or platform default)."""
    hermes_home = os.environ.get("HERMES_HOME", "").strip()
    if hermes_home:
        return Path(hermes_home)
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
        base = Path(local_appdata) if local_appdata else Path.home() / "AppData" / "Local"
        return base / "hermes"
    return Path.home() / ".hermes"


def get_auth_file() -> Path:
    """Path to the Antigravity OAuth credential JSON."""
    return get_hermes_home() / "auth" / "antigravity_oauth.json"
