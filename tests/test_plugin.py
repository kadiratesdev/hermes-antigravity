"""Tests for the Hermes Antigravity provider plugin."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def test_manifest_structure():
    """Verify plugin.yaml exists and adheres to the model-provider schema."""
    manifest_file = PLUGIN_ROOT / "plugin.yaml"
    assert manifest_file.is_file(), "plugin.yaml must exist"

    manifest = yaml.safe_load(manifest_file.read_text(encoding="utf-8"))
    assert manifest.get("name") == "antigravity-provider"
    assert manifest.get("kind") == "model-provider"
    assert manifest.get("version") == "1.0.0"
    assert "antigravity" in manifest.get("description", "").lower()


def test_plugin_guard_scan_clean():
    """Verify plugin static security scanner passes with zero critical/high findings."""
    from tools.plugin_guard import scan_plugin, should_allow_plugin_install

    res = scan_plugin(PLUGIN_ROOT)
    allowed, reason = should_allow_plugin_install(res)
    assert allowed is True, f"Scan blocked: {reason}"
    critical_or_high = [
        f for f in res.findings if f.severity in ("critical", "high")
    ]
    assert not critical_or_high, f"Unexpected high/critical findings: {critical_or_high}"


def test_provider_registration():
    """Verify Antigravity profile registration and aliases."""
    import sys

    # Ensure repo root is on sys.path
    if str(PLUGIN_ROOT) not in sys.path:
        sys.path.insert(0, str(PLUGIN_ROOT))

    import client
    from providers import _REGISTRY, _ALIASES, get_provider_profile
    import __init__ as plugin_mod

    profile = get_provider_profile("antigravity")
    assert profile is not None
    assert profile.name == "antigravity"
    assert "google-antigravity" in profile.aliases
    assert "cloudcode" in profile.aliases
    assert "ag" in profile.aliases
    assert profile.base_url == "https://daily-cloudcode-pa.sandbox.googleapis.com"
    assert profile.supports_vision is True


def test_client_enveloping_and_unwrapping():
    """Verify request enveloping and unwrapping match Antigravity's gateway protocol."""
    import sys

    if str(PLUGIN_ROOT) not in sys.path:
        sys.path.insert(0, str(PLUGIN_ROOT))

    from client import AntigravityClient

    # Test envelope
    req = {"contents": [{"parts": [{"text": "hello"}]}]}
    envelope = AntigravityClient._envelope("gemini-3-flash", req)
    assert envelope["model"] == "gemini-3-flash"
    assert envelope["request"] == req
    assert envelope["userAgent"] == "antigravity"
    assert "requestId" in envelope

    # Test unwrap
    wrapped = {"response": {"candidates": [{"content": {"parts": [{"text": "hi"}]}}]}}
    unwrapped = AntigravityClient._unwrap(wrapped)
    assert unwrapped == wrapped["response"]

    # Test unwrap passthrough
    raw = {"candidates": []}
    assert AntigravityClient._unwrap(raw) == raw


def test_request_sanitization():
    """Verify maxOutputTokens clamping and tool sanitization."""
    import sys

    if str(PLUGIN_ROOT) not in sys.path:
        sys.path.insert(0, str(PLUGIN_ROOT))

    from client import _sanitize_request

    # Test token clamping for claude
    req = {
        "generationConfig": {
            "maxOutputTokens": 100000,
        }
    }
    sanitized = _sanitize_request(req, model="claude-sonnet-4-5-20250929")
    assert sanitized["generationConfig"]["maxOutputTokens"] == 64000

    # Test token clamping for gemini
    req2 = {
        "generationConfig": {
            "maxOutputTokens": 128000,
        }
    }
    sanitized2 = _sanitize_request(req2, model="gemini-3.8-flash-tiered")
    assert sanitized2["generationConfig"]["maxOutputTokens"] == 65536


def test_auth_file_resolution(monkeypatch, tmp_path):
    """Verify get_auth_file respects HERMES_HOME."""
    import sys

    if str(PLUGIN_ROOT) not in sys.path:
        sys.path.insert(0, str(PLUGIN_ROOT))

    from client import get_auth_file

    custom_home = tmp_path / "custom_hermes"
    monkeypatch.setenv("HERMES_HOME", str(custom_home))
    assert get_auth_file() == custom_home / "auth" / "antigravity_oauth.json"

    monkeypatch.delenv("HERMES_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert get_auth_file() == tmp_path / ".hermes" / "auth" / "antigravity_oauth.json"
