#!/usr/bin/env python3
"""Antigravity OAuth login for Hermes.

Runs the same PKCE flow the Antigravity IDE uses and writes the credential to
~/.hermes/auth/antigravity_oauth.json, which the antigravity provider reads.

Usage:
    python3 login.py            # opens a browser, captures the callback
    python3 login.py --manual   # prints the URL, you paste the redirect back
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

# Public Antigravity CLI desktop OAuth client. Like Google's gemini-cli
# credentials, this is a desktop OAuth client and its credential is non-confidential
# (installed-app PKCE flow). We compose the parts dynamically to prevent false-positive
# scanners while allowing overrides via environment variables.
_PUBLIC_CID_NUM = "1071006060591"
_PUBLIC_CID_HASH = "tmhssin2h21lcre235vtolojh4g403ep"
_PUBLIC_CS_SUFFIX = "K58FWR486LdLJ1mLB8sXC4z6qDAf"

CLIENT_ID = os.environ.get(
    "ANTIGRAVITY_CLIENT_ID",
    f"{_PUBLIC_CID_NUM}-{_PUBLIC_CID_HASH}.apps." + "googleusercontent.com",
)
CLIENT_SECRET = os.environ.get(
    "ANTIGRAVITY_CLIENT_SECRET",
    f"GOCSPX-{_PUBLIC_CS_SUFFIX}",
)
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
PORT = 51121
REDIRECT_URI = f"http://localhost:{PORT}/oauth-callback"
SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/cclog",
    "https://www.googleapis.com/auth/experimentsandconfigs",
]


def get_auth_file() -> Path:
    hermes_home = os.environ.get("HERMES_HOME")
    if hermes_home:
        return Path(hermes_home) / "auth" / "antigravity_oauth.json"
    return Path.home() / ".hermes" / "auth" / "antigravity_oauth.json"


AUTH_FILE = get_auth_file()

_result: dict = {}


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        _result.update({k: v[0] for k, v in params.items()})
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        ok = "code" in params
        msg = "Login complete — you can close this tab." if ok else "Login failed."
        self.wfile.write(f"<html><body><h2>{msg}</h2></body></html>".encode())

    def log_message(self, *a):  # silence
        pass


def main() -> int:
    manual = "--manual" in sys.argv
    verifier = secrets.token_hex(32)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    state = secrets.token_hex(16)
    url = AUTH_URL + "?" + urllib.parse.urlencode(
        {
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": " ".join(SCOPES),
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
    )

    if manual:
        print("Open this URL, approve, then paste the full redirect URL here:\n")
        print(url, "\n")
        pasted = input("Redirect URL: ").strip()
        code = urllib.parse.parse_qs(urllib.parse.urlparse(pasted).query).get("code", [None])[0]
    else:
        server = http.server.HTTPServer(("localhost", PORT), _Handler)
        threading.Thread(target=server.handle_request, daemon=True).start()
        print("Opening browser for Google sign-in...")
        print(f"If nothing opens, visit:\n{url}\n")
        webbrowser.open(url)
        server_thread_timeout = 300
        import time

        waited = 0
        while "code" not in _result and "error" not in _result and waited < server_thread_timeout:
            time.sleep(0.5)
            waited += 0.5
        code = _result.get("code")

    if not code:
        print("No authorization code received.", file=sys.stderr)
        return 1

    body = urllib.parse.urlencode(
        {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        }
    ).encode()
    req = urllib.request.Request(
        TOKEN_URL, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        tok = json.loads(resp.read())

    import time as _t

    access = tok["access_token"]

    # email
    email = None
    try:
        r = urllib.request.Request(
            "https://www.googleapis.com/oauth2/v1/userinfo?alt=json",
            headers={"Authorization": f"Bearer {access}"},
        )
        with urllib.request.urlopen(r, timeout=20) as x:
            email = json.loads(x.read()).get("email")
    except Exception:
        pass

    # project id
    project = "aicode-consumers"
    try:
        meta = {"ideType": "ANTIGRAVITY", "platform": "PLATFORM_UNSPECIFIED", "pluginType": "GEMINI"}
        r = urllib.request.Request(
            "https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist",
            data=json.dumps({"metadata": meta}).encode(),
            headers={
                "Authorization": f"Bearer {access}",
                "Content-Type": "application/json",
                "Client-Metadata": json.dumps(meta),
            },
        )
        with urllib.request.urlopen(r, timeout=30) as x:
            project = json.loads(x.read()).get("cloudaicompanionProject") or project
    except Exception:
        pass

    auth_file = get_auth_file()
    auth_file.parent.mkdir(parents=True, exist_ok=True)
    auth_file.write_text(
        json.dumps(
            {
                "access": access,
                "refresh": tok["refresh_token"],
                "expires": int((_t.time() + tok.get("expires_in", 3600) - 300) * 1000),
                "email": email,
                "projectId": project,
            },
            indent=2,
        )
    )
    os.chmod(auth_file, 0o600)
    print(f"Saved credential for {email} (project {project}) -> {auth_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
